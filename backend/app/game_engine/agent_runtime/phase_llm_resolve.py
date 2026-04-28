from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.settings import PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.llm_client import LlmCallSpec


def _default_phase_config(phase: str) -> PhaseLlmPhaseConfig:
    """When instance attributes.phase_llm omits a phase: plan/do/check use plan; act skips LLM."""
    from app.game_engine.agent_runtime.frameworks.pdca import PDCAPhase

    if phase == PDCAPhase.act.value:
        return PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip)
    return PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan)


def merge_phase_config(
    phase: str,
    instance_phase_llm: Dict[str, PhaseLlmPhaseConfig],
    ctx_overrides: Optional[Dict[str, Any]],
) -> PhaseLlmPhaseConfig:
    """Base config from npc_agent.attributes.phase_llm; tick overrides win."""
    base = instance_phase_llm.get(phase) if instance_phase_llm else None
    if base is None:
        base = _default_phase_config(phase)
    raw = (ctx_overrides or {}).get(phase)
    if not raw:
        return base
    if isinstance(raw, PhaseLlmPhaseConfig):
        merged = base.model_dump()
        merged.update(raw.model_dump(exclude_unset=True))
        return PhaseLlmPhaseConfig.model_validate(merged)
    if isinstance(raw, dict):
        merged = base.model_dump()
        merged.update(raw)
        return PhaseLlmPhaseConfig.model_validate(merged)
    return base


def to_llm_call_spec(
    phase_cfg: PhaseLlmPhaseConfig,
    *,
    mode_models: Dict[str, str],
    default_model: str,
) -> LlmCallSpec:
    if phase_cfg.mode == PhaseLlmMode.skip:
        return LlmCallSpec(mode=PhaseLlmMode.skip)
    mode_key = phase_cfg.mode.value
    resolved_model = (phase_cfg.model or "").strip() or mode_models.get(mode_key) or (default_model or "").strip()
    return LlmCallSpec(
        mode=phase_cfg.mode,
        model=resolved_model,
        temperature=phase_cfg.temperature,
        max_tokens=phase_cfg.max_tokens,
        timeout_sec=phase_cfg.timeout_sec,
        extra=dict(phase_cfg.extra or {}),
    )
