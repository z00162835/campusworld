"""Tests for B7 — stop_evaluator exception handling (log + allow fallback)."""
from __future__ import annotations

import logging

from app.game_engine.agent_runtime.policy import PolicyContext, PolicyEngine
from app.game_engine.agent_runtime.policy.check_points import CheckPoint
from app.game_engine.agent_runtime.policy.config import (
    PolicyConfig,
    QualityDomainConfig,
    SkillDomainConfig,
    GateDomainConfig,
)
from app.game_engine.agent_runtime.policy.domain import DomainRegistry
from app.game_engine.agent_runtime.policy.domains.gate_domain import GateDomain
from app.game_engine.agent_runtime.policy.domains.quality_domain import (
    QualityDomain,
    stop_evaluator,
)
from app.game_engine.agent_runtime.policy.domains.skill_domain import SkillDomain


class _BoomEvaluator:
    """An evaluator that always raises."""

    def __call__(self, ctx):
        raise RuntimeError("evaluator exploded")


class _BoomQualityDomain(QualityDomain):
    def evaluators(self):
        return [_BoomEvaluator()]


class TestStopEvaluatorException:
    def test_evaluator_exception_returns_allow(self, caplog):
        """B7: evaluator exception → log evaluator_error + return allow (byte-equiv)."""
        config = PolicyConfig(
            skill=SkillDomainConfig(),
            gate=GateDomainConfig(),
            quality=QualityDomainConfig(),
        )
        registry = DomainRegistry()
        registry.register(SkillDomain(config.skill))
        registry.register(GateDomain(config.gate))
        registry.register(_BoomQualityDomain(config.quality))
        engine = PolicyEngine(registry=registry, config=config)

        ctx = PolicyContext(check_point=CheckPoint.AFTER_STATE_EXECUTE)
        with caplog.at_level(logging.ERROR, logger="campusworld.policy.engine"):
            decision = engine.evaluate(ctx)
        assert decision.is_allow is True
        assert any("evaluator_error" in r.message for r in caplog.records)

    def test_stop_evaluator_pure_function_no_exception(self):
        """The real stop_evaluator must never raise on a minimal context."""
        ctx = PolicyContext(check_point=CheckPoint.AFTER_STATE_EXECUTE)
        assert stop_evaluator(ctx) is None
