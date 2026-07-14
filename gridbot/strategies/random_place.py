"""Occasionally drop a square somewhere random.

This seeds new colonies (useful since visibility only radiates from our
own squares) and is biased toward the outer band of the grid, where the
land is emptier after each expansion.
"""

import random

from ..models import Point
from ..world import World
from .base import Action, ActionKind, Strategy

_MAX_TRIES = 20


class RandomPlace(Strategy):
    @property
    def weight(self) -> float:
        return self.config.weight_random_place

    def propose(self, world: World) -> Action | None:
        grid = world.grid
        if grid.width <= 1 or grid.height <= 1:
            return None

        band = max(1, int(min(grid.width, grid.height) / 2 * self.config.outer_band_fraction))
        for _ in range(_MAX_TRIES):
            p = Point(
                random.randint(grid.min_x, grid.max_x),
                random.randint(grid.min_y, grid.max_y),
            )
            # With probability `random_outer_bias`, only accept points in
            # the outer band; otherwise take any placeable point.
            if random.random() < self.config.random_outer_bias and grid.edge_distance(p) > band:
                continue
            if world.is_placeable(p):
                return Action(
                    kind=ActionKind.PLACE,
                    target=p,
                    reason="random seed placement",
                )
        return None
