"""Tests for final_success_evaluator — wraps assess_draft_completeness hard_gates."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.game_engine.agent_runtime.agent_loop import draft_gate
from app.game_engine.agent_runtime.agent_loop.signals import (
    DraftCompletenessVerdict,
)
from app.game_engine.agent_runtime.policy import PolicyContext
from app.game_engine.agent_runtime.policy.check_points import CheckPoint
from app.game_engine.agent_runtime.policy.domains.quality_domain import (
    final_success_evaluator,
)


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
            draft_gate, "assess_draft_completeness_with_budget",
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
            draft_gate, "assess_draft_completeness_with_budget",
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
            draft_gate, "assess_draft_completeness_with_budget",
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
            draft_gate, "assess_draft_completeness_with_budget",
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
            draft_gate, "assess_draft_completeness_with_budget",
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
            draft_gate, "assess_draft_completeness_with_budget",
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
            draft_gate, "assess_draft_completeness_with_budget", _raise,
        )
        ctx = _ctx_with_tick_state(
            draft_text="x",
            user_message="q",
            agent_loop_config=MagicMock(), final_success_drive_mode="shadow",
        )
        import pytest

        with pytest.raises(RuntimeError, match="assess exploded"):
            final_success_evaluator(ctx)
