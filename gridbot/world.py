"""In-memory model of everything we know about the board.

Visibility is limited to squares adjacent to our own, so the world model
accumulates observations over time and exposes the derived views the
strategies need: our squares, the frontier (our squares with free
neighbors), and known flags.
"""

import time

from .models import Flag, GridInfo, Ownership, Point, Square


class World:
    def __init__(self):
        self.grid = GridInfo(0, 0, 0, 0)
        self.our_color: str | None = None
        # Latest known state per cell. Cells never observed are absent
        # (treat as UNKNOWN); observations can go stale if a cell leaves
        # our visibility, which is fine for heuristic play.
        self.cells: dict[Point, Square] = {}
        self.flags: list[Flag] = []
        self.flags_fetched_at: float = 0.0

    # ------------------------------------------------------------------ #
    # updates
    # ------------------------------------------------------------------ #
    def update_grid(self, grid: GridInfo) -> None:
        self.grid = grid

    def update_squares(self, squares: list[Square]) -> None:
        for sq in squares:
            self.cells[sq.pos] = sq

    def update_flags(self, flags: list[Flag]) -> None:
        self.flags = flags
        self.flags_fetched_at = time.monotonic()

    def record_own_placement(self, pos: Point) -> None:
        """Optimistically mark a successful placement as ours so the next
        tick's frontier includes it even before the server confirms."""
        self.cells[pos] = Square(pos=pos, color=self.our_color, ownership=Ownership.OURS)

    # ------------------------------------------------------------------ #
    # derived views
    # ------------------------------------------------------------------ #
    def ownership_at(self, pos: Point) -> Ownership:
        sq = self.cells.get(pos)
        return sq.ownership if sq else Ownership.UNKNOWN

    def our_squares(self) -> list[Point]:
        return [p for p, sq in self.cells.items() if sq.ownership == Ownership.OURS]

    def is_placeable(self, pos: Point) -> bool:
        """A cell we could try to claim: inside the grid and, as far as we
        know, not already taken. UNKNOWN cells are allowed — placement can
        be attempted anywhere, and a rejection just costs one attempt."""
        if not self.grid.contains(pos):
            return False
        return self.ownership_at(pos) in (Ownership.EMPTY, Ownership.UNKNOWN)

    def frontier(self) -> list[tuple[Point, Point]]:
        """(own_square, free_neighbor) pairs where we can grow next."""
        out = []
        for own in self.our_squares():
            for nb in own.neighbors():
                if self.is_placeable(nb):
                    out.append((own, nb))
        return out

    def enemy_flags(self) -> list[Flag]:
        return [
            f for f in self.flags
            if f.owner_color is not None and f.owner_color != self.our_color
        ]

    def unowned_target_flags(self) -> list[Flag]:
        """Flags worth walking toward: anything we don't own yet."""
        return [f for f in self.flags if f.owner_color != self.our_color]
