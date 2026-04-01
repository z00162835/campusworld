"""Import side effects: register thing typeclasses for runtime resolution."""

from .base import WorldThing
from .terminals import AccessTerminal
from .agents import NpcAgent
from .zones import LogicalZone
from .furniture import Furniture

__all__ = [
    "WorldThing",
    "AccessTerminal",
    "NpcAgent",
    "LogicalZone",
    "Furniture",
]
