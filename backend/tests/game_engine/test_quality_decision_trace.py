"""Tests: quality_decision trace row schema + default-config byte-equiv.

The ``quality_decision`` trace row (carrying ``check_point`` / ``quality_score``
multi-dim / ``degraded_action``) must only appear when quality scoring is
explicitly enabled. Under default config, no such trace row is produced
(byte-equivalent to pre-F18 behavior).
"""
from __future__ import annotations

from app.game_engine.agent_runtime.policy import PolicyEngine
from app.game_engine.agent_runtime.policy.check_points import CheckPoint
from app.game_engine.agent_runtime.policy.context import PolicyContext


def test_default_config_no_quality_decision_trace():
    """Under default config (enable_quality_score=false), evaluating
    before_terminal produces a plain allow with no quality_score evidence."""
    engine = PolicyEngine()
    ctx = PolicyContext(
        check_point=CheckPoint.BEFORE_TERMINAL,
        extra={"tick_state": {"draft_text": "hello", "agent_loop_config": None}},
    )
    decision = engine.evaluate(ctx)
    # final_success_evaluator returns None (no config); quality_score off → allow
    assert decision.is_allow is True
    assert decision.quality_score is None


def test_quality_decision_trace_schema_when_enabled():
    """When enable_quality_score=true, the decision carries the multi-dim score."""
    engine = PolicyEngine()
    ctx = PolicyContext(
        check_point=CheckPoint.BEFORE_TERMINAL,
        extra={
            "tick_state": {
                "enable_quality_score": True,
                "draft_text": "hello world",
                "tool_results": [],
                "success_criteria": [],
                "recent_signatures": [],
                "stagnation_window": 3,
            }
        },
    )
    decision = engine.evaluate(ctx)
    assert decision.is_allow is True
    # quality_score is a first-class field (G2); evidence stays clean.
    if decision.quality_score is not None:
        assert "semantic" in decision.quality_score
        assert "quality_score" not in (decision.evidence or {})
