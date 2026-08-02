"""Skill domain — F15/F16 skill activation compliance.

Owns the ``before_skill_activation`` check_point. The single detector validates
the skill activation mode. (``skill_tool_group`` runs at ``before_tool_call``,
so it lives in the gate domain — it gates tool calls using skill metadata.)
"""
from __future__ import annotations

from typing import List, Optional

from app.game_engine.agent_runtime.policy.config import SkillDomainConfig
from app.game_engine.agent_runtime.policy.context import PolicyContext
from app.game_engine.agent_runtime.policy.decisions import PolicyDecision
from app.game_engine.agent_runtime.policy.domain import Detector, Domain

_BLOCKED_SKILL_ACTIVATION_MODES: frozenset[str] = frozenset()


def skill_activation_mode_detector(ctx: PolicyContext) -> Optional[PolicyDecision]:
    """Optionally block skills whose activation_mode is administratively disabled."""
    from app.game_engine.agent_runtime.policy.check_points import CheckPoint

    if ctx.check_point != CheckPoint.BEFORE_SKILL_ACTIVATION:
        return None
    mode = str(ctx.skill_activation_mode or "").strip().lower()
    if mode in _BLOCKED_SKILL_ACTIVATION_MODES:
        return PolicyDecision.deny(
            CheckPoint.BEFORE_SKILL_ACTIVATION,
            "policy_blocked_skill_activation_mode",
            evidence={"skill_id": ctx.skill_id, "activation_mode": mode},
        )
    return None


class SkillDomain(Domain):
    domain_id = "skill"
    check_points = ("before_skill_activation",)

    def __init__(self, config: SkillDomainConfig) -> None:
        self._config = config

    def detectors(self) -> List[Detector]:
        return [skill_activation_mode_detector]

    def build_context(self, base: PolicyContext) -> PolicyContext:
        return base
