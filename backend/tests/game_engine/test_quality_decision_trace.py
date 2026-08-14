"""Tests: quality_decision trace row schema + default-config byte-equiv.

The ``quality_decision`` trace row (carrying ``check_point`` / ``quality_score``
multi-dim / ``degraded_action``) must only appear when quality scoring is
explicitly enabled. Under default config, no such trace row is produced
(byte-equivalent to pre-F18 behavior).
"""
from __future__ import annotations

from unittest.mock import MagicMock

from app.game_engine.agent_runtime.agent_loop.signals import DraftCompletenessVerdict
from app.game_engine.agent_runtime.policy import PolicyEngine
from app.game_engine.agent_runtime.policy.check_points import CheckPoint
from app.game_engine.agent_runtime.policy.context import PolicyContext
from app.game_engine.agent_runtime.policy.domains import quality_domain


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
    assert decision.quality_score is not None
    assert "semantic" in decision.quality_score
    assert "quality_score" not in (decision.evidence or {})


def test_quality_score_survives_final_success_short_circuit(monkeypatch):
    monkeypatch.setattr(
        quality_domain,
        "assess_final_draft_completeness",
        lambda **kw: DraftCompletenessVerdict.complete,
    )
    engine = PolicyEngine()
    ctx = PolicyContext(
        check_point=CheckPoint.BEFORE_TERMINAL,
        extra={
            "tick_state": {
                "enable_quality_score": True,
                "final_success_drive_mode": "shadow",
                "agent_loop_config": MagicMock(),
                "draft_text": "hello world",
                "user_message": "hello?",
                "tool_results": [],
                "success_criteria": [],
                "recent_signatures": [],
                "stagnation_window": 3,
            }
        },
    )

    decision = engine.evaluate(ctx)

    assert decision.decision == "final_success"
    assert decision.quality_score is not None
    assert "semantic" in decision.quality_score
