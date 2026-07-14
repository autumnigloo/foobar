"""Strategy interface.

Each strategy looks at the world and proposes a single action (or None
if it has nothing useful to do this tick). The bot picks among placement
proposals by weight; cooldown-gated strategies (nuke, scan) fire whenever
they're ready.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from ..config import Config
from ..models import Point
from ..world import World


class ActionKind(Enum):
    PLACE = "place"
    NUKE = "nuke"
    SCAN = "scan"


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    target: Point
    reason: str  # for logs, e.g. "advance toward flag f1 at (3, 4)"
    size: int | None = None  # SCAN only: side length of the scanned square


class Strategy(ABC):
    def __init__(self, config: Config):
        self.config = config

    @property
    @abstractmethod
    def weight(self) -> float:
        """Relative chance of being picked when it proposes an action."""

    @abstractmethod
    def propose(self, world: World) -> Action | None:
        ...


class CooldownGated(Strategy):
    """Strategy that fires whenever its cooldown has elapsed, outside the
    weighted lottery. The bot calls `mark_fired` on acceptance and
    `snooze` with the server's retry_after on rejection."""

    def __init__(self, config: Config, cooldown_seconds: float):
        super().__init__(config)
        self.cooldown_seconds = cooldown_seconds
        self._ready_at = 0.0  # monotonic timestamp; 0 = ready immediately

    @property
    def weight(self) -> float:
        return float("inf")

    def ready(self) -> bool:
        return time.monotonic() >= self._ready_at

    def mark_fired(self) -> None:
        self._ready_at = time.monotonic() + self.cooldown_seconds

    def snooze(self, seconds: float) -> None:
        self._ready_at = max(self._ready_at, time.monotonic() + seconds)
