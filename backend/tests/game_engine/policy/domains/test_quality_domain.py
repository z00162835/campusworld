"""Tests for the quality domain — stop_evaluator + unified check_replan (B3)."""
from __future__ import annotations

from app.game_engine.agent_runtime.policy.config import QualityDomainConfig
from app.game_engine.agent_runtime.policy.domains.quality_domain import (
    QualityDomain,
    detect_check_replan,
    parse_check_retry_signal,
)


class TestParseCheckRetrySignal:
    def test_none_when_no_marker(self):
        assert parse_check_retry_signal("all good, no retry") is None

    def test_empty_when_marker_without_tools(self):
        # The regex requires at least one tool char; "need_tools=" with nothing
        # after does not match → None (consistent with legacy behavior).
        assert parse_check_retry_signal("RETRY: need_tools=") is None

    def test_single_tool(self):
        assert parse_check_retry_signal("RETRY: need_tools=task") == ["task"]

    def test_multiple_tools(self):
        result = parse_check_retry_signal("RETRY: need_tools=task, agent")
        assert result == ["task", "agent"]

    def test_case_insensitive(self):
        assert parse_check_retry_signal("retry: NEED_TOOLS=task") == ["task"]

    def test_empty_text(self):
        assert parse_check_retry_signal("") is None


class TestDetectCheckReplan:
    def test_check_retry_beats_mandatory_gap(self):
        """B3 priority: check_retry wins over mandatory_gap."""
        result = detect_check_replan(
            check_out="RETRY: need_tools=task",
            check_skipped=False,
            tool_router_snapshot={"mandatory_tool_names": ["task"]},
            accumulated_tick_tool_results=[],
            plan_trace=[],
        )
        event, retry_tools, gap_detail = result
        assert event == "check_retry"
        assert retry_tools == ["task"]
        assert gap_detail is None

    def test_mandatory_gap_when_no_retry_marker(self):
        """When no RETRY marker but mandatory tools missing → mandatory_gap."""
        from app.game_engine.agent_runtime.tool_router.mandatory_gap import (
            mandatory_observation_gap,
        )

        # Build a scenario where mandatory tool is missing.
        result = detect_check_replan(
            check_out="looks good",
            check_skipped=False,
            tool_router_snapshot={"mandatory_tool_names": ["task"]},
            accumulated_tick_tool_results=[],  # no results → gap
            plan_trace=[],
        )
        event, retry_tools, gap_detail = result
        assert event == "mandatory_gap"
        assert retry_tools == ["task"]
        assert gap_detail is not None

    def test_no_replan_when_check_skipped_and_no_mandatory(self):
        """When check is skipped and no mandatory tools configured → no replan.

        (When check is skipped but mandatory tools ARE configured and missing,
        mandatory_gap can still fire — matching legacy behavior.)"""
        result = detect_check_replan(
            check_out="",
            check_skipped=True,
            tool_router_snapshot=None,
            accumulated_tick_tool_results=[],
            plan_trace=[],
        )
        assert result == (None, None, None)

    def test_no_replan_when_no_snapshot(self):
        result = detect_check_replan(
            check_out="looks good",
            check_skipped=False,
            tool_router_snapshot=None,
            accumulated_tick_tool_results=[],
            plan_trace=[],
        )
        assert result == (None, None, None)

    def test_no_replan_when_mandatory_satisfied(self):
        """When mandatory tools are present in results → no gap."""
        # Provide a tool result that satisfies the mandatory tool.
        class _OkResult:
            ok = True
            name = "task"

        result = detect_check_replan(
            check_out="looks good",
            check_skipped=False,
            tool_router_snapshot={"mandatory_tool_names": ["task"]},
            accumulated_tick_tool_results=[_OkResult()],
            plan_trace=[],
        )
        assert result == (None, None, None)


class TestStopEvaluator:
    def test_returns_none_at_after_state_execute(self):
        """v1 stop_evaluator returns None (allow) — new dimensions default-off."""
        from app.game_engine.agent_runtime.policy import PolicyContext
        from app.game_engine.agent_runtime.policy.check_points import CheckPoint

        domain = QualityDomain(QualityDomainConfig())
        ctx = PolicyContext(check_point=CheckPoint.AFTER_STATE_EXECUTE)
        ctx = domain.build_context(ctx)
        decisions = [e(ctx) for e in domain.evaluators()]
        assert all(d is None for d in decisions)

    def test_returns_none_at_wrong_check_point(self):
        from app.game_engine.agent_runtime.policy import PolicyContext
        from app.game_engine.agent_runtime.policy.check_points import CheckPoint

        domain = QualityDomain(QualityDomainConfig())
        ctx = PolicyContext(check_point=CheckPoint.BEFORE_TOOL_CALL)
        ctx = domain.build_context(ctx)
        decisions = [e(ctx) for e in domain.evaluators()]
        assert all(d is None for d in decisions)


class TestStopEvaluatorDimensions:
    """P5: stop_evaluator body — stagnation/max_iterations/max_consecutive (gated)."""

    def _ctx(self, **tick_state):
        from app.game_engine.agent_runtime.policy import PolicyContext
        from app.game_engine.agent_runtime.policy.check_points import CheckPoint

        return PolicyContext(
            check_point=CheckPoint.AFTER_STATE_EXECUTE,
            extra={"tick_state": {"enable_stop_dimensions": True, **tick_state}},
        )

    def test_returns_none_when_gate_off(self):
        from app.game_engine.agent_runtime.policy.domains.quality_domain import stop_evaluator

        ctx = self._ctx(turn_count=100, current_state="plan")
        ctx.extra["tick_state"]["enable_stop_dimensions"] = False
        assert stop_evaluator(ctx) is None

    def test_max_iterations_exceeded(self):
        from app.game_engine.agent_runtime.policy.domains.quality_domain import stop_evaluator

        ctx = self._ctx(turn_count=12, max_iterations=12, current_state="plan")
        d = stop_evaluator(ctx)
        assert d is not None
        assert d.decision == "fail"
        assert d.reason_code == "max_iterations_exceeded"

    def test_max_consecutive_tool_failures(self):
        from app.game_engine.agent_runtime.policy.domains.quality_domain import stop_evaluator

        ctx = self._ctx(
            turn_count=0,
            consecutive_tool_failures=3,
            max_consecutive_tool_failures=3,
            current_state="do",
        )
        d = stop_evaluator(ctx)
        assert d is not None
        assert d.decision == "fail"
        assert d.reason_code == "max_consecutive_tool_failures_exceeded"

    def test_stagnation_replan_in_plan(self):
        from app.game_engine.agent_runtime.policy.domains.quality_domain import stop_evaluator

        ctx = self._ctx(
            turn_count=0,
            current_state="plan",
            recent_signatures=["a", "a", "a"],
            stagnation_window=3,
        )
        d = stop_evaluator(ctx)
        assert d is not None
        assert d.decision == "replan"
        assert d.reason_code == "stagnation"

    def test_stagnation_suppressed_in_act(self):
        """B6-a: stagnation does not fire in act state."""
        from app.game_engine.agent_runtime.policy.domains.quality_domain import stop_evaluator

        ctx = self._ctx(
            turn_count=0,
            current_state="act",
            recent_signatures=["a", "a", "a"],
            stagnation_window=3,
        )
        assert stop_evaluator(ctx) is None

    def test_no_stop_when_progressing(self):
        from app.game_engine.agent_runtime.policy.domains.quality_domain import stop_evaluator

        ctx = self._ctx(
            turn_count=1,
            current_state="do",
            consecutive_tool_failures=0,
            recent_signatures=["a", "b", "c"],
            stagnation_window=3,
        )
        assert stop_evaluator(ctx) is None


class TestStopEvaluatorReactRound:
    """B4 (P5-B2): stop_evaluator consumes react_round_decision (opt-in)."""

    def _ctx(self, **tick_state):
        from app.game_engine.agent_runtime.policy import PolicyContext
        from app.game_engine.agent_runtime.policy.check_points import CheckPoint

        return PolicyContext(
            check_point=CheckPoint.AFTER_STATE_EXECUTE,
            extra={"tick_state": {"enable_stop_dimensions": False, **tick_state}},
        )

    def test_fail_routes_to_fail(self):
        from app.game_engine.agent_runtime.policy.domains.quality_domain import stop_evaluator

        ctx = self._ctx(
            current_state="plan",
            react_round_decision={"decision": "fail", "reason_code": "criteria_unmet"},
        )
        d = stop_evaluator(ctx)
        assert d is not None
        assert d.decision == "fail"
        assert d.reason_code == "react_round_fail"

    def test_replan_routes_to_stagnation(self):
        from app.game_engine.agent_runtime.policy.domains.quality_domain import stop_evaluator

        ctx = self._ctx(
            current_state="do",
            react_round_decision={"decision": "replan", "reason_code": "criteria_unmet"},
        )
        d = stop_evaluator(ctx)
        assert d is not None
        assert d.decision == "replan"
        assert d.reason_code == "stagnation"

    def test_continue_yields_no_decision(self):
        from app.game_engine.agent_runtime.policy.domains.quality_domain import stop_evaluator

        ctx = self._ctx(
            current_state="plan",
            react_round_decision={"decision": "continue", "reason_code": "ok"},
        )
        assert stop_evaluator(ctx) is None

    def test_none_when_no_react_round_decision(self):
        from app.game_engine.agent_runtime.policy.domains.quality_domain import stop_evaluator

        ctx = self._ctx(current_state="plan")
        assert stop_evaluator(ctx) is None
