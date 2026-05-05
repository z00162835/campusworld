"""Unit tests for ToolGather gate (F10 / ADR-F10)."""

from __future__ import annotations

import pytest

from app.commands.base import CommandContext
from app.game_engine.agent_runtime.resolved_tool_surface import PreauthorizedToolExecutor, ResolvedToolSurface
from app.game_engine.agent_runtime.tool_gather import ToolGatherBudgets, ToolGatherCounters
from app.game_engine.agent_runtime.tool_runtime_view import resolve_tool_runtime_view


def _ctx() -> CommandContext:
    return CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        roles=[],
    )


def _executor(names: tuple[str, ...] = ("help",)) -> PreauthorizedToolExecutor:
    c = _ctx()
    surface = ResolvedToolSurface(
        allowed_command_names=frozenset(names),
        tool_command_context=c,
    )
    return PreauthorizedToolExecutor(surface)


@pytest.mark.unit
def test_resolve_missing_executor() -> None:
    v = resolve_tool_runtime_view(
        pre_tool=None,
        tool_command_context=_ctx(),
        budgets=ToolGatherBudgets(),
        counters=ToolGatherCounters(),
    )
    assert v.can_execute is False
    assert v.reason == "missing_executor"


@pytest.mark.unit
def test_resolve_missing_tool_context() -> None:
    v = resolve_tool_runtime_view(
        pre_tool=_executor(),
        tool_command_context=None,
        budgets=ToolGatherBudgets(),
        counters=ToolGatherCounters(),
    )
    assert v.can_execute is False
    assert v.reason == "missing_tool_context"


@pytest.mark.unit
def test_resolve_tick_command_budget_exhausted() -> None:
    budgets = ToolGatherBudgets(max_commands_per_tick=2)
    counters = ToolGatherCounters(commands_run=2, observation_chars=0)
    ex = _executor()
    ctx = _ctx()
    v = resolve_tool_runtime_view(
        pre_tool=ex,
        tool_command_context=ctx,
        budgets=budgets,
        counters=counters,
    )
    assert v.can_execute is False
    assert v.reason == "tick_command_budget_exhausted"
    assert v.executor is ex
    assert v.tool_context is ctx


@pytest.mark.unit
def test_resolve_tick_char_budget_exhausted() -> None:
    budgets = ToolGatherBudgets(max_chars_observations_per_tick=100)
    counters = ToolGatherCounters(commands_run=0, observation_chars=100)
    v = resolve_tool_runtime_view(
        pre_tool=_executor(),
        tool_command_context=_ctx(),
        budgets=budgets,
        counters=counters,
    )
    assert v.can_execute is False
    assert v.reason == "tick_char_budget_exhausted"


@pytest.mark.unit
def test_resolve_can_execute() -> None:
    ex = _executor()
    ctx = _ctx()
    budgets = ToolGatherBudgets()
    counters = ToolGatherCounters()
    v = resolve_tool_runtime_view(
        pre_tool=ex,
        tool_command_context=ctx,
        budgets=budgets,
        counters=counters,
    )
    assert v.can_execute is True
    assert v.reason == ""
    assert v.executor is ex
    assert v.tool_context is ctx
    assert v.budgets is budgets
