"""Tests for B4: per_react_round decision propagation to the inner ReAct loop.

The ``react_turn_success_evaluator`` writes ``ctx.payload['react_round_decision']``.
The inner ReAct loop consumes it: ``continue`` → next round; ``replan``/``fail``
→ break loop + flag propagation to the outer ``after_state_execute``. This test
locks the payload contract (the loop reads ``decision`` + ``reason_code``).
"""
from __future__ import annotations

from app.game_engine.agent_runtime.policy import PolicyContext
from app.game_engine.agent_runtime.policy.check_points import CheckPoint
from app.game_engine.agent_runtime.policy.domains.quality_domain import (
    react_turn_success_evaluator,
)


def _simulate_inner_react_loop_consume(payload: dict) -> str:
    """Simulate the inner ReAct loop's consumption of react_round_decision (B4).

    Returns 'continue' / 'break_replan' / 'break_fail' mirroring the loop's
    behavior: continue → next round; replan/fail → break + flag propagation.
    """
    decision = payload.get("react_round_decision", {})
    verdict = decision.get("decision")
    if verdict == "continue":
        return "continue"
    if verdict == "replan":
        return "break_replan"
    if verdict == "fail":
        return "break_fail"
    return "continue"


class TestReactRoundPropagation:
    def test_continue_propagates_as_next_round(self):
        ctx = PolicyContext(
            check_point=CheckPoint.PER_REACT_ROUND,
            extra={"tick_state": {"react_turn": {"final_answer": "task list done"}, "success_criteria": ["task list"]}},
            payload={},
        )
        react_turn_success_evaluator(ctx)
        assert _simulate_inner_react_loop_consume(ctx.payload) == "continue"

    def test_replan_breaks_loop_with_flag(self):
        """G9: criteria unmet (0 hits) → replan (recoverable, R4), not fail."""
        ctx = PolicyContext(
            check_point=CheckPoint.PER_REACT_ROUND,
            extra={"tick_state": {"react_turn": {"final_answer": "unrelated"}, "success_criteria": ["task list"]}},
            payload={},
        )
        react_turn_success_evaluator(ctx)
        assert _simulate_inner_react_loop_consume(ctx.payload) == "break_replan"
        # Flag carried for outer after_state_execute 二次确认
        assert ctx.payload["react_round_decision"]["reason_code"] == "react_turn_criteria_unmet"

    def test_fail_breaks_loop(self):
        """The consumer still maps a 'fail' verdict to break_fail; the evaluator
        does not produce fail in v1 (criteria unmet → replan), but the outer
        after_state_execute may escalate to fail when replan budget is exhausted."""
        payload = {"react_round_decision": {"decision": "fail", "reason_code": "budget_exhausted"}}
        assert _simulate_inner_react_loop_consume(payload) == "break_fail"

    def test_payload_keys_are_decision_and_reason_code(self):
        ctx = PolicyContext(
            check_point=CheckPoint.PER_REACT_ROUND,
            extra={"tick_state": {"react_turn": {"final_answer": "x"}, "success_criteria": []}},
            payload={},
        )
        react_turn_success_evaluator(ctx)
        assert set(ctx.payload["react_round_decision"].keys()) == {"decision", "reason_code"}
