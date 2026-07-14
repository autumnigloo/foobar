"""Grow a corridor from our nearest square toward the nearest flag we
don't own. Flags give extra points while held."""

from ..models import Flag, Point
from ..world import World
from .base import Action, ActionKind, Strategy


class ExpandToFlag(Strategy):
    @property
    def weight(self) -> float:
        return self.config.weight_expand_to_flag

    def propose(self, world: World) -> Action | None:
        flags = world.unowned_target_flags()
        frontier = world.frontier()
        if not flags or not frontier:
            return None

        # Pick the (frontier cell, flag) pair with the smallest remaining
        # distance, i.e. greedily walk our closest tendril at its closest
        # target. Good enough as a heuristic; A* around enemy walls can
        # come later once we know how contested the maps are.
        best: tuple[int, Point, Flag] | None = None
        for _, cell in frontier:
            for flag in flags:
                d = cell.manhattan(flag.pos)
                if best is None or d < best[0]:
                    best = (d, cell, flag)

        assert best is not None
        _, target, flag = best
        return Action(
            kind=ActionKind.PLACE,
            target=target,
            reason=f"advance toward flag at ({flag.pos.x}, {flag.pos.y})",
        )
