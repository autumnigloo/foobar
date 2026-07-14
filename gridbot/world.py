"""In-memory model of everything we know about the board.

Visibility is fog-of-war: `GET /map` returns our tiles plus a padding
ring around them (plus scanned areas), so the world model accumulates
observations over time and exposes the derived views the strategies
need: our tiles, the frontier (our tiles with free neighbors), and
flags with inferred ownership.

Identity is name-based: the API only ever shows display names, so
`our_name` (learned from the leaderboard's `is_self` row) is what tile
owners are compared against.
"""

import time

from .models import Flag, GridInfo, MapView, Ownership, Point, Tile


class World:
    def __init__(self):
        self.grid = GridInfo(0, 0, 0, 0)
        self.our_name: str | None = None
        self.our_color: str | None = None
        # Latest known state per cell. Cells never observed are absent
        # (treat as UNKNOWN); observations can go stale once a cell falls
        # back into fog, which is fine for heuristic play.
        self.cells: dict[Point, Tile] = {}
        self.flags: list[Flag] = []
        self.flags_fetched_at: float = 0.0

    # ------------------------------------------------------------------ #
    # updates
    # ------------------------------------------------------------------ #
    def update_map(self, view: MapView) -> None:
        self.grid = view.bounds
        for tile in view.tiles:
            self.cells[tile.pos] = tile

    def update_flags(self, flags: list[Flag]) -> None:
        self.flags = flags
        self.flags_fetched_at = time.monotonic()

    def record_own_placement(self, pos: Point) -> None:
        """Optimistically mark a successful placement as ours so the next
        tick's frontier includes it even before the server confirms."""
        self.cells[pos] = Tile(pos=pos, owner=self.our_name)

    # ------------------------------------------------------------------ #
    # derived views
    # ------------------------------------------------------------------ #
    def ownership_at(self, pos: Point) -> Ownership:
        tile = self.cells.get(pos)
        if tile is None:
            return Ownership.UNKNOWN
        if tile.owner is None:
            return Ownership.EMPTY
        return Ownership.OURS if tile.owner == self.our_name else Ownership.ENEMY

    def our_tiles(self) -> list[Point]:
        return [p for p in self.cells if self.ownership_at(p) == Ownership.OURS]

    def is_placeable(self, pos: Point) -> bool:
        """A cell we could try to claim: inside the map and, as far as we
        know, not already taken. UNKNOWN cells are allowed — placement can
        be attempted anywhere, and a rejection just costs one attempt."""
        if not self.grid.contains(pos):
            return False
        return self.ownership_at(pos) in (Ownership.EMPTY, Ownership.UNKNOWN)

    def frontier(self) -> list[tuple[Point, Point]]:
        """(own_tile, free_neighbor) pairs where we can grow next."""
        out = []
        for own in self.our_tiles():
            for nb in own.neighbors():
                if self.is_placeable(nb):
                    out.append((own, nb))
        return out

    # ------------------------------------------------------------------ #
    # flags
    # ------------------------------------------------------------------ #
    def flag_ownership(self, flag: Flag) -> Ownership:
        """Flags don't carry an owner in the API — infer it from the tile
        under the flag (UNKNOWN while the flag sits in fog)."""
        return self.ownership_at(flag.pos)

    def target_flags(self) -> list[Flag]:
        """Flags worth expanding toward: not held by us, not nuked."""
        return [
            f for f in self.flags
            if not f.nuked and self.flag_ownership(f) != Ownership.OURS
        ]

    def enemy_flags(self) -> list[Flag]:
        """Flags confirmed held by an enemy (visible, owned, not us)."""
        return [
            f for f in self.flags
            if not f.nuked and self.flag_ownership(f) == Ownership.ENEMY
        ]

    def hidden_flags(self) -> list[Flag]:
        """Flags still in fog — scan candidates."""
        return [
            f for f in self.flags
            if not f.nuked and self.flag_ownership(f) == Ownership.UNKNOWN
        ]
