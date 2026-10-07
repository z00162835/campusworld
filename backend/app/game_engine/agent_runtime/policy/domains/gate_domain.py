"""Gate domain — F16 tool execution safety.

Owns the ``before_tool_call`` / ``after_tool_observation`` / ``before_final_answer``
check_points. Detectors validate side-effect level, data classification, and
(opt-in) skill tool-group coverage. Detector order is preserved from the legacy
flat ``detectors.py``: ``[side_effect_level, data_classification, skill_tool_group,
pattern_match]``. ``pii_scanner`` is a SPEC placeholder not yet implemented.
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional

from app.game_engine.agent_runtime.policy.config import GateDomainConfig
from app.game_engine.agent_runtime.policy.context import PolicyContext
from app.game_engine.agent_runtime.policy.decisions import PolicyDecision
from app.game_engine.agent_runtime.policy.domain import Detector, Domain

logger = logging.getLogger("campusworld.policy.gate")

_BLOCKED_SIDE_EFFECT_LEVELS = {"write_high"}
_BLOCKED_DATA_CLASSIFICATIONS = {"confidential", "restricted"}
# Valid decision strings for side_effect_defaults (fail-closed on unknown).
_VALID_SIDE_EFFECT_DECISIONS = frozenset({"allow", "require_approval", "deny"})


def side_effect_level_detector(ctx: PolicyContext) -> Optional[PolicyDecision]:
    """Side-effect gate driven by ``side_effect_defaults`` config (H1+H5).

    Reads ``gate_config['side_effect_defaults']`` (level → decision string) from
    ``ctx.extra``. Emits ``require_approval``/``deny`` when the configured
    decision for the current ``side_effect_level`` is non-allow; ``None`` (allow)
    otherwise. Falls back to the hardcoded ``_BLOCKED_SIDE_EFFECT_LEVELS`` set
    when no config is injected (byte-equiv for paths that bypass build_context).

    **Fail-closed (P1):** an unrecognized decision string (e.g. a typo like
    ``require-approva1``) or an unknown ``side_effect_level`` not present in the
    config map is treated as ``require_approval`` rather than silently allowed,
    so a config typo cannot weaken the security boundary.
    """
    from app.game_engine.agent_runtime.policy.check_points import CheckPoint

    if ctx.check_point != CheckPoint.BEFORE_TOOL_CALL:
        return None
    level = str(ctx.side_effect_level or "none").strip().lower()
    gate_cfg = ctx.extra.get("gate_config") if ctx.extra else None
    if isinstance(gate_cfg, dict) and "side_effect_defaults" in gate_cfg:
        defaults = gate_cfg["side_effect_defaults"]
        if level not in defaults:
            # Unknown level not in config map → fail-closed (require_approval).
            logger.warning(
                "side_effect_level %r not in side_effect_defaults config; "
                "fail-closed to require_approval", level,
            )
            return PolicyDecision.require_approval(
                CheckPoint.BEFORE_TOOL_CALL,
                "policy_blocked_side_effect_unknown_level",
                evidence={"side_effect_level": level, "command_name": ctx.command_name},
            )
        decision_str = str(defaults.get(level, "allow")).strip().lower()
        if decision_str == "require_approval":
            return PolicyDecision.require_approval(
                CheckPoint.BEFORE_TOOL_CALL,
                "policy_blocked_side_effect_write_high",
                evidence={"side_effect_level": level, "command_name": ctx.command_name},
            )
        if decision_str == "deny":
            return PolicyDecision.deny(
                CheckPoint.BEFORE_TOOL_CALL,
                "policy_blocked_side_effect",
                evidence={"side_effect_level": level, "command_name": ctx.command_name},
            )
        if decision_str != "allow":
            # Unrecognized decision string (typo) → fail-closed.
            logger.warning(
                "side_effect_defaults[%r]=%r is not a valid decision "
                "(allow/require_approval/deny); fail-closed to require_approval",
                level, decision_str,
            )
            return PolicyDecision.require_approval(
                CheckPoint.BEFORE_TOOL_CALL,
                "policy_blocked_side_effect_invalid_decision",
                evidence={
                    "side_effect_level": level,
                    "configured_decision": decision_str,
                    "command_name": ctx.command_name,
                },
            )
        return None
    # Fallback: hardcoded baseline (byte-equiv when config not injected).
    if level in _BLOCKED_SIDE_EFFECT_LEVELS:
        return PolicyDecision.require_approval(
            CheckPoint.BEFORE_TOOL_CALL,
            "policy_blocked_side_effect_write_high",
            evidence={"side_effect_level": level, "command_name": ctx.command_name},
        )
    return None


def data_classification_detector(ctx: PolicyContext) -> Optional[PolicyDecision]:
    """confidential/restricted → require_approval (v1: synchronous block).

    Reads ``gate_config['blocked_data_classifications']`` from ``ctx.extra``;
    falls back to hardcoded ``_BLOCKED_DATA_CLASSIFICATIONS`` (byte-equiv).
    """
    from app.game_engine.agent_runtime.policy.check_points import CheckPoint

    if ctx.check_point != CheckPoint.BEFORE_TOOL_CALL:
        return None
    cls = str(ctx.data_classification or "").strip().lower()
    if not cls:
        return None
    gate_cfg = ctx.extra.get("gate_config") if ctx.extra else None
    if isinstance(gate_cfg, dict) and "blocked_data_classifications" in gate_cfg:
        blocked = gate_cfg["blocked_data_classifications"]
    else:
        blocked = _BLOCKED_DATA_CLASSIFICATIONS
    if cls in blocked:
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

    gate_cfg = ctx.extra.get("gate_config") if ctx.extra else None
    hierarchy = gate_cfg.get("tool_group_hierarchy") if isinstance(gate_cfg, dict) else None

    if not is_any_group_allowed(command_groups, tuple(allowed_groups), hierarchy=hierarchy):
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


def pattern_match_detector(ctx: PolicyContext) -> Optional[PolicyDecision]:
    """Prompt injection / 越权短语 detector (P4).

    Matches ``user_message`` + command ``args`` (at ``before_tool_call``) or
    the final ``draft_text`` (at ``before_final_answer``, non-streaming only)
    against configured regex patterns (``gate.pattern_match_patterns``). On hit,
    emits the configured decision (default ``require_approval``). Default-off
    so default config is byte-equivalent; an empty pattern set is a no-op even
    when the detector is enabled.

    Streaming path is explicitly post-v1 (F18 §4.1): mid-stream evaluation would
    break first-token latency and streaming golden traces, so the driver only
    invokes this check_point at the non-streaming act finalization boundary.
    """
    from app.game_engine.agent_runtime.policy.check_points import CheckPoint

    if ctx.check_point not in (CheckPoint.BEFORE_TOOL_CALL, CheckPoint.BEFORE_FINAL_ANSWER):
        return None
    gate_cfg = ctx.extra.get("gate_config") if ctx.extra else None
    if not isinstance(gate_cfg, dict):
        return None
    patterns = gate_cfg.get("pattern_match_patterns")
    if not patterns:
        return None  # empty set → no-op (byte-equiv)
    # Select target text by check_point.
    if ctx.check_point == CheckPoint.BEFORE_TOOL_CALL:
        target = str(ctx.user_message or "")
        args = ctx.command_args
        if args:
            target += " " + " ".join(str(a) for a in args)
    else:  # BEFORE_FINAL_ANSWER (non-streaming)
        target = str(ctx.draft_text or "")
    if not target.strip():
        return None
    decision_str = str(gate_cfg.get("pattern_match_decision", "require_approval")).strip().lower()
    for pat in patterns:
        try:
            if re.search(pat, target, re.IGNORECASE):
                if decision_str == "deny":
                    return PolicyDecision.deny(
                        ctx.check_point,
                        "policy_blocked_pattern_match",
                        evidence={"pattern": pat, "check_point": ctx.check_point},
                    )
                if decision_str == "allow":
                    # Misconfig: allow means audit-only; emit no blocking decision.
                    logger.warning(
                        "pattern_match_decision='allow' configured; pattern %r "
                        "hit but not blocking (audit-only)", pat,
                    )
                    return None
                # default + require_approval
                return PolicyDecision.require_approval(
                    ctx.check_point,
                    "policy_blocked_pattern_match",
                    evidence={"pattern": pat, "check_point": ctx.check_point},
                )
        except re.error as exc:
            logger.warning("pattern_match regex %r invalid: %s; skipped", pat, exc)
            continue
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
        # side_effect → data_classification → [skill_tool_group] → [pattern_match].
        dets: List[Detector] = []
        if self._config.enable_side_effect_detector:
            dets.append(side_effect_level_detector)
        if self._config.enable_data_classification_detector:
            dets.append(data_classification_detector)
        if self._config.enable_skill_tool_group_detector:
            dets.append(skill_tool_group_detector)
        if self._config.enable_pattern_match_detector:
            dets.append(pattern_match_detector)
        return dets

    def build_context(self, base: PolicyContext) -> PolicyContext:
        # Inject the gate-domain config snapshot so detectors read thresholds from
        # config (H1/H2/H4/H5) instead of module-level hardcoded constants.
        base.extra["gate_config"] = {
            "side_effect_defaults": dict(self._config.side_effect_defaults),
            "blocked_data_classifications": tuple(self._config.blocked_data_classifications),
            "tool_group_hierarchy": {
                k: tuple(v) for k, v in self._config.tool_group_hierarchy.items()
            },
            "pattern_match_patterns": tuple(self._config.pattern_match_patterns),
            "pattern_match_decision": self._config.pattern_match_decision,
        }
        return base
