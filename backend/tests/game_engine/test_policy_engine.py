"""Unit tests for the F16 PolicyEngine and detectors."""
from __future__ import annotations

from app.game_engine.agent_runtime.policy import PolicyContext, PolicyDecision, PolicyEngine
from app.game_engine.agent_runtime.policy.check_points import CheckPoint
from app.game_engine.agent_runtime.policy.detectors import (
    data_classification_detector,
    side_effect_level_detector,
    skill_activation_mode_detector,
    skill_tool_group_detector,
)


class TestPolicyDecision:
    def test_allow_factory(self):
        d = PolicyDecision.allow(CheckPoint.BEFORE_TOOL_CALL)
        assert d.decision == "allow"
        assert d.runtime_action == "pass"
        assert d.is_allow is True
        assert d.is_block is False

    def test_deny_factory(self):
        d = PolicyDecision.deny(CheckPoint.BEFORE_TOOL_CALL, "test_deny")
        assert d.decision == "deny"
        assert d.runtime_action == "block"
        assert d.is_block is True
        assert d.is_allow is False

    def test_require_approval_degrades_to_block(self):
        d = PolicyDecision.require_approval(CheckPoint.BEFORE_TOOL_CALL, "test_ra")
        assert d.decision == "require_approval"
        assert d.runtime_action == "block"
        assert d.is_block is True


class TestSideEffectLevelDetector:
    def test_write_high_blocks(self):
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="task",
            side_effect_level="write_high",
        )
        decision = side_effect_level_detector(ctx)
        assert decision is not None
        assert decision.is_block is True
        assert decision.reason_code == "policy_blocked_side_effect_write_high"
        assert decision.evidence["side_effect_level"] == "write_high"

    def test_write_low_allows(self):
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            side_effect_level="write_low",
        )
        assert side_effect_level_detector(ctx) is None

    def test_read_allows(self):
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            side_effect_level="read",
        )
        assert side_effect_level_detector(ctx) is None

    def test_wrong_check_point_skipped(self):
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_SKILL_ACTIVATION,
            side_effect_level="write_high",
        )
        assert side_effect_level_detector(ctx) is None


class TestDataClassificationDetector:
    def test_confidential_blocks(self):
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            data_classification="confidential",
        )
        decision = data_classification_detector(ctx)
        assert decision is not None
        assert decision.is_block is True
        assert decision.reason_code == "policy_blocked_data_classification"

    def test_restricted_blocks(self):
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            data_classification="restricted",
        )
        decision = data_classification_detector(ctx)
        assert decision is not None
        assert decision.is_block is True

    def test_public_allows(self):
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            data_classification="public",
        )
        assert data_classification_detector(ctx) is None

    def test_internal_allows(self):
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            data_classification="internal",
        )
        assert data_classification_detector(ctx) is None

    def test_none_allows(self):
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            data_classification=None,
        )
        assert data_classification_detector(ctx) is None


class TestSkillActivationModeDetector:
    def test_prompt_mode_allows(self):
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_SKILL_ACTIVATION,
            skill_id="test_skill",
            skill_activation_mode="prompt",
        )
        assert skill_activation_mode_detector(ctx) is None

    def test_wrong_check_point_skipped(self):
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            skill_activation_mode="prompt",
        )
        assert skill_activation_mode_detector(ctx) is None


class TestToolGroupHierarchy:
    """Tests for the tool_group parent/child matching (SPEC §4.4)."""

    def test_read_parent_covers_observe(self):
        from app.game_engine.agent_runtime.policy.tool_groups import is_group_allowed
        assert is_group_allowed("observe", ("read",)) is True

    def test_read_parent_covers_agent_meta(self):
        from app.game_engine.agent_runtime.policy.tool_groups import is_group_allowed
        assert is_group_allowed("agent_meta", ("read",)) is True

    def test_read_parent_covers_identity(self):
        from app.game_engine.agent_runtime.policy.tool_groups import is_group_allowed
        assert is_group_allowed("identity", ("read",)) is True

    def test_read_parent_covers_communicate(self):
        from app.game_engine.agent_runtime.policy.tool_groups import is_group_allowed
        assert is_group_allowed("communicate", ("read",)) is True

    def test_read_exact_match(self):
        from app.game_engine.agent_runtime.policy.tool_groups import is_group_allowed
        assert is_group_allowed("read", ("read",)) is True

    def test_observe_does_not_cover_agent_meta(self):
        from app.game_engine.agent_runtime.policy.tool_groups import is_group_allowed
        assert is_group_allowed("agent_meta", ("observe",)) is False

    def test_observe_does_not_cover_read(self):
        from app.game_engine.agent_runtime.policy.tool_groups import is_group_allowed
        assert is_group_allowed("read", ("observe",)) is False

    def test_mutate_not_covered_by_read(self):
        from app.game_engine.agent_runtime.policy.tool_groups import is_group_allowed
        assert is_group_allowed("mutate", ("read",)) is False

    def test_any_group_allowed(self):
        from app.game_engine.agent_runtime.policy.tool_groups import is_any_group_allowed
        assert is_any_group_allowed(("read",), ("read",)) is True
        assert is_any_group_allowed(("observe",), ("read",)) is True
        assert is_any_group_allowed(("mutate",), ("read",)) is False
        assert is_any_group_allowed(("read", "mutate"), ("read",)) is True
        assert is_any_group_allowed(("mutate",), ("mutate",)) is True


class TestSkillToolGroupDetector:
    def test_read_command_allowed_by_read_skill(self):
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="help",
            interaction_profile="read",
            tool_groups=("read",),
            active_skill_context={
                "active_skill_ids": ["problem_framing"],
                "active_skill_allowed_tool_groups": ["read"],
            },
        )
        assert skill_tool_group_detector(ctx) is None

    def test_observe_command_allowed_by_read_skill(self):
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="task",
            interaction_profile="read",
            tool_groups=("observe",),
            active_skill_context={
                "active_skill_ids": ["problem_framing"],
                "active_skill_allowed_tool_groups": ["read"],
            },
        )
        assert skill_tool_group_detector(ctx) is None

    def test_mutate_command_denied_by_read_skill(self):
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="task",
            interaction_profile="mutate",
            tool_groups=("mutate",),
            active_skill_context={
                "active_skill_ids": ["problem_framing"],
                "active_skill_allowed_tool_groups": ["read"],
            },
        )
        decision = skill_tool_group_detector(ctx)
        assert decision is not None
        assert decision.is_block is True
        assert decision.reason_code == "policy_blocked_skill_tool_group"

    def test_no_active_skills_does_not_deny(self):
        """When active_skill_ids is empty, detector must not fire (forward compat)."""
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="task",
            interaction_profile="mutate",
            tool_groups=("mutate",),
            active_skill_context={
                "active_skill_ids": [],
                "active_skill_allowed_tool_groups": [],
            },
        )
        assert skill_tool_group_detector(ctx) is None

    def test_missing_active_skill_context_does_not_deny(self):
        """When active_skill_context is None, detector must not fire."""
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="task",
            interaction_profile="mutate",
            tool_groups=("mutate",),
            active_skill_context=None,
        )
        assert skill_tool_group_detector(ctx) is None

    def test_skills_with_no_groups_does_not_deny(self):
        """When skills declare no allowed_tool_groups, allow everything."""
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="task",
            interaction_profile="mutate",
            tool_groups=("mutate",),
            active_skill_context={
                "active_skill_ids": ["custom_skill"],
                "active_skill_allowed_tool_groups": [],
            },
        )
        assert skill_tool_group_detector(ctx) is None

    def test_observe_skill_denies_agent_meta(self):
        """[observe] skill should not allow agent_meta commands."""
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="agent",
            interaction_profile="read",
            tool_groups=("agent_meta",),
            active_skill_context={
                "active_skill_ids": ["narrow_skill"],
                "active_skill_allowed_tool_groups": ["observe"],
            },
        )
        decision = skill_tool_group_detector(ctx)
        assert decision is not None
        assert decision.is_block is True

    def test_multiple_command_groups_any_match_allows(self):
        """If any of the command's groups is covered, allow."""
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="task",
            interaction_profile="mutate",
            tool_groups=("observe", "mutate"),
            active_skill_context={
                "active_skill_ids": ["problem_framing"],
                "active_skill_allowed_tool_groups": ["read"],
            },
        )
        # observe is covered by read parent → allow (even though mutate is not)
        assert skill_tool_group_detector(ctx) is None

    def test_wrong_check_point_skipped(self):
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_SKILL_ACTIVATION,
            active_skill_context={
                "active_skill_ids": ["x"],
                "active_skill_allowed_tool_groups": ["read"],
            },
        )
        assert skill_tool_group_detector(ctx) is None


class TestPolicyEngine:
    def test_no_detectors_returns_allow(self):
        engine = PolicyEngine(detectors=[])
        ctx = PolicyContext(check_point=CheckPoint.BEFORE_TOOL_CALL)
        decision = engine.evaluate(ctx)
        assert decision.is_allow is True
        assert decision.reason_code == "policy_pass"

    def test_write_high_blocks_through_engine(self):
        engine = PolicyEngine()
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="task",
            side_effect_level="write_high",
        )
        decision = engine.evaluate(ctx)
        assert decision.is_block is True
        assert decision.reason_code == "policy_blocked_side_effect_write_high"

    def test_data_classification_blocks_through_engine(self):
        engine = PolicyEngine()
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="task",
            data_classification="restricted",
        )
        decision = engine.evaluate(ctx)
        assert decision.is_block is True
        assert decision.reason_code == "policy_blocked_data_classification"

    def test_read_command_allows(self):
        engine = PolicyEngine()
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="help",
            side_effect_level="read",
            data_classification="public",
        )
        decision = engine.evaluate(ctx)
        assert decision.is_allow is True

    def test_first_deny_wins(self):
        """When multiple detectors would fire, the first in registration order wins."""
        engine = PolicyEngine()
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="task",
            side_effect_level="write_high",
            data_classification="restricted",
        )
        decision = engine.evaluate(ctx)
        # side_effect_level is registered before data_classification
        assert decision.reason_code == "policy_blocked_side_effect_write_high"

    def test_before_skill_activation_allows_normal_skill(self):
        engine = PolicyEngine()
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_SKILL_ACTIVATION,
            skill_id="problem_framing",
            skill_activation_mode="prompt",
        )
        decision = engine.evaluate(ctx)
        assert decision.is_allow is True


class TestPolicyEngineConfigToggles:
    """Verify that PolicyConfig switches actually control detector registration."""

    def test_disabling_side_effect_detector_allows_write_high(self, monkeypatch):
        from app.core.config_manager import get_config
        cm = get_config()
        original = cm.get_nested
        def patched_get_nested(*keys, default=None):
            if keys == ('policy', 'enable_side_effect_detector'):
                return False
            return original(*keys, default=default)
        monkeypatch.setattr(cm, "get_nested", patched_get_nested)

        engine = PolicyEngine()
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="task",
            side_effect_level="write_high",
        )
        decision = engine.evaluate(ctx)
        assert decision.is_allow is True

    def test_disabling_data_classification_detector_allows_restricted(self, monkeypatch):
        from app.core.config_manager import get_config
        cm = get_config()
        original = cm.get_nested
        def patched_get_nested(*keys, default=None):
            if keys == ('policy', 'enable_data_classification_detector'):
                return False
            return original(*keys, default=default)
        monkeypatch.setattr(cm, "get_nested", patched_get_nested)

        engine = PolicyEngine()
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="task",
            data_classification="restricted",
        )
        decision = engine.evaluate(ctx)
        assert decision.is_allow is True

    def test_enabling_both_detectors_blocks_write_high(self, monkeypatch):
        from app.core.config_manager import get_config
        cm = get_config()
        original = cm.get_nested
        def patched_get_nested(*keys, default=None):
            if keys == ('policy', 'enable_side_effect_detector'):
                return True
            if keys == ('policy', 'enable_data_classification_detector'):
                return True
            return original(*keys, default=default)
        monkeypatch.setattr(cm, "get_nested", patched_get_nested)

        engine = PolicyEngine()
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="task",
            side_effect_level="write_high",
        )
        decision = engine.evaluate(ctx)
        assert decision.is_block is True

    def test_skill_tool_group_detector_off_by_default(self, monkeypatch):
        """P3 detector is opt-in; with default config it should not fire."""
        from app.core.config_manager import get_config
        cm = get_config()
        original = cm.get_nested
        def patched_get_nested(*keys, default=None):
            if keys == ('policy', 'enable_skill_tool_group_detector'):
                return False
            return original(*keys, default=default)
        monkeypatch.setattr(cm, "get_nested", patched_get_nested)

        engine = PolicyEngine()
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="task",
            interaction_profile="mutate",
            tool_groups=("mutate",),
            active_skill_context={
                "active_skill_ids": ["problem_framing"],
                "active_skill_allowed_tool_groups": ["read"],
            },
        )
        decision = engine.evaluate(ctx)
        assert decision.is_allow is True

    def test_skill_tool_group_detector_blocks_when_enabled(self, monkeypatch):
        """When enabled, mutate command denied by [read] skill."""
        from app.core.config_manager import get_config
        cm = get_config()
        original = cm.get_nested
        def patched_get_nested(*keys, default=None):
            if keys == ('policy', 'enable_skill_tool_group_detector'):
                return True
            return original(*keys, default=default)
        monkeypatch.setattr(cm, "get_nested", patched_get_nested)

        engine = PolicyEngine()
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="task",
            interaction_profile="mutate",
            tool_groups=("mutate",),
            active_skill_context={
                "active_skill_ids": ["problem_framing"],
                "active_skill_allowed_tool_groups": ["read"],
            },
        )
        decision = engine.evaluate(ctx)
        assert decision.is_block is True
        assert decision.reason_code == "policy_blocked_skill_tool_group"

    def test_skill_tool_group_detector_allows_read_when_enabled(self, monkeypatch):
        """When enabled, read command allowed by [read] skill."""
        from app.core.config_manager import get_config
        cm = get_config()
        original = cm.get_nested
        def patched_get_nested(*keys, default=None):
            if keys == ('policy', 'enable_skill_tool_group_detector'):
                return True
            return original(*keys, default=default)
        monkeypatch.setattr(cm, "get_nested", patched_get_nested)

        engine = PolicyEngine()
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="help",
            interaction_profile="read",
            tool_groups=("read",),
            active_skill_context={
                "active_skill_ids": ["problem_framing"],
                "active_skill_allowed_tool_groups": ["read"],
            },
        )
        decision = engine.evaluate(ctx)
        assert decision.is_allow is True
