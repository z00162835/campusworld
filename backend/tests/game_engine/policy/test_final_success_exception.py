"""B7: final_success_evaluator outer-exception handling (log + degrade)."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

from app.game_engine.agent_runtime.policy import PolicyContext, PolicyEngine
from app.game_engine.agent_runtime.policy.check_points import CheckPoint
from app.game_engine.agent_runtime.policy.config import (
    GateDomainConfig,
    PolicyConfig,
    QualityDomainConfig,
    SkillDomainConfig,
)
from app.game_engine.agent_runtime.policy.domain import DomainRegistry
from app.game_engine.agent_runtime.policy.domains.gate_domain import GateDomain
from app.game_engine.agent_runtime.policy.domains.quality_domain import (
    QualityDomain,
    final_success_evaluator,
)
from app.game_engine.agent_runtime.policy.domains.skill_domain import SkillDomain


class _OuterBoomQualityDomain(QualityDomain):
    """A quality domain whose final_success_evaluator raises an outer exception."""

    def evaluators(self):
        def _boom(ctx):
            raise RuntimeError("outer evaluator exploded")

        return [_boom]


class TestFinalSuccessException:
    def test_outer_exception_returns_allow(self, caplog):
        """B7: outer logic exception → log evaluator_error + return allow."""
        config = PolicyConfig(
            skill=SkillDomainConfig(),
            gate=GateDomainConfig(),
            quality=QualityDomainConfig(),
        )
        registry = DomainRegistry()
        registry.register(SkillDomain(config.skill))
        registry.register(GateDomain(config.gate))
        registry.register(_OuterBoomQualityDomain(config.quality))
        engine = PolicyEngine(registry=registry, config=config)

        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TERMINAL,
            extra={"tick_state": {"agent_loop_config": MagicMock()}},
        )
        with caplog.at_level(logging.ERROR, logger="campusworld.policy.engine"):
            decision = engine.evaluate(ctx)
        assert decision.is_allow is True
        assert any("evaluator_error" in r.message for r in caplog.records)

    def test_assess_self_exception_propagates_through_evaluator(self, monkeypatch):
        """B7: assess_draft_completeness self-exception re-raises from the evaluator
        (the engine safety net catches it and returns allow, since the evaluator
        chose to re-raise rather than handle)."""
        from app.game_engine.agent_runtime.agent_loop import draft_gate
        from app.game_engine.agent_runtime.agent_loop.signals import (
            DraftCompletenessVerdict,
        )

        def _raise(**kw):
            raise RuntimeError("assess exploded")

        monkeypatch.setattr(
            draft_gate, "assess_draft_completeness_with_budget", _raise,
        )
        ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_TERMINAL,
            extra={"tick_state": {"agent_loop_config": MagicMock(), "enable_final_success_gate": True}},
        )
        # The evaluator re-raises; the engine safety net catches it → allow.
        engine = PolicyEngine()
        decision = engine.evaluate(ctx)
        assert decision.is_allow is True
