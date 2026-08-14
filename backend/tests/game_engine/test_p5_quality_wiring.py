"""P5 driver wiring: PolicyEngine.evaluate at F18 check_points.

Verifies byte-equivalence under default config (no ``quality_decision`` trace
rows, no control-flow override) and opt-in driving when the quality-domain
gates are enabled.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.settings import PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.agent_loop.signals import DraftCompletenessVerdict
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
from app.game_engine.agent_runtime.policy.config import (
    PolicyConfig,
    QualityDomainConfig,
)
from app.game_engine.agent_runtime.policy.engine import PolicyEngine
from app.game_engine.agent_runtime.policy.domains import quality_domain
from app.game_engine.agent_runtime.policy.check_points import CheckPoint
from app.game_engine.agent_runtime.policy.decisions import PolicyDecision
from app.game_engine.agent_runtime.state_machine.workflow_loader import load_workflow
from app.game_engine.agent_runtime.thinking_pipeline import NoOpAgentTickHooks
from app.game_engine.agent_runtime.tool_calling import (
    CompleteWithToolsResult,
    ToolSchema,
)
from app.game_engine.agent_runtime.tool_gather import (
    ToolGatherBudgets,
    ToolGatherCounters,
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


class _RecordingCompleteLlm(_CompleteLlm):
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete_with_tools(self, *, system, turns, tools, call_spec=None, cancel_check=None):
        self.prompts.append("\n".join(str(getattr(turn, "text", "")) for turn in turns))
        return super().complete_with_tools(
            system=system,
            turns=turns,
            tools=tools,
            call_spec=call_spec,
            cancel_check=cancel_check,
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


def _build_fw(
    *,
    quality: QualityDomainConfig,
    llm=None,
    state_machine=None,
    tool_gather_budgets: ToolGatherBudgets | None = None,
) -> tuple[LlmPDCAFramework, _TraceMem]:
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
        llm=llm or _CompleteLlm(),
        tick_hooks=NoOpAgentTickHooks(),
        tool_schemas=[ToolSchema(name="look", description="look", input_schema={"type": "object"})],
        state_machine=state_machine,
        tool_gather_budgets=tool_gather_budgets,
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
    assert res.error_code == "max_iterations_exceeded"
    rows = _quality_rows(mem.last_trace)
    assert rows, "expected at least one quality_decision row"
    assert any(r["reason_code"] == "max_iterations_exceeded" for r in rows)


@pytest.mark.unit
def test_final_success_gate_emits_before_terminal_row():
    """final_success_drive_mode=shadow → before_terminal quality_decision row
    appears (audit); deferral stays authoritative so tick still succeeds."""
    fw, mem = _build_fw(
        quality=QualityDomainConfig(final_success_drive_mode="shadow")
    )
    res = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    # shadow is audit/trace-only + divergence detection; _detect_tick_emit_deferral
    # stays authoritative, so the tick still succeeds for a complete answer.
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
    assert res.error_code == "stagnation_replan_exhausted"
    rows = _quality_rows(mem.last_trace)
    assert any(r["reason_code"] == "stagnation" for r in rows)


@pytest.mark.unit
def test_budget_soft_fail_continue_records_row_no_flow_change(monkeypatch):
    """P5-B3: budget_exceeded soft-fail → ``continue`` decision. The driver
    records a ``quality_decision`` trace row (audit) but does NOT change
    control flow (no stop_fail, no replan) — the existing draft-gate
    fail_fallback path remains authoritative. Tick still succeeds for a
    complete draft."""
    from app.game_engine.agent_runtime.policy.domains import quality_domain

    def _force_budget_continue(ctx):
        tick_state = ctx.extra.get("tick_state") or {}
        if not tick_state.get("enable_stop_dimensions"):
            return None
        if tick_state.get("current_state") == "plan":
            return PolicyDecision.continue_(
                CheckPoint.AFTER_STATE_EXECUTE,
                reason_code="budget_exceeded",
                evidence={"mode": "soft_fail"},
            )
        return None

    monkeypatch.setattr(quality_domain, "stop_evaluator", _force_budget_continue)
    fw, mem = _build_fw(
        quality=QualityDomainConfig(enable_stop_dimensions=True, max_iterations=12)
    )
    res = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    # soft-fail continue does not abort; complete draft → success.
    assert res.ok
    rows = _quality_rows(mem.last_trace)
    budget_rows = [r for r in rows if r["reason_code"] == "budget_exceeded"]
    assert budget_rows, "expected a budget_exceeded quality_decision row"
    # No stop_fail state_transition (soft-fail does not drive *→fail).
    transitions = [r for r in mem.last_trace if r.get("step") == "state_transition"]
    assert all(r.get("to") != "fail" for r in transitions)


# ---------------------------------------------------------------------------
# D-B Step1: final_success_drive_mode (shadow / enforce)
# ---------------------------------------------------------------------------

def _divergence_rows(trace: list) -> list:
    return [r for r in trace if r.get("step") == "final_success_divergence"]


@pytest.mark.unit
def test_final_success_shadow_byte_equiv_no_divergence(monkeypatch):
    """D-B shadow: evaluator agrees with deferral (both complete) → no
    divergence row; tick still succeeds (deferral authoritative)."""
    monkeypatch.setattr(
        quality_domain, "assess_final_draft_completeness",
        lambda **kw: DraftCompletenessVerdict.complete,
    )
    fw, mem = _build_fw(
        quality=QualityDomainConfig(final_success_drive_mode="shadow")
    )
    res = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert res.ok
    rows = _quality_rows(mem.last_trace)
    assert any(r["check_point"] == "before_terminal" for r in rows)
    assert _divergence_rows(mem.last_trace) == [], "no divergence when verdicts agree"


@pytest.mark.unit
def test_final_success_shadow_records_divergence_on_fail_disagreement(monkeypatch):
    """D-B shadow: evaluator says fail_fallback but deferral says complete →
    divergence row recorded; deferral stays authoritative so tick still succeeds."""
    monkeypatch.setattr(
        quality_domain, "assess_final_draft_completeness",
        lambda **kw: DraftCompletenessVerdict.fail_fallback,
    )
    fw, mem = _build_fw(
        quality=QualityDomainConfig(final_success_drive_mode="shadow")
    )
    res = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    # deferral authoritative → complete draft → success despite evaluator fail.
    assert res.ok
    div = _divergence_rows(mem.last_trace)
    assert div, "expected a final_success_divergence row"
    assert div[0]["drive_mode"] == "shadow"
    assert div[0]["verdict"] == "fail_fallback"
    assert div[0]["deferral_draft_incomplete"] is False
    assert div[0]["would_enforce_draft_incomplete"] is True


@pytest.mark.unit
def test_final_success_shadow_retry_loop_always_divergence(monkeypatch):
    """D-B shadow: retry_loop is a third state the binary deferral gate can't
    express → divergence row recorded regardless of deferral verdict."""
    monkeypatch.setattr(
        quality_domain, "assess_final_draft_completeness",
        lambda **kw: DraftCompletenessVerdict.retry_loop,
    )
    fw, mem = _build_fw(
        quality=QualityDomainConfig(final_success_drive_mode="shadow")
    )
    res = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert res.ok  # deferral authoritative → complete draft → success
    div = _divergence_rows(mem.last_trace)
    assert div, "retry_loop always surfaces as divergence"
    assert div[0]["verdict"] == "retry_loop"
    assert div[0]["would_enforce_draft_incomplete"] is None


@pytest.mark.unit
def test_final_success_enforce_fail_drives_tick_to_fail(monkeypatch):
    """D-B enforce: evaluator fail_fallback overrides deferral (complete) →
    _draft_incomplete set → act→fail. deferral no longer authoritative."""
    monkeypatch.setattr(
        quality_domain, "assess_final_draft_completeness",
        lambda **kw: DraftCompletenessVerdict.fail_fallback,
    )
    fw, mem = _build_fw(
        quality=QualityDomainConfig(final_success_drive_mode="enforce")
    )
    res = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert not res.ok, "enforce fail should drive the tick to fail"
    transitions = [r for r in mem.last_trace if r.get("step") == "state_transition"]
    assert any(r.get("to") == "fail" for r in transitions)


@pytest.mark.unit
def test_final_success_enforce_complete_keeps_success(monkeypatch):
    """D-B enforce: evaluator complete agrees with deferral → no divergence,
    _draft_incomplete cleared, tick succeeds."""
    monkeypatch.setattr(
        quality_domain, "assess_final_draft_completeness",
        lambda **kw: DraftCompletenessVerdict.complete,
    )
    fw, mem = _build_fw(
        quality=QualityDomainConfig(final_success_drive_mode="enforce")
    )
    res = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert res.ok
    assert _divergence_rows(mem.last_trace) == []


@pytest.mark.unit
def test_final_success_enforce_retry_loop_drives_draft_retry(monkeypatch):
    """enforce + retry_loop drives one outer draft_retry replan."""
    monkeypatch.setattr(
        quality_domain, "assess_final_draft_completeness",
        lambda **kw: DraftCompletenessVerdict.retry_loop,
    )
    fw, mem = _build_fw(
        quality=QualityDomainConfig(final_success_drive_mode="enforce")
    )
    res = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert not res.ok
    assert res.error_code == "draft_retry_exhausted"
    rows = [r for r in mem.last_trace if r.get("step") == "state_transition"]
    assert any(r.get("event") == "draft_retry" and r.get("to") == "plan" for r in rows)
    div = _divergence_rows(mem.last_trace)
    assert div, "retry_loop surfaces as divergence in enforce"
    assert div[0]["would_enforce_draft_incomplete"] is None


@pytest.mark.unit
def test_final_success_retry_recovers_with_corrective_plan_context(monkeypatch):
    verdicts = iter([
        DraftCompletenessVerdict.retry_loop,
        DraftCompletenessVerdict.complete,
    ])
    monkeypatch.setattr(
        quality_domain,
        "assess_final_draft_completeness",
        lambda **kw: next(verdicts),
    )
    llm = _RecordingCompleteLlm()
    fw, mem = _build_fw(
        quality=QualityDomainConfig(final_success_drive_mode="enforce"),
        llm=llm,
    )

    res = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))

    assert res.ok
    transitions = [r for r in mem.last_trace if r.get("step") == "state_transition"]
    assert any(r.get("event") == "draft_retry" and r.get("to") == "plan" for r in transitions)
    assert len(llm.prompts) == 2
    assert "Previous rejected draft" in llm.prompts[1]
    assert "final_success_retry_loop" in llm.prompts[1]


@pytest.mark.unit
def test_final_success_retry_fails_closed_without_workflow_transition(monkeypatch):
    monkeypatch.setattr(
        quality_domain,
        "assess_final_draft_completeness",
        lambda **kw: DraftCompletenessVerdict.retry_loop,
    )
    state_machine = load_workflow({
        "mode": "pdca",
        "stages": [
            {"id": "plan"},
            {"id": "do"},
            {"id": "check"},
            {"id": "act"},
            {"id": "end", "exit": True},
        ],
        "transitions": [
            {"from": "plan", "to": "do"},
            {"from": "do", "to": "check"},
            {"from": "check", "to": "act"},
            {"from": "act", "to": "end"},
        ],
    })
    fw, mem = _build_fw(
        quality=QualityDomainConfig(final_success_drive_mode="enforce"),
        state_machine=state_machine,
    )

    res = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))

    assert not res.ok
    assert res.error_code == "draft_retry_unsupported"
    assert any(
        row.get("step") == "draft_retry_blocked"
        and row.get("reason_code") == "draft_retry_unsupported"
        for row in mem.last_trace
    )


@pytest.mark.unit
def test_tick_budget_requires_observation_capacity():
    fw, _ = _build_fw(
        quality=QualityDomainConfig(),
        tool_gather_budgets=ToolGatherBudgets(
            max_commands_per_tick=16,
            max_chars_observations_per_tick=10,
        ),
    )

    assert not fw._tick_budget_remaining(
        ToolGatherCounters(commands_run=0, observation_chars=10)
    )


@pytest.mark.unit
def test_final_success_off_byte_equiv_no_rows(monkeypatch):
    """D-B off (default): no before_terminal quality_decision row, no
    divergence row — byte-equivalent to pre-D-B behavior."""
    monkeypatch.setattr(
        quality_domain, "assess_final_draft_completeness",
        lambda **kw: DraftCompletenessVerdict.fail_fallback,
    )
    fw, mem = _build_fw(quality=QualityDomainConfig(final_success_drive_mode="off"))
    res = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert res.ok  # deferral authoritative, complete draft
    assert _quality_rows(mem.last_trace) == []
    assert _divergence_rows(mem.last_trace) == []
