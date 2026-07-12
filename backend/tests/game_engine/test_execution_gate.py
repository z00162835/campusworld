from __future__ import annotations

import pytest

from app.commands.base import CommandContext, CommandResult
from app.commands.init_commands import initialize_commands
from app.game_engine.agent_runtime.execution_gate import evaluate_execution_gate
from app.game_engine.agent_runtime.resolved_tool_surface import (
    PreauthorizedToolExecutor,
    ResolvedToolSurface,
)
from app.game_engine.agent_runtime.tool_gather import (
    ToolGatherBudgets,
    ToolGatherCounters,
    ToolInvocationPlan,
    gather_tool_observations,
)


@pytest.fixture(scope='module', autouse=True)
def _init_commands():
    initialize_commands(force_reinit=True)


def _ctx(meta=None) -> CommandContext:
    return CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        roles=[],
        metadata=dict(meta or {}),
        db_session=None,
    )


def test_execution_gate_blocks_mutate_when_caller_profile_read():
    d = evaluate_execution_gate(
        db_session=None,
        command_name="task",
        args=["create", "--title", "x"],
        context_metadata={
            "agent_interaction_profile": "read",
            "user_message": "请帮我创建任务",
        },
    )
    assert d.allow is False
    assert d.reason_code == "guard_blocked_profile_ceiling"


def test_execution_gate_allows_read_tool_for_info_intent():
    d = evaluate_execution_gate(
        db_session=None,
        command_name="help",
        args=["task"],
        context_metadata={
            "agent_interaction_profile": "read",
            "user_message": "给我一个 task 的例子",
        },
    )
    assert d.allow is True
    assert d.effective_profile == "read"


def test_execution_gate_policy_blocks_write_high_even_with_confirmation(monkeypatch):
    """F16 P1: write_high → require_approval → v1 block, even when confirmed."""
    from app.commands.command_tool_semantics import CommandToolSemantics
    from app.game_engine.agent_runtime import execution_gate as gate_mod

    fake_sem = CommandToolSemantics(
        interaction_profile='mutate',
        side_effect_level='write_high',
        data_classification='internal',
        tool_groups=('mutate',),
    )
    monkeypatch.setattr(
        gate_mod,
        "resolve_command_tool_semantics",
        lambda command_name, args=None: fake_sem,
    )
    d = evaluate_execution_gate(
        db_session=None,
        command_name="task",
        args=["create", "--title", "x"],
        context_metadata={
            "agent_interaction_profile": "mutate",
            "agent_intent": "execute",
            "user_message": "确认执行 create task",
            "confirmed_execute": True,
        },
    )
    assert d.allow is False
    assert d.reason_code == "guard_blocked_policy"
    policy_trace = d.effective_guard.get("policy_decision")
    assert policy_trace is not None
    assert policy_trace["step"] == "policy_decision"
    assert policy_trace["check_point"] == "before_tool_call"
    assert policy_trace["reason_code"] == "policy_blocked_side_effect_write_high"


def test_execution_gate_policy_blocks_data_classification(monkeypatch):
    """F16 P1: data_classification=restricted → block."""
    from app.commands.command_tool_semantics import CommandToolSemantics
    from app.game_engine.agent_runtime import execution_gate as gate_mod

    fake_sem = CommandToolSemantics(
        interaction_profile='read',
        side_effect_level='read',
        data_classification='restricted',
        tool_groups=('read',),
    )
    monkeypatch.setattr(
        gate_mod,
        "resolve_command_tool_semantics",
        lambda command_name, args=None: fake_sem,
    )
    d = evaluate_execution_gate(
        db_session=None,
        command_name="task",
        args=["list"],
        context_metadata={
            "agent_interaction_profile": "read",
            "user_message": "查一下当前任务",
        },
    )
    assert d.allow is False
    assert d.reason_code == "guard_blocked_policy"
    policy_trace = d.effective_guard.get("policy_decision")
    assert policy_trace["reason_code"] == "policy_blocked_data_classification"


def test_execution_gate_policy_passes_for_read_commands():
    """F16 adapter: read commands should pass both legacy gate and PolicyEngine."""
    d = evaluate_execution_gate(
        db_session=None,
        command_name="help",
        args=["look"],
        context_metadata={
            "agent_interaction_profile": "read",
            "user_message": "how do I look around",
        },
    )
    assert d.allow is True
    assert d.reason_code == "guard_pass"
    assert "policy_decision" not in d.effective_guard


def test_execution_gate_allows_task_list_for_verify_intent():
    d = evaluate_execution_gate(
        db_session=None,
        command_name="task",
        args=["list"],
        context_metadata={
            "agent_interaction_profile": "read",
            "user_message": "查一下当前任务",
        },
    )
    assert d.allow is True
    assert d.callee_profile == "read"


def test_execution_gate_allows_notice_list_for_verify_intent():
    d = evaluate_execution_gate(
        db_session=None,
        command_name="notice",
        args=["list"],
        context_metadata={
            "agent_interaction_profile": "read",
            "user_message": "查一下公告列表",
        },
    )
    assert d.allow is True
    assert d.callee_profile == "read"


def test_execution_gate_blocks_notice_publish_without_confirmation():
    d = evaluate_execution_gate(
        db_session=None,
        command_name="notice",
        args=["publish"],
        context_metadata={
            "agent_interaction_profile": "mutate",
            "agent_intent": "execute",
            "user_message": "publish a new notice",
        },
    )
    assert d.allow is False
    assert d.reason_code == "guard_blocked_confirmation"
    assert d.callee_profile == "mutate"


def test_preauthorized_executor_blocks_and_reports_guard(monkeypatch):
    from app.commands.command_tool_semantics import TASK_MUTATE_SEMANTICS

    class DummyCmd:
        name = "task"
        tool_semantics = TASK_MUTATE_SEMANTICS

        def execute(self, context, args):
            return CommandResult.success_result("ok", data={})

    from app.game_engine.agent_runtime import resolved_tool_surface as rts

    monkeypatch.setattr(rts.command_registry, "get_command", lambda _: DummyCmd())
    ex = PreauthorizedToolExecutor(
        surface=ResolvedToolSurface(
            allowed_command_names=frozenset({"task"}),
            tool_command_context=_ctx(),
        )
    )
    res = ex.execute_command(
        _ctx({"agent_interaction_profile": "read", "user_message": "请创建一个任务"}),
        "task",
        ["create", "--title", "x"],
    )
    assert res.success is False
    assert res.error == "guard_blocked_profile_ceiling"


def test_tool_gather_emits_guard_events():
    class FakeExecutor:
        def execute_command(self, context, command_name, args):
            if command_name == "a":
                return CommandResult.error_result("blocked", error="guard_blocked_intent")
            return CommandResult.success_result(
                "ok",
                data={
                    "guard_decision": "guard_pass",
                    "guard_intent": "verify_state",
                    "guard_effective_profile": "read",
                },
            )

    text, entries = gather_tool_observations(
        FakeExecutor(),
        _ctx(),
        ToolInvocationPlan(commands=[("a", []), ("b", [])]),
        budgets=ToolGatherBudgets(),
        counters=ToolGatherCounters(),
        phase_label="plan",
    )
    assert "command=a" in text and "command=b" in text
    assert any(e.get("step") == "guard_block" for e in entries)
    assert any(e.get("step") == "guard_pass" for e in entries)


def test_tool_gather_emits_policy_decision_trace():
    """F16: policy_decision trace entry emitted when a policy block occurs."""
    class FakePolicyExecutor:
        def execute_command(self, context, command_name, args):
            return CommandResult.error_result(
                "blocked by behaviour policy",
                error="guard_blocked_policy",
            )

    # Simulate the data that resolved_tool_surface attaches on policy blocks.
    class FakePolicyExecutorWithData:
        def execute_command(self, context, command_name, args):
            res = CommandResult.error_result(
                "blocked by behaviour policy",
                error="guard_blocked_policy",
            )
            res.data = {
                "guard_decision": "guard_blocked_policy",
                "policy_decision": {
                    "step": "policy_decision",
                    "check_point": "before_tool_call",
                    "decision": "require_approval",
                    "reason_code": "policy_blocked_side_effect_write_high",
                    "runtime_action": "block",
                    "evidence": {"side_effect_level": "write_high"},
                },
            }
            return res

    _, entries = gather_tool_observations(
        FakePolicyExecutorWithData(),
        _ctx(),
        ToolInvocationPlan(commands=[("task", ["create"])]),
        budgets=ToolGatherBudgets(),
        counters=ToolGatherCounters(),
        phase_label="plan",
    )
    policy_entries = [e for e in entries if e.get("step") == "policy_decision"]
    assert len(policy_entries) == 1
    assert policy_entries[0]["check_point"] == "before_tool_call"
    assert policy_entries[0]["reason_code"] == "policy_blocked_side_effect_write_high"
    assert policy_entries[0]["phase"] == "plan"
    assert policy_entries[0]["command_name"] == "task"
