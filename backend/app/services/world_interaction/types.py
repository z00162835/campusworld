"""Shared types for CampusWorld HTTP interaction aggregation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

CAMPUS_HUB_WORLD_ID = "__campus_hub__"

DISPLAY_POLICY = {
    "maxDecisionEventsVisible": 2,
    "maxActionsPerCard": 3,
    "maxMapNodesVisible": 7,
    "maxAgentsHighlighted": 3,
    "contextDefaultCollapsed": True,
    "mapDefaultCollapsed": False,
    "historyDefaultCollapsed": True,
}


@dataclass(frozen=True)
class WorldActor:
    user_id: str
    username: str
    permissions: List[str]
    roles: List[str]
