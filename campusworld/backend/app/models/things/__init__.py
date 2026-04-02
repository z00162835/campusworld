"""Import side effects: register thing typeclasses for runtime resolution."""

from .base import WorldThing
from .terminals import AccessTerminal
from .agents import NpcAgent
from .zones import LogicalZone
from .furniture import Furniture
from .devices import AvDisplay, LightingFixture, NetworkAccessPoint
from .seating import ConferenceSeating, LoungeFurniture

__all__ = [
    "WorldThing",
    "AccessTerminal",
    "NpcAgent",
    "LogicalZone",
    "Furniture",
    "NetworkAccessPoint",
    "AvDisplay",
    "LightingFixture",
    "ConferenceSeating",
    "LoungeFurniture",
]
