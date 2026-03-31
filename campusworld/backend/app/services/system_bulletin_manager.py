"""
System bulletin notices — query and persistence helpers for `system_notice` nodes.

BulletinBoardService should delegate filtering, sorting, and DTO shaping here.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.log import get_logger, LoggerNames
from app.models.graph import Node, NodeType
from app.models.system.bulletin_board import BulletinBoard
from app.models.system.system_notice import SystemNotice

logger = get_logger(LoggerNames.GAME)


def _notice_attrs(node: Node) -> Dict[str, Any]:
    return dict(node.attributes or {})


def _is_public_list_notice(node: Node) -> bool:
    """Published and not logically offline (is_active is False only when explicitly false)."""
    attrs = _notice_attrs(node)
    if attrs.get("status") != "published":
        return False
    if attrs.get("is_active") is False:
        return False
    return True


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts or not isinstance(ts, str):
        return None
    s = ts.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _sort_key_notice(node: Node) -> Tuple[float, float]:
    """Higher tuple sorts first (newer first)."""
    attrs = _notice_attrs(node)
    pub = _parse_iso(attrs.get("published_at"))
    created = node.created_at
    if created and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    pub_ts = pub.timestamp() if pub else 0.0
    cr_ts = created.timestamp() if created else 0.0
    return (pub_ts, cr_ts)


def notice_node_to_dto(node: Node) -> Dict[str, Any]:
    """Map a persisted notice Node to a plain dict for commands/UI."""
    attrs = _notice_attrs(node)
    return {
        "id": node.id,
        "uuid": str(node.uuid),
        "title": attrs.get("title", node.name),
        "content_md": attrs.get("content_md", ""),
        "status": attrs.get("status", "published"),
        "is_active": attrs.get("is_active", True),
        "priority": attrs.get("priority", "normal"),
        "published_at": attrs.get("published_at"),
        "updated_at": attrs.get("updated_at"),
        "author_id": attrs.get("author_id"),
        "notice_code": attrs.get("notice_code"),
        "tags": attrs.get("tags", []) if isinstance(attrs.get("tags"), list) else [],
    }


def validate_notice_title(title: str) -> Tuple[bool, str]:
    t = (title or "").strip()
    if not t:
        return False, "title is required"
    if len(t) > 120:
        return False, "title must be at most 120 characters"
    return True, ""


def validate_notice_content(content_md: str) -> Tuple[bool, str]:
    if content_md is None or not str(content_md).strip():
        return False, "content_md is required"
    return True, ""


class SystemBulletinManager:
    """Read/write `system_notice` rows under a bulletin board node."""

    def resolve_board_node_id(self, session: Session, root_node_id: int) -> Optional[int]:
        row = (
            session.query(Node)
            .filter(
                and_(
                    Node.type_code == "system_bulletin_board",
                    Node.location_id == root_node_id,
                    Node.is_active == True,  # noqa: E712
                    Node.attributes["board_key"].astext == BulletinBoard.DEFAULT_BOARD_KEY,
                )
            )
            .first()
        )
        return row.id if row else None

    def _fetch_notice_candidates(self, session: Session, board_node_id: int) -> List[Node]:
        return (
            session.query(Node)
            .filter(
                and_(
                    Node.type_code == "system_notice",
                    Node.location_id == board_node_id,
                    Node.is_active == True,  # noqa: E712
                )
            )
            .all()
        )

    def list_published_notices(
        self,
        session: Session,
        board_node_id: int,
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 10

        try:
            candidates = self._fetch_notice_candidates(session, board_node_id)
            public = [n for n in candidates if _is_public_list_notice(n)]
            public.sort(key=_sort_key_notice, reverse=True)
            total = len(public)
            total_pages = max(1, math.ceil(total / page_size)) if total else 1
            if total == 0:
                return {
                    "items": [],
                    "total": 0,
                    "total_pages": 1,
                    "page": 1,
                    "page_size": page_size,
                }
            if page > total_pages:
                page = total_pages
            offset = (page - 1) * page_size
            slice_rows = public[offset : offset + page_size]
            items = []
            for n in slice_rows:
                dto = notice_node_to_dto(n)
                items.append(
                    {
                        "id": dto["id"],
                        "title": dto["title"],
                        "published_at": dto["published_at"],
                        "priority": dto["priority"],
                        "status": dto["status"],
                    }
                )
            return {
                "items": items,
                "total": total,
                "total_pages": total_pages,
                "page": page,
                "page_size": page_size,
            }
        except Exception as e:
            logger.error("list_published_notices failed: %s", e)
            return {
                "items": [],
                "total": 0,
                "total_pages": 1,
                "page": max(1, page),
                "page_size": page_size,
            }

    def get_notice_by_id(
        self,
        session: Session,
        notice_id: int,
        *,
        board_node_id: Optional[int] = None,
        public_only: bool = True,
    ) -> Optional[Dict[str, Any]]:
        try:
            node = session.query(Node).filter(Node.id == notice_id, Node.type_code == "system_notice").first()
            if not node:
                return None
            if board_node_id is not None and node.location_id != board_node_id:
                return None
            if public_only and not _is_public_list_notice(node):
                return None
            return notice_node_to_dto(node)
        except Exception as e:
            logger.error("get_notice_by_id failed: %s", e)
            return None

    def get_notice_by_page_index(
        self,
        session: Session,
        board_node_id: int,
        page: int,
        index: int,
        page_size: int = 10,
    ) -> Optional[Dict[str, Any]]:
        payload = self.list_published_notices(session, board_node_id, page=page, page_size=page_size)
        items = payload.get("items") or []
        if index < 1 or index > len(items):
            return None
        summary = items[index - 1]
        nid = summary.get("id")
        if nid is None:
            return None
        return self.get_notice_by_id(session, int(nid), board_node_id=board_node_id, public_only=True)

    def ensure_system_notice_type(self, session: Session) -> Optional[int]:
        row = session.query(NodeType).filter(NodeType.type_code == "system_notice").first()
        if row:
            return row.id
        nt = NodeType(
            type_code="system_notice",
            type_name="SystemNotice",
            typeclass="app.models.system.system_notice.SystemNotice",
            classname="SystemNotice",
            module_path="app.models.system.system_notice",
            description="System bulletin notice",
            schema_definition={
                "title": "string",
                "content_md": "text",
                "status": "string",
                "is_active": "boolean",
                "published_at": "string",
            },
            is_active=True,
        )
        session.add(nt)
        session.commit()
        session.refresh(nt)
        return nt.id

    def create_notice(
        self,
        session: Session,
        board_node_id: int,
        title: str,
        content_md: str,
        *,
        status: str = "published",
        author_id: Optional[int] = None,
        notice_code: Optional[str] = None,
        **kwargs: Any,
    ) -> Optional[Node]:
        ok, err = validate_notice_title(title)
        if not ok:
            logger.warning("create_notice validation: %s", err)
            return None
        ok, err = validate_notice_content(content_md)
        if not ok:
            logger.warning("create_notice validation: %s", err)
            return None

        type_id = self.ensure_system_notice_type(session)
        if not type_id:
            return None

        notice = SystemNotice(
            title=title.strip(),
            content_md=str(content_md),
            status=status,
            author_id=author_id,
            notice_code=notice_code,
            disable_auto_sync=True,
            **kwargs,
        )
        node = Node(
            uuid=notice._node_uuid,
            type_id=type_id,
            type_code="system_notice",
            name=notice._node_name,
            description=(notice._node_attributes or {}).get("title", ""),
            is_active=True,
            is_public=True,
            access_level="normal",
            location_id=board_node_id,
            home_id=board_node_id,
            attributes=notice._node_attributes,
            tags=getattr(notice, "_node_tags", []) or [],
        )
        session.add(node)
        session.commit()
        session.refresh(node)
        return node
