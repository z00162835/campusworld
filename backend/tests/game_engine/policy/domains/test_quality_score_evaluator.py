"""Tests for quality_score_evaluator — layered scoring (S2/S3/S4), default-off."""
from __future__ import annotations

from app.game_engine.agent_runtime.policy import PolicyContext
from app.game_engine.agent_runtime.policy.check_points import CheckPoint
from app.game_engine.agent_runtime.policy.domains.quality_domain import (
    compute_quality_score,
    quality_score_evaluator,
    _grounding_quality,
    _criteria_coverage,
    _progress,
)


class TestGroundingQuality:
    def test_empty_draft_vacuously_satisfied(self):
        assert _grounding_quality("", []) == 1.0

    def test_nonempty_draft_no_observations_scores_zero(self):
        assert _grounding_quality("hello world", []) == 0.0

    def test_full_overlap_scores_one(self):
        class _Obs:
            text = "hello world"
        assert _grounding_quality("hello world", [_Obs()]) == 1.0

    def test_partial_overlap(self):
        class _Obs:
            text = "hello there"
        score = _grounding_quality("hello world", [_Obs()])
        # "hello" covered, "world" not → 1/2
        assert 0.0 < score < 1.0


class TestCriteriaCoverage:
    def test_no_criteria_vacuously_satisfied(self):
        assert _criteria_coverage("draft", []) == 1.0

    def test_all_criteria_covered(self):
        assert _criteria_coverage("the task list shows items", ["task list"]) == 1.0

    def test_no_criteria_covered(self):
        assert _criteria_coverage("unrelated text", ["task list"]) == 0.0

    def test_partial_coverage(self):
        score = _criteria_coverage("task done", ["task list", "task done"])
        assert score == 0.5


class TestProgress:
    def test_empty_signatures_not_stagnating(self):
        assert _progress(3, []) == 1.0

    def test_single_signature_not_stagnating(self):
        assert _progress(3, ["sig_a"]) == 1.0

    def test_identical_window_stagnating(self):
        assert _progress(3, ["sig_a", "sig_a", "sig_a"]) == 0.0

    def test_varied_signatures_progressing(self):
        assert _progress(3, ["sig_a", "sig_b", "sig_c"]) == 1.0

    def test_abab_cycle_stagnating_r6(self):
        """R6: A→B→A→B cycle (last 2K signatures collapse to ≤ 2 distinct)."""
        assert _progress(3, ["a", "b", "a", "b", "a", "b"]) == 0.0

    def test_abcabc_not_stagnating(self):
        """3 distinct values in a 6-window is not a 2-cycle."""
        assert _progress(3, ["a", "b", "c", "a", "b", "c"]) == 1.0

    def test_short_cycle_window_not_stagnating(self):
        """Fewer than 2K signatures cannot trigger the cycle rule."""
        assert _progress(3, ["a", "b", "a"]) == 1.0


class TestComputeQualityScore:
    def test_returns_three_layers(self):
        score = compute_quality_score(
            draft_text="hello world",
            tool_results=[],
            success_criteria=[],
            recent_signatures=[],
            stagnation_window=3,
        )
        assert set(score.keys()) == {"surface", "process", "semantic"}
        assert 0.0 <= score["surface"] <= 1.0
        assert 0.0 <= score["process"] <= 1.0
        assert 0.0 <= score["semantic"] <= 1.0

    def test_semantic_dominated_by_grounding(self):
        class _Obs:
            text = "hello world"
        score = compute_quality_score(
            draft_text="hello world",
            tool_results=[_Obs()],
            success_criteria=[],
            recent_signatures=[],
            stagnation_window=3,
        )
        assert score["semantic"] > 0.5


class TestQualityScoreEvaluator:
    def test_returns_none_when_disabled(self):
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TERMINAL,
            extra={"tick_state": {"enable_quality_score": False}},
        )
        assert quality_score_evaluator(ctx) is None

    def test_returns_none_when_no_tick_state(self):
        ctx = PolicyContext(check_point=CheckPoint.BEFORE_TERMINAL)
        assert quality_score_evaluator(ctx) is None

    def test_returns_none_at_wrong_check_point(self):
        ctx = PolicyContext(
            check_point=CheckPoint.AFTER_STATE_EXECUTE,
            extra={"tick_state": {"enable_quality_score": True}},
        )
        assert quality_score_evaluator(ctx) is None

    def test_returns_allow_with_score_when_enabled(self):
        class _Obs:
            text = "hello world"
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TERMINAL,
            extra={
                "tick_state": {
                    "enable_quality_score": True,
                    "draft_text": "hello world",
                    "tool_results": [_Obs()],
                    "success_criteria": [],
                    "recent_signatures": [],
                    "stagnation_window": 3,
                }
            },
        )
        decision = quality_score_evaluator(ctx)
        assert decision is not None
        assert decision.is_allow is True
        assert decision.quality_score is not None
        assert "semantic" in decision.quality_score

    def test_does_not_block_when_enabled(self):
        """v1: quality_score is audit-only; even a low score returns allow."""
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TERMINAL,
            extra={
                "tick_state": {
                    "enable_quality_score": True,
                    "draft_text": "completely unrelated gibberish",
                    "tool_results": [],
                    "success_criteria": ["task list"],
                    "recent_signatures": ["sig", "sig", "sig"],
                    "stagnation_window": 3,
                }
            },
        )
        decision = quality_score_evaluator(ctx)
        assert decision is not None
        assert decision.is_allow is True
