"""Conversation STM (Mode A / Mode B), thread ids, deterministic compaction."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.commands.base import CommandContext
from app.models.system.agent_memory_tables import (
    AgentConversationStm,
    AgentConversationThread,
    AgentDaemonStmLock,
)

CONV_SCOPE_PER_USER = "per_user_session"
CONV_SCOPE_DAEMON = "system_shared_exclusive"


def parse_conversation_scope_mode(attrs: Dict[str, Any]) -> str:
    raw = str((attrs or {}).get("conversation_scope_mode") or CONV_SCOPE_PER_USER).strip().lower()
    if raw == CONV_SCOPE_DAEMON:
        return CONV_SCOPE_DAEMON
    return CONV_SCOPE_PER_USER


def get_thread_id_from_context(context: CommandContext) -> Optional[uuid.UUID]:
    md = context.metadata or {}
    raw = md.get("conversation_thread_id")
    if raw is None:
        return None
    if isinstance(raw, uuid.UUID):
        return raw
    try:
        return uuid.UUID(str(raw))
    except Exception:
        return None


def set_thread_id_on_context(context: CommandContext, tid: uuid.UUID) -> None:
    if context.metadata is None:
        context.metadata = {}
    context.metadata["conversation_thread_id"] = str(tid)


def ensure_mode_a_thread_id(
    session: Session,
    *,
    context: CommandContext,
    caller_account_node_id: int,
    agent_node_id: int,
) -> uuid.UUID:
    existing = get_thread_id_from_context(context)
    if existing:
        return existing
    tid = uuid.uuid4()
    transport = str(context.session_id or "")
    session.add(
        AgentConversationThread(
            id=tid,
            owner_account_node_id=caller_account_node_id,
            agent_node_id=agent_node_id,
            transport_session_id=transport,
            title_snippet=None,
        )
    )
    session.flush()
    set_thread_id_on_context(context, tid)
    return tid


def load_or_create_mode_a_stm(
    session: Session,
    *,
    caller_account_node_id: int,
    transport_session_id: str,
    agent_node_id: int,
    conversation_thread_id: uuid.UUID,
) -> AgentConversationStm:
    row = (
        session.query(AgentConversationStm)
        .filter(
            AgentConversationStm.caller_account_node_id == caller_account_node_id,
            AgentConversationStm.transport_session_id == transport_session_id,
            AgentConversationStm.agent_node_id == agent_node_id,
            AgentConversationStm.conversation_thread_id == conversation_thread_id,
        )
        .first()
    )
    if row:
        return row
    row = AgentConversationStm(
        caller_account_node_id=caller_account_node_id,
        transport_session_id=transport_session_id,
        agent_node_id=agent_node_id,
        conversation_thread_id=conversation_thread_id,
        messages=[],
        rolling_summary="",
    )
    session.add(row)
    session.flush()
    return row


def normalize_messages(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "")
        ts = item.get("ts")
        out.append({"role": role, "content": content, "ts": ts})
    return out


def format_stm_for_prompt(messages: List[Dict[str, Any]], rolling_summary: str) -> str:
    parts: List[str] = []
    rs = (rolling_summary or "").strip()
    if rs:
        parts.append(f"Conversation summary:\n{rs}")
    for m in messages:
        role = m.get("role") or "unknown"
        content = m.get("content") or ""
        parts.append(f"{role}: {content}")
    return "\n".join(parts).strip()


def apply_compaction_truncate(
    messages: List[Dict[str, Any]],
    rolling_summary: str,
    *,
    stm_max_turns: int,
    stm_max_chars: int,
) -> Tuple[List[Dict[str, Any]], str]:
    msgs = list(messages)
    rs = rolling_summary or ""

    def total_chars() -> int:
        return len(format_stm_for_prompt(msgs, rs))

    max_msgs = max(1, int(stm_max_turns)) * 2
    while msgs and (len(msgs) > max_msgs or total_chars() > int(stm_max_chars)):
        msgs.pop(0)
    while msgs and total_chars() > int(stm_max_chars):
        msgs.pop(0)
    return msgs, rs


def stm_should_compact_after_append(
    messages: List[Dict[str, Any]],
    rolling_summary: str,
    *,
    stm_max_chars: int,
    compaction_trigger_ratio: float,
) -> bool:
    if stm_max_chars <= 0:
        return False
    cur = len(format_stm_for_prompt(messages, rolling_summary))
    threshold = float(compaction_trigger_ratio) * float(stm_max_chars)
    return cur >= threshold


def load_daemon_row_for_update(session: Session, agent_node_id: int) -> AgentDaemonStmLock:
    row = (
        session.query(AgentDaemonStmLock)
        .filter(AgentDaemonStmLock.agent_node_id == agent_node_id)
        .with_for_update()
        .first()
    )
    if row is None:
        session.execute(
            text(
                """
                INSERT INTO agent_daemon_stm_lock (
                    agent_node_id, messages, rolling_summary, stm_generation, possession_generation, updated_at
                )
                VALUES (
                    :aid, '[]'::jsonb, '', 0, 0, CURRENT_TIMESTAMP
                )
                ON CONFLICT (agent_node_id) DO NOTHING
                """
            ),
            {"aid": agent_node_id},
        )
        session.flush()
        row = (
            session.query(AgentDaemonStmLock)
            .filter(AgentDaemonStmLock.agent_node_id == agent_node_id)
            .with_for_update()
            .first()
        )
    if row is None:
        raise RuntimeError("daemon stm row missing")
    return row


def try_acquire_daemon_possession(
    session: Session,
    *,
    agent_node_id: int,
    caller_account_node_id: int,
    transport_session_id: str,
    idle_release_seconds: int,
    username_for_bound: str,
) -> Tuple[bool, Optional[str], AgentDaemonStmLock]:
    row = load_daemon_row_for_update(session, agent_node_id)
    now = datetime.now(timezone.utc)
    holder = row.locked_by_account_node_id
    last = row.last_successful_tick_at

    if holder is not None and int(holder) != int(caller_account_node_id):
        if last is not None and idle_release_seconds > 0:
            age = (now - last).total_seconds()
            if age >= float(idle_release_seconds):
                row.locked_by_account_node_id = None
                row.lock_transport_session_id = None
                row.messages = []
                row.rolling_summary = ""
                row.stm_generation = int(row.stm_generation or 0) + 1
                holder = None
        if row.locked_by_account_node_id is not None and int(row.locked_by_account_node_id) != int(
            caller_account_node_id
        ):
            return False, "该代理正由其他会话使用，请稍后再试。", row

    # Possession holder is committed only after a successful NLP tick (see finalize_daemon_possession_after_success).
    return True, None, row


def finalize_daemon_possession_after_success(
    session: Session,
    row: AgentDaemonStmLock,
    *,
    caller_account_node_id: int,
    transport_session_id: str,
    username_for_bound: str,
) -> None:
    """Record Mode B holder after FrameworkRunResult.ok; bumps possession_generation only when newly held."""
    prev = row.locked_by_account_node_id
    if prev is None:
        row.locked_by_account_node_id = caller_account_node_id
        row.lock_transport_session_id = transport_session_id or row.lock_transport_session_id
        row.bound_username = username_for_bound or row.bound_username
        row.possession_generation = int(row.possession_generation or 0) + 1
        return
    if int(prev) != int(caller_account_node_id):
        row.locked_by_account_node_id = caller_account_node_id
        row.lock_transport_session_id = transport_session_id or row.lock_transport_session_id
        row.bound_username = username_for_bound or row.bound_username
        row.possession_generation = int(row.possession_generation or 0) + 1
        return
    row.lock_transport_session_id = transport_session_id or row.lock_transport_session_id
    if username_for_bound:
        row.bound_username = username_for_bound


def refresh_daemon_success_tick(session: Session, row: AgentDaemonStmLock) -> None:
    row.last_successful_tick_at = datetime.now(timezone.utc)


def append_turns_to_messages(
    messages: List[Dict[str, Any]],
    *,
    user_text: str,
    assistant_text: str,
) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    out = list(messages)
    out.append({"role": "user", "content": user_text, "ts": now})
    out.append({"role": "assistant", "content": assistant_text, "ts": now})
    return out


def touch_thread_metadata(session: Session, thread_id: uuid.UUID, snippet: str) -> None:
    row = session.query(AgentConversationThread).filter(AgentConversationThread.id == thread_id).first()
    if row is None:
        return
    row.last_message_at = datetime.now(timezone.utc)
    if snippet and not (row.title_snippet or "").strip():
        row.title_snippet = snippet[:200]


def release_mode_b_possession_for_transport_session(session: Session, transport_session_id: str) -> int:
    """
    Clear Mode B locks bound to this transport session (SSH / WebSocket CommandContext.session_id).
    Idempotent. Clears in-memory STM blob on those rows (same pattern as idle takeover).
    """
    sid = str(transport_session_id or "").strip()
    if not sid:
        return 0
    rows = (
        session.query(AgentDaemonStmLock)
        .filter(AgentDaemonStmLock.lock_transport_session_id == sid)
        .all()
    )
    n = 0
    for row in rows:
        row.locked_by_account_node_id = None
        row.lock_transport_session_id = None
        row.bound_username = None
        row.messages = []
        row.rolling_summary = ""
        row.stm_generation = int(row.stm_generation or 0) + 1
        n += 1
    if n:
        session.flush()
    return n


def release_mode_b_possession_for_transport_session_if_configured(session: Session, transport_session_id: str) -> int:
    from app.core.config_manager import get_nested_setting

    if not bool(
        get_nested_setting(
            "npc_agent",
            "daemon_possession",
            "possession_release_on_transport_close",
            default=True,
        )
    ):
        return 0
    return release_mode_b_possession_for_transport_session(session, transport_session_id)


def list_threads_for_owner_agent(
    session: Session,
    *,
    owner_account_node_id: int,
    agent_node_id: int,
    limit: int = 32,
) -> List[AgentConversationThread]:
    return (
        session.query(AgentConversationThread)
        .filter(
            AgentConversationThread.owner_account_node_id == owner_account_node_id,
            AgentConversationThread.agent_node_id == agent_node_id,
        )
        .order_by(AgentConversationThread.last_message_at.desc())
        .limit(limit)
        .all()
    )
