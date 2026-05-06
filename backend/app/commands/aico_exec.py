"""Shared `aico` / `@aico` execution (F13): argv routing, list/history/delete, REPL flag."""

from __future__ import annotations

import time
import uuid as uuid_mod
from typing import Any, Dict, List, Optional, Tuple

from app.commands.base import CommandContext, CommandResult
from app.commands.npc_agent_nlp import assistant_nlp_command_result, run_npc_agent_nlp_tick
from app.commands.npc_agent_resolve import resolve_npc_agent_by_handle
from app.game_engine.agent_runtime.command_caller_graph import resolve_caller_node_id
from app.game_engine.agent_runtime.conversation_stm_service import (
    aggregate_stm_messages_for_thread,
    clear_conversation_thread_for_transport,
    delete_conversation_thread_for_owner,
    list_threads_for_owner_agent,
    persist_conversation_thread_for_transport,
    set_thread_id_on_context,
)
from app.models.system import AgentConversationThread

# F13: SSHHandler._attach_aico_stream_context reads this from command_ephemeral (D8).
AICO_STREAM_EPHEMERAL_KEY = "supports_aico_stream"
AICO_DELETE_PENDING_KEY = "aico_delete_pending"
AICO_DELETE_TTL_SEC = 120.0

AICO_USAGE_LINE = (
    "aico [-i [text...]] | [-l [-a]] | [-his <uuid> [-a]] | [-d <uuid>|confirm] | "
    "[-nd [text...]] | [-cd <uuid>] | <message...>"
)


def _ensure_command_ephemeral(context: CommandContext) -> Optional[Dict[str, Any]]:
    sess = context.session
    if sess is None:
        return None
    ep = getattr(sess, "command_ephemeral", None)
    if not isinstance(ep, dict):
        ep = {}
        try:
            setattr(sess, "command_ephemeral", ep)
        except Exception:
            return None
    return ep


def take_last_n_rounds(messages: List[Dict[str, Any]], n_rounds: int) -> List[Dict[str, Any]]:
    """Keep last n_rounds dialogue rounds (user + optional following assistant)."""
    if n_rounds <= 0:
        return []
    rounds: List[List[Dict[str, Any]]] = []
    i = 0
    while i < len(messages):
        role = str(messages[i].get("role") or "").lower()
        if role == "user":
            block = [messages[i]]
            if i + 1 < len(messages) and str(messages[i + 1].get("role") or "").lower() == "assistant":
                block.append(messages[i + 1])
                i += 2
            else:
                i += 1
            rounds.append(block)
        else:
            rounds.append([messages[i]])
            i += 1
    tail = rounds[-n_rounds:] if rounds else []
    out: List[Dict[str, Any]] = []
    for b in tail:
        out.extend(b)
    return out


def _format_history_messages(messages: List[Dict[str, Any]]) -> str:
    lines = []
    for m in messages:
        role = str(m.get("role") or "?").upper()
        content = str(m.get("content") or "").strip()
        lines.append(f"[{role}] {content}")
    return "\n".join(lines) if lines else "(empty transcript)"


def _format_aico_thread_table(rows: List[AgentConversationThread]) -> Tuple[str, List[Dict[str, Any]]]:
    lines = [
        f"{'thread_id':<40} {'title':<32} {'last_message_at':<28}",
        "-" * 104,
    ]
    items: List[Dict[str, Any]] = []
    for r in rows:
        tid = str(r.id)
        title = ((r.title_snippet or "").strip() or "(untitled)")[:32]
        lma = ""
        if r.last_message_at is not None:
            try:
                lma = r.last_message_at.isoformat()[:28]
            except Exception:
                lma = str(r.last_message_at)[:28]
        lines.append(f"{tid:<40} {title:<32} {lma:<28}")
        items.append({"thread_id": tid, "title": title.strip(), "last_message_at": lma})
    lines.append("")
    lines.append(f"(total={len(rows)})")
    return "\n".join(lines), items


def _resolve_aico_node(context: CommandContext):
    node, rerr = resolve_npc_agent_by_handle(context.db_session, "aico")
    if rerr:
        return None, rerr
    attrs = node.attributes or {}
    if str(attrs.get("decision_mode", "")).lower() != "llm":
        return None, "aico requires decision_mode=llm on the agent node"
    return node, None


def _aico_delete_confirm(context: CommandContext, node, cid: int) -> CommandResult:
    ep = _ensure_command_ephemeral(context)
    if ep is None:
        return CommandResult.error_result("session storage required for delete confirmation")
    pending = ep.get(AICO_DELETE_PENDING_KEY)
    now = time.time()
    if not isinstance(pending, dict):
        return CommandResult.error_result("no pending thread deletion; run: aico -d <thread_uuid>")
    exp = float(pending.get("expires_at") or 0)
    if now > exp:
        ep.pop(AICO_DELETE_PENDING_KEY, None)
        return CommandResult.error_result("delete confirmation expired; run: aico -d <thread_uuid> again")
    if int(pending.get("agent_node_id") or 0) != int(node.id):
        return CommandResult.error_result("pending delete does not match this assistant")
    try:
        tid = uuid_mod.UUID(str(pending.get("thread_id") or "").strip())
    except Exception:
        ep.pop(AICO_DELETE_PENDING_KEY, None)
        return CommandResult.error_result("invalid pending thread id")

    ok = delete_conversation_thread_for_owner(
        context.db_session,
        owner_account_node_id=cid,
        agent_node_id=node.id,
        thread_id=tid,
    )
    if not ok:
        ep.pop(AICO_DELETE_PENDING_KEY, None)
        context.db_session.commit()
        return CommandResult.error_result("thread not found or already deleted")

    ep.pop(AICO_DELETE_PENDING_KEY, None)
    clear_conversation_thread_for_transport(context, node.id)
    md = context.metadata or {}
    cur = md.get("conversation_thread_id")
    if cur is not None and str(cur).strip() == str(tid):
        md.pop("conversation_thread_id", None)

    context.db_session.commit()
    return CommandResult.success_result(f"Deleted conversation thread {tid}.")


def execute_aico_command(context: CommandContext, args: List[str]) -> CommandResult:
    """Single entry for `aico ...` and `@aico ...` argv (after handle stripped)."""
    if not args:
        return CommandResult.error_result("usage: " + AICO_USAGE_LINE)
    if not context.db_session:
        return CommandResult.error_result("database session required")

    node, rerr = _resolve_aico_node(context)
    if rerr:
        return CommandResult.error_result(rerr)
    attrs = node.attributes or {}
    sid = str(attrs.get("service_id") or "aico")

    cid = resolve_caller_node_id(context.db_session, context)
    if cid is None:
        return CommandResult.error_result("cannot resolve caller account")

    # --- list ---
    if args[0] == "-l":
        want_all = len(args) > 1 and args[1] == "-a"
        limit = None if want_all else 8
        rows = list_threads_for_owner_agent(
            context.db_session,
            owner_account_node_id=cid,
            agent_node_id=node.id,
            limit=limit,
        )
        if not rows:
            return CommandResult.success_result("(no conversation threads yet)", data={"items": [], "total": 0})
        msg, items = _format_aico_thread_table(rows)
        return CommandResult.success_result(msg, data={"items": items, "total": len(rows)})

    # --- history ---
    if args[0] == "-his":
        if len(args) < 2:
            return CommandResult.error_result("usage: aico -his <uuid> [-a]")
        try:
            hid = uuid_mod.UUID(str(args[1]).strip())
        except Exception:
            return CommandResult.error_result("invalid thread uuid")
        want_all = len(args) > 2 and "-a" in args[2:]
        thr = (
            context.db_session.query(AgentConversationThread)
            .filter(
                AgentConversationThread.id == hid,
                AgentConversationThread.owner_account_node_id == cid,
                AgentConversationThread.agent_node_id == node.id,
            )
            .first()
        )
        if thr is None:
            return CommandResult.error_result("thread not found")
        msgs = aggregate_stm_messages_for_thread(
            context.db_session,
            owner_account_node_id=cid,
            agent_node_id=node.id,
            conversation_thread_id=hid,
        )
        if not want_all:
            msgs = take_last_n_rounds(msgs, 8)
        body = _format_history_messages(msgs)
        return CommandResult.success_result(body, data={"thread_id": str(hid), "truncated": not want_all})

    # --- delete ---
    if args[0] == "-d":
        if len(args) < 2:
            return CommandResult.error_result("usage: aico -d <uuid>  OR  aico -d confirm")
        if str(args[1]).strip().lower() == "confirm":
            return _aico_delete_confirm(context, node, cid)
        try:
            did = uuid_mod.UUID(str(args[1]).strip())
        except Exception:
            return CommandResult.error_result("invalid thread uuid")
        row = (
            context.db_session.query(AgentConversationThread)
            .filter(
                AgentConversationThread.id == did,
                AgentConversationThread.owner_account_node_id == cid,
                AgentConversationThread.agent_node_id == node.id,
            )
            .first()
        )
        if row is None:
            return CommandResult.error_result("thread not found")
        ep = _ensure_command_ephemeral(context)
        if ep is None:
            return CommandResult.error_result("session storage required for delete confirmation")
        ep[AICO_DELETE_PENDING_KEY] = {
            "thread_id": str(did),
            "agent_node_id": int(node.id),
            "expires_at": time.time() + AICO_DELETE_TTL_SEC,
        }
        context.db_session.commit()
        return CommandResult.success_result(
            "Pending deletion for this thread. To confirm, run: aico -d confirm\n"
            "(confirmation expires in about two minutes.)"
        )

    # --- continue ---
    if args[0] == "-cd":
        if len(args) < 2:
            return CommandResult.error_result("usage: aico -cd <conversation_thread_uuid>")
        try:
            tid = uuid_mod.UUID(str(args[1]).strip())
        except Exception:
            return CommandResult.error_result("invalid thread uuid")
        row = (
            context.db_session.query(AgentConversationThread)
            .filter(
                AgentConversationThread.id == tid,
                AgentConversationThread.owner_account_node_id == cid,
                AgentConversationThread.agent_node_id == node.id,
            )
            .first()
        )
        if row is None:
            return CommandResult.error_result("thread not found")
        set_thread_id_on_context(context, tid)
        persist_conversation_thread_for_transport(context, node.id, tid)
        context.db_session.commit()
        return CommandResult.success_result(f"Switched to thread {tid}.")

    # --- new thread ---
    if args[0] == "-nd":
        if context.metadata is None:
            context.metadata = {}
        context.metadata.pop("conversation_thread_id", None)
        clear_conversation_thread_for_transport(context, node.id)
        rest = args[1:]
        if not rest:
            context.db_session.commit()
            return CommandResult.success_result("New dialogue thread started. Send: aico <message>")
        message = " ".join(rest).strip()
        if len(message) >= 2 and message[0] == message[-1] and message[0] in "'\"":
            message = message[1:-1].strip()
        res = run_npc_agent_nlp_tick(context.db_session, node, context, message)
        context.db_session.commit()
        return assistant_nlp_command_result("aico", res, service_id=sid, context=context)

    # --- interactive REPL (SSH: session.nested_repl + console delegates I/O) ---
    if args[0] == "-i":
        if context.session is None:
            return CommandResult.error_result("interactive mode requires a session (e.g. SSH)")
        from app.ssh.nested_repl.aico_repl import AicoNestedReplDriver

        context.session.nested_repl = AicoNestedReplDriver()
        rest = args[1:]
        hud_tid = ""
        md = context.metadata or {}
        raw_tid = md.get("conversation_thread_id")
        if raw_tid:
            hud_tid = str(raw_tid).strip()
        title = ""
        if hud_tid:
            try:
                u = uuid_mod.UUID(hud_tid)
                tr = (
                    context.db_session.query(AgentConversationThread)
                    .filter(
                        AgentConversationThread.id == u,
                        AgentConversationThread.owner_account_node_id == cid,
                        AgentConversationThread.agent_node_id == node.id,
                    )
                    .first()
                )
                if tr and (tr.title_snippet or "").strip():
                    title = (tr.title_snippet or "").strip()[:80]
            except Exception:
                pass
        lines = [
            "AICO interactive mode (SSH). Ctrl+Q exits; Ctrl+C cancels current reply.",
            f"thread_id: {hud_tid or '(implicit until first message)'}",
        ]
        if title:
            lines.append(f"title: {title}")
        lines.append("End input with Enter. Prefix shell commands with ! (e.g. !help).")
        msg = "\n".join(lines)
        if rest:
            message = " ".join(rest).strip()
            if len(message) >= 2 and message[0] == message[-1] and message[0] in "'\"":
                message = message[1:-1].strip()
            if message:
                res = run_npc_agent_nlp_tick(context.db_session, node, context, message)
                context.db_session.commit()
                open_txt = assistant_nlp_command_result("aico", res, service_id=sid, context=context).message
                return CommandResult.success_result(msg + "\n\n" + open_txt, data={"aico_repl": True})
        context.db_session.commit()
        return CommandResult.success_result(msg, data={"aico_repl": True})

    message = " ".join(args).strip()
    res = run_npc_agent_nlp_tick(context.db_session, node, context, message)
    context.db_session.commit()
    return assistant_nlp_command_result("aico", res, service_id=sid, context=context)
