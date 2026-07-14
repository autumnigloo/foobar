"""Strategy interface.

Each strategy looks at the world and proposes a single action (or None
if it has nothing useful to do this tick). The bot picks among proposals
by weight, so strategies stay independent and easy to tune or replace.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from ..config import Config
from ..models import Point
from ..world import World


class ActionKind(Enum):
    PLACE = "place"
    ROCKET = "rocket"


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    target: Point
    reason: str  # for logs, e.g. "expand toward flag at (3, 4)"


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
