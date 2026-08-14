"""PolicyConfig — loader for the standalone ``backend/config/policy.yaml``.

Policy configuration is kept in a dedicated file (``backend/config/policy.yaml``)
separate from ``settings.yaml`` because policy rules (skill/gate/quality domain
toggles and thresholds) are orthogonal to infrastructure config (DB, auth,
logging). This keeps ops diff/audit/grayscale independent.

``PolicyConfig`` parses the file at startup into per-domain dataclasses and feeds
them to the ``DomainRegistry``. When the file is missing or a key is absent, code
defaults apply — so unit tests run without the file present.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger("campusworld.policy.config")

_DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[5] / "config" / "policy.yaml"


@dataclass(frozen=True)
class SkillDomainConfig:
    """Skill domain config (``before_skill_activation`` check_point).

    Note: ``enable_skill_tool_group_detector`` lives in :class:`GateDomainConfig`
    because the ``skill_tool_group`` detector runs at ``before_tool_call`` (gate
    domain check_point), not ``before_skill_activation``.
    """


@dataclass(frozen=True)
class GateDomainConfig:
    enable_side_effect_detector: bool = True
    enable_data_classification_detector: bool = True
    enable_prompt_fallback: bool = True
    enable_skill_tool_group_detector: bool = False
    side_effect_defaults: Dict[str, str] = field(
        default_factory=lambda: {
            "none": "allow",
            "read": "allow",
            "write_low": "allow",
            "write_high": "require_approval",
        }
    )


@dataclass(frozen=True)
class QualityDomainConfig:
    enable_quality_score: bool = False
    enable_stop_dimensions: bool = False   # gates stop_evaluator dimensions and tick budget checks
    final_success_drive_mode: str = "off"  # off / shadow (audit+divergence) / enforce (evaluator drives draft_incomplete)
    enable_budget_hard_fail: bool = False  # opt-in hard-fail terminal for budget_exceeded; default soft-fail
    max_iterations: int = 12
    max_consecutive_tool_failures: int = 3
    stagnation_window: int = 3


@dataclass(frozen=True)
class PolicyConfig:
    skill: SkillDomainConfig = field(default_factory=SkillDomainConfig)
    gate: GateDomainConfig = field(default_factory=GateDomainConfig)
    quality: QualityDomainConfig = field(default_factory=QualityDomainConfig)


def _coerce_bool(value: Any, default: bool, *, key: str = "value") -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        logger.warning("Invalid boolean policy config for %s: %r; using default %s", key, value, default)
        return default
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value in (0, 1):
            return bool(value)
        logger.warning("Invalid numeric boolean policy config for %s: %r; using default %s", key, value, default)
        return default
    return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


_VALID_DRIVE_MODES = frozenset({"off", "shadow", "enforce"})


def _coerce_drive_mode(value: Any, default: str = "off") -> str:
    """Coerce ``final_success_drive_mode`` (off/shadow/enforce).

    Backward compat: a legacy boolean ``enable_final_success_gate: true`` maps
    to ``"shadow"`` (audit + divergence, non-driving) so old configs that opted
    into the audit gate keep the same non-driving semantics.
    """
    if isinstance(value, bool):
        return "shadow" if value else "off"
    if isinstance(value, str):
        v = value.strip().lower()
        if v in _VALID_DRIVE_MODES:
            return v
        return default
    return default


def load_policy_config(path: Optional[Path] = None) -> PolicyConfig:
    """Load ``policy.yaml``; fall back to code defaults when missing/invalid."""
    resolved = path or _DEFAULT_POLICY_PATH
    if not resolved.exists():
        return PolicyConfig()
    try:
        with open(resolved, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        logger.error("YAML syntax error in %s: %s", resolved, e)
        return PolicyConfig()
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to read policy config %s: %s", resolved, e)
        return PolicyConfig()

    if not isinstance(raw, dict):
        return PolicyConfig()

    skill_raw = raw.get("skill") or {}
    gate_raw = raw.get("gate") or {}
    quality_raw = raw.get("quality") or {}

    skill = SkillDomainConfig()

    gate_side_defaults = gate_raw.get("side_effect_defaults")
    if not isinstance(gate_side_defaults, dict):
        gate_side_defaults = {}
    merged_side_defaults = dict(GateDomainConfig().side_effect_defaults)
    merged_side_defaults.update(
        {str(k): str(v) for k, v in gate_side_defaults.items()}
    )

    gate = GateDomainConfig(
        enable_side_effect_detector=_coerce_bool(
            gate_raw.get("enable_side_effect_detector"), True, key="gate.enable_side_effect_detector"
        ),
        enable_data_classification_detector=_coerce_bool(
            gate_raw.get("enable_data_classification_detector"), True, key="gate.enable_data_classification_detector"
        ),
        enable_prompt_fallback=_coerce_bool(
            gate_raw.get("enable_prompt_fallback"), True, key="gate.enable_prompt_fallback"
        ),
        enable_skill_tool_group_detector=_coerce_bool(
            gate_raw.get("enable_skill_tool_group_detector"), False, key="gate.enable_skill_tool_group_detector"
        ),
        side_effect_defaults=merged_side_defaults,
    )

    quality = QualityDomainConfig(
        enable_quality_score=_coerce_bool(
            quality_raw.get("enable_quality_score"), False, key="quality.enable_quality_score"
        ),
        enable_stop_dimensions=_coerce_bool(
            quality_raw.get("enable_stop_dimensions"), False, key="quality.enable_stop_dimensions"
        ),
        final_success_drive_mode=_coerce_drive_mode(
            quality_raw.get("final_success_drive_mode")
            if "final_success_drive_mode" in quality_raw
            else quality_raw.get("enable_final_success_gate"),
            "off",
        ),
        enable_budget_hard_fail=_coerce_bool(
            quality_raw.get("enable_budget_hard_fail"), False, key="quality.enable_budget_hard_fail"
        ),
        max_iterations=_coerce_int(quality_raw.get("max_iterations"), 12),
        max_consecutive_tool_failures=_coerce_int(
            quality_raw.get("max_consecutive_tool_failures"), 3
        ),
        stagnation_window=_coerce_int(quality_raw.get("stagnation_window"), 3),
    )

    return PolicyConfig(skill=skill, gate=gate, quality=quality)


_default_config: Optional[PolicyConfig] = None


def get_policy_config() -> PolicyConfig:
    global _default_config
    if _default_config is None:
        _default_config = load_policy_config()
    return _default_config
