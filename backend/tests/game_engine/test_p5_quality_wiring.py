"""P5 driver wiring: PolicyEngine.evaluate at F18 check_points.

Verifies byte-equivalence under default config (no ``quality_decision`` trace
rows, no control-flow override) and opt-in driving when the quality-domain
gates are enabled.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.settings import PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
from app.game_engine.agent_runtime.policy.config import (
    PolicyConfig,
    QualityDomainConfig,
)
from app.game_engine.agent_runtime.policy.engine import PolicyEngine
from app.game_engine.agent_runtime.policy.check_points import CheckPoint
from app.game_engine.agent_runtime.policy.decisions import PolicyDecision
from app.game_engine.agent_runtime.thinking_pipeline import NoOpAgentTickHooks
from app.game_engine.agent_runtime.tool_calling import (
    CompleteWithToolsResult,
    ToolSchema,
)


class _CompleteLlm:
    """Emits a long, complete answer with no tool calls on the first call."""

    def supports_tools(self) -> bool:
        return True

    def complete_with_tools(self, *, system, turns, tools, call_spec=None, cancel_check=None):
        return CompleteWithToolsResult(
            text="这是一个足够长的完整回答，包含足够的内容以满足草稿完整性检查。" * 3,
            tool_calls=[],
            finish_reason="stop",
        )


class _TraceMem:
    """Captures the trace handed to finish_run for assertion."""

    def __init__(self) -> None:
        self.last_trace: list = []

    def start_run(self, *a, **k) -> None:
        return None

    def update_run(self, *a, **k) -> None:
        return None

    def finish_run(self, *a, **k) -> None:
        # finish_run(run_id, phase, trace, status, graph_ops_summary=...)
        self.last_trace = list(a[2]) if len(a) > 2 else list(k.get("trace") or [])

    def append_raw(self, *a, **k) -> None:
        return None


def _build_fw(*, quality: QualityDomainConfig) -> tuple[LlmPDCAFramework, _TraceMem]:
    mem = _TraceMem()
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=SimpleNamespace(
            extra={"agent_loop_min_complete_chars": 1},
            model="",
            system_prompt="test",
            phase_prompts={},
        ),
        instance_phase_llm={
            "plan": PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan),
            "do": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            "check": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            "act": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
        },
        instance_mode_models={},
        llm=_CompleteLlm(),
        tick_hooks=NoOpAgentTickHooks(),
        tool_schemas=[ToolSchema(name="look", description="look", input_schema={"type": "object"})],
    )
    fw._policy_engine = PolicyEngine(config=PolicyConfig(quality=quality))
    return fw, mem


def _quality_rows(trace: list) -> list:
    return [r for r in trace if r.get("step") == "quality_decision"]


@pytest.mark.unit
def test_byte_equiv_no_quality_decision_rows_under_default_config():
    """Default config → no quality_decision trace rows (byte-equivalence)."""
    fw, mem = _build_fw(quality=QualityDomainConfig())
    res = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert res.ok
    assert _quality_rows(mem.last_trace) == []


@pytest.mark.unit
def test_stop_dimensions_max_iterations_drives_fail():
    """enable_stop_dimensions + max_iterations=1 → fail decision drives tick to fail."""
    fw, mem = _build_fw(
        quality=QualityDomainConfig(enable_stop_dimensions=True, max_iterations=1)
    )
    res = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert not res.ok
    rows = _quality_rows(mem.last_trace)
    assert rows, "expected at least one quality_decision row"
    assert any(r["reason_code"] == "max_iterations_exceeded" for r in rows)


@pytest.mark.unit
def test_final_success_gate_emits_before_terminal_row():
    """enable_final_success_gate → before_terminal quality_decision row appears (audit)."""
    fw, mem = _build_fw(
        quality=QualityDomainConfig(enable_final_success_gate=True)
    )
    res = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    # final_success is audit/trace-only; _detect_tick_emit_deferral stays
    # authoritative, so the tick still succeeds for a complete answer.
    assert res.ok
    rows = _quality_rows(mem.last_trace)
    before_terminal = [r for r in rows if r["check_point"] == "before_terminal"]
    assert before_terminal, "expected a before_terminal quality_decision row"


@pytest.mark.unit
def test_stagnation_replan_drives_replan_to_plan(monkeypatch):
    """D2: stop_evaluator stagnation → driver maps to event=stagnation →
    F17 *→plan replan (replan_count increments); tick still succeeds after
    one replan since the forced evaluator only fires at replan_count==0."""
    from app.game_engine.agent_runtime.policy.domains import quality_domain

    def _force_stagnation(ctx):
        tick_state = ctx.extra.get("tick_state") or {}
        if not tick_state.get("enable_stop_dimensions"):
            return None
        if (
            tick_state.get("current_state") in ("plan", "do", "check")
            and tick_state.get("replan_count", 0) == 0
        ):
            return PolicyDecision.replan(
                CheckPoint.AFTER_STATE_EXECUTE, "stagnation", evidence={}
            )
        return None

    monkeypatch.setattr(quality_domain, "stop_evaluator", _force_stagnation)
    fw, mem = _build_fw(
        quality=QualityDomainConfig(enable_stop_dimensions=True, max_iterations=12)
    )
    res = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    # One stagnation replan, then proceeds to a complete draft → success.
    assert res.ok
    rows = _quality_rows(mem.last_trace)
    stagnation_rows = [r for r in rows if r["reason_code"] == "stagnation"]
    assert stagnation_rows, "expected a stagnation quality_decision row"
    # The replan produced a state_transition with event=stagnation and replan_count=1.
    transitions = [r for r in mem.last_trace if r.get("step") == "state_transition"]
    replan_transitions = [
        r for r in transitions if r.get("event") == "stagnation" and r.get("replan_count") == 1
    ]
    assert replan_transitions, "expected a state_transition row with event=stagnation, replan_count=1"


@pytest.mark.unit
def test_stagnation_over_limit_drives_stop_fail(monkeypatch):
    """D2: stagnation over the replan cap → driver sets runtime.stop_fail →
    F17 *→fail (any state). The forced evaluator always returns stagnation;
    after the first replan (replan_count=1 == max_replans=1), the next stagnation
    is over-limit → stop_fail → tick fails."""
    from app.game_engine.agent_runtime.policy.domains import quality_domain

    def _always_stagnation(ctx):
        tick_state = ctx.extra.get("tick_state") or {}
        if not tick_state.get("enable_stop_dimensions"):
            return None
        if tick_state.get("current_state") in ("plan", "do", "check"):
            return PolicyDecision.replan(
                CheckPoint.AFTER_STATE_EXECUTE, "stagnation", evidence={}
            )
        return None

    monkeypatch.setattr(quality_domain, "stop_evaluator", _always_stagnation)
    fw, mem = _build_fw(
        quality=QualityDomainConfig(enable_stop_dimensions=True, max_iterations=12)
    )
    res = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    # First plan: stagnation, replan_count 0<1 → replan to plan (replan_count=1).
    # Second plan: stagnation, replan_count 1>=1 → stop_fail → *→fail.
    assert not res.ok
    rows = _quality_rows(mem.last_trace)
    assert any(r["reason_code"] == "stagnation" for r in rows)
