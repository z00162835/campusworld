from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from app.commands.base import CommandContext, CommandResult
from app.commands.registry import command_registry


class ToolExecutor(Protocol):
    """Dispatches allowlisted tools — typically wraps CommandRegistry."""

    def list_tool_ids(
        self,
        context: CommandContext,
        allowlist: Optional[List[str]] = None,
    ) -> List[str]:
        ...

    def execute_command(
        self,
        context: CommandContext,
        command_name: str,
        args: List[str],
    ) -> CommandResult:
        ...


@dataclass
class RegistryToolExecutor:
    """Command-registry backed executor (F02 default)."""

    def list_tool_ids(
        self,
        context: CommandContext,
        allowlist: Optional[List[str]] = None,
    ) -> List[str]:
        available = command_registry.get_available_commands(context)
        names = sorted(c.name for c in available)
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
        cmd = command_registry.get_command(command_name)
        if cmd is None:
            return CommandResult.error_result(f"unknown command: {command_name}")
        decision = command_registry.authorize_command(cmd, context)
        if not decision.allowed:
            return CommandResult.error_result(
                f"command not authorized: {command_name} ({decision.reason})"
            )
        return cmd.execute(context, args)


@dataclass
class ToolRouter:
    """Resolves tool ids from agent node allowlist (F02 §10)."""

    allowlist: List[str] = field(default_factory=list)

    def filter(self, all_ids: List[str]) -> List[str]:
        if not self.allowlist:
            return list(all_ids)
        return [i for i in all_ids if i in self.allowlist]
