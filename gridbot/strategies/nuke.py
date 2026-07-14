"""Every once in a while, launch a nuke at an enemy-held flag.

Nukes cost points and have a server cooldown + max-active cap
(GET /method-limits); the bot syncs our cooldown to the server's at
startup and snoozes on any rejection's retry_after.
"""

from ..config import Config
from ..world import World
from .base import Action, ActionKind, CooldownGated


class NukeEnemyFlag(CooldownGated):
    def __init__(self, config: Config):
        super().__init__(config, config.nuke_cooldown_seconds)

    def propose(self, world: World) -> Action | None:
        if not self.ready():
            return None
        targets = world.enemy_flags()
        if not targets:
            return None
        # Biggest pot first: that's the most enemy score denied per nuke.
        flag = max(targets, key=lambda f: f.pot)
        return Action(
            kind=ActionKind.NUKE,
            target=flag.pos,
            reason=f"nuke enemy flag {flag.flag_id} (pot {flag.pot})",
        )
