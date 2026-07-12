"""Detectors — pure functions that evaluate a single policy rule.

Each detector returns ``None`` when the rule passes (no opinion) or a
``PolicyDecision`` when it fires. Detectors are stateless and never call the
LLM or the database (D1). The engine applies them in registration order; the
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
