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
import math
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

    blocked_skill_activation_modes: tuple[str, ...] = ()


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
    blocked_data_classifications: tuple[str, ...] = ("confidential", "restricted")
    tool_group_hierarchy: Dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "read": ("observe", "agent_meta", "identity", "communicate"),
        }
    )
    # P4 pattern_match detector (prompt injection / 越权短语). Default-off so
    # default config is byte-equivalent; an empty pattern set is a no-op even
    # when the detector is enabled. Patterns are kept case-sensitive (regex
    # matching uses re.IGNORECASE at the detector); do not lowercase them.
    enable_pattern_match_detector: bool = False
    pattern_match_patterns: tuple[str, ...] = ()
    pattern_match_decision: str = "require_approval"


@dataclass(frozen=True)
class QualityDomainConfig:
    enable_quality_score: bool = False
    enable_stop_dimensions: bool = False   # gates stop_evaluator dimensions and tick budget checks
    final_success_drive_mode: str = "off"  # off / shadow (audit+divergence) / enforce (evaluator drives draft_incomplete)
    enable_budget_hard_fail: bool = False  # opt-in hard-fail terminal for budget_exceeded; default soft-fail
    enable_obs_grounded_claims_gate: bool = False  # S2: grounding_quality hard_gate at before_terminal (default-off, byte-equiv)
    obs_grounded_gte: float = 0.15  # S2: grounding quality threshold (token overlap)
    enable_success_criteria_gate: bool = False  # S3: success_criteria_addressed hard_gate at before_terminal (default-off, byte-equiv)
    react_turn_min_criteria_hits: int = 1  # S3 / react_turn_success: min criteria hit count for pass (N-hit rule)
    semantic_weight_grounding: float = 0.5  # H6: semantic dim weight for grounding_quality
    semantic_weight_criteria: float = 0.3  # H6: semantic dim weight for criteria_coverage
    semantic_weight_progress: float = 0.2  # H6: semantic dim weight for progress
    stagnation_cycle_window_multiplier: int = 2  # H7: cycle window = multiplier * stagnation_window
    token_min_length: int = 2  # H8: min token length for grounding/criteria tokenization
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


def _coerce_float(value: Any, default: float) -> float:
    """Coerce to float; reject NaN/inf and fall back to default on invalid input."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    # Reject NaN and infinities — they silently break comparisons and scoring.
    if math.isnan(result) or math.isinf(result):
        logger.warning("Invalid float policy config (NaN/inf): %r; using default %s", value, default)
        return default
    return result


def _coerce_float_range(
    value: Any, default: float, *, lo: float, hi: float, key: str = "value"
) -> float:
    """Coerce to float within [lo, hi]; reject NaN/inf/out-of-range."""
    result = _coerce_float(value, default)
    if not (lo <= result <= hi):
        logger.warning(
            "Invalid float policy config for %s: %r out of range [%s, %s]; using default %s",
            key, value, lo, hi, default,
        )
        return default
    return result


def _coerce_nonneg_float(value: Any, default: float, *, key: str = "value") -> float:
    """Coerce to a non-negative float; reject NaN/inf/negative."""
    result = _coerce_float(value, default)
    if result < 0:
        logger.warning(
            "Invalid float policy config for %s: %r is negative; using default %s",
            key, value, default,
        )
        return default
    return result


def _coerce_str_list(value: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    """Coerce a YAML list/str into a tuple of stripped lowercase strings.

    Only falls back to ``default`` when the key is missing (``None``) or the
    value is the wrong type. An **explicitly empty** list/string is preserved
    as an empty tuple — this lets admins set ``blocked_data_classifications: []``
    to mean "block nothing" rather than silently restoring the default.
    """
    if value is None:
        return default
    if isinstance(value, str):
        return (value.strip().lower(),) if value.strip() else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(v).strip().lower() for v in value if str(v).strip())
    return default


def _coerce_pattern_list(value: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    """Coerce a YAML list/str into a tuple of stripped **case-preserved** strings.

    Unlike :func:`_coerce_str_list`, patterns keep their original case because
    regex semantics may depend on it (matching itself uses ``re.IGNORECASE`` at
    the detector). An explicitly empty list/str is preserved as an empty tuple
    (no-op); only a missing key (``None``) or wrong type falls back to default.
    """
    if value is None:
        return default
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(v).strip() for v in value if str(v).strip())
    return default


_VALID_PATTERN_DECISIONS = frozenset({"allow", "require_approval", "deny"})


def _coerce_pattern_decision(value: Any, default: str = "require_approval") -> str:
    """Coerce ``pattern_match_decision``; fall back to default on invalid value."""
    if isinstance(value, str):
        v = value.strip().lower()
        if v in _VALID_PATTERN_DECISIONS:
            return v
    return default


def _coerce_str_dict_of_lists(
    value: Any, default: dict[str, tuple[str, ...]]
) -> dict[str, tuple[str, ...]]:
    """Coerce a YAML dict[str, list[str]] into a normalized dict.

    Only falls back to ``default`` when the value is not a dict. An **explicitly
    empty** dict (``{}``) is preserved as an empty dict — this lets admins clear
    the tool_group_hierarchy rather than silently restoring the default.
    """
    if not isinstance(value, dict):
        return dict(default)
    out: dict[str, tuple[str, ...]] = {}
    for k, v in value.items():
        key = str(k).strip().lower()
        if not key:
            continue
        if isinstance(v, str):
            children = (v.strip().lower(),) if v.strip() else ()
        elif isinstance(v, (list, tuple)):
            children = tuple(str(x).strip().lower() for x in v if str(x).strip())
        else:
            children = ()
        out[key] = children
    return out


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

    skill = SkillDomainConfig(
        blocked_skill_activation_modes=_coerce_str_list(
            skill_raw.get("blocked_skill_activation_modes"), ()
        ),
    )

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
        blocked_data_classifications=_coerce_str_list(
            gate_raw.get("blocked_data_classifications"),
            ("confidential", "restricted"),
        ),
        tool_group_hierarchy=_coerce_str_dict_of_lists(
            gate_raw.get("tool_group_hierarchy"),
            {"read": ("observe", "agent_meta", "identity", "communicate")},
        ),
        enable_pattern_match_detector=_coerce_bool(
            gate_raw.get("enable_pattern_match_detector"), False,
            key="gate.enable_pattern_match_detector",
        ),
        pattern_match_patterns=_coerce_pattern_list(
            gate_raw.get("pattern_match_patterns"), ()
        ),
        pattern_match_decision=_coerce_pattern_decision(
            gate_raw.get("pattern_match_decision"), "require_approval"
        ),
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
        enable_obs_grounded_claims_gate=_coerce_bool(
            quality_raw.get("enable_obs_grounded_claims_gate"), False,
            key="quality.enable_obs_grounded_claims_gate",
        ),
        obs_grounded_gte=_coerce_float_range(
            quality_raw.get("obs_grounded_gte"), 0.15, lo=0.0, hi=1.0,
            key="quality.obs_grounded_gte",
        ),
        enable_success_criteria_gate=_coerce_bool(
            quality_raw.get("enable_success_criteria_gate"), False,
            key="quality.enable_success_criteria_gate",
        ),
        react_turn_min_criteria_hits=_coerce_int(
            quality_raw.get("react_turn_min_criteria_hits"), 1
        ),
        semantic_weight_grounding=_coerce_nonneg_float(
            quality_raw.get("semantic_weight_grounding"), 0.5,
            key="quality.semantic_weight_grounding",
        ),
        semantic_weight_criteria=_coerce_nonneg_float(
            quality_raw.get("semantic_weight_criteria"), 0.3,
            key="quality.semantic_weight_criteria",
        ),
        semantic_weight_progress=_coerce_nonneg_float(
            quality_raw.get("semantic_weight_progress"), 0.2,
            key="quality.semantic_weight_progress",
        ),
        stagnation_cycle_window_multiplier=_coerce_int(
            quality_raw.get("stagnation_cycle_window_multiplier"), 2
        ),
        token_min_length=_coerce_int(quality_raw.get("token_min_length"), 2),
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
