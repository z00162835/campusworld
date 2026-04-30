from __future__ import annotations

from app.commands.base import CommandContext, CommandResult
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


def test_execution_gate_allows_document_tool_for_info_intent():
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
    assert d.effective_profile == "document"


def test_preauthorized_executor_blocks_and_reports_guard(monkeypatch):
    class DummyCmd:
        name = "task"

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
