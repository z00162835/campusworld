"""Tests for Domain.build_context — per-domain field extraction from tick_state."""
from __future__ import annotations

from app.game_engine.agent_runtime.policy import DomainRegistry, PolicyContext
from app.game_engine.agent_runtime.policy.config import (
    GateDomainConfig,
    PolicyConfig,
    SkillDomainConfig,
)
from app.game_engine.agent_runtime.policy.domains.gate_domain import GateDomain
from app.game_engine.agent_runtime.policy.domains.skill_domain import SkillDomain


class TestBuildContext:
    def test_skill_domain_build_context_no_tick_state_is_noop(self):
        domain = SkillDomain(SkillDomainConfig())
        base = PolicyContext(check_point="before_skill_activation")
        out = domain.build_context(base)
        assert out is base

    def test_gate_domain_build_context_no_tick_state_is_noop(self):
        domain = GateDomain(GateDomainConfig())
        base = PolicyContext(check_point="before_tool_call")
        out = domain.build_context(base)
        assert out is base

    def test_skill_domain_build_context_with_tick_state_preserves_base(self):
        domain = SkillDomain(SkillDomainConfig())
        base = PolicyContext(
            check_point="before_skill_activation",
            extra={"tick_state": {"skill_id": "problem_framing"}},
        )
        out = domain.build_context(base)
        # skill domain has no extra fields to extract today (skill_* set by
        # caller); build_context must not drop the tick_state ref.
        assert out.extra["tick_state"] == {"skill_id": "problem_framing"}

    def test_gate_domain_build_context_preserves_tick_state(self):
        domain = GateDomain(GateDomainConfig())
        base = PolicyContext(
            check_point="before_tool_call",
            extra={"tick_state": {"command_name": "task"}},
        )
        out = domain.build_context(base)
        assert out.extra["tick_state"] == {"command_name": "task"}

    def test_engine_evaluate_calls_build_context_before_detectors(self):
        """End-to-end: engine dispatches to domain, which builds context, then
        runs detectors. A gate-domain detector reading ctx.command_name should
        see the value set on the base context (driver-set fields)."""
        from app.game_engine.agent_runtime.policy import PolicyEngine
        from app.game_engine.agent_runtime.policy.check_points import CheckPoint

        config = PolicyConfig(
            skill=SkillDomainConfig(),
            gate=GateDomainConfig(enable_side_effect_detector=True),
        )
        registry = DomainRegistry()
        registry.register(SkillDomain(config.skill))
        registry.register(GateDomain(config.gate))
        engine = PolicyEngine(registry=registry, config=config)

        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TOOL_CALL,
            command_name="task",
            side_effect_level="write_high",
        )
        decision = engine.evaluate(ctx)
        assert decision.is_block is True
        assert decision.evidence["domain"] == "gate"
