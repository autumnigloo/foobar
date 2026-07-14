"""Every once in a while, fire a rocket at an enemy-held flag."""

import random
import time

from ..world import World
from .base import Action, ActionKind, Strategy


class RocketEnemyFlag(Strategy):
    def __init__(self, config):
        super().__init__(config)
        self._last_fired: float | None = None

    @property
    def weight(self) -> float:
        # Rockets are gated by cooldown, not by the weighted lottery:
        # whenever one is available and there's a target, propose it.
        return float("inf")

    def propose(self, world: World) -> Action | None:
        if (
            self._last_fired is not None
            and time.monotonic() - self._last_fired < self.config.rocket_cooldown_seconds
        ):
            return None
        targets = world.enemy_flags()
        if not targets:
            return None
        flag = random.choice(targets)
        return Action(
            kind=ActionKind.ROCKET,
            target=flag.pos,
            reason=f"rocket enemy flag owned by {flag.owner_color}",
        )

    def mark_fired(self) -> None:
        self._last_fired = time.monotonic()
