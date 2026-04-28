"""Tests for ToolRuntimeView / resolve_tool_runtime_view (ADR-F10)."""

from __future__ import annotations

import pytest

from app.commands.base import CommandContext
from app.game_engine.agent_runtime.resolved_tool_surface import PreauthorizedToolExecutor, ResolvedToolSurface
from app.game_engine.agent_runtime.tool_gather import ToolGatherBudgets, ToolGatherCounters
from app.game_engine.agent_runtime.tool_runtime_view import resolve_tool_runtime_view


@pytest.mark.unit
def test_resolve_view_missing_executor():
    ctx = CommandContext(user_id="1", username="u", session_id="s", permissions=[], roles=[])
    v = resolve_tool_runtime_view(
        pre_tool=None,
        tool_command_context=ctx,
        budgets=ToolGatherBudgets(),
        counters=ToolGatherCounters(),
    )
    assert v.can_execute is False
    assert v.reason == "missing_executor"


@pytest.mark.unit
def test_resolve_view_missing_tool_context():
    ctx = CommandContext(user_id="1", username="u", session_id="s", permissions=[], roles=[])
    surface = ResolvedToolSurface(allowed_command_names=frozenset(), tool_command_context=ctx)
    pre = PreauthorizedToolExecutor(surface)
    v = resolve_tool_runtime_view(
        pre_tool=pre,
        tool_command_context=None,
        budgets=ToolGatherBudgets(),
        counters=ToolGatherCounters(),
    )
    assert v.can_execute is False
    assert v.reason == "missing_tool_context"


@pytest.mark.unit
def test_resolve_view_tick_command_budget_exhausted():
    ctx = CommandContext(user_id="1", username="u", session_id="s", permissions=[], roles=[])
    surface = ResolvedToolSurface(allowed_command_names=frozenset(), tool_command_context=ctx)
    pre = PreauthorizedToolExecutor(surface)
    budgets = ToolGatherBudgets(max_commands_per_tick=2)
    counters = ToolGatherCounters(commands_run=2, observation_chars=0)
    v = resolve_tool_runtime_view(
        pre_tool=pre,
        tool_command_context=ctx,
        budgets=budgets,
        counters=counters,
    )
    assert v.can_execute is False
    assert v.reason == "tick_command_budget_exhausted"


@pytest.mark.unit
def test_resolve_view_tick_char_budget_exhausted():
    ctx = CommandContext(user_id="1", username="u", session_id="s", permissions=[], roles=[])
    surface = ResolvedToolSurface(allowed_command_names=frozenset(), tool_command_context=ctx)
    pre = PreauthorizedToolExecutor(surface)
    budgets = ToolGatherBudgets(max_chars_observations_per_tick=100)
    counters = ToolGatherCounters(commands_run=0, observation_chars=100)
    v = resolve_tool_runtime_view(
        pre_tool=pre,
        tool_command_context=ctx,
        budgets=budgets,
        counters=counters,
    )
    assert v.can_execute is False
    assert v.reason == "tick_char_budget_exhausted"


@pytest.mark.unit
def test_resolve_view_ok_when_under_caps():
    ctx = CommandContext(user_id="1", username="u", session_id="s", permissions=[], roles=[])
    surface = ResolvedToolSurface(allowed_command_names=frozenset(), tool_command_context=ctx)
    pre = PreauthorizedToolExecutor(surface)
    budgets = ToolGatherBudgets()
    counters = ToolGatherCounters()
    v = resolve_tool_runtime_view(
        pre_tool=pre,
        tool_command_context=ctx,
        budgets=budgets,
        counters=counters,
    )
    assert v.can_execute is True
    assert v.reason == ""
    assert v.executor is pre
    assert v.tool_context is ctx
