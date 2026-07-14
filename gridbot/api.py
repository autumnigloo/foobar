"""Thin client for the competition REST API.

The exact API spec is not known yet, so every endpoint below is a best
guess kept behind one small method each. When the real spec arrives,
only this file (paths, payload shapes, response parsing) should need to
change — the world model and strategies depend only on the typed methods
and the domain objects in `models.py`.

Known constraints the client must respect:
- We only see colors of squares adjacent to our own squares; the server
  presumably enforces this, so `get_visible_squares` returns just that.
- Flags positions can be requested explicitly.
- Rockets can be fired at coordinates.
"""

import logging

import requests

from .config import Config
from .models import Flag, GridInfo, Ownership, Point, Square

log = logging.getLogger(__name__)


class ApiError(Exception):
    pass


class GameClient:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        if config.api_token:
            self.session.headers["Authorization"] = f"Bearer {config.api_token}"

    # ------------------------------------------------------------------ #
    # low-level helpers
    # ------------------------------------------------------------------ #
    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            resp = self.session.request(
                method, url, timeout=self.config.request_timeout, **kwargs
            )
        except requests.RequestException as exc:
            raise ApiError(f"{method} {path} failed: {exc}") from exc
        if resp.status_code >= 400:
            raise ApiError(f"{method} {path} -> {resp.status_code}: {resp.text[:300]}")
        if not resp.content:
            return {}
        return resp.json()

    def _get(self, path: str, **params) -> dict:
        return self._request("GET", path, params=params or None)

    def _post(self, path: str, payload: dict) -> dict:
        return self._request("POST", path, json=payload)

    # ------------------------------------------------------------------ #
    # endpoints (paths/shapes are placeholders — update to the real spec)
    # ------------------------------------------------------------------ #
    def get_me(self) -> dict:
        """Our player info: color, score, remaining resources, etc."""
        return self._get("/me")  # TODO: real endpoint

    def get_grid_info(self) -> GridInfo:
        """Current grid bounds; the grid grows when it hits 70% full."""
        data = self._get("/grid")  # TODO: real endpoint
        return GridInfo(
            min_x=data.get("min_x", 0),
            min_y=data.get("min_y", 0),
            max_x=data.get("max_x", 0),
            max_y=data.get("max_y", 0),
        )

    def get_visible_squares(self, our_color: str) -> list[Square]:
        """Squares whose color we are allowed to see (around our squares)."""
        data = self._get("/squares/visible")  # TODO: real endpoint
        squares = []
        for item in data.get("squares", []):
            color = item.get("color")
            if color is None:
                ownership = Ownership.EMPTY
            elif color == our_color:
                ownership = Ownership.OURS
            else:
                ownership = Ownership.ENEMY
            squares.append(
                Square(pos=Point(item["x"], item["y"]), color=color, ownership=ownership)
            )
        return squares

    def place_square(self, pos: Point) -> bool:
        """Place one of our squares. Returns True on success."""
        try:
            self._post("/squares", {"x": pos.x, "y": pos.y})  # TODO: real endpoint
            return True
        except ApiError as exc:
            # Occupied cells / rate limits are expected in normal play;
            # log and let the strategy pick a different move next tick.
            log.info("place_square(%s, %s) rejected: %s", pos.x, pos.y, exc)
            return False

    def get_flags(self) -> list[Flag]:
        data = self._get("/flags")  # TODO: real endpoint
        return [
            Flag(pos=Point(item["x"], item["y"]), owner_color=item.get("owner"))
            for item in data.get("flags", [])
        ]

    def fire_rocket(self, target: Point) -> bool:
        try:
            self._post("/rockets", {"x": target.x, "y": target.y})  # TODO: real endpoint
            return True
        except ApiError as exc:
            log.info("fire_rocket(%s, %s) rejected: %s", target.x, target.y, exc)
            return False
