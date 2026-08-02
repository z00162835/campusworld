"""Gate domain — F16 tool execution safety.

Owns the ``before_tool_call`` / ``after_tool_observation`` / ``before_final_answer``
check_points. Detectors validate side-effect level, data classification, and
(opt-in) skill tool-group coverage. Detector order is preserved from the legacy
flat ``detectors.py``: ``[side_effect_level, data_classification, skill_tool_group]``.
``pattern_match`` / ``pii_scanner`` are SPEC placeholders not yet implemented.
"""
from __future__ import annotations

from typing import List, Optional

from app.game_engine.agent_runtime.policy.config import GateDomainConfig
from app.game_engine.agent_runtime.policy.context import PolicyContext
from app.game_engine.agent_runtime.policy.decisions import PolicyDecision
from app.game_engine.agent_runtime.policy.domain import Detector, Domain

_BLOCKED_SIDE_EFFECT_LEVELS = {"write_high"}
_BLOCKED_DATA_CLASSIFICATIONS = {"confidential", "restricted"}


def side_effect_level_detector(ctx: PolicyContext) -> Optional[PolicyDecision]:
    """write_high → require_approval (v1: synchronous block)."""
    from app.game_engine.agent_runtime.policy.check_points import CheckPoint

    if ctx.check_point != CheckPoint.BEFORE_TOOL_CALL:
        return None
    level = str(ctx.side_effect_level or "none").strip().lower()
    if level in _BLOCKED_SIDE_EFFECT_LEVELS:
        return PolicyDecision.require_approval(
            CheckPoint.BEFORE_TOOL_CALL,
            "policy_blocked_side_effect_write_high",
            evidence={"side_effect_level": level, "command_name": ctx.command_name},
        )
    return None


def data_classification_detector(ctx: PolicyContext) -> Optional[PolicyDecision]:
    """confidential/restricted → require_approval (v1: synchronous block)."""
    from app.game_engine.agent_runtime.policy.check_points import CheckPoint

    if ctx.check_point != CheckPoint.BEFORE_TOOL_CALL:
        return None
    cls = str(ctx.data_classification or "").strip().lower()
    if cls in _BLOCKED_DATA_CLASSIFICATIONS:
        return PolicyDecision.require_approval(
            CheckPoint.BEFORE_TOOL_CALL,
            "policy_blocked_data_classification",
            evidence={"data_classification": cls, "command_name": ctx.command_name},
        )
    return None


def skill_tool_group_detector(ctx: PolicyContext) -> Optional[PolicyDecision]:
    """Deny when the command's tool_groups are not covered by active skills.

    Runs at ``before_tool_call`` (gate domain check_point) but reads skill
    metadata (``active_skill_context``). If the agent has active skills, every
    command must have at least one ``tool_group`` covered by the union of the
    active skills' ``allowed_tool_groups``.

    When there are no active skills (``active_skill_context`` is missing or
    ``active_skill_ids`` is empty), the detector does **not** fire — this
    preserves forward compatibility with agents that have no ``skill_refs``.
    """
    from app.game_engine.agent_runtime.policy.check_points import CheckPoint

    if ctx.check_point != CheckPoint.BEFORE_TOOL_CALL:
        return None
    asc = ctx.active_skill_context
    if not isinstance(asc, dict):
        return None
    active_ids = asc.get("active_skill_ids")
    if not active_ids:
        return None
    allowed_groups = asc.get("active_skill_allowed_tool_groups")
    if not allowed_groups:
        # Skills are active but declare no groups — allow everything rather
        # than over-block. The skill authors can tighten by declaring groups.
        return None
    command_groups = tuple(ctx.tool_groups or ())
    if not command_groups:
        command_groups = (ctx.interaction_profile or "read",)
    from app.game_engine.agent_runtime.policy.tool_groups import is_any_group_allowed

    if not is_any_group_allowed(command_groups, tuple(allowed_groups)):
        return PolicyDecision.deny(
            CheckPoint.BEFORE_TOOL_CALL,
            "policy_blocked_skill_tool_group",
            evidence={
                "command_name": ctx.command_name,
                "command_tool_groups": list(command_groups),
                "active_skill_ids": list(active_ids),
                "active_skill_allowed_tool_groups": list(allowed_groups),
            },
        )
    return None


class GateDomain(Domain):
    domain_id = "gate"
    check_points = (
        "before_tool_call",
        "after_tool_observation",
        "before_final_answer",
    )

    def __init__(self, config: GateDomainConfig) -> None:
        self._config = config

    def detectors(self) -> List[Detector]:
        # Order preserved from legacy _detectors_from_config:
        # side_effect → data_classification → [skill_tool_group].
        dets: List[Detector] = []
        if self._config.enable_side_effect_detector:
            dets.append(side_effect_level_detector)
        if self._config.enable_data_classification_detector:
            dets.append(data_classification_detector)
        if self._config.enable_skill_tool_group_detector:
            dets.append(skill_tool_group_detector)
        return dets

    def build_context(self, base: PolicyContext) -> PolicyContext:
        return base
