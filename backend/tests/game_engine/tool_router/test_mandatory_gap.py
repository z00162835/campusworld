from __future__ import annotations

import pytest

from app.game_engine.agent_runtime.tool_calling import ToolResult
from app.game_engine.agent_runtime.tool_router.mandatory_gap import (
    format_mandatory_gap_user_notice,
    mandatory_observation_gap,
    normalize_command_name,
)


@pytest.mark.unit
def test_normalize_lowercase_and_trim():
    assert normalize_command_name("") == ""
    assert normalize_command_name("  Look  ") == "look"


@pytest.mark.unit
def test_gap_when_mandatory_never_called():
    has_gap, detail = mandatory_observation_gap(
        ["whoami"],
        [ToolResult(id="1", name="look", ok=True, text="x")],
    )
    assert has_gap is True
    assert "whoami" in detail["missing"]
    assert detail["reason_codes"] == ["mandatory_not_invoked"]


@pytest.mark.unit
def test_gap_when_mandatory_only_failed():
    has_gap, detail = mandatory_observation_gap(
        ["look"],
        [ToolResult(id="1", name="look", ok=False, text="err")],
    )
    assert has_gap is True
    assert "look" in detail["failed"]
    assert "mandatory_failed" in detail["reason_codes"]


@pytest.mark.unit
def test_no_gap_when_mandatory_succeeded():
    has_gap, detail = mandatory_observation_gap(
        ["look"],
        [ToolResult(id="1", name="look", ok=True, text="ok")],
    )
    assert has_gap is False
    assert detail["missing"] == []
    assert detail["failed"] == []


@pytest.mark.unit
def test_user_notice_non_empty_on_gap():
    text = format_mandatory_gap_user_notice({"missing": ["a"], "failed": [], "reason_codes": []})
    assert "a" in text


@pytest.mark.unit
def test_gap_adds_gather_budget_code_from_plan_trace():
    has_gap, detail = mandatory_observation_gap(
        ["look"],
        [],
        plan_trace=[
            {"phase": "plan", "step": "tool_cap", "detail": "tick_max_commands"},
        ],
    )
    assert has_gap is True
    assert "gather_budget_limited" in detail["reason_codes"]
    assert detail["gather_budget_limited"] is True


@pytest.mark.unit
def test_gap_adds_permission_denied_from_tool_exec():
    has_gap, detail = mandatory_observation_gap(
        ["whoami"],
        [],
        plan_trace=[
            {
                "phase": "plan",
                "step": "tool_exec",
                "command_name": "whoami",
                "success": False,
                "error": "Permission denied for caller",
            },
        ],
    )
    assert has_gap is True
    assert "permission_denied" in detail["reason_codes"]
    assert "whoami" in detail["permission_denied_tools"]


@pytest.mark.unit
def test_notice_mentions_permission_hint():
    text = format_mandatory_gap_user_notice(
        {
            "missing": ["x"],
            "failed": [],
            "reason_codes": ["mandatory_not_invoked", "permission_denied"],
        }
    )
    assert "权限" in text or "门禁" in text


@pytest.mark.unit
def test_gap_reports_tick_wide_observed_phases():
    has_gap, detail = mandatory_observation_gap(
        ["look"],
        [ToolResult(id="1", name="look", ok=True, text="ok")],
        plan_trace=[
            {"phase": "plan", "step": "plan"},
            {"phase": "do", "step": "tool_exec", "command_name": "look", "success": True},
        ],
    )
    assert has_gap is False
    assert "do" in detail["checked_phases"]
    assert "look" in detail["observed_tools"]
    assert detail["observed_phases_by_tool"]["look"] == ["do"]
