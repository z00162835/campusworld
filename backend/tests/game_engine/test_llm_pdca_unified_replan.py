"""B3 byte-equiv: unified check_replan preserves trace rows + replan_count.

After extracting check_retry/mandatory_gap detection into
``quality_domain.detect_check_replan``, the driver must still emit the same
trace rows (``mandatory_gap_retry_override`` / ``check_retry_triggered``) and
increment ``replan_count`` identically.
"""
from __future__ import annotations


def test_parse_check_retry_signal_moved_to_quality_domain():
    """The detection logic now lives in quality_domain (统一收归)."""
    from app.game_engine.agent_runtime.policy.domains.quality_domain import (
        parse_check_retry_signal,
    )

    assert parse_check_retry_signal("RETRY: need_tools=task") == ["task"]
    assert parse_check_retry_signal("no marker") is None


def test_detect_check_replan_check_retry_event():
    from app.game_engine.agent_runtime.policy.domains.quality_domain import (
        detect_check_replan,
    )

    event, retry_tools, gap_detail = detect_check_replan(
        check_out="RETRY: need_tools=task,agent",
        check_skipped=False,
        tool_router_snapshot=None,
        accumulated_tick_tool_results=[],
        plan_trace=[],
    )
    assert event == "check_retry"
    assert retry_tools == ["task", "agent"]
    assert gap_detail is None


def test_detect_check_replan_mandatory_gap_event():
    from app.game_engine.agent_runtime.policy.domains.quality_domain import (
        detect_check_replan,
    )

    event, retry_tools, gap_detail = detect_check_replan(
        check_out="looks good",
        check_skipped=False,
        tool_router_snapshot={"mandatory_tool_names": ["task"]},
        accumulated_tick_tool_results=[],  # missing → gap
        plan_trace=[],
    )
    assert event == "mandatory_gap"
    assert retry_tools == ["task"]
    assert gap_detail is not None
    assert "missing" in gap_detail or "failed" in gap_detail


def test_detect_check_replan_priority_check_retry_beats_mandatory_gap():
    """B3 priority: when both signals present, check_retry wins."""
    from app.game_engine.agent_runtime.policy.domains.quality_domain import (
        detect_check_replan,
    )

    event, _, _ = detect_check_replan(
        check_out="RETRY: need_tools=task",
        check_skipped=False,
        tool_router_snapshot={"mandatory_tool_names": ["task"]},
        accumulated_tick_tool_results=[],
        plan_trace=[],
    )
    assert event == "check_retry"
