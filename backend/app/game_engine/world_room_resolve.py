"""Resolve world (package) rooms in the graph by world_id + package_node_id."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.graph import Node


def find_world_room_node(session: Session, world_id: str, package_node_id: str) -> Optional[Node]:
    """Return the active room Node for a world package room id, or None."""
    wid = str(world_id or "").strip().lower()
    pid = str(package_node_id or "").strip().lower()
    if not wid or not pid:
        return None
    return (
        session.query(Node)
        .filter(
            Node.type_code == "room",
            Node.attributes["world_id"].astext == wid,
            Node.attributes["package_node_id"].astext == pid,
            Node.is_active == True,  # noqa: E712
        )
        .first()
    )


def get_world_entry_package_node_id(session: Session, world_id: str) -> Optional[str]:
    """
    Package room id of the world's entry / spawn room (from seeded ``world`` metadata node).

    Reads ``entry_room_id`` (HiCampus world.yaml) or legacy keys on the graph ``world`` row.
    """
    wid = str(world_id or "").strip().lower()
    if not wid:
        return None
    meta = (
        session.query(Node)
        .filter(
            Node.type_code == "world",
            Node.attributes["world_id"].astext == wid,
            Node.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not meta:
        return None
    a: Dict[str, Any] = dict(meta.attributes or {})
    for key in ("entry_room_id", "entry_room", "portal_spawn_key"):
        v = a.get(key)
        if v is not None and str(v).strip():
            return str(v).strip().lower()
    return None


def room_is_world_entry_gate(session: Session, room: Optional[Node], world_id: str) -> bool:
    """True if ``room`` is the configured entry room for ``world_id`` (e.g. gate → ``out`` → singularity)."""
    if room is None or str(room.type_code or "") != "room":
        return False
    ra = dict(room.attributes or {})
    rw = str(ra.get("world_id") or "").strip().lower()
    if rw != str(world_id or "").strip().lower():
        return False
    pkg = str(ra.get("package_node_id") or "").strip().lower()
    entry = get_world_entry_package_node_id(session, world_id)
    return bool(entry and pkg == entry)
