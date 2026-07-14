"""Core domain objects shared by the API client, world model and strategies."""

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class Point:
    x: int
    y: int

    def neighbors(self) -> tuple["Point", ...]:
        return (
            Point(self.x + 1, self.y),
            Point(self.x - 1, self.y),
            Point(self.x, self.y + 1),
            Point(self.x, self.y - 1),
        )

    def manhattan(self, other: "Point") -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)

    def chebyshev(self, other: "Point") -> int:
        return max(abs(self.x - other.x), abs(self.y - other.y))


class Ownership(Enum):
    OURS = "ours"
    ENEMY = "enemy"
    EMPTY = "empty"
    UNKNOWN = "unknown"  # outside our fog-of-war view


@dataclass(frozen=True)
class Tile:
    """One visible map cell. `owner` is a display name (the API never
    exposes player ids — see spec "Player identity in responses")."""

    pos: Point
    owner: str | None  # None = unowned
    has_flag: bool = False


@dataclass(frozen=True)
class Flag:
    flag_id: str
    pos: Point
    pot: int  # points awarded to the holder
    nuked: bool


@dataclass(frozen=True)
class LeaderboardEntry:
    display_name: str
    is_self: bool
    color: str
    tile_count: int
    flags_held: int | None
    score: int | None


@dataclass(frozen=True)
class GridInfo:
    """Current map bounds. The map expands over time (~every 10 min,
    triggered when it is 70% full), so these are refreshed each tick."""

    min_x: int
    min_y: int
    max_x: int
    max_y: int

    @property
    def width(self) -> int:
        return self.max_x - self.min_x + 1

    @property
    def height(self) -> int:
        return self.max_y - self.min_y + 1

    @property
    def center(self) -> Point:
        return Point((self.min_x + self.max_x) // 2, (self.min_y + self.max_y) // 2)

    def contains(self, p: Point) -> bool:
        return self.min_x <= p.x <= self.max_x and self.min_y <= p.y <= self.max_y

    def edge_distance(self, p: Point) -> int:
        """Distance to the nearest map edge. 0 means on the border.
        Small values = "outside", which is where we want to expand."""
        return min(
            p.x - self.min_x,
            self.max_x - p.x,
            p.y - self.min_y,
            self.max_y - p.y,
        )


@dataclass(frozen=True)
class MapView:
    bounds: GridInfo
    tiles: list[Tile]
    fog_padding_tiles: int
