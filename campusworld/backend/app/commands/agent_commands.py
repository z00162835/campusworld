"""
F02 agent commands: capabilities, tools, run (PDCA sample path).
"""

from __future__ import annotations

import json
from typing import List

from app.commands.agent_command_context import command_context_for_npc_agent
from app.commands.base import CommandContext, CommandResult, SystemCommand
from app.commands.registry import command_registry
from app.game_engine.agent_runtime.registry import get_worker_for_typeclass
from app.game_engine.agent_runtime.tooling import RegistryToolExecutor, ToolRouter
from app.commands.npc_agent_nlp import format_nlp_tick_result, run_npc_agent_nlp_tick
from app.game_engine.agent_runtime.worker import SysSampleWorker
from app.models.graph import Node, NodeType


def _find_agent_by_service_id(session, service_id: str) -> Node | None:
    return (
        session.query(Node)
        .filter(
            Node.type_code == "npc_agent",
            Node.attributes["service_id"].astext == service_id,
            Node.is_active == True,  # noqa: E712
        )
        .first()
    )


class AgentCapabilitiesCommand(SystemCommand):
    """List static capabilities for an agent instance (F02 §10)."""

    def __init__(self):
        super().__init__(
            "agent_capabilities",
            "List agent capabilities for a service_id (F02)",
            ["agent.capabilities"],
        )

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("usage: agent_capabilities <service_id>")
        if not context.db_session:
            return CommandResult.error_result("database session required")
        sid = args[0]
        node = _find_agent_by_service_id(context.db_session, sid)
        if node is None:
            return CommandResult.error_result(f"no npc_agent with service_id={sid!r}")
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
        super().__init__("agent_tools", "List agent tools / registered commands (F02)", ["agent.tools"])

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            ids = sorted(c.name for c in command_registry.get_available_commands(context))
            return CommandResult.success_result(json.dumps({"tools": ids}, ensure_ascii=False))
        if not context.db_session:
            return CommandResult.error_result("database session required")
        node = _find_agent_by_service_id(context.db_session, args[0])
        if node is None:
            return CommandResult.error_result(f"no npc_agent with service_id={args[0]!r}")
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
    Run one PDCA tick for sample D (rules, no LLM).

    usage: agent_run <service_id> <ticket_id> <severity> <device_node_id>
    """

    def __init__(self):
        super().__init__("agent_run", "Run agent worker tick (PDCA sample)", [])

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
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
        node = _find_agent_by_service_id(context.db_session, service_id)
        if node is None:
            return CommandResult.error_result(f"no npc_agent with service_id={service_id!r}")
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
    Run one NLP + LLM + PDCA tick for assistants (F03).

    usage: agent_nlp <service_id> <message...>
    """

    def __init__(self):
        super().__init__("agent_nlp", "Run NLP assistant tick (LLM + PDCA)", [])

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if len(args) < 2:
            return CommandResult.error_result("usage: agent_nlp <service_id> <message...>")
        if not context.db_session:
            return CommandResult.error_result("database session required")
        service_id, message = args[0], " ".join(args[1:]).strip()
        if not message:
            return CommandResult.error_result("message must not be empty")
        node = _find_agent_by_service_id(context.db_session, service_id)
        if node is None:
            return CommandResult.error_result(f"no npc_agent with service_id={service_id!r}")
        attrs = node.attributes or {}
        if str(attrs.get("decision_mode", "")).lower() != "llm":
            return CommandResult.error_result("agent_nlp requires decision_mode=llm on the agent node")
        res = run_npc_agent_nlp_tick(context.db_session, node, context, message)
        context.db_session.commit()
        return CommandResult.success_result(format_nlp_tick_result(res))


class AicoCommand(SystemCommand):
    """Shorthand for `@aico` (F04): `aico <message...>`."""

    def __init__(self):
        super().__init__("aico", "Talk to default assistant AICO (same as @aico)", [])

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("usage: aico <message...>")
        if not context.db_session:
            return CommandResult.error_result("database session required")
        message = " ".join(args).strip()
        node = _find_agent_by_service_id(context.db_session, "aico")
        if node is None:
            return CommandResult.error_result("no npc_agent with service_id='aico'")
        attrs = node.attributes or {}
        if str(attrs.get("decision_mode", "")).lower() != "llm":
            return CommandResult.error_result("aico requires decision_mode=llm on the agent node")
        res = run_npc_agent_nlp_tick(context.db_session, node, context, message)
        context.db_session.commit()
        return CommandResult.success_result(format_nlp_tick_result(res))


AGENT_COMMANDS = [
    AgentCapabilitiesCommand(),
    AgentToolsCommand(),
    AgentRunCommand(),
    AgentNlpCommand(),
    AicoCommand(),
]
