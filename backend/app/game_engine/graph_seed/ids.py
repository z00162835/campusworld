"""Deterministic node UUIDs for idempotent graph seeding."""

from __future__ import annotations

import uuid

# Stable namespace for CampusWorld graph seed (UUIDv5).
NAMESPACE_GRAPH_SEED = uuid.uuid5(uuid.NAMESPACE_URL, "https://campusworld.dev/graph-seed/v1")


def node_uuid(world_id: str, package_node_id: str) -> uuid.UUID:
    key = f"{world_id}:{package_node_id}"
    return uuid.uuid5(NAMESPACE_GRAPH_SEED, key)
