"""Tests for S5: structured Check output parsing (PASS|RETRY|FAIL)."""
from __future__ import annotations

from app.game_engine.agent_runtime.policy.domains.quality_domain import (
    parse_structured_check_output,
)


class TestParseStructuredCheckOutput:
    def test_pass(self):
        result = parse_structured_check_output("PASS")
        assert result["verdict"] == "pass"
        assert result["need_tools"] == []
        assert result["reason"] == ""

    def test_pass_with_trailing_text(self):
        result = parse_structured_check_output("PASS - all criteria met")
        assert result["verdict"] == "pass"

    def test_retry_with_need_tools(self):
        result = parse_structured_check_output("RETRY: need_tools=task,agent")
        assert result["verdict"] == "retry"
        assert result["need_tools"] == ["task", "agent"]

    def test_retry_without_tools(self):
        result = parse_structured_check_output("RETRY: need_tools=")
        assert result["verdict"] == "retry"
        assert result["need_tools"] == []

    def test_fail_with_reason(self):
        result = parse_structured_check_output("FAIL: reason=grounding insufficient")
        assert result["verdict"] == "fail"
        assert result["reason"] == "grounding insufficient"

    def test_fail_without_reason(self):
        result = parse_structured_check_output("FAIL")
        assert result["verdict"] == "fail"
        assert result["reason"] == ""

    def test_case_insensitive(self):
        assert parse_structured_check_output("pass")["verdict"] == "pass"
        assert parse_structured_check_output("Retry: need_tools=task")["verdict"] == "retry"

    def test_empty_text_returns_unknown(self):
        result = parse_structured_check_output("")
        assert result["verdict"] == "unknown"

    def test_free_text_falls_back_to_legacy_heuristic(self):
        """When the output doesn't follow the structured shape, fall back to the
        legacy ``'error' not in co.lower()[:80]`` heuristic for byte-equiv."""
        result = parse_structured_check_output("The answer looks good, all criteria met.")
        assert result["verdict"] == "pass"
        result_err = parse_structured_check_output("error: something went wrong")
        assert result_err["verdict"] == "fail"

    def test_replaces_substring_heuristic_verification_passed(self):
        """S5: the structured parser replaces the legacy substring heuristic
        ``verification_passed`` (which was ``'error' not in co.lower()[:80]``)."""
        # Legacy: 'error' in first 80 chars → fail
        legacy_fail = "error" in "error: bad grounding"[:80].lower()
        structured = parse_structured_check_output("error: bad grounding")
        assert legacy_fail is True
        assert structured["verdict"] == "fail"
        # Legacy: no 'error' → pass
        legacy_pass = "error" not in "all good here"[:80].lower()
        structured_pass = parse_structured_check_output("all good here")
        assert legacy_pass is True
        assert structured_pass["verdict"] == "pass"
