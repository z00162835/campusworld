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
    enable_stop_dimensions: bool = False   # gates stop_evaluator new dims (stagnation/max_iterations/max_consecutive)
    enable_final_success_gate: bool = False  # gates final_success_evaluator driving (audit otherwise)
    max_iterations: int = 12
    max_consecutive_tool_failures: int = 3
    stagnation_window: int = 3


@dataclass(frozen=True)
class PolicyConfig:
    skill: SkillDomainConfig = field(default_factory=SkillDomainConfig)
    gate: GateDomainConfig = field(default_factory=GateDomainConfig)
    quality: QualityDomainConfig = field(default_factory=QualityDomainConfig)


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
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
            gate_raw.get("enable_side_effect_detector"), True
        ),
        enable_data_classification_detector=_coerce_bool(
            gate_raw.get("enable_data_classification_detector"), True
        ),
        enable_prompt_fallback=_coerce_bool(
            gate_raw.get("enable_prompt_fallback"), True
        ),
        enable_skill_tool_group_detector=_coerce_bool(
            gate_raw.get("enable_skill_tool_group_detector"), False
        ),
        side_effect_defaults=merged_side_defaults,
    )

    quality = QualityDomainConfig(
        enable_quality_score=_coerce_bool(quality_raw.get("enable_quality_score"), False),
        enable_stop_dimensions=_coerce_bool(quality_raw.get("enable_stop_dimensions"), False),
        enable_final_success_gate=_coerce_bool(quality_raw.get("enable_final_success_gate"), False),
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
