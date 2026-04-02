"""
Subgraph boundary helpers: world_id on nodes, authorized cross-world bridges on relationships.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.models.graph import Node, Relationship


def node_world_id(node: Optional[Node]) -> str:
    if node is None:
        return ""
    return str((node.attributes or {}).get("world_id") or "").strip().lower()


def relationship_endpoints_span_worlds(src: Optional[Node], tgt: Optional[Node]) -> bool:
    sw, tw = node_world_id(src), node_world_id(tgt)
    if not sw or not tw:
        return False
    return sw != tw


def is_authorized_cross_world_bridge(rel: Optional[Relationship]) -> bool:
    if rel is None:
        return False
    attrs: Dict[str, Any] = dict(rel.attributes or {})
    if not attrs.get("cross_world_bridge"):
        return False
    return bool(str(attrs.get("bridge_id") or "").strip())


def bridge_enabled(rel: Optional[Relationship]) -> bool:
    if rel is None:
        return False
    attrs = rel.attributes or {}
    if "enabled" not in attrs:
        return True
    v = attrs.get("enabled")
    if v is False or v == 0:
        return False
    if isinstance(v, str) and v.strip().lower() in ("false", "0", "no"):
        return False
    return bool(v)
