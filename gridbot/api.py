"""Client for the AgentWars Gateway API (OpenAPI 0.1.0).

Identity (event mode, the competition default): every request carries the
`X-Player-Id` header with the player_id the operator handed out. Responses
never contain player ids — only display names — so we learn our own name
from the leaderboard row with `is_self: true`. In token mode
(AGW_AUTH_ENABLED=true) a Bearer token is sent instead.

Action endpoints return an ActionResponse with exactly one of
`accepted` / `rejected`; rejections (cooldown, insufficient points,
rate limit) also arrive as 4xx bodies of the same shape. Both are
normalized into `ActionResult` so callers never have to parse HTTP.
"""

import logging
from dataclasses import dataclass, field

import requests

from .config import Config
from .models import Flag, GridInfo, LeaderboardEntry, MapView, Point, Tile

log = logging.getLogger(__name__)


class ApiError(Exception):
    """Transport-level or unexpected failure (not a game-rule rejection)."""


@dataclass
class ActionResult:
    ok: bool
    reason: str | None = None
    retry_after: float | None = None
    effect: dict = field(default_factory=dict)


def _parse_owner(ownership) -> str | None:
    """Tile.ownership is `string | object` in the spec. The string form is
    the owner's display name ("" = unowned). The object form's exact shape
    is undocumented — TODO: verify against the live server; for now pull
    any plausible name field out of it."""
    if isinstance(ownership, str):
        return ownership or None
    if isinstance(ownership, dict):
        for key in ("display_name", "player", "owner", "name"):
            value = ownership.get(key)
            if isinstance(value, str) and value:
                return value
    return None


class GameClient:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        if config.player_id:
            self.session.headers["X-Player-Id"] = config.player_id
        else:
            # Without the header the gateway silently acts as 'dev-player',
            # which is not in any real game — actions then all fail.
            log.warning("GRIDBOT_PLAYER_ID is not set; requests will act as 'dev-player'")
        if config.api_token:  # token mode only; ignored in event mode
            self.session.headers["Authorization"] = f"Bearer {config.api_token}"

    # ------------------------------------------------------------------ #
    # low-level helpers
    # ------------------------------------------------------------------ #
    def _url(self, path: str) -> str:
        return f"{self.config.base_url.rstrip('/')}/api/v1/{path.lstrip('/')}"

    def _get_json(self, path: str, **params) -> dict:
        params.setdefault("game_id", self.config.game_id)
        try:
            resp = self.session.get(
                self._url(path), params=params, timeout=self.config.request_timeout
            )
        except requests.RequestException as exc:
            raise ApiError(f"GET {path} failed: {exc}") from exc
        if resp.status_code >= 400:
            raise ApiError(f"GET {path} -> {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def _action(self, path: str, payload: dict) -> ActionResult:
        payload.setdefault("game_id", self.config.game_id)
        try:
            resp = self.session.post(
                self._url(path), json=payload, timeout=self.config.request_timeout
            )
        except requests.RequestException as exc:
            raise ApiError(f"POST {path} failed: {exc}") from exc

        try:
            body = resp.json() if resp.content else {}
        except ValueError:
            body = {}

        rejected = body.get("rejected")
        if rejected:
            result = ActionResult(
                ok=False,
                reason=rejected.get("reason"),
                retry_after=rejected.get("retry_after"),
            )
            log.info("POST %s rejected: %s (retry_after=%s)", path, result.reason, result.retry_after)
            return result
        if resp.status_code >= 400:
            raise ApiError(f"POST {path} -> {resp.status_code}: {resp.text[:300]}")
        accepted = body.get("accepted") or {}
        return ActionResult(ok=True, effect=accepted.get("effect", {}))

    # ------------------------------------------------------------------ #
    # reads
    # ------------------------------------------------------------------ #
    def get_map(self) -> MapView:
        """Visible portion of the map: our tiles plus `fog_padding_tiles`
        around them (and anything revealed by an active scan)."""
        data = self._get_json("map")
        b = data["bounds"]
        tiles = [
            Tile(
                pos=Point(t["x"], t["y"]),
                owner=_parse_owner(t.get("ownership")),
                has_flag=t.get("has_flag", False),
            )
            for t in data.get("tiles", [])
        ]
        return MapView(
            bounds=GridInfo(b["min_x"], b["min_y"], b["max_x"], b["max_y"]),
            tiles=tiles,
            fog_padding_tiles=data.get("fog_padding_tiles", 0),
        )

    def get_flags(self) -> list[Flag]:
        data = self._get_json("flags")
        return [
            Flag(
                flag_id=f["flag_id"],
                pos=Point(f["x"], f["y"]),
                pot=f.get("pot", 0),
                nuked=f.get("nuked", False),
            )
            for f in data.get("flags", [])
        ]

    def get_leaderboard(self) -> list[LeaderboardEntry]:
        data = self._get_json("leaderboard")
        return [
            LeaderboardEntry(
                display_name=e["display_name"],
                is_self=e.get("is_self", False),
                color=e.get("color", ""),
                tile_count=e.get("tile_count", 0),
                flags_held=e.get("flags_held"),
                score=e.get("score"),
            )
            for e in data.get("entries", [])
        ]

    def get_method_limits(self) -> dict:
        """Server-side cooldowns/costs/scan caps; shape per MethodLimitsResponse."""
        return self._get_json("method-limits")

    # ------------------------------------------------------------------ #
    # actions
    # ------------------------------------------------------------------ #
    def place_tile(self, pos: Point) -> ActionResult:
        return self._action("place-tile", {"x": pos.x, "y": pos.y})

    def launch_nuke(self, target: Point) -> ActionResult:
        return self._action("launch-nuke", {"target_x": target.x, "target_y": target.y})

    def request_scan(self, center: Point, size: int) -> ActionResult:
        return self._action("request-scan", {"x": center.x, "y": center.y, "size": size})

    def set_emotion(self, emotion: str) -> ActionResult:
        """Cosmetic spectator-HUD state; no gameplay effect."""
        return self._action("emotion", {"emotion": emotion})
