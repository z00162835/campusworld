"""
PDCA per-phase LLM routing (phase_llm, mode_models) — source of truth: npc_agent nodes.attributes.

System YAML (agents.llm) supplies connection parameters only; see F03.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from app.core.settings import PhaseLlmPhaseConfig


def parse_phase_llm_from_attributes(attrs: Dict[str, Any]) -> Tuple[Dict[str, PhaseLlmPhaseConfig], Dict[str, str]]:
    """
    Read instance-level phase_llm and mode_models from node.attributes.

    Expected shapes:
      attributes.phase_llm: { "plan": { "mode": "fast" }, ... }
      attributes.mode_models: { "fast": "gpt-4o-mini", ... }
    """
    raw_phases = attrs.get("phase_llm") if isinstance(attrs, dict) else None
    phase_llm: Dict[str, PhaseLlmPhaseConfig] = {}
    if isinstance(raw_phases, dict):
        for k, v in raw_phases.items():
            sk = str(k).strip()
            if not sk:
                continue
            if isinstance(v, PhaseLlmPhaseConfig):
                phase_llm[sk] = v
            elif isinstance(v, dict):
                phase_llm[sk] = PhaseLlmPhaseConfig.model_validate(v)

    raw_modes = attrs.get("mode_models") if isinstance(attrs, dict) else None
    mode_models: Dict[str, str] = {}
    if isinstance(raw_modes, dict):
        for k, v in raw_modes.items():
            mode_models[str(k).strip()] = str(v).strip() if v is not None else ""

    return phase_llm, mode_models
