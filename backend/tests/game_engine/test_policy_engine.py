"""Unit tests for the F16 PolicyEngine and detectors."""
from __future__ import annotations

from app.game_engine.agent_runtime.policy import PolicyContext, PolicyDecision, PolicyEngine
from app.game_engine.agent_runtime.policy.check_points import CheckPoint
from app.game_engine.agent_runtime.policy.detectors import (
    data_classification_detector,
    side_effect_level_detector,
    skill_activation_mode_detector,
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
