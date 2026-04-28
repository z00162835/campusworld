"""HiCampus declarative package types -> DB node_types / relationship_types for graph seed."""

from __future__ import annotations

from typing import FrozenSet

from app.game_engine.graph_seed.errors import GraphSeedError
from app.game_engine.runtime_store import WorldErrorCode

# Keys: entity/spatial type_code in package YAML; values: node_types.type_code in DB.
# Ontology cross-check: HiCampus SPEC features/ entity type registry document.
_PACKAGE_TO_DB_NODE_TYPE = {
    "world": "world",
    "building": "building",
    "building_floor": "building_floor",
    "room": "room",
    "npc_agent": "npc_agent",
    "access_terminal": "access_terminal",
    "world_object": "world_object",
    "furniture": "furniture",
    "network_access_point": "network_access_point",
    "av_display": "av_display",
    "lighting_fixture": "lighting_fixture",
    "conference_seating": "conference_seating",
    "lounge_furniture": "lounge_furniture",
    "logical_zone": "logical_zone",
}


class HiCampusGraphProfile:
    """WorldGraphProfile implementation for package `hicampus`."""

    @property
    def strict_relationships(self) -> bool:
        """When True, snapshot relationships outside allowed_relationship_type_codes fail seed."""
        return False

    @property
    def world_package_id(self) -> str:
        return "hicampus"

    @property
    def allowed_relationship_type_codes(self) -> FrozenSet[str]:
        return frozenset({"contains", "connects_to", "located_in"})

    def map_node_type(self, package_type_code: str) -> str:
        code = str(package_type_code or "").strip()
        if code not in _PACKAGE_TO_DB_NODE_TYPE:
            raise GraphSeedError(
                WorldErrorCode.GRAPH_SEED_TYPE_UNKNOWN.value,
                f"no node type mapping for package type_code={code!r}",
            )
        return _PACKAGE_TO_DB_NODE_TYPE[code]


# Singleton-style export for seed_graph
HICAMPUS_GRAPH_PROFILE = HiCampusGraphProfile()
