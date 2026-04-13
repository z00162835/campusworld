"""
Admin-managed cross-world bridge links (connects_to + cross_world_bridge metadata).
"""

from __future__ import annotations

import uuid as uuidlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.game_engine.direction_util import normalize_direction
from app.core.database import db_session_context
from app.game_engine.subgraph_boundary import (
    bridge_enabled,
    is_authorized_cross_world_bridge,
    node_world_id,
)
from app.models.graph import Node, Relationship, RelationshipType

# Stable string error codes for bridge operations (document in world bridge SPEC).
WORLD_BRIDGE_PERMISSION_DENIED = "WORLD_BRIDGE_PERMISSION_DENIED"
WORLD_BRIDGE_INVALID_ARGUMENT = "WORLD_BRIDGE_INVALID_ARGUMENT"
WORLD_BRIDGE_NOT_FOUND = "WORLD_BRIDGE_NOT_FOUND"
WORLD_BRIDGE_ALREADY_EXISTS = "WORLD_BRIDGE_ALREADY_EXISTS"
WORLD_BRIDGE_CROSS_BOUNDARY_VIOLATION = "WORLD_BRIDGE_CROSS_BOUNDARY_VIOLATION"
WORLD_BRIDGE_DIRECTION_CONFLICT = "WORLD_BRIDGE_DIRECTION_CONFLICT"
WORLD_BRIDGE_APPLY_FAILED = "WORLD_BRIDGE_APPLY_FAILED"


_OPPOSITE_DIRECTION: Dict[str, str] = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "northeast": "southwest",
    "southwest": "northeast",
    "northwest": "southeast",
    "southeast": "northwest",
    "up": "down",
    "down": "up",
    "enter": "out",
    "out": "enter",
}


def opposite_direction(direction: str) -> str:
    d = normalize_direction(direction)
    return _OPPOSITE_DIRECTION.get(d, d)


def _find_room(session, world_id: str, package_node_id: str) -> Optional[Node]:
    wid = str(world_id).strip().lower()
    pkg = str(package_node_id).strip().lower()
    if not wid or not pkg:
        return None
    return (
        session.query(Node)
        .filter(
            Node.type_code == "room",
            Node.attributes["world_id"].astext == wid,
            Node.attributes["package_node_id"].astext == pkg,
            Node.is_active == True,  # noqa: E712
        )
        .first()
    )


def _existing_connects_same_direction(
    session, source_id: int, direction_norm: str
) -> Optional[Relationship]:
    rels = (
        session.query(Relationship)
        .filter(
            Relationship.source_id == source_id,
            Relationship.type_code == "connects_to",
            Relationship.is_active == True,  # noqa: E712
        )
        .all()
    )
    for r in rels:
        rd = normalize_direction(str((r.attributes or {}).get("direction") or ""))
        if rd == direction_norm:
            return r
    return None


def _bridge_payload(rel: Relationship, session) -> Dict[str, Any]:
    src = session.query(Node).filter(Node.id == rel.source_id).first()
    tgt = session.query(Node).filter(Node.id == rel.target_id).first()
    attrs = dict(rel.attributes or {})
    return {
        "bridge_id": str(attrs.get("bridge_id") or ""),
        "src_world": node_world_id(src),
        "dst_world": node_world_id(tgt),
        "src_node": str((src.attributes or {}).get("package_node_id") or "") if src else "",
        "dst_node": str((tgt.attributes or {}).get("package_node_id") or "") if tgt else "",
        "direction": normalize_direction(str(attrs.get("direction") or "")),
        "bridge_type": str(attrs.get("bridge_type") or "portal"),
        "enabled": bridge_enabled(rel),
        "relationship_id": rel.id,
    }


class WorldBridgeService:
    def add_bridge(
        self,
        *,
        operator: str,
        src_world: str,
        src_node_pkg: str,
        direction: str,
        dst_world: str,
        dst_node_pkg: str,
        two_way: bool = False,
        bridge_type: str = "portal",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        sw = str(src_world).strip().lower()
        dw = str(dst_world).strip().lower()
        if sw == dw:
            return {
                "ok": False,
                "error": WORLD_BRIDGE_CROSS_BOUNDARY_VIOLATION,
                "message": "bridge must span two different worlds",
                "validation_failures": [{"field": "dst_world", "reason": "same_as_src_world"}],
            }
        dir_norm = normalize_direction(direction)
        if not dir_norm:
            return {
                "ok": False,
                "error": WORLD_BRIDGE_INVALID_ARGUMENT,
                "message": "direction is required",
            }
        bt = str(bridge_type or "portal").strip().lower() or "portal"
        if bt not in ("portal", "gate", "transit"):
            return {
                "ok": False,
                "error": WORLD_BRIDGE_INVALID_ARGUMENT,
                "message": f"unsupported bridge_type: {bridge_type}",
            }

        validation_failures: List[Dict[str, Any]] = []
        with db_session_context() as session:
            src_room = _find_room(session, sw, src_node_pkg)
            dst_room = _find_room(session, dw, dst_node_pkg)
            if not src_room:
                validation_failures.append({"field": "src_node", "reason": "room_not_found", "world_id": sw})
            elif node_world_id(src_room) != sw:
                validation_failures.append({"field": "src_node", "reason": "world_mismatch"})
            if not dst_room:
                validation_failures.append({"field": "dst_node", "reason": "room_not_found", "world_id": dw})
            elif node_world_id(dst_room) != dw:
                validation_failures.append({"field": "dst_node", "reason": "world_mismatch"})
            if validation_failures:
                return {
                    "ok": False,
                    "error": WORLD_BRIDGE_CROSS_BOUNDARY_VIOLATION,
                    "message": "endpoint validation failed",
                    "validation_failures": validation_failures,
                }
            existing = _existing_connects_same_direction(session, int(src_room.id), dir_norm)
            if existing:
                tgt_id = int(existing.target_id)
                if tgt_id == int(dst_room.id):
                    bid = str((existing.attributes or {}).get("bridge_id") or "")
                    return {
                        "ok": False,
                        "error": WORLD_BRIDGE_ALREADY_EXISTS,
                        "message": "identical bridge already exists",
                        "bridge_id": bid,
                        "conflict_with": {"relationship_id": existing.id},
                    }
                return {
                    "ok": False,
                    "error": WORLD_BRIDGE_DIRECTION_CONFLICT,
                    "message": f"direction {dir_norm} already used from this room",
                    "conflict_with": {"relationship_id": existing.id, "existing_target_id": tgt_id},
                }

            bridge_id = str(uuidlib.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            base_attrs: Dict[str, Any] = {
                "direction": dir_norm,
                "cross_world_bridge": True,
                "bridge_id": bridge_id,
                "bridge_type": bt,
                "enabled": True,
                "created_by": operator,
                "approved_at": now,
            }

            if dry_run:
                created_links = [
                    {
                        "source_id": src_room.id,
                        "target_id": dst_room.id,
                        "direction": dir_norm,
                        **{k: v for k, v in base_attrs.items() if k != "direction"},
                    }
                ]
                if two_way:
                    created_links.append(
                        {
                            "source_id": dst_room.id,
                            "target_id": src_room.id,
                            "direction": opposite_direction(dir_norm),
                            "bridge_id": bridge_id,
                            "cross_world_bridge": True,
                            "bridge_type": bt,
                            "enabled": True,
                        }
                    )
                return {
                    "ok": True,
                    "status": "dry_run",
                    "bridge_id": bridge_id,
                    "two_way": two_way,
                    "bridge_type": bt,
                    "created_links": created_links,
                    "message": "dry-run: no database changes",
                }

            rt = session.query(RelationshipType).filter(RelationshipType.type_code == "connects_to").first()
            if not rt:
                return {"ok": False, "error": WORLD_BRIDGE_APPLY_FAILED, "message": "connects_to type missing"}

            def _ensure_forward() -> Relationship:
                rel = Relationship(
                    uuid=uuidlib.uuid4(),
                    type_id=rt.id,
                    type_code="connects_to",
                    source_id=src_room.id,
                    target_id=dst_room.id,
                    is_active=True,
                    attributes=dict(base_attrs),
                    tags=[],
                )
                session.add(rel)
                return rel

            _ensure_forward()
            created: List[Dict[str, Any]] = [{"source_id": src_room.id, "target_id": dst_room.id, "direction": dir_norm}]
            if two_way:
                rev_attrs = dict(base_attrs)
                rev_attrs["direction"] = opposite_direction(dir_norm)
                rev = Relationship(
                    uuid=uuidlib.uuid4(),
                    type_id=rt.id,
                    type_code="connects_to",
                    source_id=dst_room.id,
                    target_id=src_room.id,
                    is_active=True,
                    attributes=rev_attrs,
                    tags=[],
                )
                session.add(rev)
                created.append(
                    {
                        "source_id": dst_room.id,
                        "target_id": src_room.id,
                        "direction": rev_attrs["direction"],
                    }
                )

            session.commit()
            return {
                "ok": True,
                "status": "applied",
                "bridge_id": bridge_id,
                "two_way": two_way,
                "bridge_type": bt,
                "created_links": created,
                "message": "bridge created",
            }

    def remove_bridge(
        self,
        *,
        bridge_id: Optional[str] = None,
        src_world: Optional[str] = None,
        src_node_pkg: Optional[str] = None,
        direction: Optional[str] = None,
        dry_run: bool = False,
        force: bool = True,
    ) -> Dict[str, Any]:
        _ = force  # reserved; remove always allowed when permitted
        with db_session_context() as session:
            to_disable: List[Relationship] = []
            if bridge_id and str(bridge_id).strip():
                bid = str(bridge_id).strip()
                to_disable = (
                    session.query(Relationship)
                    .filter(
                        Relationship.type_code == "connects_to",
                        Relationship.is_active == True,  # noqa: E712
                        Relationship.attributes["bridge_id"].astext == bid,
                    )
                    .all()
                )
            elif src_world and src_node_pkg and direction:
                sw = str(src_world).strip().lower()
                src_room = _find_room(session, sw, str(src_node_pkg))
                if not src_room:
                    return {"ok": False, "error": WORLD_BRIDGE_NOT_FOUND, "message": "source room not found"}
                dir_norm = normalize_direction(str(direction))
                rels = (
                    session.query(Relationship)
                    .filter(
                        Relationship.source_id == src_room.id,
                        Relationship.type_code == "connects_to",
                        Relationship.is_active == True,  # noqa: E712
                    )
                    .all()
                )
                for r in rels:
                    if not is_authorized_cross_world_bridge(r):
                        continue
                    if normalize_direction(str((r.attributes or {}).get("direction") or "")) == dir_norm:
                        to_disable = [r]
                        break
            else:
                return {
                    "ok": False,
                    "error": WORLD_BRIDGE_INVALID_ARGUMENT,
                    "message": "provide bridge_id or (src_world, src_node, direction)",
                }

            if not to_disable:
                return {"ok": False, "error": WORLD_BRIDGE_NOT_FOUND, "message": "no matching bridge"}

            removed = [{"relationship_id": r.id} for r in to_disable]
            if dry_run:
                return {
                    "ok": True,
                    "status": "dry_run",
                    "removed_links": removed,
                    "message": "dry-run: no database changes",
                }
            for r in to_disable:
                r.is_active = False
                session.add(r)
            session.commit()
            return {"ok": True, "status": "applied", "removed_links": removed, "message": "bridge removed"}

    def list_bridges(
        self, world_id: Optional[str] = None, include_disabled: bool = False
    ) -> Dict[str, Any]:
        wid = str(world_id).strip().lower() if world_id else ""
        with db_session_context() as session:
            q = session.query(Relationship).filter(Relationship.type_code == "connects_to")
            if not include_disabled:
                q = q.filter(Relationship.is_active == True)  # noqa: E712
            rels = q.all()
            bridges: List[Dict[str, Any]] = []
            for r in rels:
                if not is_authorized_cross_world_bridge(r):
                    continue
                row = _bridge_payload(r, session)
                if wid:
                    if row["src_world"] != wid and row["dst_world"] != wid:
                        continue
                bridges.append(row)
            return {"ok": True, "bridges": bridges, "total": len(bridges)}

    def validate_bridges(self, world_id: Optional[str] = None) -> Dict[str, Any]:
        from app.game_engine.topology_service import world_topology_service

        wid = str(world_id).strip() if world_id else ""
        if not wid:
            return {
                "ok": False,
                "error": WORLD_BRIDGE_INVALID_ARGUMENT,
                "message": "world bridge validate requires world_id",
            }
        report = world_topology_service.validate_topology(wid)
        issues = [x for x in report.get("issues", []) if x.get("code") == "UNAUTHORIZED_CROSS_WORLD_RELATIONSHIP"]
        ok = len(issues) == 0
        return {
            "ok": ok,
            "world_id": wid,
            "issues": issues,
            "issue_count": len(issues),
            "summary": report,
        }


world_bridge_service = WorldBridgeService()
