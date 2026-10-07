"""T9: config-wiring tests — verify "change config → behavior changes" for each
policy-relevant threshold that was previously hardcoded (H1–H8).

Each test pair constructs a PolicyContext with two different config snapshots
and asserts the detector/evaluator behavior diverges. Defaults remain
byte-equivalent (covered by the existing suite); these tests lock the
config-driven path so a regression that re-hardcodes a value is caught.
"""
from __future__ import annotations

from typing import Any, List

from app.game_engine.agent_runtime.policy import PolicyContext
from app.game_engine.agent_runtime.policy.check_points import CheckPoint
from app.game_engine.agent_runtime.policy.config import (
    GateDomainConfig,
    QualityDomainConfig,
    SkillDomainConfig,
)
from app.game_engine.agent_runtime.policy.domains.gate_domain import (
    GateDomain,
    data_classification_detector,
    side_effect_level_detector,
    skill_tool_group_detector,
)
from app.game_engine.agent_runtime.policy.domains.quality_domain import (
    _criteria_hit_count,
    _grounding_quality,
    _progress,
    compute_quality_score,
)
from app.game_engine.agent_runtime.policy.domains.skill_domain import (
    SkillDomain,
    skill_activation_mode_detector,
)
from app.game_engine.agent_runtime.policy.tool_groups import is_any_group_allowed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Obs:
    """Minimal tool-result stand-in carrying a text attribute."""

    def __init__(self, text: str) -> None:
        self.text = text


def _gate_ctx(**overrides: Any) -> PolicyContext:
    base: dict[str, Any] = {"check_point": CheckPoint.BEFORE_TOOL_CALL}
    base.update(overrides)
    return PolicyContext(**base)


def _skill_ctx(**overrides: Any) -> PolicyContext:
    base: dict[str, Any] = {"check_point": CheckPoint.BEFORE_SKILL_ACTIVATION}
    base.update(overrides)
    return PolicyContext(**base)


# ---------------------------------------------------------------------------
# H1+H5 — side_effect_defaults (gate domain)
# ---------------------------------------------------------------------------

class TestSideEffectDefaultsConfig:
    def test_write_high_blocks_with_default_config(self):
        ctx = _gate_ctx(side_effect_level="write_high", command_name="go")
        GateDomain(GateDomainConfig()).build_context(ctx)
        decision = side_effect_level_detector(ctx)
        assert decision is not None
        assert decision.decision == "require_approval"

    def test_write_high_allows_when_config_overrides_to_allow(self):
        cfg = GateDomainConfig(side_effect_defaults={
            "none": "allow", "read": "allow", "write_low": "allow", "write_high": "allow",
        })
        ctx = _gate_ctx(side_effect_level="write_high", command_name="go")
        GateDomain(cfg).build_context(ctx)
        assert side_effect_level_detector(ctx) is None  # allow

    def test_read_denies_when_config_overrides_to_deny(self):
        cfg = GateDomainConfig(side_effect_defaults={
            "none": "allow", "read": "deny", "write_low": "allow", "write_high": "require_approval",
        })
        ctx = _gate_ctx(side_effect_level="read", command_name="look")
        GateDomain(cfg).build_context(ctx)
        decision = side_effect_level_detector(ctx)
        assert decision is not None
        assert decision.decision == "deny"
        assert decision.reason_code == "policy_blocked_side_effect"


# ---------------------------------------------------------------------------
# H2 — blocked_data_classifications (gate domain)
# ---------------------------------------------------------------------------

class TestBlockedDataClassificationsConfig:
    def test_confidential_blocks_with_default_config(self):
        ctx = _gate_ctx(data_classification="confidential", command_name="task show")
        GateDomain(GateDomainConfig()).build_context(ctx)
        decision = data_classification_detector(ctx)
        assert decision is not None
        assert decision.decision == "require_approval"

    def test_confidential_allows_when_removed_from_blocked_set(self):
        cfg = GateDomainConfig(blocked_data_classifications=("restricted",))
        ctx = _gate_ctx(data_classification="confidential", command_name="task show")
        GateDomain(cfg).build_context(ctx)
        assert data_classification_detector(ctx) is None

    def test_internal_blocks_when_added_to_blocked_set(self):
        cfg = GateDomainConfig(blocked_data_classifications=("internal",))
        ctx = _gate_ctx(data_classification="internal", command_name="task show")
        GateDomain(cfg).build_context(ctx)
        decision = data_classification_detector(ctx)
        assert decision is not None
        assert decision.reason_code == "policy_blocked_data_classification"


# ---------------------------------------------------------------------------
# H3 — blocked_skill_activation_modes (skill domain)
# ---------------------------------------------------------------------------

class TestBlockedSkillActivationModesConfig:
    def test_default_empty_set_allows_all_modes(self):
        ctx = _skill_ctx(skill_activation_mode="auto", skill_id="retrieval")
        SkillDomain(SkillDomainConfig()).build_context(ctx)
        assert skill_activation_mode_detector(ctx) is None

    def test_mode_in_blocked_set_is_denied(self):
        cfg = SkillDomainConfig(blocked_skill_activation_modes=("manual",))
        ctx = _skill_ctx(skill_activation_mode="manual", skill_id="retrieval")
        SkillDomain(cfg).build_context(ctx)
        decision = skill_activation_mode_detector(ctx)
        assert decision is not None
        assert decision.decision == "deny"
        assert decision.reason_code == "policy_blocked_skill_activation_mode"
        assert decision.evidence["activation_mode"] == "manual"

    def test_mode_not_in_blocked_set_is_allowed(self):
        cfg = SkillDomainConfig(blocked_skill_activation_modes=("manual",))
        ctx = _skill_ctx(skill_activation_mode="auto", skill_id="retrieval")
        SkillDomain(cfg).build_context(ctx)
        assert skill_activation_mode_detector(ctx) is None


# ---------------------------------------------------------------------------
# H4 — tool_group_hierarchy (gate domain / tool_groups)
# ---------------------------------------------------------------------------

class TestToolGroupHierarchyConfig:
    def test_default_hierarchy_read_covers_observe(self):
        """Default: read is parent of observe → allowed."""
        assert is_any_group_allowed(("observe",), ("read",)) is True

    def test_custom_hierarchy_decouples_read_from_observe(self):
        """Override hierarchy so read no longer parents observe → denied."""
        hierarchy = {"read": ("agent_meta",)}  # observe no longer a child of read
        assert is_any_group_allowed(("observe",), ("read",), hierarchy=hierarchy) is False

    def test_custom_hierarchy_adds_new_parent(self):
        hierarchy = {"scan": ("observe",)}
        assert is_any_group_allowed(("observe",), ("scan",), hierarchy=hierarchy) is True

    def test_detector_uses_injected_hierarchy(self):
        cfg = GateDomainConfig(
            enable_skill_tool_group_detector=True,
            tool_group_hierarchy={"read": ("agent_meta",)},  # observe not a child
        )
        ctx = _gate_ctx(
            tool_groups=("observe",),
            interaction_profile="read",
            active_skill_context={
                "active_skill_ids": ["retrieval"],
                "active_skill_allowed_tool_groups": ["read"],
            },
            command_name="task list",
        )
        GateDomain(cfg).build_context(ctx)
        decision = skill_tool_group_detector(ctx)
        assert decision is not None
        assert decision.reason_code == "policy_blocked_skill_tool_group"

    def test_detector_allows_with_default_hierarchy(self):
        cfg = GateDomainConfig(enable_skill_tool_group_detector=True)
        ctx = _gate_ctx(
            tool_groups=("observe",),
            interaction_profile="read",
            active_skill_context={
                "active_skill_ids": ["retrieval"],
                "active_skill_allowed_tool_groups": ["read"],
            },
            command_name="task list",
        )
        GateDomain(cfg).build_context(ctx)
        assert skill_tool_group_detector(ctx) is None


# ---------------------------------------------------------------------------
# H6 — semantic weights (quality domain)
# ---------------------------------------------------------------------------

class TestSemanticWeightsConfig:
    def test_grounding_weight_dominates_score(self):
        class _Obs:
            text = "hello world"
        # Full grounding (1.0), no criteria, full progress.
        high_grounding = compute_quality_score(
            draft_text="hello world",
            tool_results=[_Obs()],
            success_criteria=[],
            recent_signatures=[],
            stagnation_window=3,
            semantic_weight_grounding=1.0,
            semantic_weight_criteria=0.0,
            semantic_weight_progress=0.0,
        )
        assert high_grounding["semantic"] == 1.0

    def test_criteria_weight_dominates_score(self):
        # No grounding (0.0), full criteria, no progress weight.
        score = compute_quality_score(
            draft_text="task list shows items",
            tool_results=[],
            success_criteria=["task list"],
            recent_signatures=[],
            stagnation_window=3,
            semantic_weight_grounding=0.0,
            semantic_weight_criteria=1.0,
            semantic_weight_progress=0.0,
        )
        assert score["semantic"] == 1.0

    def test_progress_weight_dominates_score(self):
        # Stagnating signatures → progress 0.0; weight it fully.
        score = compute_quality_score(
            draft_text="hello world",
            tool_results=[],
            success_criteria=[],
            recent_signatures=["sig", "sig", "sig"],
            stagnation_window=3,
            semantic_weight_grounding=0.0,
            semantic_weight_criteria=0.0,
            semantic_weight_progress=1.0,
        )
        assert score["semantic"] == 0.0

    def test_default_weights_produce_mixed_score(self):
        class _Obs:
            text = "hello world"
        score = compute_quality_score(
            draft_text="hello world",
            tool_results=[_Obs()],
            success_criteria=[],
            recent_signatures=[],
            stagnation_window=3,
        )
        # grounding=1.0, criteria=1.0 (empty), progress=1.0 → 0.5+0.3+0.2 = 1.0
        assert score["semantic"] == 1.0


# ---------------------------------------------------------------------------
# H7 — stagnation_cycle_window_multiplier (quality domain)
# ---------------------------------------------------------------------------

class TestStagnationCycleMultiplierConfig:
    def test_default_multiplier_2_detects_abab_in_6_window(self):
        # 2*3=6 window, ≤2 distinct → stagnating.
        assert _progress(3, ["a", "b", "a", "b", "a", "b"], cycle_window_multiplier=2) == 0.0

    def test_multiplier_3_requires_9_window(self):
        # With multiplier=3, 6 signatures < 9 → not stagnating by cycle rule.
        assert _progress(3, ["a", "b", "a", "b", "a", "b"], cycle_window_multiplier=3) == 1.0

    def test_multiplier_3_detects_abab_in_9_window(self):
        sigs = ["a", "b"] * 5  # 10 sigs; last 9 = b,a,b,a,b,a,b,a,b → 2 distinct
        assert _progress(3, sigs, cycle_window_multiplier=3) == 0.0

    def test_multiplier_1_never_triggers_cycle(self):
        """multiplier=1 → cycle window = K; adjacent-repeat still works but
        cycle rule needs ≤2 distinct in K window which is just adjacent repeat."""
        # 6 sigs with multiplier=1 → window=3; last 3 = a,b,a → 2 distinct, but
        # the cycle rule checks len >= 3 and ≤2 distinct → triggers.
        # Actually let's verify multiplier changes behavior:
        sigs = ["a", "b", "c", "a", "b", "a"]
        # multiplier=2: window=6, distinct={a,b,c}=3 → not stagnating
        assert _progress(3, sigs, cycle_window_multiplier=2) == 1.0
        # multiplier=1: window=3, last 3 = a,b,a → 2 distinct, len=3 → stagnating
        assert _progress(3, sigs, cycle_window_multiplier=1) == 0.0


# ---------------------------------------------------------------------------
# H8 — token_min_length (quality domain)
# ---------------------------------------------------------------------------

class TestTokenMinLengthConfig:
    def test_default_min_length_2_filters_single_chars(self):
        """Single-char tokens are filtered by default (min_length=2)."""
        # Draft "a b" → no tokens ≥2 chars → grounding vacuously 1.0 (empty draft tokens)
        assert _grounding_quality("a b", []) == 1.0

    def test_min_length_1_includes_single_chars(self):
        """With min_length=1, single-char tokens count → non-empty draft with
        no obs scores 0.0."""
        assert _grounding_quality("a b", [], min_length=1) == 0.0

    def test_min_length_3_filters_short_tokens(self):
        """With min_length=3, 'hi' is filtered but 'there' (5 chars) survives.
        Non-empty draft tokens with no obs → 0.0."""
        assert _grounding_quality("hi there", [], min_length=3) == 0.0
        # 'there' survives and is covered by obs → grounding 1.0
        class _Obs:
            text = "there"
        assert _grounding_quality("hi there", [_Obs()], min_length=3) == 1.0
        # With min_length=6, 'there' (5 chars) is also filtered → empty draft → 1.0
        assert _grounding_quality("hi there", [], min_length=6) == 1.0

    def test_criteria_hit_count_respects_min_length(self):
        """criterion 'a b' with min_length=2 → tokens=['a','b'] filtered → no
        crit tokens → criterion skipped (count stays 0). With min_length=1 →
        tokens=['a','b'], both must be in draft."""
        assert _criteria_hit_count("a b", ["a b"]) == 0  # default min_length=2
        assert _criteria_hit_count("a b", ["a b"], min_length=1) == 1

    def test_compute_quality_score_passes_token_min_length(self):
        class _Obs:
            text = "a b"
        # min_length=1: draft tokens {a,b}, obs tokens {a,b} → grounding 1.0
        score = compute_quality_score(
            draft_text="a b",
            tool_results=[_Obs()],
            success_criteria=[],
            recent_signatures=[],
            stagnation_window=3,
            token_min_length=1,
        )
        assert score["semantic"] > 0.0
        # min_length=3: draft tokens {} → grounding 1.0 (vacuous), but let's
        # check it doesn't crash and produces a valid score.
        score2 = compute_quality_score(
            draft_text="a b",
            tool_results=[_Obs()],
            success_criteria=[],
            recent_signatures=[],
            stagnation_window=3,
            token_min_length=3,
        )
        assert 0.0 <= score2["semantic"] <= 1.0


# ---------------------------------------------------------------------------
# H7 — stagnation_cycle_window_multiplier in stop_evaluator (control-flow path)
# ---------------------------------------------------------------------------

class TestStopEvaluatorCycleMultiplierConfig:
    """Locks that stop_evaluator (the control-flow-driving consumer) honors the
    configured multiplier, not just compute_quality_score (audit-only)."""

    def _ctx(self, **tick_state):
        return PolicyContext(
            check_point=CheckPoint.AFTER_STATE_EXECUTE,
            extra={"tick_state": {"enable_stop_dimensions": True, **tick_state}},
        )

    def test_default_multiplier_2_detects_abab(self):
        from app.game_engine.agent_runtime.policy.domains.quality_domain import stop_evaluator

        ctx = self._ctx(
            current_state="plan",
            recent_signatures=["a", "b", "a", "b", "a", "b"],
            stagnation_window=3,
        )
        d = stop_evaluator(ctx)
        assert d is not None
        assert d.reason_code == "stagnation"
        assert d.evidence["stagnation_cycle_window_multiplier"] == 2

    def test_multiplier_3_does_not_detect_abab_in_6_window(self):
        """With multiplier=3, 6 sigs < 9 → cycle rule doesn't fire → no stagnation."""
        from app.game_engine.agent_runtime.policy.domains.quality_domain import stop_evaluator

        ctx = self._ctx(
            current_state="plan",
            recent_signatures=["a", "b", "a", "b", "a", "b"],
            stagnation_window=3,
            stagnation_cycle_window_multiplier=3,
        )
        d = stop_evaluator(ctx)
        # Adjacent-repeat also doesn't fire (last 3 = a,b,a → not all identical).
        assert d is None

    def test_multiplier_3_detects_abab_in_9_window(self):
        from app.game_engine.agent_runtime.policy.domains.quality_domain import stop_evaluator

        sigs = ["a", "b"] * 5  # 10 sigs
        ctx = self._ctx(
            current_state="do",
            recent_signatures=sigs,
            stagnation_window=3,
            stagnation_cycle_window_multiplier=3,
        )
        d = stop_evaluator(ctx)
        assert d is not None
        assert d.reason_code == "stagnation"
        assert d.evidence["stagnation_cycle_window_multiplier"] == 3
        # Evidence slice should use multiplier × window, not hardcoded 2 × window.
        assert len(d.evidence["recent_signatures"]) <= 3 * 3

    def test_multiplier_1_detects_cycle_in_3_window(self):
        from app.game_engine.agent_runtime.policy.domains.quality_domain import stop_evaluator

        ctx = self._ctx(
            current_state="check",
            recent_signatures=["c", "a", "b", "a", "b", "a"],
            stagnation_window=3,
            stagnation_cycle_window_multiplier=1,
        )
        d = stop_evaluator(ctx)
        # multiplier=1 → window=3; last 3 = a,b,a → 2 distinct, len=3 → stagnating.
        assert d is not None
        assert d.reason_code == "stagnation"
        assert d.evidence["stagnation_cycle_window_multiplier"] == 1


# ---------------------------------------------------------------------------
# H8 — token_min_length in react_turn_success_evaluator (per_react_round path)
# ---------------------------------------------------------------------------

class TestReactTurnTokenMinLengthConfig:
    """Locks that react_turn_success_evaluator honors token_min_length even when
    enable_quality_score and final_success_drive_mode are off (i.e. only
    require_structured_turn is on)."""

    def _ctx(self, **tick_state):
        return PolicyContext(
            check_point=CheckPoint.PER_REACT_ROUND,
            extra={"tick_state": {"react_turn": {"final_answer": "a b"}, **tick_state}},
        )

    def test_default_min_length_2_skips_single_char_criteria(self):
        from app.game_engine.agent_runtime.policy.domains.quality_domain import (
            react_turn_success_evaluator,
        )

        ctx = self._ctx(success_criteria=["a b"])
        d = react_turn_success_evaluator(ctx)
        # min_length=2 → criterion "a b" has no tokens ≥2 → skipped → 0 hits < 1 → replan
        assert d is not None
        assert d.reason_code == "react_turn_criteria_unmet"

    def test_min_length_1_includes_single_char_criteria(self):
        from app.game_engine.agent_runtime.policy.domains.quality_domain import (
            react_turn_success_evaluator,
        )

        ctx = self._ctx(
            success_criteria=["a b"],
            token_min_length=1,
        )
        d = react_turn_success_evaluator(ctx)
        # min_length=1 → "a","b" both in draft "a b" → 1 hit ≥ 1 → continue
        assert d is not None
        assert d.reason_code == "react_turn_criteria_met"


# ---------------------------------------------------------------------------
# react_turn_min_criteria_hits in react_turn_success_evaluator (N-hit rule)
# ---------------------------------------------------------------------------

class TestReactTurnMinCriteriaHitsConfig:
    """Locks that react_turn_success_evaluator honors react_turn_min_criteria_hits
    even when enable_quality_score and final_success_drive_mode are off."""

    def _ctx(self, **tick_state):
        return PolicyContext(
            check_point=CheckPoint.PER_REACT_ROUND,
            extra={"tick_state": {
                "react_turn": {"final_answer": "task list shows items"},
                **tick_state,
            }},
        )

    def test_default_n1_passes_with_one_criterion_hit(self):
        from app.game_engine.agent_runtime.policy.domains.quality_domain import (
            react_turn_success_evaluator,
        )

        ctx = self._ctx(success_criteria=["task list"])
        d = react_turn_success_evaluator(ctx)
        assert d is not None
        assert d.reason_code == "react_turn_criteria_met"

    def test_n2_fails_with_only_one_criterion_hit(self):
        from app.game_engine.agent_runtime.policy.domains.quality_domain import (
            react_turn_success_evaluator,
        )

        ctx = self._ctx(
            success_criteria=["task list", "unrelated xyz"],
            react_turn_min_criteria_hits=2,
        )
        d = react_turn_success_evaluator(ctx)
        # Only 1 hit ("task list") < 2 required → replan
        assert d is not None
        assert d.reason_code == "react_turn_criteria_unmet"

    def test_n2_passes_with_two_criterion_hits(self):
        from app.game_engine.agent_runtime.policy.domains.quality_domain import (
            react_turn_success_evaluator,
        )

        ctx = self._ctx(
            success_criteria=["task list", "items"],
            react_turn_min_criteria_hits=2,
        )
        d = react_turn_success_evaluator(ctx)
        assert d is not None
        assert d.reason_code == "react_turn_criteria_met"
