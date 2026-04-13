"""Agent-facing commands: capabilities, tools, worker tick, NLP assistant, and agent directory."""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.commands.agent_command_context import command_context_for_npc_agent
from app.commands.base import CommandContext, CommandResult, SystemCommand
from app.commands.registry import command_registry
from app.commands.npc_agent_resolve import (
    enabled_allows,
    normalize_handle,
    resolve_npc_agent_by_handle,
)
from app.models.graph import Node, NodeType
from app.models.system import AgentRunRecord

# Unified user-facing message when status lookup must not distinguish missing vs inaccessible agents.
AGENT_STATUS_ACCESS_ERROR = "agent not found or not accessible"


def derive_agent_status(node: Node, session: Session) -> str:
    """Return agent row status: unavailable | idle | working (from node attributes and run records)."""
    if not node.is_active:
        return "unavailable"
    attrs = dict(node.attributes or {})
    if not enabled_allows(attrs):
        return "unavailable"
    running = (
        session.query(AgentRunRecord)
        .filter(
            AgentRunRecord.agent_node_id == node.id,
            AgentRunRecord.ended_at.is_(None),
            AgentRunRecord.status == "running",
        )
        .first()
    )
    if running is not None:
        return "working"
    return "idle"


def _service_id_display(node: Node) -> str:
    attrs = dict(node.attributes or {})
    raw = str(attrs.get("service_id") or "").strip()
    return raw or str(node.id)


def _query_active_npc_agent_nodes(session: Session) -> List[Node]:
    return (
        session.query(Node)
        .filter(
            Node.type_code == "npc_agent",
            Node.is_active == True,  # noqa: E712
        )
        .order_by(Node.id)
        .all()
    )


def _find_npc_agent_nodes_by_handle(session: Session, handle: str) -> List[Node]:
    """Match service_id or handle_aliases (same as resolve); includes disabled agents."""
    h = normalize_handle(handle)
    if not h:
        return []
    matches: List[Node] = []
    seen: set[int] = set()
    for n in _query_active_npc_agent_nodes(session):
        attrs = dict(n.attributes or {})
        sid = str(attrs.get("service_id") or "").strip().lower()
        matched = sid == h
        if not matched:
            raw = attrs.get("handle_aliases")
            if isinstance(raw, list):
                for a in raw:
                    if str(a).strip().lower() == h:
                        matched = True
                        break
        if matched:
            if n.id not in seen:
                seen.add(n.id)
                matches.append(n)
    return matches


def _agent_row_dict(node: Node, session: Session) -> Dict[str, Any]:
    return {
        "service_id": _service_id_display(node),
        "name": node.name or "",
        "status": derive_agent_status(node, session),
        "agent_node_id": node.id,
    }


class AgentCapabilitiesCommand(SystemCommand):
    """List static capabilities for an agent instance."""

    def __init__(self):
        super().__init__(
            "agent_capabilities",
            "List agent capabilities for a service_id",
            ["agent.capabilities"],
        )

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("usage: agent_capabilities <service_id>")
        if not context.db_session:
            return CommandResult.error_result("database session required")
        sid = args[0]
        node, rerr = resolve_npc_agent_by_handle(context.db_session, sid)
        if rerr:
            return CommandResult.error_result(rerr)
        nt = context.db_session.query(NodeType).filter(NodeType.id == node.type_id).first()
        typeclass = nt.typeclass if nt else None
        data = {
            "service_id": sid,
            "agent_node_id": node.id,
            "typeclass": typeclass,
            "decision_mode": (node.attributes or {}).get("decision_mode"),
            "cognition": (node.attributes or {}).get("cognition_profile_ref"),
            "capabilities": [
                "command.execute",
                "agent.memory",
                "agent.run.pdca",
                "agent.run.nlp",
            ],
        }
        return CommandResult.success_result(json.dumps(data, ensure_ascii=False))


class AgentToolsCommand(SystemCommand):
    """List tools (command names) optionally filtered by allowlist."""

    def __init__(self):
        super().__init__("agent_tools", "List agent tools / registered commands", ["agent.tools"])

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        from app.game_engine.agent_runtime.tooling import RegistryToolExecutor, ToolRouter

        if not args:
            ids = sorted(c.name for c in command_registry.get_available_commands(context))
            return CommandResult.success_result(json.dumps({"tools": ids}, ensure_ascii=False))
        if not context.db_session:
            return CommandResult.error_result("database session required")
        node, rerr = resolve_npc_agent_by_handle(context.db_session, args[0])
        if rerr:
            return CommandResult.error_result(rerr)
        raw = (node.attributes or {}).get("tool_allowlist") or []
        allowlist: List[str] | None = None
        if isinstance(raw, list):
            allowlist = [str(x) for x in raw]
        actx = command_context_for_npc_agent(context.db_session, node, context)
        router = ToolRouter(allowlist=allowlist or [])
        ex = RegistryToolExecutor()
        ids = router.filter(ex.list_tool_ids(actx, allowlist=None))
        return CommandResult.success_result(json.dumps({"tools": ids}, ensure_ascii=False))


class AgentRunCommand(SystemCommand):
    """
    Run one rules-based worker tick for the sample scenario.

    usage: agent_run <service_id> <ticket_id> <severity> <device_node_id>
    """

    def __init__(self):
        super().__init__("agent_run", "Run agent worker tick", [])

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        from app.game_engine.agent_runtime.registry import get_worker_for_typeclass
        from app.game_engine.agent_runtime.worker import SysSampleWorker

        if len(args) < 4:
            return CommandResult.error_result(
                "usage: agent_run <service_id> <ticket_id> <severity> <device_node_id>"
            )
        if not context.db_session:
            return CommandResult.error_result("database session required")
        service_id, ticket_id, severity, device_s = args[0], args[1], args[2], args[3]
        try:
            device_node_id = int(device_s)
        except ValueError:
            return CommandResult.error_result("device_node_id must be integer")
        node, rerr = resolve_npc_agent_by_handle(context.db_session, service_id)
        if rerr:
            return CommandResult.error_result(rerr)
        nt = context.db_session.query(NodeType).filter(NodeType.id == node.type_id).first()
        typeclass = (
            nt.typeclass if nt else "app.models.things.agents.NpcAgent"
        )
        worker_cls = get_worker_for_typeclass(typeclass)
        if worker_cls is not SysSampleWorker:
            return CommandResult.error_result(f"worker {worker_cls.__name__} not supported for agent_run")
        w = SysSampleWorker.create(context.db_session, node.id, invoker_context=context)
        payload = {
            "ticket_id": ticket_id,
            "severity": severity,
            "device_node_id": device_node_id,
        }
        res = w.tick(payload, correlation_id=ticket_id)
        context.db_session.commit()
        return CommandResult.success_result(
            json.dumps({"ok": res.ok, "message": res.message, "phase": res.final_phase}, ensure_ascii=False)
        )


class AgentNlpCommand(SystemCommand):
    """
    Run one NLP assistant tick.

    usage: agent_nlp <service_id> <message...>
    """

    def __init__(self):
        super().__init__("agent_nlp", "Run NLP assistant tick", [])

    def get_usage(self) -> str:
        return "agent_nlp <service_id> <message...>"

    def _get_specific_help(self) -> str:
        return (
            "\nSame semantics as line-prefix assistant dispatch when configured.\n"
        )

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        from app.commands.npc_agent_nlp import format_nlp_tick_result, run_npc_agent_nlp_tick

        if len(args) < 2:
            return CommandResult.error_result("usage: agent_nlp <service_id> <message...>")
        if not context.db_session:
            return CommandResult.error_result("database session required")
        service_id, message = args[0], " ".join(args[1:]).strip()
        if not message:
            return CommandResult.error_result("message must not be empty")
        node, rerr = resolve_npc_agent_by_handle(context.db_session, service_id)
        if rerr:
            return CommandResult.error_result(rerr)
        attrs = node.attributes or {}
        if str(attrs.get("decision_mode", "")).lower() != "llm":
            return CommandResult.error_result("agent_nlp requires decision_mode=llm on the agent node")
        res = run_npc_agent_nlp_tick(context.db_session, node, context, message)
        context.db_session.commit()
        return CommandResult.success_result(format_nlp_tick_result(res))


class AicoCommand(SystemCommand):
    """Shorthand for talking to the default assistant AICO."""

    def __init__(self):
        super().__init__("aico", "Talk to default assistant AICO", [])

    def get_usage(self) -> str:
        return "aico <message...>"

    def _get_specific_help(self) -> str:
        return "\nEquivalent to: @aico <message>\n"

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        from app.commands.npc_agent_nlp import format_nlp_tick_result, run_npc_agent_nlp_tick

        if not args:
            return CommandResult.error_result("usage: aico <message...>")
        if not context.db_session:
            return CommandResult.error_result("database session required")
        message = " ".join(args).strip()
        node, rerr = resolve_npc_agent_by_handle(context.db_session, "aico")
        if rerr:
            return CommandResult.error_result(rerr)
        attrs = node.attributes or {}
        if str(attrs.get("decision_mode", "")).lower() != "llm":
            return CommandResult.error_result("aico requires decision_mode=llm on the agent node")
        res = run_npc_agent_nlp_tick(context.db_session, node, context, message)
        context.db_session.commit()
        return CommandResult.success_result(format_nlp_tick_result(res))


class AgentCommand(SystemCommand):
    """
    List visible agents and their status, or query one agent by service id.
    """

    def __init__(self):
        super().__init__(
            "agent",
            "List agents and query status",
            [],
        )

    def get_usage(self) -> str:
        return "agent <list|status> ..."

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not context.db_session:
            return CommandResult.error_result("database session required")
        if not args:
            return CommandResult.error_result(self.get_usage())
        sub = str(args[0]).lower().strip()
        session = context.db_session
        if sub == "list":
            rows = []
            for node in _query_active_npc_agent_nodes(session):
                rows.append(_agent_row_dict(node, session))
            rows.sort(key=lambda r: (r.get("service_id") or "", r.get("name") or ""))
            return CommandResult.success_result(
                json.dumps({"agents": rows}, ensure_ascii=False)
            )
        if sub == "status":
            if len(args) < 2:
                return CommandResult.error_result("usage: agent status <service_id>")
            handle = args[1].strip()
            matches = _find_npc_agent_nodes_by_handle(session, handle)
            if len(matches) != 1:
                return CommandResult.error_result(AGENT_STATUS_ACCESS_ERROR)
            return CommandResult.success_result(
                json.dumps(_agent_row_dict(matches[0], session), ensure_ascii=False)
            )
        return CommandResult.error_result(self.get_usage())


_agent_commands_cache = None
_agent_commands_lock = threading.Lock()


def get_agent_commands() -> List[SystemCommand]:
    """Factory + cache to avoid module-import time command object construction side effects."""
    global _agent_commands_cache
    if _agent_commands_cache is not None:
        return _agent_commands_cache
    with _agent_commands_lock:
        if _agent_commands_cache is None:
            _agent_commands_cache = [
                AgentCapabilitiesCommand(),
                AgentToolsCommand(),
                AgentRunCommand(),
                AgentNlpCommand(),
                AicoCommand(),
                AgentCommand(),
            ]
    return _agent_commands_cache
