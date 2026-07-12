"""PolicyEngine — deterministic check-point evaluator.

The engine is a pure function over ``PolicyContext``: no DB, no LLM, no I/O.
Detectors are registered at import time and evaluated in order; the first
non-allow decision short-circuits the chain. If no detector fires the engine
returns ``allow``.

Registered detectors: ``side_effect_level``, ``data_classification``,
``skill_activation_mode`` (always on, inert until modes are populated), and
``skill_tool_group`` (opt-in via config toggle).
"""
from __future__ import annotations

import dataclasses
from typing import Callable, List, Optional, Tuple

from app.game_engine.agent_runtime.policy.context import PolicyContext
from app.game_engine.agent_runtime.policy.decisions import PolicyDecision

Detector = Callable[[PolicyContext], Optional[PolicyDecision]]


class PolicyEngine:
    """Stateless evaluator. Constructed once per process; safe to reuse."""

    def __init__(self, detectors: Optional[List[Detector]] = None) -> None:
        if detectors is None:
            detectors = _detectors_from_config()
        self._detectors: Tuple[Detector, ...] = tuple(detectors)

    def evaluate(self, ctx: PolicyContext) -> PolicyDecision:
        for detector in self._detectors:
            decision = detector(ctx)
            if decision is not None and not decision.is_allow:
                tagged = dataclasses.replace(
                    decision,
                    evidence={**decision.evidence, 'detector': detector.__name__},
                )
                return tagged
        return PolicyDecision.allow(ctx.check_point)

    @property
    def detectors(self) -> Tuple[Detector, ...]:
        return self._detectors


def _default_detectors() -> List[Detector]:
    # Local import to avoid module-level cycle when detectors import engine types.
    from app.game_engine.agent_runtime.policy.detectors import (
        data_classification_detector,
        side_effect_level_detector,
        skill_activation_mode_detector,
    )

    return [
        side_effect_level_detector,
        data_classification_detector,
        skill_activation_mode_detector,
    ]


def _detectors_from_config() -> List[Detector]:
    """Build the detector list honouring ``PolicyConfig`` toggles."""
    from app.core.config_manager import get_config
    from app.game_engine.agent_runtime.policy.detectors import (
        data_classification_detector,
        side_effect_level_detector,
        skill_activation_mode_detector,
        skill_tool_group_detector,
    )

    try:
        cm = get_config()
        enable_side_effect = cm.get_nested('policy', 'enable_side_effect_detector', default=True)
        enable_data_cls = cm.get_nested('policy', 'enable_data_classification_detector', default=True)
        enable_skill_group = cm.get_nested('policy', 'enable_skill_tool_group_detector', default=False)
    except Exception:  # noqa: BLE001 — config may be unavailable in unit tests
        return _default_detectors()

    detectors: List[Detector] = []
    if enable_side_effect:
        detectors.append(side_effect_level_detector)
    if enable_data_cls:
        detectors.append(data_classification_detector)
    if enable_skill_group:
        detectors.append(skill_tool_group_detector)
    detectors.append(skill_activation_mode_detector)
    return detectors


# Module-level singleton; detectors are stateless so reuse is safe.
default_engine = PolicyEngine()
