"""
CommandContext for npc_agent tool execution.

When the agent node has ``attributes.service_account_id`` pointing to an account
``Node``, tools use that account's permissions/roles; otherwise the invoker's
context is used (metadata marks ``principal`` as ``invoker`` vs ``service_account``).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.commands.base import CommandContext
from app.models.graph import Node


def command_context_for_npc_agent(
    session: Session,
    agent_node: Node,
    fallback: CommandContext,
) -> CommandContext:
    attrs = agent_node.attributes or {}
    sid = attrs.get("service_account_id")
    aid: int | None = None
    if sid is not None:
        try:
            aid = int(sid)
        except (TypeError, ValueError):
            aid = None

    if aid is not None:
        acc = (
            session.query(Node)
            .filter(
                Node.id == aid,
                Node.type_code == "account",
                Node.is_active == True,  # noqa: E712
            )
            .first()
        )
        if acc is not None:
            a = dict(acc.attributes or {})
            perms = list(a.get("permissions", []))
            roles = list(a.get("roles", []))
            meta = dict(fallback.metadata or {})
            meta["principal"] = "service_account"
            meta["agent_node_id"] = agent_node.id
            return CommandContext(
                user_id=str(acc.id),
                username=acc.name or str(acc.id),
                session_id=fallback.session_id or f"agent_worker_{agent_node.id}",
                permissions=perms,
                roles=roles,
                db_session=session,
                caller=fallback.caller,
                metadata=meta,
            )

    meta = dict(fallback.metadata or {})
    meta["principal"] = "invoker"
    meta["agent_node_id"] = agent_node.id
    return CommandContext(
        user_id=fallback.user_id,
        username=fallback.username,
        session_id=fallback.session_id,
        permissions=list(fallback.permissions or []),
        roles=list(fallback.roles or []),
        db_session=fallback.db_session,
        caller=fallback.caller,
        metadata=meta,
    )
