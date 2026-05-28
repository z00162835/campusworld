"""Unit tests for tool_gather and resolved_tool_surface (no DB)."""

from __future__ import annotations

import pytest

from app.commands.base import CommandContext, CommandResult
from app.game_engine.agent_runtime.resolved_tool_surface import (
    PreauthorizedToolExecutor,
    ResolvedToolSurface,
    build_resolved_tool_surface,
)
from app.game_engine.agent_runtime.tool_gather import (
    ToolGatherBudgets,
    ToolGatherCounters,
    ToolInvocationPlan,
    format_tool_observation_block,
    gather_tool_observations,
    parse_tool_invocation_plan_from_text,
)
from app.game_engine.agent_runtime.tool_observation_policy import ToolObservationPolicy


class _FakeExec:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def list_tool_ids(self, context, allowlist=None):
        return ["help", "look"]

    def execute_command(self, context, command_name: str, args: list[str]) -> CommandResult:
        self.calls.append((command_name, args))
        return CommandResult.success_result(f"out:{command_name}")


@pytest.mark.unit
def test_parse_tool_plan_multi_command():
    text = """
Some prose
```json
{"commands": [{"name": "help", "args": ["help"]}, {"name": "look", "args": []}]}
```
"""
    plan = parse_tool_invocation_plan_from_text(text)
    assert plan.commands == [("help", ["help"]), ("look", [])]


@pytest.mark.unit
def test_gather_respects_tick_cap():
    fake = _FakeExec()
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        roles=[],
    )
    plan = ToolInvocationPlan(
        commands=[("help", []), ("look", []), ("help", [])],
    )
    budgets = ToolGatherBudgets(max_commands_per_tick=2, max_chars_observations_per_tick=100000, max_commands_per_phase=8)
    counters = ToolGatherCounters()
    text, trace = gather_tool_observations(
        fake, ctx, plan, budgets=budgets, counters=counters, phase_label="plan"
    )
    assert len(fake.calls) == 2
    assert "tick_max_commands" in str(trace[-1])


@pytest.mark.unit
def test_preauthorized_executor_blocks_unknown_and_allows_member():
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        roles=[],
    )
    surface = ResolvedToolSurface(allowed_command_names=frozenset({"help"}), tool_command_context=ctx)
    ex = PreauthorizedToolExecutor(surface)

    class _Cmd:
        name = "help"

        def execute(self, c, args):
            return CommandResult.success_result("hi")

    from unittest.mock import patch

    # Return the fake command only for "help" (matches its primary name);
    # any other lookup returns None so PreauthorizedToolExecutor will see
    # the unregistered command as unknown and reject via the surface check.
    def _lookup(name):
        return _Cmd() if name == "help" else None

    with patch(
        "app.game_engine.agent_runtime.resolved_tool_surface.command_registry.get_command",
        side_effect=_lookup,
    ):
        ok = ex.execute_command(ctx, "help", [])
        bad = ex.execute_command(ctx, "aico", [])
    assert ok.success
    assert not bad.success


@pytest.mark.unit
def test_build_resolved_surface_excludes_aico_when_in_policy():
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        roles=[],
    )

    from unittest.mock import patch

    class _C:
        name = "x"

    with patch(
        "app.game_engine.agent_runtime.resolved_tool_surface.RegistryToolExecutor.list_tool_ids",
        return_value=["help", "aico", "look"],
    ):
        s = build_resolved_tool_surface(node_tool_allowlist=["help", "aico", "look"], tool_command_context=ctx)
    assert "aico" not in s.allowed_command_names
    assert "help" in s.allowed_command_names


@pytest.mark.unit
def test_tool_gather_summarizes_mutating_command_observation():
    class _CreateExec(_FakeExec):
        def execute_command(self, context, command_name: str, args: list[str]) -> CommandResult:
            self.calls.append((command_name, args))
            return CommandResult.success_result("created node\nsecret second line")

    fake = _CreateExec()
    ctx = CommandContext(user_id="1", username="u", session_id="s", permissions=[], roles=[])
    budgets = ToolGatherBudgets(max_commands_per_tick=2, max_chars_observations_per_tick=100000, max_commands_per_phase=8)
    text, trace = gather_tool_observations(
        fake,
        ctx,
        ToolInvocationPlan(commands=[("create", [])]),
        budgets=budgets,
        counters=ToolGatherCounters(),
        phase_label="plan",
    )
    assert "created node" in text
    assert "secret second line" not in text
    assert "original_chars=" in text
    assert trace[0]["observation_message_mode"] == "summary"
    assert "secret second line" not in trace[0]["message_preview"]


@pytest.mark.unit
def test_tool_gather_caches_observation_policy_per_command(monkeypatch):
    calls: list[tuple[str, tuple]] = []

    def fake_policy(command_name, *, args=None, session=None):
        calls.append((command_name, tuple(args or [])))
        return ToolObservationPolicy(message_mode="summary")

    monkeypatch.setattr(
        "app.game_engine.agent_runtime.tool_gather.resolve_tool_observation_policy",
        fake_policy,
    )
    fake = _FakeExec()
    ctx = CommandContext(user_id="1", username="u", session_id="s", permissions=[], roles=[])
    budgets = ToolGatherBudgets(max_commands_per_tick=4, max_chars_observations_per_tick=100000, max_commands_per_phase=8)

    gather_tool_observations(
        fake,
        ctx,
        ToolInvocationPlan(
            commands=[("help", []), ("help", []), ("help", ["again"]), ("look", [])]
        ),
        budgets=budgets,
        counters=ToolGatherCounters(),
        phase_label="plan",
    )

    assert calls == [("help", ()), ("help", ("again",)), ("look", ())]


@pytest.mark.unit
def test_tool_observation_block_can_block_message():
    block = format_tool_observation_block(
        1,
        "create",
        [],
        CommandResult.success_result("sensitive content"),
        policy=ToolObservationPolicy(message_mode="blocked"),
    )
    assert "sensitive content" not in block
    assert "message blocked by observation policy" in block
