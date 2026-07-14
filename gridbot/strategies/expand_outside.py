"""Grow our territory outward, toward the grid edge.

Rationale: the grid expands (~every 10 min, at 70% fullness), so the
outer ring is chronically emptier than the center — cheap land. Staying
anchored near the edge also protects us from the enclosure-capture rule:
territory touching the border is much harder for a single enemy to fully
surround.
"""

import random

from ..world import World
from .base import Action, ActionKind, Strategy


class ExpandOutside(Strategy):
    @property
    def weight(self) -> float:
        return self.config.weight_expand_outside

    def propose(self, world: World) -> Action | None:
        frontier = world.frontier()
        if not frontier:
            return None
        # Prefer frontier cells closest to the grid edge; jitter among the
        # best few so we don't grow a single predictable line.
        frontier.sort(key=lambda pair: world.grid.edge_distance(pair[1]))
        _, target = random.choice(frontier[: max(1, len(frontier) // 4)])
        return Action(
            kind=ActionKind.PLACE,
            target=target,
            reason=f"expand outward (edge distance {world.grid.edge_distance(target)})",
        )
