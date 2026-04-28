"""Resolve the command invoker's account node and location from a graph session.

Shared by ``npc_agent_nlp`` ticks and the ``primer`` command.
"""

from __future__ import annotations

from typing import Optional

from app.commands.base import CommandContext


def resolve_caller_node_id(session, context: CommandContext) -> Optional[int]:
    """Best-effort: ``account`` node id for the invoker, or ``None``."""
    try:
        uid = getattr(context, "user_id", None)
        if uid is not None:
            try:
                return int(uid)
            except (TypeError, ValueError):
                pass
        name = getattr(context, "username", None)
        if not name or session is None:
            return None
        from app.models.graph import Node as _Node

        row = (
            session.query(_Node)
            .filter(
                _Node.type_code == "account",
                _Node.name == str(name),
                _Node.is_active == True,  # noqa: E712
            )
            .first()
        )
        return int(row.id) if row is not None else None
    except Exception:
        return None


def resolve_caller_location_id(session, caller_node_id: Optional[int]) -> Optional[int]:
    """Return ``location_id`` for the caller's account node, or ``None``."""
    if not caller_node_id or session is None:
        return None
    try:
        from app.models.graph import Node as _Node

        row = session.query(_Node).filter(_Node.id == caller_node_id).first()
        if row is None:
            return None
        loc = getattr(row, "location_id", None)
        return int(loc) if loc else None
    except Exception:
        return None


def resolve_room_display_name(session, location_node_id: Optional[int]) -> Optional[str]:
    """Best-effort room ``name`` for a graph node id."""
    if not location_node_id or session is None:
        return None
    try:
        from app.models.graph import Node as _Node

        row = session.query(_Node).filter(_Node.id == location_node_id).first()
        if row is None:
            return None
        name = (row.name or "").strip()
        return name or None
    except Exception:
        return None
