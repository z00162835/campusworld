"""Single gate for whether ToolGather may run in a tick (F10 / ADR-F10)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from app.commands.base import CommandContext
from app.game_engine.agent_runtime.tool_gather import ToolGatherBudgets, ToolGatherCounters

if TYPE_CHECKING:
    from app.game_engine.agent_runtime.resolved_tool_surface import PreauthorizedToolExecutor


@dataclass(frozen=True)
class ToolRuntimeView:
    """Read-only snapshot: may we invoke ``gather_tool_observations`` for this step."""

    can_execute: bool
    reason: str
    executor: Optional["PreauthorizedToolExecutor"]
    tool_context: Optional[CommandContext]
    budgets: ToolGatherBudgets


def resolve_tool_runtime_view(
    *,
    pre_tool: Optional["PreauthorizedToolExecutor"],
    tool_command_context: Optional[CommandContext],
    budgets: ToolGatherBudgets,
    counters: ToolGatherCounters,
) -> ToolRuntimeView:
    """Return a view used by :class:`LlmPDCAFramework` for all tool-gather branches.

    When ``can_execute`` is false, callers must not call ``gather_tool_observations``;
    they may append a ``tool_gather_skip`` trace row instead.
    """
    if pre_tool is None:
        return ToolRuntimeView(False, "missing_executor", None, None, budgets)
    if tool_command_context is None:
        return ToolRuntimeView(False, "missing_tool_context", None, None, budgets)
    if counters.commands_run >= budgets.max_commands_per_tick:
        return ToolRuntimeView(
            False,
            "tick_command_budget_exhausted",
            pre_tool,
            tool_command_context,
            budgets,
        )
    if counters.observation_chars >= budgets.max_chars_observations_per_tick:
        return ToolRuntimeView(
            False,
            "tick_char_budget_exhausted",
            pre_tool,
            tool_command_context,
            budgets,
        )
    return ToolRuntimeView(True, "", pre_tool, tool_command_context, budgets)
