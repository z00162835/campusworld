"""PolicyEngine — deterministic check-point evaluator.

The engine is a pure function over ``PolicyContext``: no DB, no LLM, no I/O.
Rules are registered per **domain** (see ``domain.py``); ``evaluate`` dispatches
by ``check_point -> domain`` and runs only that domain's detector/evaluator
chain. The first non-allow decision short-circuits the chain; if no detector
fires the engine returns ``allow``.

Domain fields are populated by the owning domain's ``build_context`` before its
detectors run (data sourced from ``base.extra['tick_state']``).
"""
from __future__ import annotations

import dataclasses
import logging
from typing import Optional, Tuple

from app.game_engine.agent_runtime.policy.config import PolicyConfig, get_policy_config
from app.game_engine.agent_runtime.policy.context import PolicyContext
from app.game_engine.agent_runtime.policy.decisions import PolicyDecision
from app.game_engine.agent_runtime.policy.domain import Domain, DomainRegistry, Detector

logger = logging.getLogger("campusworld.policy.engine")


class PolicyEngine:
    """Stateless evaluator. Constructed once per process; safe to reuse."""

    def __init__(
        self,
        registry: Optional[DomainRegistry] = None,
        config: Optional[PolicyConfig] = None,
    ) -> None:
        if registry is None:
            registry, config = _build_default_registry(config)
        self._registry: DomainRegistry = registry
        self._config: PolicyConfig = config or PolicyConfig()

    def evaluate(self, ctx: PolicyContext) -> PolicyDecision:
        domain = self._registry.domain_for(ctx.check_point)
        if domain is None:
            return PolicyDecision.allow(ctx.check_point)
        ctx = domain.build_context(ctx)
        for detector in domain.detectors():
            decision = detector(ctx)
            if decision is not None and not decision.is_allow:
                evidence = dict(decision.evidence or {})
                evidence["detector"] = detector.__name__
                evidence["domain"] = domain.domain_id
                tagged = dataclasses.replace(decision, evidence=evidence)
                return tagged
        allow_with_score: Optional[PolicyDecision] = None
        for evaluator in domain.evaluators():
            try:
                decision = evaluator(ctx)
            except Exception as exc:  # noqa: BLE001 — evaluator safety net
                logger.error("evaluator_error: %s raised by %s: %s", domain.domain_id, getattr(evaluator, "__name__", evaluator), exc)
                decision = None
            if decision is not None and decision.decision == 'allow' and decision.quality_score is not None:
                evidence = dict(decision.evidence or {})
                evidence["evaluator"] = getattr(evaluator, "__name__", "evaluator")
                evidence["domain"] = domain.domain_id
                allow_with_score = dataclasses.replace(decision, evidence=evidence)
                continue
            # Surface any explicit non-default decision. Quality evaluators may
            # emit pass-through decisions such as final_success / replan /
            # continue; these carry audit signal the driver must observe.
            if decision is not None and decision.decision != 'allow':
                evidence = dict(decision.evidence or {})
                evidence["evaluator"] = getattr(evaluator, "__name__", "evaluator")
                evidence["domain"] = domain.domain_id
                quality_score = decision.quality_score
                if quality_score is None and allow_with_score is not None:
                    quality_score = allow_with_score.quality_score
                return dataclasses.replace(decision, evidence=evidence, quality_score=quality_score)
        if allow_with_score is not None:
            return allow_with_score
        return PolicyDecision.allow(ctx.check_point)

    @property
    def registry(self) -> DomainRegistry:
        return self._registry

    @property
    def config(self) -> PolicyConfig:
        return self._config


def _build_default_registry(
    config: Optional[PolicyConfig],
) -> Tuple[DomainRegistry, PolicyConfig]:
    from app.game_engine.agent_runtime.policy.domains.gate_domain import GateDomain
    from app.game_engine.agent_runtime.policy.domains.quality_domain import (
        QualityDomain,
    )
    from app.game_engine.agent_runtime.policy.domains.skill_domain import SkillDomain

    if config is None:
        config = get_policy_config()

    registry = DomainRegistry()
    registry.register(SkillDomain(config.skill))
    registry.register(GateDomain(config.gate))
    registry.register(QualityDomain(config.quality))
    return registry, config


# Module-level singleton; detectors are stateless so reuse is safe.
default_engine = PolicyEngine()
