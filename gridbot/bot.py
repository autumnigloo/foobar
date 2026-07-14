"""Main loop: observe -> decide -> act, once per tick.

Per tick:
1. Refresh grid bounds and visible squares (and flags, on an interval —
   flag positions are a separate, presumably rate-limited request).
2. Fire a rocket at an enemy flag if the cooldown allows.
3. Pick one placement among the strategies' proposals by weighted lottery
   and place a square.
"""

import logging
import random
import time

from .api import ApiError, GameClient
from .config import Config
from .strategies import ExpandOutside, ExpandToFlag, RandomPlace, RocketEnemyFlag
from .strategies.base import Action, ActionKind, Strategy
from .world import World

log = logging.getLogger(__name__)


class Bot:
    def __init__(self, config: Config, client: GameClient | None = None):
        self.config = config
        self.client = client or GameClient(config)
        self.world = World()
        self.rocket = RocketEnemyFlag(config)
        self.placement_strategies: list[Strategy] = [
            ExpandOutside(config),
            ExpandToFlag(config),
            RandomPlace(config),
        ]

    # ------------------------------------------------------------------ #
    def run_forever(self) -> None:
        me = self.client.get_me()
        self.world.our_color = me.get("color")  # TODO: adjust to real payload
        log.info("playing as color %s", self.world.our_color)
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
        rocket_action = self.rocket.propose(self.world)
        if rocket_action is not None:
            self._execute(rocket_action)
        placement = self._choose_placement()
        if placement is not None:
            self._execute(placement)
        else:
            log.debug("no placement proposed this tick")

    def _observe(self) -> None:
        self.world.update_grid(self.client.get_grid_info())
        if self.world.our_color:
            self.world.update_squares(
                self.client.get_visible_squares(self.world.our_color)
            )
        stale = time.monotonic() - self.world.flags_fetched_at
        if not self.world.flags or stale > self.config.flag_refresh_seconds:
            self.world.update_flags(self.client.get_flags())

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
            if self.client.place_square(action.target):
                self.world.record_own_placement(action.target)
        elif action.kind is ActionKind.ROCKET:
            if self.client.fire_rocket(action.target):
                self.rocket.mark_fired()
