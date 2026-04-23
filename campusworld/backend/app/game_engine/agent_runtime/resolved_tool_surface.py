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


def _normalize_allowlist(entries: Sequence[str]) -> List[str]:
    """Map any allowlist alias to its registered primary command name.

    The node-level ``tool_allowlist`` may reference aliases (e.g.
    ``locate`` for ``find`` or ``ex`` for ``describe``). We normalize to
    primary names so downstream filtering against ``list_tool_ids``
    (which only returns primaries) works regardless of which spelling
    ops wrote into the node attributes.
    """
    out: List[str] = []
    seen: set = set()
    for raw in entries or []:
        name = str(raw).strip().lower()
        if not name:
            continue
        cmd = command_registry.get_command(name)
        primary = cmd.name if cmd is not None else name
        if primary in seen:
            continue
        seen.add(primary)
        out.append(primary)
    return out


def build_resolved_tool_surface(
    *,
    node_tool_allowlist: Sequence[str],
    tool_command_context: CommandContext,
    blocked_names: Optional[FrozenSet[str]] = None,
) -> ResolvedToolSurface:
    """
    Compute once per worker/tick scope: eligible names from registry policy, then node allowlist,
    then remove blocked names (e.g. recursive assistant command).

    Allowlist aliases are normalized to primary command names so ops
    can spell tools by any registered alias (e.g. ``ex`` → ``describe``)
    without breaking surface filtering.
    """
    blocked = blocked_names if blocked_names is not None else DEFAULT_BLOCKED_IN_AGENT_TOOL_CONTEXT
    ex = RegistryToolExecutor()
    policy_names = ex.list_tool_ids(tool_command_context, allowlist=None)
    allow = _normalize_allowlist(node_tool_allowlist or [])
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
        # Resolve alias → primary so that e.g. `locate` or `ex` still
        # routes to `find` / `describe` when only the primary appears on
        # the resolved surface.
        cmd = command_registry.get_command(name)
        primary = cmd.name if cmd is not None else name
        if primary not in self.surface.allowed_command_names:
            return CommandResult.error_result(
                f"command not allowed for agent tools: {command_name}",
                error="not_on_resolved_surface",
            )
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
