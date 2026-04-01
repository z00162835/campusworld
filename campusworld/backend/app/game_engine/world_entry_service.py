"""
World entry integration service.

Keeps a user-facing world entry object visible in SingularityRoom and
provides entry resolution/validation for `enter <world_id>`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.database import db_session_context
from app.core.log import get_logger, LoggerNames
from app.commands.policy_expr import evaluate_policy_expr, PolicyExprError
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
                node = self._find_world_entry_node(session, wid)
                if not node:
                    node = self._create_world_entry_node(session, wid, root.id)
                    if not node:
                        return False, "WORLD_ENTRY_PORTAL_MISSING"
                attrs = dict(node.attributes or {})
                attrs["portal_enabled"] = bool(enabled)
                attrs["portal_world_id"] = wid
                attrs["entity_kind"] = "item"
                attrs["presentation_domains"] = ["room"]
                attrs["access_locks"] = {"view": "all()", "interact": "all()"}
                attrs["portal_spawn_key"] = str(attrs.get("portal_spawn_key") or attrs.get("entry_room_id") or "campus")
                attrs["entry_hint"] = f"enter {wid}"
                node.attributes = attrs
                node.name = wid
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

    def _find_world_entry_node(self, session: Session, world_id: str) -> Optional[Node]:
        return (
            session.query(Node)
            .filter(
                and_(
                    Node.type_code == "world",
                    Node.attributes["world_id"].astext == str(world_id),
                )
            )
            .first()
        )

    def _create_world_entry_node(self, session: Session, world_id: str, root_node_id: int) -> Optional[Node]:
        nt = session.query(NodeType).filter(NodeType.type_code == "world").first()
        if not nt:
            return None
        node = Node(
            type_id=nt.id,
            type_code="world",
            name=world_id,
            description=f"{world_id} 世界入口。输入 'enter {world_id}' 进入。",
            is_active=True,
            is_public=True,
            access_level="normal",
            location_id=root_node_id,
            home_id=root_node_id,
            attributes={
                "world_id": world_id,
                "portal_world_id": world_id,
                "portal_spawn_key": "hicampus_gate" if world_id == "hicampus" else "campus",
                "portal_enabled": True,
                "entity_kind": "item",
                "presentation_domains": ["room"],
                "access_locks": {"view": "all()", "interact": "all()"},
                "entry_hint": f"enter {world_id}",
            },
            tags=["world", world_id],
        )
        session.add(node)
        session.flush()
        return node


world_entry_service = WorldEntryService()

