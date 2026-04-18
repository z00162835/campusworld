"""Frozen command surface for npc_agent tools (F08 R2): init-time allowlist ∩ policy, runtime execute without re-authorize."""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, List, Optional, Sequence

from app.commands.base import CommandContext, CommandResult
from app.commands.registry import command_registry
from app.game_engine.agent_runtime.tooling import RegistryToolExecutor, ToolExecutor, ToolRouter


# Commands that must not run from inside an agent tool tick (nested NLP / loops).
DEFAULT_BLOCKED_IN_AGENT_TOOL_CONTEXT: FrozenSet[str] = frozenset({"aico"})


@dataclass(frozen=True)
class ResolvedToolSurface:
    """Allowed tool command names after allowlist ∩ get_available_commands, minus safety blocks."""

    allowed_command_names: FrozenSet[str]
    tool_command_context: CommandContext


def build_resolved_tool_surface(
    *,
    node_tool_allowlist: Sequence[str],
    tool_command_context: CommandContext,
    blocked_names: Optional[FrozenSet[str]] = None,
) -> ResolvedToolSurface:
    """
    Compute once per worker/tick scope: eligible names from registry policy, then node allowlist,
    then remove blocked names (e.g. recursive assistant command).
    """
    blocked = blocked_names if blocked_names is not None else DEFAULT_BLOCKED_IN_AGENT_TOOL_CONTEXT
    ex = RegistryToolExecutor()
    policy_names = ex.list_tool_ids(tool_command_context, allowlist=None)
    allow = [str(x) for x in node_tool_allowlist] if node_tool_allowlist else []
    filtered = ToolRouter(allowlist=allow).filter(policy_names)
    allowed: FrozenSet[str] = frozenset(n for n in filtered if n not in blocked)
    return ResolvedToolSurface(allowed_command_names=allowed, tool_command_context=tool_command_context)


@dataclass
class PreauthorizedToolExecutor:
    """
    ToolExecutor that only allows commands in ResolvedToolSurface and skips per-call authorize_command.

    Authorization is equivalent to the intersection computed at surface build time (F08 R2).
    """

    surface: ResolvedToolSurface

    def list_tool_ids(
        self,
        context: CommandContext,
        allowlist: Optional[List[str]] = None,
    ) -> List[str]:
        _ = context
        names = sorted(self.surface.allowed_command_names)
        if allowlist is None:
            return names
        allow = set(allowlist)
        return [n for n in names if n in allow]

    def execute_command(
        self,
        context: CommandContext,
        command_name: str,
        args: List[str],
    ) -> CommandResult:
        name = (command_name or "").strip().lower()
        if name not in self.surface.allowed_command_names:
            return CommandResult.error_result(
                f"command not allowed for agent tools: {command_name}",
                error="not_on_resolved_surface",
            )
        cmd = command_registry.get_command(name)
        if cmd is None:
            return CommandResult.error_result(f"unknown command: {command_name}")
        meta = dict(context.metadata or {})
        meta["agent_tool_invocation"] = True
        ctx = CommandContext(
            user_id=context.user_id,
            username=context.username,
            session_id=context.session_id,
            permissions=list(context.permissions or []),
            roles=list(context.roles or []),
            db_session=context.db_session,
            caller=context.caller,
            game_state=context.game_state,
            metadata=meta,
        )
        return cmd.execute(ctx, args)
