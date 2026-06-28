"""Persist logout conversation archives as account-owned graph nodes."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.graph import Node, NodeType, Relationship, RelationshipType
from app.schemas.world_history import MAX_ARCHIVE_BATCH_BYTES

ARCHIVE_NODE_TYPE = "world_conversation_archive"
OWNS_RELATIONSHIP_TYPE = "owns"
DEFAULT_MAX_ARCHIVES_PER_USER = 100


class WorldHistoryArchiveLimitError(ValueError):
    """Raised when archive storage limits are exceeded."""


class WorldConversationArchiveRepository:
    def __init__(self, *, max_archives_per_user: int = DEFAULT_MAX_ARCHIVES_PER_USER) -> None:
        self._max_archives_per_user = max(1, int(max_archives_per_user))

    def list_summaries_for_account(
        self,
        session: Session,
        account_node_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[Dict[str, Any]], int]:
        base_query = (
            session.query(Node)
            .join(Relationship, Relationship.target_id == Node.id)
            .filter(
                Relationship.source_id == account_node_id,
                Relationship.type_code == OWNS_RELATIONSHIP_TYPE,
                Relationship.is_active == True,
                Node.type_code == ARCHIVE_NODE_TYPE,
                Node.is_active == True,
            )
        )
        total = base_query.count()
        nodes = (
            base_query.order_by(Node.created_at.desc())
            .offset(max(0, offset))
            .limit(max(1, limit))
            .all()
        )
        entries = [self._summary_entry_from_node(node) for node in nodes]
        return entries, total

    def append_for_account(self, session: Session, account_node: Node, entry: Dict[str, Any]) -> Dict[str, Any]:
        self._lock_account_row(session, account_node.id)
        current_count = self.count_for_account(session, account_node.id)
        if current_count >= self._max_archives_per_user:
            raise WorldHistoryArchiveLimitError(
                f"Archive limit reached ({self._max_archives_per_user} batches per account)"
            )

        payload_bytes = len(json.dumps(entry, ensure_ascii=False).encode("utf-8"))
        if payload_bytes > MAX_ARCHIVE_BATCH_BYTES:
            raise WorldHistoryArchiveLimitError(
                f"Archive batch exceeds size limit ({MAX_ARCHIVE_BATCH_BYTES} bytes)"
            )

        archive_type_id = self._require_node_type_id(session)
        owns_type_id = self._require_relationship_type_id(session)

        archive_id = str(entry.get("id") or "")
        archive_node = Node(
            type_id=archive_type_id,
            type_code=ARCHIVE_NODE_TYPE,
            name=archive_id or "conversation_archive",
            description="Archived AICO and command conversations",
            is_active=True,
            is_public=False,
            access_level="private",
            attributes={
                "archive_id": archive_id,
                "archived_at": entry.get("archivedAt"),
                "aico_threads": list(entry.get("aico_threads") or []),
                "command_conversation": list(entry.get("command_conversation") or []),
                "history_summary": dict(entry.get("history_summary") or {}),
            },
            tags=["world_history", "conversation_archive"],
        )
        session.add(archive_node)
        session.flush()

        relationship = Relationship(
            type_id=owns_type_id,
            type_code=OWNS_RELATIONSHIP_TYPE,
            source_id=account_node.id,
            target_id=archive_node.id,
            source_role="owner",
            target_role="archive",
            is_active=True,
            attributes={"kind": "world_conversation_archive"},
        )
        session.add(relationship)
        session.flush()
        return entry

    def count_for_account(self, session: Session, account_node_id: int) -> int:
        return (
            session.query(Node.id)
            .join(Relationship, Relationship.target_id == Node.id)
            .filter(
                Relationship.source_id == account_node_id,
                Relationship.type_code == OWNS_RELATIONSHIP_TYPE,
                Relationship.is_active == True,
                Node.type_code == ARCHIVE_NODE_TYPE,
                Node.is_active == True,
            )
            .count()
        )

    @staticmethod
    def _summary_entry_from_node(node: Node) -> Dict[str, Any]:
        attrs = dict(node.attributes or {})
        history_summary = dict(attrs.get("history_summary") or {})
        archived_at = attrs.get("archived_at") or (node.created_at.isoformat() if node.created_at else None)
        return {
            "id": str(attrs.get("archive_id") or node.uuid),
            "archivedAt": archived_at,
            "history_summary": history_summary,
            "aico_threads": list(attrs.get("aico_threads") or []),
            "command_conversation": list(attrs.get("command_conversation") or []),
        }

    @staticmethod
    def _lock_account_row(session: Session, account_node_id: int) -> None:
        locked = (
            session.query(Node)
            .filter(Node.id == account_node_id, Node.type_code == "account", Node.is_active == True)
            .with_for_update()
            .first()
        )
        if not locked:
            raise ValueError("Account node not found for archive lock")

    @staticmethod
    def _require_node_type_id(session: Session) -> int:
        row = (
            session.query(NodeType.id)
            .filter(NodeType.type_code == ARCHIVE_NODE_TYPE, NodeType.status == 0)
            .first()
        )
        if not row:
            raise RuntimeError(
                "world_conversation_archive node type is missing; run database migrate"
            )
        return int(row[0])

    @staticmethod
    def _require_relationship_type_id(session: Session) -> int:
        row = (
            session.query(RelationshipType.id)
            .filter(RelationshipType.type_code == OWNS_RELATIONSHIP_TYPE, RelationshipType.status == 0)
            .first()
        )
        if not row:
            raise RuntimeError("owns relationship type is missing; run database migrate")
        return int(row[0])
