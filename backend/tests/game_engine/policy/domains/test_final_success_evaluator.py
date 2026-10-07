"""Tests for final_success_evaluator — wraps assess_draft_completeness hard_gates."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.game_engine.agent_runtime.agent_loop import AgentLoopConfig
from app.game_engine.agent_runtime.agent_loop.signals import (
    DraftCompletenessVerdict,
)
from app.game_engine.agent_runtime.policy import PolicyContext
from app.game_engine.agent_runtime.policy.check_points import CheckPoint
from app.game_engine.agent_runtime.policy.domains.quality_domain import (
    final_success_evaluator,
)
from app.game_engine.agent_runtime.policy.domains import quality_domain


def _ctx_with_tick_state(**tick_state):
    return PolicyContext(
        check_point=CheckPoint.BEFORE_TERMINAL,
        extra={"tick_state": tick_state},
    )


class TestFinalSuccessEvaluator:
    def test_returns_none_when_no_tick_state(self):
        ctx = PolicyContext(check_point=CheckPoint.BEFORE_TERMINAL)
        assert final_success_evaluator(ctx) is None

    def test_returns_none_when_no_config(self):
        ctx = _ctx_with_tick_state(draft_text="hello", user_message="hi")
        assert final_success_evaluator(ctx) is None

    def test_returns_none_when_drive_mode_off(self, monkeypatch):
        """D-B: ``off`` (default) → byte-equiv, evaluator not consulted."""
        monkeypatch.setattr(
            quality_domain, "assess_final_draft_completeness",
            lambda **kw: DraftCompletenessVerdict.complete,
        )
        ctx = _ctx_with_tick_state(
            draft_text="a complete answer",
            user_message="q",
            agent_loop_config=MagicMock(), final_success_drive_mode="off",
        )
        assert final_success_evaluator(ctx) is None

    def test_returns_none_when_drive_mode_missing(self, monkeypatch):
        """D-B: missing drive_mode treated as ``off`` → byte-equiv."""
        monkeypatch.setattr(
            quality_domain, "assess_final_draft_completeness",
            lambda **kw: DraftCompletenessVerdict.complete,
        )
        ctx = _ctx_with_tick_state(
            draft_text="a complete answer",
            user_message="q",
            agent_loop_config=MagicMock(),
        )
        assert final_success_evaluator(ctx) is None

    def test_returns_none_at_wrong_check_point(self):
        ctx = PolicyContext(
            check_point=CheckPoint.AFTER_STATE_EXECUTE,
            extra={"tick_state": {"agent_loop_config": MagicMock()}},
        )
        assert final_success_evaluator(ctx) is None

    def test_complete_maps_to_final_success(self, monkeypatch):
        monkeypatch.setattr(
            quality_domain, "assess_final_draft_completeness",
            lambda **kw: DraftCompletenessVerdict.complete,
        )
        ctx = _ctx_with_tick_state(
            draft_text="a complete answer",
            user_message="what is x?",
            agent_loop_config=MagicMock(), final_success_drive_mode="shadow",
        )
        decision = final_success_evaluator(ctx)
        assert decision.decision == "final_success"
        assert decision.runtime_action == "pass"
        assert decision.reason_code == "final_success_complete"

    def test_retry_loop_maps_to_replan(self, monkeypatch):
        monkeypatch.setattr(
            quality_domain, "assess_final_draft_completeness",
            lambda **kw: DraftCompletenessVerdict.retry_loop,
        )
        ctx = _ctx_with_tick_state(
            draft_text="",
            user_message="what is x?",
            agent_loop_config=MagicMock(), final_success_drive_mode="shadow",
        )
        decision = final_success_evaluator(ctx)
        assert decision.decision == "replan"
        assert decision.runtime_action == "pass"
        assert decision.reason_code == "final_success_retry_loop"
        assert decision.evidence["drive_mode"] == "shadow"

    def test_fail_fallback_maps_to_fail(self, monkeypatch):
        monkeypatch.setattr(
            quality_domain, "assess_final_draft_completeness",
            lambda **kw: DraftCompletenessVerdict.fail_fallback,
        )
        ctx = _ctx_with_tick_state(
            draft_text="",
            user_message="what is x?",
            agent_loop_config=MagicMock(), final_success_drive_mode="enforce",
        )
        decision = final_success_evaluator(ctx)
        assert decision.decision == "fail"
        assert decision.runtime_action == "block"
        assert decision.reason_code == "final_success_fail_fallback"
        assert decision.evidence["drive_mode"] == "enforce"

    def test_evidence_carries_draft_incomplete_flag(self, monkeypatch):
        monkeypatch.setattr(
            quality_domain, "assess_final_draft_completeness",
            lambda **kw: DraftCompletenessVerdict.complete,
        )
        ctx = _ctx_with_tick_state(
            draft_text="answer",
            user_message="q",
            agent_loop_config=MagicMock(), final_success_drive_mode="shadow",
            draft_incomplete=True,
        )
        decision = final_success_evaluator(ctx)
        assert decision.evidence["draft_incomplete"] is True

    def test_assess_self_exception_propagates(self, monkeypatch):
        """B7: assess_draft_completeness self-exception re-raises (fail_fallback path)."""
        def _raise(**kw):
            raise RuntimeError("assess exploded")

        monkeypatch.setattr(
            quality_domain, "assess_final_draft_completeness", _raise,
        )
        ctx = _ctx_with_tick_state(
            draft_text="x",
            user_message="q",
            agent_loop_config=MagicMock(), final_success_drive_mode="shadow",
        )
        import pytest

        with pytest.raises(RuntimeError, match="assess exploded"):
            final_success_evaluator(ctx)

    def test_real_retry_verdict_is_not_downgraded_by_outer_budget(self):
        """The evaluator returns the raw verdict; the driver owns retry budgets."""
        ctx = _ctx_with_tick_state(
            draft_text="Let me check",
            user_message="Tell me about CampusWorld",
            agent_loop_config=AgentLoopConfig(),
            final_success_drive_mode="enforce",
            rounds_remaining=0,
        )

        decision = final_success_evaluator(ctx)

        assert decision is not None
        assert decision.decision == "replan"
        assert decision.reason_code == "final_success_retry_loop"


class TestObsGroundedClaimsGate:
    """S2: obs_grounded_claims hard_gate (default-off)."""

    def test_no_gate_when_disabled(self, monkeypatch):
        monkeypatch.setattr(
            quality_domain, "assess_final_draft_completeness",
            lambda **kw: DraftCompletenessVerdict.complete,
        )
        ctx = _ctx_with_tick_state(
            draft_text="answer",
            user_message="what is the room?",
            agent_loop_config=MagicMock(),
            final_success_drive_mode="enforce",
            enable_obs_grounded_claims_gate=False,
            tool_results=[],
        )
        decision = final_success_evaluator(ctx)
        assert decision.decision == "final_success"

    def test_replan_when_grounding_below_threshold(self, monkeypatch):
        monkeypatch.setattr(
            quality_domain, "assess_final_draft_completeness",
            lambda **kw: DraftCompletenessVerdict.complete,
        )
        # Draft tokens barely overlap with obs → low grounding quality.
        ctx = _ctx_with_tick_state(
            draft_text="zzz qqq xxx",
            user_message="where is the library?",
            agent_loop_config=MagicMock(),
            final_success_drive_mode="enforce",
            enable_obs_grounded_claims_gate=True,
            obs_grounded_gte=0.5,
            tool_results=[MagicMock(text="the library is on the second floor")],
        )
        decision = final_success_evaluator(ctx)
        assert decision.decision == "replan"
        assert decision.reason_code == "obs_grounded_claims_unmet"
        assert decision.evidence["grounding_quality"] < 0.5

    def test_pass_when_grounding_meets_threshold(self, monkeypatch):
        monkeypatch.setattr(
            quality_domain, "assess_final_draft_completeness",
            lambda **kw: DraftCompletenessVerdict.complete,
        )
        ctx = _ctx_with_tick_state(
            draft_text="the library is on the second floor",
            user_message="where is the library?",
            agent_loop_config=MagicMock(),
            final_success_drive_mode="enforce",
            enable_obs_grounded_claims_gate=True,
            obs_grounded_gte=0.15,
            tool_results=[MagicMock(text="the library is on the second floor")],
        )
        decision = final_success_evaluator(ctx)
        assert decision.decision == "final_success"

    def test_skip_when_chitchat_no_grounding_needed(self, monkeypatch):
        monkeypatch.setattr(
            quality_domain, "assess_final_draft_completeness",
            lambda **kw: DraftCompletenessVerdict.complete,
        )
        ctx = _ctx_with_tick_state(
            draft_text="hello there",
            user_message="hi",
            agent_loop_config=MagicMock(),
            final_success_drive_mode="enforce",
            enable_obs_grounded_claims_gate=True,
            obs_grounded_gte=0.99,
            tool_results=[MagicMock(text="some observation")],
        )
        decision = final_success_evaluator(ctx)
        # chitchat → _needs_runtime_grounding False → gate skipped → final_success
        assert decision.decision == "final_success"


class TestSuccessCriteriaGate:
    """S3: success_criteria_addressed hard_gate (default-off)."""

    def test_no_gate_when_disabled(self, monkeypatch):
        monkeypatch.setattr(
            quality_domain, "assess_final_draft_completeness",
            lambda **kw: DraftCompletenessVerdict.complete,
        )
        ctx = _ctx_with_tick_state(
            draft_text="answer",
            user_message="what is x?",
            agent_loop_config=MagicMock(),
            final_success_drive_mode="enforce",
            enable_success_criteria_gate=False,
            success_criteria=["library", "floor"],
        )
        decision = final_success_evaluator(ctx)
        assert decision.decision == "final_success"

    def test_replan_when_criteria_unmet(self, monkeypatch):
        monkeypatch.setattr(
            quality_domain, "assess_final_draft_completeness",
            lambda **kw: DraftCompletenessVerdict.complete,
        )
        ctx = _ctx_with_tick_state(
            draft_text="the answer is something else entirely",
            user_message="what is x?",
            agent_loop_config=MagicMock(),
            final_success_drive_mode="enforce",
            enable_success_criteria_gate=True,
            success_criteria=["library", "floor"],
            react_turn_min_criteria_hits=1,
        )
        decision = final_success_evaluator(ctx)
        assert decision.decision == "replan"
        assert decision.reason_code == "success_criteria_addressed_unmet"

    def test_pass_when_criteria_met(self, monkeypatch):
        monkeypatch.setattr(
            quality_domain, "assess_final_draft_completeness",
            lambda **kw: DraftCompletenessVerdict.complete,
        )
        ctx = _ctx_with_tick_state(
            draft_text="the library is on the second floor",
            user_message="where is the library?",
            agent_loop_config=MagicMock(),
            final_success_drive_mode="enforce",
            enable_success_criteria_gate=True,
            success_criteria=["library", "floor"],
            react_turn_min_criteria_hits=1,
        )
        decision = final_success_evaluator(ctx)
        assert decision.decision == "final_success"

    def test_skip_when_no_criteria(self, monkeypatch):
        monkeypatch.setattr(
            quality_domain, "assess_final_draft_completeness",
            lambda **kw: DraftCompletenessVerdict.complete,
        )
        ctx = _ctx_with_tick_state(
            draft_text="answer",
            user_message="what is x?",
            agent_loop_config=MagicMock(),
            final_success_drive_mode="enforce",
            enable_success_criteria_gate=True,
            success_criteria=[],
        )
        decision = final_success_evaluator(ctx)
        assert decision.decision == "final_success"

    def test_replan_when_hits_below_configured_n(self, monkeypatch):
        """D6: S3 gate honors a configured react_turn_min_criteria_hits > 1."""
        monkeypatch.setattr(
            quality_domain, "assess_final_draft_completeness",
            lambda **kw: DraftCompletenessVerdict.complete,
        )
        # Draft hits 1 of 2 criteria; with N=2 → replan.
        ctx = _ctx_with_tick_state(
            draft_text="the library is nearby",
            user_message="where is the library and what floor?",
            agent_loop_config=MagicMock(),
            final_success_drive_mode="enforce",
            enable_success_criteria_gate=True,
            success_criteria=["library", "floor"],
            react_turn_min_criteria_hits=2,
        )
        decision = final_success_evaluator(ctx)
        assert decision.decision == "replan"
        assert decision.reason_code == "success_criteria_addressed_unmet"
        assert decision.evidence["criteria_hit_count"] == 1
        assert decision.evidence["criteria_required"] == 2
