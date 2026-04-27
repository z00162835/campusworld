"""
Shared ``connects_to`` room exit resolution for ``look`` and ``space``.

Single source of truth for outgoing room adjacency; avoids duplicating
direction normalization and target display logic.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.game_engine.direction_util import normalize_direction
from app.models.graph import Node, Relationship


def target_room_display(node: Any) -> Dict[str, str]:
    """Build short display strings for a target room node (``look`` / ``space``)."""
    attrs = dict(getattr(node, "attributes", {}) or {})
    display_name = str(
        attrs.get("room_name")
        or attrs.get("display_name")
        or getattr(node, "name", "")
        or attrs.get("package_node_id")
        or "?"
    ).strip()
    short_desc = str(attrs.get("room_short_description") or "").strip()
    pkg = str(attrs.get("package_node_id") or "").strip().lower()
    return {
        "target_display_name": display_name,
        "target_short_desc": short_desc,
        "target_package_node_id": pkg,
    }


def connects_to_exits_from_room(
    session: Any,
    room_node_id: int,
) -> List[Dict[str, Any]]:
    """
    Return outgoing ``connects_to`` rows for a room, including target node id.

    Each dict: ``direction``, ``target_id`` (int), ``target_display_name``,
    ``target_short_desc``, ``target_package_node_id``, ``is_cross_world``.
    """
    entries: List[Dict[str, Any]] = []
    outgoing = (
        session.query(Relationship, Node)
        .join(Node, Relationship.target_id == Node.id)
        .filter(
            Relationship.source_id == room_node_id,
            Relationship.type_code == "connects_to",
            Relationship.is_active == True,  # noqa: E712
            Node.is_active == True,  # noqa: E712
        )
        .all()
    )
    for rel, target in outgoing:
        rattrs = dict(rel.attributes or {})
        raw = str(rattrs.get("direction") or "").strip().lower()
        if raw:
            direction = normalize_direction(raw)
        else:
            pkg = str((target.attributes or {}).get("package_node_id") or "").strip().lower()
            direction = pkg if pkg else ""
        if not direction:
            continue
        tgt = target_room_display(target)
        entries.append(
            {
                "direction": direction,
                "target_id": int(target.id),
                "target_display_name": tgt["target_display_name"],
                "target_short_desc": tgt["target_short_desc"],
                "target_package_node_id": tgt["target_package_node_id"],
                "is_cross_world": False,
            }
        )
    entries.sort(
        key=lambda x: (str(x.get("direction") or ""), str(x.get("target_display_name") or ""))
    )
    return entries


def connects_to_exit_entries_for_look(session: Any, room_node_id: int) -> List[Dict[str, Any]]:
    """Same shape as legacy ``LookCommand._exit_entries_from_connects_to`` (no ``target_id``)."""
    out: List[Dict[str, Any]] = []
    for row in connects_to_exits_from_room(session, room_node_id):
        out.append(
            {
                "direction": row["direction"],
                "target_display_name": row["target_display_name"],
                "target_short_desc": row["target_short_desc"],
                "target_package_node_id": row["target_package_node_id"],
                "is_cross_world": row.get("is_cross_world", False),
            }
        )
    return out
