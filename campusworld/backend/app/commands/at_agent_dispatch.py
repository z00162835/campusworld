"""
F04: dispatch `@<handle> <payload>` to npc_agent NLP tick (same semantics as agent_nlp).
"""

from __future__ import annotations

from typing import Optional

from app.commands.base import CommandContext, CommandResult
from app.commands.npc_agent_resolve import resolve_npc_agent_by_handle
from app.commands.npc_agent_nlp import format_nlp_tick_result, run_npc_agent_nlp_tick
from app.commands.registry import command_registry
from app.commands.shell_words import split_command_line


def try_dispatch_at_line(command_line: str, context: CommandContext) -> Optional[CommandResult]:
    """
    If line starts with `@`, parse handle and payload and run LLM+PDCA tick for that service_id.
    Returns None if the line is not an @-agent line (caller continues normal command routing).
    """
    line = (command_line or "").strip()
    if not line.startswith("@"):
        return None
    rest = line[1:].strip()
    if not rest:
        return CommandResult.error_result(
            "usage: @<handle> <message>. Type 'help' for available commands."
        )
    parts = split_command_line(rest)
    handle = parts[0].lower()
    message = " ".join(parts[1:]).strip() if len(parts) > 1 else ""
    if not message:
        return CommandResult.error_result(
            "usage: @<handle> <message>. Type 'help' for available commands."
        )

    ref = command_registry.get_command("agent_nlp")
    if ref:
        decision = command_registry.authorize_command(ref, context)
        if not decision.allowed:
            return CommandResult.error_result(
                "Permission denied for @ agent. Type 'help' for available commands."
            )

    if not context.db_session:
        return CommandResult.error_result(
            "database session required. Type 'help' for available commands."
        )

    node, rerr = resolve_npc_agent_by_handle(context.db_session, handle)
    if rerr:
        return CommandResult.error_result(rerr)
    attrs = node.attributes or {}
    if str(attrs.get("decision_mode", "")).lower() != "llm":
        return CommandResult.error_result("@ agent requires decision_mode=llm on the agent node")

    res = run_npc_agent_nlp_tick(context.db_session, node, context, message)
    context.db_session.commit()
    return CommandResult.success_result(format_nlp_tick_result(res))
