"""Main loop: observe -> decide -> act, once per tick.

Startup:
1. Poll the leaderboard until our row (`is_self: true`) appears, which
   tells us our display name and color (the API never exposes ids).
2. Sync nuke/scan cooldowns and the scan size cap from GET /method-limits.

Per tick:
1. Refresh the visible map (and flags / leaderboard on their intervals).
2. Fire cooldown-gated actions that are ready: nuke an enemy flag,
   scan the richest hidden flag.
3. Pick one tile placement among the strategies' proposals by weighted
   lottery and place it.
"""

import logging
import random
import time

from .api import ActionResult, ApiError, GameClient
from .config import Config
from .strategies import (
    Action,
    ActionKind,
    ExpandOutside,
    ExpandToFlag,
    NukeEnemyFlag,
    RandomPlace,
    ScanHiddenFlag,
    Strategy,
)
from .world import World

log = logging.getLogger(__name__)

_REJECTION_FALLBACK_SNOOZE = 5.0


class Bot:
    def __init__(self, config: Config, client: GameClient | None = None):
        self.config = config
        self.client = client or GameClient(config)
        self.world = World()
        self.nuke = NukeEnemyFlag(config)
        self.scan = ScanHiddenFlag(config)
        self.placement_strategies: list[Strategy] = [
            ExpandOutside(config),
            ExpandToFlag(config),
            RandomPlace(config),
        ]
        self.leaderboard_fetched_at = 0.0
        self.current_emotion: str | None = None

    # ------------------------------------------------------------------ #
    def run_forever(self) -> None:
        while self.world.our_name is None:
            try:
                self._refresh_leaderboard()
            except ApiError as exc:
                log.warning("leaderboard fetch failed: %s", exc)
            if self.world.our_name is None:
                log.warning(
                    "no is_self row on the leaderboard yet — is GRIDBOT_PLAYER_ID "
                    "set to the id the operator gave you?"
                )
                time.sleep(self.config.tick_seconds)
        log.info("playing as %r (color %s)", self.world.our_name, self.world.our_color)
        self._sync_method_limits()
        while True:
            started = time.monotonic()
            try:
                self.tick()
            except ApiError as exc:
                log.warning("tick failed, retrying next tick: %s", exc)
            elapsed = time.monotonic() - started
            time.sleep(max(0.0, self.config.tick_seconds - elapsed))

    # ------------------------------------------------------------------ #
    def tick(self) -> None:
        self._observe()
        for gated in (self.nuke, self.scan):
            action = gated.propose(self.world)
            if action is not None:
                self._execute(action)
        placement = self._choose_placement()
        if placement is not None:
            self._execute(placement)
        else:
            log.debug("no placement proposed this tick")

    # ------------------------------------------------------------------ #
    # observation
    # ------------------------------------------------------------------ #
    def _observe(self) -> None:
        self.world.update_map(self.client.get_map())
        now = time.monotonic()
        if not self.world.flags or now - self.world.flags_fetched_at > self.config.flag_refresh_seconds:
            self.world.update_flags(self.client.get_flags())
        if now - self.leaderboard_fetched_at > self.config.leaderboard_refresh_seconds:
            try:
                self._refresh_leaderboard()
            except ApiError as exc:
                log.debug("leaderboard refresh failed: %s", exc)

    def _refresh_leaderboard(self) -> None:
        entries = self.client.get_leaderboard()
        self.leaderboard_fetched_at = time.monotonic()
        for rank, entry in enumerate(entries, start=1):
            if entry.is_self:
                self.world.our_name = entry.display_name
                self.world.our_color = entry.color
                self._report_emotion(rank, len(entries))
                return

    def _report_emotion(self, rank: int, total: int) -> None:
        """Cosmetic spectator-HUD flair; failures are irrelevant."""
        if rank == 1:
            emotion = "confident"
        elif total > 2 and rank == total:
            emotion = "desperate"
        elif rank <= total / 2:
            emotion = "focused"
        else:
            emotion = "neutral"
        if emotion == self.current_emotion:
            return
        try:
            if self.client.set_emotion(emotion).ok:
                self.current_emotion = emotion
        except ApiError:
            pass

    def _sync_method_limits(self) -> None:
        """Adopt server cooldowns/caps so we never burn actions on
        predictable rejections. Best-effort: config values remain the
        fallback if the endpoint is missing or partial."""
        try:
            limits = self.client.get_method_limits()
        except ApiError as exc:
            log.warning("method-limits unavailable, using config defaults: %s", exc)
            return
        nuke = limits.get("launch_nuke") or {}
        if nuke.get("cooldown"):
            self.nuke.cooldown_seconds = max(self.nuke.cooldown_seconds, nuke["cooldown"])
        scan = limits.get("request_scan") or {}
        if scan.get("cooldown"):
            self.scan.cooldown_seconds = max(self.scan.cooldown_seconds, scan["cooldown"])
        if scan.get("max_side_length"):
            self.scan.size = min(self.scan.size, scan["max_side_length"])
        log.info(
            "limits synced: nuke cooldown %ss, scan cooldown %ss, scan size %s",
            self.nuke.cooldown_seconds, self.scan.cooldown_seconds, self.scan.size,
        )

    # ------------------------------------------------------------------ #
    # actions
    # ------------------------------------------------------------------ #
    def _choose_placement(self) -> Action | None:
        proposals: list[tuple[float, Action]] = []
        for strategy in self.placement_strategies:
            action = strategy.propose(self.world)
            if action is not None:
                proposals.append((strategy.weight, action))
        if not proposals:
            return None
        weights = [w for w, _ in proposals]
        return random.choices([a for _, a in proposals], weights=weights, k=1)[0]

    def _execute(self, action: Action) -> None:
        log.info("%s at (%s, %s): %s", action.kind.value, action.target.x, action.target.y, action.reason)
        if action.kind is ActionKind.PLACE:
            result = self.client.place_tile(action.target)
            if result.ok:
                self.world.record_own_placement(action.target)
        elif action.kind is ActionKind.NUKE:
            self._handle_gated_result(self.nuke, self.client.launch_nuke(action.target))
        elif action.kind is ActionKind.SCAN:
            self._handle_gated_result(
                self.scan, self.client.request_scan(action.target, action.size or self.scan.size)
            )

    @staticmethod
    def _handle_gated_result(strategy, result: ActionResult) -> None:
        if result.ok:
            strategy.mark_fired()
        else:
            strategy.snooze(result.retry_after or _REJECTION_FALLBACK_SNOOZE)
