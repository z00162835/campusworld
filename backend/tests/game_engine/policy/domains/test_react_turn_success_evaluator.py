"""Tests for react_turn_success_evaluator — opt-in, per_react_round, S3 criteria.

G9 alignment: pass rule is "at least N criteria hit" (default N=1, SPEC S3).
criteria unmet (0 hits) → replan (recoverable per R4), not fail.
"""
from __future__ import annotations

from app.game_engine.agent_runtime.policy import PolicyContext
from app.game_engine.agent_runtime.policy.check_points import CheckPoint
from app.game_engine.agent_runtime.policy.domains.quality_domain import (
    react_turn_success_evaluator,
)


def _ctx(**tick_state):
    return PolicyContext(
        check_point=CheckPoint.PER_REACT_ROUND,
        extra={"tick_state": tick_state},
        payload={},
    )


class TestReactTurnSuccessEvaluator:
    def test_returns_none_when_no_tick_state(self):
        ctx = PolicyContext(check_point=CheckPoint.PER_REACT_ROUND)
        assert react_turn_success_evaluator(ctx) is None

    def test_returns_none_when_no_react_turn(self):
        ctx = _ctx(success_criteria=["task list"])
        assert react_turn_success_evaluator(ctx) is None

    def test_returns_none_at_wrong_check_point(self):
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TERMINAL,
            extra={"tick_state": {"react_turn": {"final_answer": "x"}}},
        )
        assert react_turn_success_evaluator(ctx) is None

    def test_continue_when_criteria_met(self):
        ctx = _ctx(
            react_turn={"final_answer": "the task list shows items"},
            success_criteria=["task list"],
        )
        decision = react_turn_success_evaluator(ctx)
        assert decision is not None
        assert decision.is_allow is True
        assert ctx.payload["react_round_decision"]["decision"] == "continue"
        assert ctx.payload["react_round_decision"]["reason_code"] == "react_turn_criteria_met"

    def test_continue_when_partial_criteria_hit_with_n1(self):
        """N=1: hitting 1 of 2 criteria already satisfies the pass rule."""
        ctx = _ctx(
            react_turn={"final_answer": "task done"},
            success_criteria=["task list", "task done"],
        )
        react_turn_success_evaluator(ctx)
        assert ctx.payload["react_round_decision"]["decision"] == "continue"

    def test_replan_when_criteria_unmet(self):
        """0 hits → replan (recoverable, R4), not fail."""
        ctx = _ctx(
            react_turn={"final_answer": "completely unrelated"},
            success_criteria=["task list"],
        )
        decision = react_turn_success_evaluator(ctx)
        assert decision is not None
        assert ctx.payload["react_round_decision"]["decision"] == "replan"
        assert ctx.payload["react_round_decision"]["reason_code"] == "react_turn_criteria_unmet"

    def test_no_criteria_vacuously_continue(self):
        ctx = _ctx(
            react_turn={"final_answer": "anything"},
            success_criteria=[],
        )
        react_turn_success_evaluator(ctx)
        assert ctx.payload["react_round_decision"]["decision"] == "continue"
        assert ctx.payload["react_round_decision"]["reason_code"] == "react_turn_no_criteria"

    def test_n_required_configurable(self):
        """When react_turn_min_criteria_hits=2, 1 hit is not enough → replan."""
        ctx = _ctx(
            react_turn={"final_answer": "task done"},
            success_criteria=["task list", "task done"],
            react_turn_min_criteria_hits=2,
        )
        react_turn_success_evaluator(ctx)
        assert ctx.payload["react_round_decision"]["decision"] == "replan"

    def test_writes_payload_for_inner_loop_consumption(self):
        """B4: the evaluator writes react_round_decision for the inner ReAct loop."""
        ctx = _ctx(
            react_turn={"final_answer": "task list complete"},
            success_criteria=["task list"],
        )
        react_turn_success_evaluator(ctx)
        assert "react_round_decision" in ctx.payload
        assert set(ctx.payload["react_round_decision"].keys()) == {"decision", "reason_code"}
