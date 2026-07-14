"""Scan the fog around flags we can't see yet.

Flag positions are public, but the owner is only knowable by seeing the
tile under the flag. A scan reveals a square area for a while, telling
us whether a flag is free to take, ours to defend, or an enemy's to
nuke — so aim scans at the richest hidden pot.
"""

from ..config import Config
from ..world import World
from .base import Action, ActionKind, CooldownGated


class ScanHiddenFlag(CooldownGated):
    def __init__(self, config: Config):
        super().__init__(config, config.scan_cooldown_seconds)
        self.size = config.scan_size  # clamped to server max at startup

    def propose(self, world: World) -> Action | None:
        if not self.ready():
            return None
        hidden = world.hidden_flags()
        if not hidden:
            return None
        flag = max(hidden, key=lambda f: f.pot)
        return Action(
            kind=ActionKind.SCAN,
            target=flag.pos,
            size=self.size,
            reason=f"scan hidden flag {flag.flag_id} (pot {flag.pot})",
        )
