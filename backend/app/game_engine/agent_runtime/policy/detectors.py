"""Detectors — pure functions that evaluate a single policy rule.

Each detector returns ``None`` when the rule passes (no opinion) or a
``PolicyDecision`` when it fires. Detectors are stateless and never call the
LLM or the database. The engine applies them in registration order; the
first non-``None`` deny/require_approval result wins.
"""
from __future__ import annotations

from typing import Optional

from app.game_engine.agent_runtime.policy.check_points import CheckPoint
from app.game_engine.agent_runtime.policy.context import PolicyContext
from app.game_engine.agent_runtime.policy.decisions import PolicyDecision

# ---------------------------------------------------------------------------
# before_tool_call detectors
# ---------------------------------------------------------------------------

_BLOCKED_SIDE_EFFECT_LEVELS = {"write_high"}
_BLOCKED_DATA_CLASSIFICATIONS = {"confidential", "restricted"}


def side_effect_level_detector(ctx: PolicyContext) -> Optional[PolicyDecision]:
    """write_high → require_approval (v1: synchronous block)."""
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


# ---------------------------------------------------------------------------
# before_skill_activation detectors
# ---------------------------------------------------------------------------

_BLOCKED_SKILL_ACTIVATION_MODES: frozenset[str] = frozenset()


def skill_activation_mode_detector(ctx: PolicyContext) -> Optional[PolicyDecision]:
    """Optionally block skills whose activation_mode is administratively disabled."""
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


# ---------------------------------------------------------------------------
# before_tool_call: skill_tool_group (P3, D3)
# ---------------------------------------------------------------------------

def skill_tool_group_detector(ctx: PolicyContext) -> Optional[PolicyDecision]:
    """Deny when the command's tool_groups are not covered by active skills.

    If the agent has active skills, every command must have at least one
    ``tool_group`` that is covered by the union of the active skills'
    ``allowed_tool_groups`` (exact match or parent-group match).

    When there are no active skills (``active_skill_context`` is missing or
    ``active_skill_ids`` is empty), the detector does **not** fire — this
    preserves forward compatibility with agents that have no ``skill_refs``.
    """
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
