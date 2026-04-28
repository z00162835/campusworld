"""
World entry integration service.

Singularity-room exits use type_code ``world_entrance`` (Evennia-style Exit), not graph-seeded ``world`` metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import db_session_context
from app.core.log import get_logger, LoggerNames
from app.commands.policy_expr import evaluate_policy_expr, PolicyExprError
from app.game_engine.world_room_resolve import find_world_room_node
from app.models.graph import Node, NodeType
from app.models.root_manager import root_manager


@dataclass
class WorldEntryDecision:
    ok: bool
    world_id: str
    spawn_key: str
    error_code: Optional[str] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class WorldEntryService:
    def __init__(self) -> None:
        self.logger = get_logger(LoggerNames.GAME)

    def resolve_portal(self, world_id: str, caller_context: Optional[Dict[str, Any]] = None) -> WorldEntryDecision:
        wid = str(world_id or "").strip().lower()
        if not wid:
            return WorldEntryDecision(
                ok=False,
                world_id=wid,
                spawn_key="",
                error_code="WORLD_ENTRY_INVALID_TARGET",
                message="世界名不能为空",
            )
        try:
            with db_session_context() as session:
                self._migrate_legacy_root_portal_to_world_entrance(session, wid)
                session.commit()
                node = self._find_world_entry_node(session, wid)
                if not node:
                    return WorldEntryDecision(
                        ok=False,
                        world_id=wid,
                        spawn_key="",
                        error_code="WORLD_ENTRY_PORTAL_MISSING",
                        message=f"奇点屋中未找到世界入口: {wid}",
                    )
                attrs = dict(node.attributes or {})
                if not bool(attrs.get("portal_enabled", True)):
                    return WorldEntryDecision(
                        ok=False,
                        world_id=wid,
                        spawn_key="",
                        error_code="WORLD_ENTRY_PORTAL_DISABLED",
                        message=f"世界入口当前不可用: {wid}",
                    )
                spawn_key = str(attrs.get("portal_spawn_key") or attrs.get("entry_room_id") or "campus")
                return WorldEntryDecision(
                    ok=True,
                    world_id=wid,
                    spawn_key=spawn_key,
                    metadata={"attributes": attrs},
                )
        except Exception as e:
            self.logger.error("resolve world portal failed: %s", e)
            return WorldEntryDecision(
                ok=False,
                world_id=wid,
                spawn_key="",
                error_code="WORLD_ENTRY_RESOLVE_FAILED",
                message=f"世界入口解析失败: {wid}",
            )

    def authorize_entry(self, portal: WorldEntryDecision, user: Optional[Any] = None) -> WorldEntryDecision:
        if not portal.ok:
            return portal
        attrs = dict((portal.metadata or {}).get("attributes") or {})
        locks = attrs.get("access_locks", {}) if isinstance(attrs.get("access_locks", {}), dict) else {}
        interact_expr = str(locks.get("interact", "all()"))
        try:
            allowed = evaluate_policy_expr(
                interact_expr,
                user_permissions=list(getattr(user, "permissions", []) or []),
                user_roles=list(getattr(user, "roles", []) or []),
                object_attrs=attrs,
            )
        except PolicyExprError:
            allowed = False
        if not allowed:
            return WorldEntryDecision(
                ok=False,
                world_id=portal.world_id,
                spawn_key=portal.spawn_key,
                error_code="WORLD_ENTRY_FORBIDDEN",
                message=f"当前用户无权限进入世界: {portal.world_id}",
                metadata=portal.metadata,
            )
        return portal

    def build_entry_request(self, world_id: str, spawn_override: Optional[str] = None) -> WorldEntryDecision:
        decision = self.resolve_portal(world_id)
        if not decision.ok:
            return decision
        if spawn_override:
            decision.spawn_key = str(spawn_override).strip().lower()
        return decision

    def sync_world_entry_visibility(self, world_id: str, *, enabled: bool) -> Tuple[bool, Optional[str]]:
        wid = str(world_id or "").strip().lower()
        if not wid:
            return False, "WORLD_ENTRY_INVALID_TARGET"
        try:
            with db_session_context() as session:
                root = root_manager.get_root_node(session)
                if not root:
                    return False, "WORLD_ENTRY_ROOT_UNAVAILABLE"
                self._migrate_legacy_root_portal_to_world_entrance(session, wid)
                node = self._find_world_entry_node(session, wid)
                if not node:
                    node = self._create_world_entry_node(session, wid, root.id)
                    if not node:
                        return False, "WORLD_ENTRY_PORTAL_MISSING"
                attrs = dict(node.attributes or {})
                attrs["portal_enabled"] = bool(enabled)
                attrs["portal_world_id"] = wid
                attrs["entity_kind"] = "exit"
                attrs["presentation_domains"] = ["room"]
                attrs["access_locks"] = {"view": "all()", "interact": "all()"}
                attrs["portal_spawn_key"] = str(attrs.get("portal_spawn_key") or attrs.get("entry_room_id") or "campus")
                attrs["entry_hint"] = f"enter {wid}"
                spawn_key = attrs["portal_spawn_key"]
                gate = find_world_room_node(session, wid, spawn_key)
                if gate:
                    attrs["destination_node_id"] = gate.id
                node.attributes = attrs
                flag_modified(node, "attributes")
                node.name = wid
                node.type_code = "world_entrance"
                wnt = session.query(NodeType).filter(NodeType.type_code == "world_entrance").first()
                if wnt:
                    node.type_id = wnt.id
                node.is_active = bool(enabled)
                node.is_public = bool(enabled)
                if enabled:
                    node.location_id = root.id
                    node.home_id = root.id
                else:
                    node.location_id = None
                    node.home_id = None
                session.add(node)
                session.commit()
                return True, None
        except Exception as e:
            self.logger.error("sync world entry visibility failed: %s", e)
            return False, "WORLD_ENTRY_SYNC_FAILED"

    def _migrate_legacy_root_portal_to_world_entrance(self, session: Session, world_id: str) -> None:
        """Upgrade old singularity portals (type_code=world on root) to world_entrance."""
        root = root_manager.get_root_node(session)
        if not root:
            return
        wnt = session.query(NodeType).filter(NodeType.type_code == "world_entrance").first()
        if not wnt:
            return
        wid = str(world_id or "").strip().lower()
        candidates = (
            session.query(Node)
            .filter(
                and_(
                    Node.type_code == "world",
                    Node.location_id == root.id,
                    Node.attributes["world_id"].astext == wid,
                )
            )
            .all()
        )
        for node in candidates:
            attrs = dict(node.attributes or {})
            portalish = bool(
                attrs.get("portal_spawn_key")
                or attrs.get("entry_hint")
                or attrs.get("portal_world_id") == wid
                or str(node.name or "").strip().lower() == wid
            )
            if not portalish:
                continue
            node.type_code = "world_entrance"
            node.type_id = wnt.id
            attrs.setdefault("portal_world_id", wid)
            attrs.setdefault("entity_kind", "exit")
            attrs.setdefault("presentation_domains", ["room"])
            spawn_key = str(attrs.get("portal_spawn_key") or attrs.get("entry_room_id") or "campus")
            gate = find_world_room_node(session, wid, spawn_key)
            if gate:
                attrs["destination_node_id"] = gate.id
            node.attributes = attrs
            flag_modified(node, "attributes")
            session.add(node)

    def _find_world_entry_node(self, session: Session, world_id: str) -> Optional[Node]:
        wid = str(world_id or "").strip().lower()
        return (
            session.query(Node)
            .filter(
                and_(
                    Node.type_code == "world_entrance",
                    or_(
                        Node.attributes["portal_world_id"].astext == wid,
                        Node.attributes["world_id"].astext == wid,
                    ),
                )
            )
            .first()
        )

    def _create_world_entry_node(self, session: Session, world_id: str, root_node_id: int) -> Optional[Node]:
        nt = session.query(NodeType).filter(NodeType.type_code == "world_entrance").first()
        if not nt:
            return None
        wid = str(world_id or "").strip().lower()
        spawn_key = "hicampus_gate" if wid == "hicampus" else "campus"
        gate = find_world_room_node(session, wid, spawn_key)
        dest_id = gate.id if gate else None
        node = Node(
            type_id=nt.id,
            type_code="world_entrance",
            name=wid,
            description=f"{wid} 世界入口。输入 'enter {wid}' 进入。",
            is_active=True,
            is_public=True,
            access_level="normal",
            location_id=root_node_id,
            home_id=root_node_id,
            attributes={
                "world_id": wid,
                "portal_world_id": wid,
                "portal_spawn_key": spawn_key,
                "portal_enabled": True,
                "entity_kind": "exit",
                "presentation_domains": ["room"],
                "access_locks": {"view": "all()", "interact": "all()"},
                "entry_hint": f"enter {wid}",
                **({"destination_node_id": dest_id} if dest_id is not None else {}),
            },
            tags=["world_entrance", wid],
        )
        session.add(node)
        session.flush()
        return node


world_entry_service = WorldEntryService()
