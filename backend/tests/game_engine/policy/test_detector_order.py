"""Tests for N2 — domain detector order preservation after migration.

The legacy flat ``detectors.py`` registered detectors in a fixed order via
``_detectors_from_config``. After migration to per-domain modules, the order
within each domain must be preserved so reason_code hit distribution stays
byte-equivalent.
"""
from __future__ import annotations

from app.game_engine.agent_runtime.policy.config import (
    GateDomainConfig,
    SkillDomainConfig,
)
from app.game_engine.agent_runtime.policy.domains.gate_domain import GateDomain
from app.game_engine.agent_runtime.policy.domains.skill_domain import (
    skill_activation_mode_detector,
)
from app.game_engine.agent_runtime.policy.domains.skill_domain import (
    SkillDomain,
)
from app.game_engine.agent_runtime.policy.domains.gate_domain import (
    data_classification_detector,
    pattern_match_detector,
    side_effect_level_detector,
    skill_tool_group_detector,
)


class TestDetectorOrder:
    def test_gate_domain_order_with_all_enabled(self):
        """gate domain order: side_effect → data_classification → skill_tool_group → pattern_match."""
        domain = GateDomain(
            GateDomainConfig(
                enable_side_effect_detector=True,
                enable_data_classification_detector=True,
                enable_skill_tool_group_detector=True,
                enable_pattern_match_detector=True,
            )
        )
        dets = domain.detectors()
        assert dets == [
            side_effect_level_detector,
            data_classification_detector,
            skill_tool_group_detector,
            pattern_match_detector,
        ]

    def test_gate_domain_order_with_skill_group_disabled(self):
        """skill_tool_group opt-in: omitted when toggle off."""
        domain = GateDomain(
            GateDomainConfig(enable_skill_tool_group_detector=False)
        )
        dets = domain.detectors()
        assert dets == [side_effect_level_detector, data_classification_detector]

    def test_gate_domain_empty_when_all_disabled(self):
        domain = GateDomain(
            GateDomainConfig(
                enable_side_effect_detector=False,
                enable_data_classification_detector=False,
                enable_skill_tool_group_detector=False,
                enable_pattern_match_detector=False,
            )
        )
        assert domain.detectors() == []

    def test_skill_domain_order(self):
        """skill domain has a single detector: skill_activation_mode."""
        domain = SkillDomain(SkillDomainConfig())
        assert domain.detectors() == [skill_activation_mode_detector]

    def test_gate_first_firing_wins_side_effect_before_data_classification(self):
        """When both would fire, side_effect (first) must win — preserves
        legacy reason_code distribution."""
        from app.game_engine.agent_runtime.policy import PolicyContext
        from app.game_engine.agent_runtime.policy.check_points import CheckPoint

        domain = GateDomain(
            GateDomainConfig(
                enable_side_effect_detector=True,
                enable_data_classification_detector=True,
            )
        )
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="task",
            side_effect_level="write_high",
            data_classification="restricted",
        )
        ctx = domain.build_context(ctx)
        decision = None
        for det in domain.detectors():
            d = det(ctx)
            if d is not None and not d.is_allow:
                decision = d
                break
        assert decision is not None
        assert decision.reason_code == "policy_blocked_side_effect_write_high"
