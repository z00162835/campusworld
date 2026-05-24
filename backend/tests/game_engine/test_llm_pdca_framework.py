"""Unit tests for LlmPDCAFramework (no database, stub LLM)."""

from __future__ import annotations

from contextlib import contextmanager
import uuid
from typing import Any, Dict, List, Optional

import pytest

from app.commands.base import CommandContext
from app.core.settings import AgentLlmServiceConfig, PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks import llm_pdca as llm_pdca_mod
from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
from app.game_engine.agent_runtime.frameworks.pdca import PDCAPhase
from app.game_engine.agent_runtime.llm_client import StubLlmClient
from app.game_engine.agent_runtime.resolved_tool_surface import PreauthorizedToolExecutor, ResolvedToolSurface
from app.game_engine.agent_runtime.tool_gather import ToolGatherBudgets, ToolGatherCounters
from app.game_engine.agent_runtime.tool_router.router_result import EnforcementLevel, RouterResult


class _FakeMem:
    def __init__(self) -> None:
        self.runs: List[Dict[str, Any]] = []
        self.raw: List[Dict[str, Any]] = []

    def start_run(self, run_id, correlation_id, phase, command_trace, status) -> None:
        self.runs.append(
            {"op": "start", "run_id": run_id, "phase": phase, "trace": list(command_trace), "status": status}
        )

    def update_run(self, run_id, phase, command_trace, status, graph_ops_summary=None) -> None:
        self.runs.append(
            {
                "op": "update",
                "run_id": run_id,
                "phase": phase,
                "trace": list(command_trace),
                "status": status,
                "graph_ops_summary": graph_ops_summary,
            }
        )

    def finish_run(self, run_id, phase, command_trace, status, graph_ops_summary=None) -> None:
        self.runs.append(
            {
                "op": "finish",
                "run_id": run_id,
                "phase": phase,
                "trace": list(command_trace),
                "status": status,
                "graph_ops_summary": graph_ops_summary,
            }
        )

    def append_raw(self, kind: str, payload: Dict[str, Any], session_id: Optional[uuid.UUID] = None) -> None:
        self.raw.append({"kind": kind, "payload": payload})


@pytest.mark.unit
def test_llm_pdca_runs_four_phases_and_returns_reply():
    mem = _FakeMem()
    cfg = AgentLlmServiceConfig(
        system_prompt="You are a test assistant.",
        phase_prompts={
            "plan": "Plan step.",
            "do": "Answer step.",
            "check": "Check step.",
            "act": "Act step.",
        },
    )
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=cfg,
        instance_phase_llm={},
        instance_mode_models={},
        llm=StubLlmClient(),
    )
    ctx = FrameworkRunContext(
        agent_node_id=1,
        correlation_id="c1",
        payload={"message": "What is CampusWorld?"},
        memory_context="prior note about rooms",
    )
    res = fw.run(ctx)
    assert res.ok
    assert res.final_phase == PDCAPhase.act.value
    assert "[stub_llm" in res.message
    finish = [r for r in mem.runs if r["op"] == "finish"][-1]
    steps = [x.get("step") for x in finish["trace"] if isinstance(x, dict) and "step" in x]
    assert "plan" in steps and "do" in steps and "check" in steps and "act" in steps


class _RecordingLlm:
    def __init__(self) -> None:
        self.systems: List[str] = []
        self.calls = 0

    def complete(self, *, system: str, user: str, call_spec=None) -> str:
        self.calls += 1
        self.systems.append(system)
        return "ok"


class _AlwaysOkRecordingLlm:
    def __init__(self) -> None:
        self.calls = 0
        self.users: List[str] = []

    def complete(self, *, system: str, user: str, call_spec=None) -> str:
        self.calls += 1
        self.users.append(user)
        return "ok"


class _RecordingObservability:
    def __init__(self) -> None:
        self.events: List[tuple[str, str, Optional[str]]] = []
        self.llm_calls: List[Dict[str, Any]] = []
        self.tool_observations: List[Dict[str, Any]] = []

    @contextmanager
    def run_scope(self, *, run_id: str, correlation_id: Optional[str]):
        self.events.append(("enter", run_id, correlation_id))
        try:
            yield
        finally:
            self.events.append(("exit", run_id, correlation_id))

    def should_log_full_chain(self, config: Any) -> bool:
        _ = config
        return True

    def log_llm_call(self, config: Any, *, phase: str, system: str, user: str, spec: Any, skipped: bool) -> None:
        _ = config
        self.llm_calls.append({"phase": phase, "system": system, "user": user, "skipped": skipped})

    def log_tool_observations_text(self, config: Any, *, phase: str, observation_text: str) -> None:
        _ = config
        self.tool_observations.append({"phase": phase, "observation_text": observation_text})

    def log_http_exchange(self, config: Any, *, url: str, status_code: int, elapsed_ms: float, request_body: Any, response_data: Any) -> None:
        _ = (config, url, status_code, elapsed_ms, request_body, response_data)


@pytest.mark.unit
def test_llm_pdca_uses_observability_adapter_scope_and_llm_logging():
    mem = _FakeMem()
    obs = _RecordingObservability()
    cfg = AgentLlmServiceConfig(
        system_prompt="sys",
        phase_prompts={
            "plan": "Plan step.",
            "do": "Answer step.",
            "check": "Check step.",
            "act": "Act step.",
        },
    )
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=cfg,
        instance_phase_llm={},
        instance_mode_models={},
        llm=StubLlmClient(),
        observability=obs,
    )
    res = fw.run(
        FrameworkRunContext(
            agent_node_id=1,
            correlation_id="corr-obs",
            payload={"message": "hello"},
        )
    )

    assert res.ok
    assert obs.events[0][0] == "enter"
    assert obs.events[0][2] == "corr-obs"
    assert obs.events[-1][0] == "exit"
    assert obs.events[-1][1] == obs.events[0][1]
    assert [call["phase"] for call in obs.llm_calls] == ["plan", "do", "check", "act"]


@pytest.mark.unit
def test_llm_pdca_ctx_overrides_system_prompt():
    mem = _FakeMem()
    rec = _RecordingLlm()
    cfg = AgentLlmServiceConfig(system_prompt="BASE_ONLY")
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=cfg,
        instance_phase_llm={},
        instance_mode_models={},
        llm=rec,
    )
    ctx = FrameworkRunContext(
        agent_node_id=1,
        payload={"message": "hi"},
        system_prompt="CTX_OVERRIDE",
        phase_prompts={"plan": "suffix_plan"},
    )
    fw.run(ctx)
    assert rec.systems
    assert "CTX_OVERRIDE" in rec.systems[0]
    assert "suffix_plan" in rec.systems[0]


@pytest.mark.unit
def test_llm_pdca_forces_retry_when_mandatory_chain_tools_missing() -> None:
    mem = _FakeMem()
    rec = _AlwaysOkRecordingLlm()
    cfg = AgentLlmServiceConfig(
        system_prompt="sys",
        phase_prompts={
            "plan": "Plan step.",
            "do": "Answer step.",
            "check": "Check step.",
            "act": "Act step.",
        },
        extra={"tool_router": {"enabled": True}},
    )
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=cfg,
        instance_phase_llm={},
        instance_mode_models={},
        llm=rec,
    )
    ctx = FrameworkRunContext(
        agent_node_id=1,
        correlation_id="c-mandatory-gap",
        payload={"message": "find buildings and summarize space"},
        memory_context="",
    )
    fake_rr = RouterResult(
        candidates=[],
        mandatory_tool_names=["type", "find"],
        enforcement_level=EnforcementLevel.hard_must_invoke,
    )
    from unittest.mock import patch

    with patch.object(llm_pdca_mod, "run_tool_router", return_value=fake_rr):
        res = fw.run(ctx)
    assert res.ok
    finish = [r for r in mem.runs if r["op"] == "finish"][-1]
    trace = [x for x in finish["trace"] if isinstance(x, dict)]
    forced = [x for x in trace if x.get("step") == "mandatory_gap_retry_override"]
    assert forced, f"missing mandatory-gap retry override trace row; trace_steps={[x.get('step') for x in trace]}"
    assert set(forced[-1].get("tools") or []) == {"find", "type"}
    retried = [x for x in trace if x.get("step") == "check_retry_triggered"]
    assert retried, "missing check retry trigger row"
    assert len(retried) == 1
    assert set(retried[-1].get("tools") or []) == {"find", "type"}
    assert res.message.startswith("ok")
    assert "【系统提示】" in res.message
    assert "未形成观测的工具" in res.message
    assert any("Tool-chain completion criteria" in u for u in rec.users)


@pytest.mark.unit
def test_llm_pdca_mandatory_satisfied_by_do_phase_tool_observation() -> None:
    class _PlanThenDoTool:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, *, system: str, user: str, call_spec=None) -> str:
            self.calls += 1
            if self.calls == 1:
                return "plan prose"
            if self.calls == 2:
                return '{"commands": [{"name": "help", "args": []}]}'
            return "draft after tool"

    mem = _FakeMem()
    ctx_cmd = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        roles=[],
    )
    surface = ResolvedToolSurface(allowed_command_names=frozenset({"help"}), tool_command_context=ctx_cmd)
    pre = PreauthorizedToolExecutor(surface)

    class _HelpCmd:
        name = "help"

        def execute(self, c, args):
            from app.commands.base import CommandResult

            return CommandResult.success_result("help observed")

    cfg = AgentLlmServiceConfig(
        system_prompt="sys",
        phase_prompts={"plan": "P", "do": "D", "check": "C", "act": "A"},
        extra={"tool_router": {"enabled": True}},
    )
    fake_rr = RouterResult(
        candidates=[],
        mandatory_tool_names=["help"],
        enforcement_level=EnforcementLevel.hard_must_invoke,
    )
    from unittest.mock import patch

    with patch.object(llm_pdca_mod, "run_tool_router", return_value=fake_rr), patch(
        "app.game_engine.agent_runtime.resolved_tool_surface.command_registry.get_command",
        return_value=_HelpCmd(),
    ):
        fw = LlmPDCAFramework(
            memory=mem,
            llm_config=cfg,
            instance_phase_llm={
                "check": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
                "act": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            },
            instance_mode_models={},
            llm=_PlanThenDoTool(),
            tools=pre,
            tool_command_context=ctx_cmd,
            preauthorized_tool_executor=pre,
        )
        res = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "help me"}))
    assert res.ok
    finish = [r for r in mem.runs if r["op"] == "finish"][-1]
    trace = [x for x in finish["trace"] if isinstance(x, dict)]
    assert not [x for x in trace if x.get("step") == "mandatory_observation_gap"]
    assert any(x.get("step") == "tool_exec" and x.get("phase") == "do" for x in trace)


@pytest.mark.unit
def test_phase_llm_check_skip_skips_llm_call():
    mem = _FakeMem()
    rec = _RecordingLlm()
    cfg = AgentLlmServiceConfig(system_prompt="sys")
    instance_phase_llm = {
        "plan": PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan),
        "do": PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan),
        "check": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
        "act": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
    }
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=cfg,
        instance_phase_llm=instance_phase_llm,
        instance_mode_models={},
        llm=rec,
    )
    fw.run(
        FrameworkRunContext(
            agent_node_id=1,
            payload={"message": "hello"},
        )
    )
    assert rec.calls == 2
    finish = [r for r in mem.runs if r["op"] == "finish"][-1]
    chk = next(x for x in finish["trace"] if isinstance(x, dict) and x.get("step") == "check")
    assert chk.get("skipped") is True


class _PlanJsonThenStubLlm:
    """First call returns JSON tool plan; remaining calls return short stub text."""

    def __init__(self) -> None:
        self.calls = 0
        self.users: List[str] = []

    def complete(self, *, system: str, user: str, call_spec=None) -> str:
        self.calls += 1
        self.users.append(user)
        if self.calls == 1:
            return '{"commands": [{"name": "help", "args": ["help"]}]}'
        return "[stub_tail]"


@pytest.mark.unit
def test_llm_pdca_injects_tool_observation_into_do_prompt():
    mem = _FakeMem()
    rec = _PlanJsonThenStubLlm()
    cfg = AgentLlmServiceConfig(
        system_prompt="sys",
        phase_prompts={
            "plan": "Plan step.",
            "do": "Answer step.",
            "check": "Check step.",
            "act": "Act step.",
        },
    )
    ctx_cmd = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        roles=[],
    )
    surface = ResolvedToolSurface(allowed_command_names=frozenset({"help"}), tool_command_context=ctx_cmd)
    pre = PreauthorizedToolExecutor(surface)

    class _HelpCmd:
        name = "help"

        def execute(self, c, args):
            from app.commands.base import CommandResult

            return CommandResult.success_result("HELP_TEXT_FOR_MODEL")

    from unittest.mock import patch

    with patch(
        "app.game_engine.agent_runtime.resolved_tool_surface.command_registry.get_command",
        return_value=_HelpCmd(),
    ):
        fw = LlmPDCAFramework(
            memory=mem,
            llm_config=cfg,
            instance_phase_llm={},
            instance_mode_models={},
            llm=rec,
            tools=pre,
            tool_command_context=ctx_cmd,
            preauthorized_tool_executor=pre,
        )
        out = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert out.ok
    assert rec.calls >= 2
    assert len(rec.users) >= 2
    assert "tool_observation" in rec.users[1].lower() or "HELP_TEXT_FOR_MODEL" in rec.users[1]


@pytest.mark.unit
def test_gather_tools_after_llm_emits_skip_when_tick_command_budget_exhausted():
    mem = _FakeMem()
    cfg = AgentLlmServiceConfig(system_prompt="sys")
    ctx_cmd = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        roles=[],
    )
    surface = ResolvedToolSurface(allowed_command_names=frozenset({"help"}), tool_command_context=ctx_cmd)
    pre = PreauthorizedToolExecutor(surface)
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=cfg,
        instance_phase_llm={},
        instance_mode_models={},
        llm=StubLlmClient(),
        tools=pre,
        tool_command_context=ctx_cmd,
        preauthorized_tool_executor=pre,
        tool_gather_budgets=ToolGatherBudgets(max_commands_per_tick=1),
    )
    trace: List[Dict[str, Any]] = []
    counters = ToolGatherCounters(commands_run=1, observation_chars=0)
    out = fw._gather_tools_after_llm(
        "plan",
        '{"commands": [{"name": "help", "args": []}]}',
        trace,
        counters,
    )
    assert out == ""
    assert trace == [
        {"step": "tool_gather_skip", "phase": "plan", "reason": "tick_command_budget_exhausted"}
    ]


@pytest.mark.unit
def test_filter_tool_calls_drops_names_not_on_schema_surface():
    """JSON fallback can emit any name; only names on the LLM tool schema list are kept."""
    from app.game_engine.agent_runtime.frameworks import llm_pdca as m
    from app.game_engine.agent_runtime.tool_calling import ToolCall, ToolSchema

    schemas = [ToolSchema(name="look", description="x"), ToolSchema(name="help", description="y")]
    calls = [
        ToolCall.new("describe", []),
        ToolCall.new("look", []),
    ]
    kept, dropped = m._filter_tool_calls_to_schemas(calls, schemas)
    assert [c.name for c in kept] == ["look"]
    assert "describe" in dropped


class _AllEmptyLlm:
    """Returns no visible text for every `complete` call (Plan/Do/Check/Act)."""

    def complete(self, *, system: str, user: str, call_spec=None) -> str:
        return ""

    def supports_tools(self) -> bool:
        return False


def _base_pdca_config(
    extra: Optional[Dict[str, Any]] = None,
) -> AgentLlmServiceConfig:
    cfg_kwargs: Dict[str, Any] = {
        "system_prompt": "You are a test assistant.",
        "phase_prompts": {
            "plan": "Plan step.",
            "do": "Answer step.",
            "check": "Check step.",
            "act": "Act step.",
        },
    }
    if extra is not None:
        cfg_kwargs["extra"] = extra
    return AgentLlmServiceConfig(**cfg_kwargs)


@pytest.mark.unit
def test_empty_final_text_gets_default_fallback_and_trace():
    mem = _FakeMem()
    cfg = _base_pdca_config()
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=cfg,
        instance_phase_llm={},
        instance_mode_models={},
        llm=_AllEmptyLlm(),
    )
    ctx = FrameworkRunContext(
        agent_node_id=1,
        correlation_id="c-empty-1",
        payload={"message": "Hello"},
    )
    res = fw.run(ctx)
    assert res.ok
    assert res.message == llm_pdca_mod._DEFAULT_NPC_AGENT_EMPTY_REPLY
    finish = [r for r in mem.runs if r["op"] == "finish"][-1]
    fb = [x for x in finish["trace"] if isinstance(x, dict) and x.get("step") == "empty_reply_fallback"]
    assert len(fb) == 1
    assert fb[0].get("user_message_len") == 5
    gos = finish.get("graph_ops_summary") or {}
    assert gos.get("reply_excerpt") == res.message


@pytest.mark.unit
def test_empty_final_text_uses_extra_npc_agent_empty_reply_message():
    mem = _FakeMem()
    custom = "（测试）空输出时的自定义一句。"
    cfg = _base_pdca_config(
        extra={"npc_agent_empty_reply_message": custom},
    )
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=cfg,
        instance_phase_llm={},
        instance_mode_models={},
        llm=_AllEmptyLlm(),
    )
    res = fw.run(
        FrameworkRunContext(
            agent_node_id=1,
            correlation_id="c-empty-2",
            payload={"message": "x"},
        )
    )
    assert res.ok
    assert res.message == custom
    finish = [r for r in mem.runs if r["op"] == "finish"][-1]
    assert any(
        isinstance(x, dict) and x.get("step") == "empty_reply_fallback" for x in finish["trace"]
    )
