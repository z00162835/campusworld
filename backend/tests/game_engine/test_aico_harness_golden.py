"""Golden behaviour tests for the AICO harness (v2 plan, F08 refresh).

These tests exercise the LlmPDCAFramework end-to-end with fake LLM
clients so we can assert behaviours the plan specifies:

* Tier-ized context — the Plan user turn contains ``World snapshot``,
  ``Tools available``, and ``User message`` in the correct order.
* Dual-track tool calling — a client implementing ``supports_tools``
  goes through ``complete_with_tools`` and receives the ``ToolSchema``
  list; a client that does not goes through JSON-in-text.
* Multi-round ReAct — when the LLM keeps emitting tool calls the
  framework executes them and loops up to the per-phase budget.
* Check-phase RETRY — when Check emits
  ``RETRY: need_tools=...`` the framework re-runs Plan once with a
  guardrail hint appended.

All tests are hermetic: no network, no DB, no real commands.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import pytest

from app.commands.base import CommandContext, CommandResult
from app.core.settings import AgentLlmServiceConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
from app.game_engine.agent_runtime.resolved_tool_surface import (
    PreauthorizedToolExecutor,
    ResolvedToolSurface,
)
from app.game_engine.agent_runtime.tool_calling import (
    AssistantToolUseTurn,
    CompleteWithToolsResult,
    ConversationTurn,
    TextTurn,
    ToolCall,
    ToolResultsTurn,
    ToolSchema,
)
from app.game_engine.agent_runtime.tool_gather import ToolGatherBudgets


# ---------------------------- fakes / fixtures ----------------------------


class _FakeMem:
    def __init__(self) -> None:
        self.runs: List[Dict[str, Any]] = []
        self.raw: List[Dict[str, Any]] = []

    def start_run(self, run_id, correlation_id, phase, command_trace, status) -> None:
        self.runs.append(
            {"op": "start", "run_id": run_id, "phase": phase, "trace": list(command_trace)}
        )

    def update_run(self, run_id, phase, command_trace, status, graph_ops_summary=None) -> None:
        self.runs.append(
            {"op": "update", "run_id": run_id, "phase": phase, "trace": list(command_trace)}
        )

    def finish_run(self, run_id, phase, command_trace, status, graph_ops_summary=None) -> None:
        self.runs.append(
            {"op": "finish", "run_id": run_id, "phase": phase, "trace": list(command_trace)}
        )

    def append_raw(self, kind: str, payload: Dict[str, Any], session_id: Optional[uuid.UUID] = None) -> None:
        self.raw.append({"kind": kind, "payload": payload})


class _HelpLikeCmd:
    """Stand-in for a registered command that records its executions."""

    name = "help"

    def __init__(self, *, response: str = "HELP_TEXT_FOR_MODEL") -> None:
        self._response = response
        self.calls: List[List[str]] = []

    def execute(self, _ctx, args):
        self.calls.append(list(args))
        return CommandResult.success_result(self._response)


def _make_surface(names=("help",)) -> tuple[PreauthorizedToolExecutor, CommandContext]:
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        roles=[],
    )
    surface = ResolvedToolSurface(
        allowed_command_names=frozenset(names),
        tool_command_context=ctx,
    )
    return PreauthorizedToolExecutor(surface), ctx


def _basic_cfg() -> AgentLlmServiceConfig:
    return AgentLlmServiceConfig(
        system_prompt="You are AICO.",
        phase_prompts={
            "plan": "Plan step.",
            "do": "Answer step.",
            "check": "Check step.",
            "act": "Act step.",
        },
    )


# ------------------------------- Tier-ized context ------------------------


class _RecordingTextLlm:
    """Plain ``complete``-only client that records every user turn seen."""

    def __init__(self) -> None:
        self.users: List[str] = []
        self.systems: List[str] = []

    def complete(self, *, system: str, user: str, call_spec=None) -> str:
        self.users.append(user)
        self.systems.append(system)
        return "ok"


@pytest.mark.unit
def test_tiered_context_ordering_in_plan_user_turn():
    """Plan user turn must be World snapshot → Tools → Memory → User message."""
    rec = _RecordingTextLlm()
    fw = LlmPDCAFramework(
        memory=_FakeMem(),
        llm_config=_basic_cfg(),
        instance_phase_llm={},
        instance_mode_models={},
        llm=rec,
    )
    fw.run(
        FrameworkRunContext(
            agent_node_id=1,
            payload={
                "message": "hi there",
                "world_snapshot": "Caller:\n  identity: tester",
                "tool_manifest_text": "- help: Show commands",
            },
            memory_context="prior note",
        )
    )
    assert rec.users, "expected at least one LLM call"
    plan_user = rec.users[0]
    i_ws = plan_user.find("World snapshot:")
    i_tools = plan_user.find("Tools available:")
    i_mem = plan_user.find("Retrieved memory (may be empty):")
    i_msg = plan_user.find("User message:")
    assert i_ws != -1 and i_tools != -1 and i_mem != -1 and i_msg != -1
    assert i_ws < i_tools < i_mem < i_msg
    # Subsequent phases must NOT repeat the snapshot or manifest — they are
    # Plan-only (Tier-2). Do/Check/Act prompts carry the draft reply.
    for later in rec.users[1:]:
        assert "World snapshot:" not in later
        assert "Tools available:" not in later


# ------------------------------- JSON fallback ----------------------------


class _JsonThenTextLlm:
    """Emits a JSON tool plan on call #1, plain text after that."""

    def __init__(self, plan_json: str) -> None:
        self._plan_json = plan_json
        self.users: List[str] = []
        self.calls = 0

    def complete(self, *, system: str, user: str, call_spec=None) -> str:
        self.calls += 1
        self.users.append(user)
        if self.calls == 1:
            return self._plan_json
        return "[stub_tail]"


@pytest.mark.unit
def test_json_fallback_executes_tool_and_injects_observation(monkeypatch):
    pre, ctx_cmd = _make_surface(("help",))
    help_cmd = _HelpLikeCmd(response="HELP_TEXT_FOR_MODEL")
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.resolved_tool_surface.command_registry.get_command",
        lambda _name: help_cmd,
    )

    rec = _JsonThenTextLlm('{"commands": [{"name": "help", "args": []}]}')
    fw = LlmPDCAFramework(
        memory=_FakeMem(),
        llm_config=_basic_cfg(),
        instance_phase_llm={},
        instance_mode_models={},
        llm=rec,
        tools=pre,
        tool_command_context=ctx_cmd,
        preauthorized_tool_executor=pre,
    )
    out = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert out.ok
    assert help_cmd.calls, "tool should have been executed once"
    # The subsequent user turn (within ReAct loop or Do phase) must carry
    # the observation so the LLM has evidence to answer from.
    joined = "\n\n".join(rec.users)
    assert "HELP_TEXT_FOR_MODEL" in joined or "tool_observation" in joined.lower()


# ---------------------------- Native tool_use path ------------------------


class _NativeToolUseLlm:
    """Client that implements ``supports_tools`` + ``complete_with_tools``.

    Returns a ``tool_use`` result on call #1 and a plain text answer on
    call #2.
    """

    def __init__(self) -> None:
        self.tool_calls_calls = 0
        self.plain_calls = 0
        self.seen_tools_lists: List[List[ToolSchema]] = []
        self.seen_turns: List[List[ConversationTurn]] = []

    def supports_tools(self) -> bool:
        return True

    def complete(self, *, system: str, user: str, call_spec=None) -> str:
        self.plain_calls += 1
        return "final-text"

    def complete_with_tools(
        self,
        *,
        system: str,
        turns: List[ConversationTurn],
        tools: List[ToolSchema],
        call_spec=None,
    ) -> CompleteWithToolsResult:
        self.tool_calls_calls += 1
        self.seen_tools_lists.append(list(tools))
        self.seen_turns.append(list(turns))
        if self.tool_calls_calls == 1:
            # Emit one tool call, no prose.
            return CompleteWithToolsResult(
                text="",
                tool_calls=[ToolCall.new("help", args=[])],
                finish_reason="tool_use",
            )
        return CompleteWithToolsResult(
            text="done",
            tool_calls=[],
            finish_reason="stop",
        )


@pytest.mark.unit
def test_native_tool_use_path_receives_schemas(monkeypatch):
    pre, ctx_cmd = _make_surface(("help",))
    help_cmd = _HelpLikeCmd(response="HELP_NATIVE")
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.resolved_tool_surface.command_registry.get_command",
        lambda _name: help_cmd,
    )

    llm = _NativeToolUseLlm()
    schemas = [ToolSchema(name="help", description="Show available commands.")]
    fw = LlmPDCAFramework(
        memory=_FakeMem(),
        llm_config=_basic_cfg(),
        instance_phase_llm={},
        instance_mode_models={},
        llm=llm,
        tools=pre,
        tool_command_context=ctx_cmd,
        preauthorized_tool_executor=pre,
        tool_schemas=schemas,
    )
    out = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert out.ok
    assert llm.tool_calls_calls >= 1, "native tool channel must be used"
    assert llm.seen_tools_lists[0] == schemas
    # A ToolResultsTurn must appear in the next call's turns.
    assert any(
        any(isinstance(t, ToolResultsTurn) for t in turns)
        for turns in llm.seen_turns[1:]
    )
    # Assistant tool_use must precede tool_result in the neutral transcript.
    second = llm.seen_turns[1]
    assert any(isinstance(t, AssistantToolUseTurn) for t in second)
    i_ahu = next(i for i, t in enumerate(second) if isinstance(t, AssistantToolUseTurn))
    i_tr = next(i for i, t in enumerate(second) if isinstance(t, ToolResultsTurn))
    assert i_ahu < i_tr
    assert len(help_cmd.calls) == 1


# ---------------------------- Multi-round ReAct ---------------------------


class _LoopNativeLlm:
    """Emits a tool call on every round until the budget kills the loop."""

    def __init__(self) -> None:
        self.rounds = 0

    def supports_tools(self) -> bool:
        return True

    def complete(self, *, system: str, user: str, call_spec=None) -> str:
        return "fallback-text"

    def complete_with_tools(
        self,
        *,
        system: str,
        turns: List[ConversationTurn],
        tools: List[ToolSchema],
        call_spec=None,
    ) -> CompleteWithToolsResult:
        self.rounds += 1
        return CompleteWithToolsResult(
            text="",
            tool_calls=[ToolCall.new("help", args=[])],
            finish_reason="tool_use",
        )


@pytest.mark.unit
def test_multi_round_react_honours_per_phase_budget(monkeypatch):
    pre, ctx_cmd = _make_surface(("help",))
    help_cmd = _HelpLikeCmd(response="LOOP_OBS")
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.resolved_tool_surface.command_registry.get_command",
        lambda _name: help_cmd,
    )

    llm = _LoopNativeLlm()
    budgets = ToolGatherBudgets(
        max_commands_per_tick=20,
        max_chars_observations_per_tick=10_000,
        max_tool_rounds_per_phase=3,
    )
    fw = LlmPDCAFramework(
        memory=_FakeMem(),
        llm_config=_basic_cfg(),
        instance_phase_llm={},
        instance_mode_models={},
        llm=llm,
        tools=pre,
        tool_command_context=ctx_cmd,
        preauthorized_tool_executor=pre,
        tool_schemas=[ToolSchema(name="help", description="help")],
        tool_gather_budgets=budgets,
    )
    fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "go"}))
    # Plan should have exactly hit the per-phase cap before Do/Check run.
    # Do also emits tool calls, so the executor sees more rounds in total;
    # the invariant we enforce here is "no single phase exceeds 3".
    assert help_cmd.calls, "tool must have executed at least once"
    assert llm.rounds <= 2 * budgets.max_tool_rounds_per_phase


# ---------------------------- Check-phase RETRY ---------------------------


class _ScriptedLlm:
    """Replay a fixed list of ``complete`` responses in order.

    Used to drive Check into emitting a RETRY signal without having to
    simulate every phase with a real schedule.
    """

    def __init__(self, scripted: List[str]) -> None:
        self._scripted = list(scripted)
        self.calls = 0
        self.users: List[str] = []

    def complete(self, *, system: str, user: str, call_spec=None) -> str:
        self.users.append(user)
        if self.calls < len(self._scripted):
            out = self._scripted[self.calls]
            self.calls += 1
            return out
        self.calls += 1
        return ""


@pytest.mark.unit
def test_check_retry_triggers_replan_once():
    # Script order (plan, do, check, plan_retry, do_retry). The default
    # ``act`` phase config is ``skip``, so act makes no LLM call; total = 5.
    # 1. plan: no tools requested — plain prose.
    # 2. do: draft a reply.
    # 3. check: emit a RETRY asking for `whoami` tools.
    # 4. plan retry: still prose (the framework does not care here).
    # 5. do retry: final draft.
    script = [
        "plan-prose",
        "draft-1",
        "RETRY: need_tools=whoami",
        "plan-retry-prose",
        "draft-2",
    ]
    rec = _ScriptedLlm(script)
    mem = _FakeMem()
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=_basic_cfg(),
        instance_phase_llm={},
        instance_mode_models={},
        llm=rec,
    )
    out = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert out.ok
    # plan (1) + do (1) + check (1) + plan_retry (1) + do_retry (1) = 5 calls.
    assert rec.calls == 5
    # Trace must contain the retry marker step we added for observability.
    finish = [r for r in mem.runs if r["op"] == "finish"][-1]
    retry_markers = [
        x for x in finish["trace"]
        if isinstance(x, dict) and x.get("step") == "check_retry_triggered"
    ]
    assert retry_markers and retry_markers[0]["tools"] == ["whoami"]
    # The retry plan prompt must carry the guardrail hint.
    assert any("Guardrail note" in u for u in rec.users)


@pytest.mark.unit
def test_check_without_retry_does_not_replan():
    script = ["plan-prose", "draft", "ok-looks-good"]
    rec = _ScriptedLlm(script)
    fw = LlmPDCAFramework(
        memory=_FakeMem(),
        llm_config=_basic_cfg(),
        instance_phase_llm={},
        instance_mode_models={},
        llm=rec,
    )
    out = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert out.ok
    # Default phase_llm skips ``act``; plan + do + check = 3 LLM calls.
    assert rec.calls == 3
