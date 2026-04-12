from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.config_manager import get_config
from app.core.settings import AgentLlmServiceConfig


def apply_prompt_overrides(cfg: AgentLlmServiceConfig, prompt_overrides: Dict[str, Any]) -> AgentLlmServiceConfig:
    """
    Merge F03 nodes.attributes.prompt_overrides into YAML-resolved config.

    Only non-secret fields allowed: system_prompt, phase_prompts (same keys as YAML).
    Unknown keys are ignored. phase_prompts merges by key on top of cfg.phase_prompts.
    """
    updates: Dict[str, Any] = {}
    if "system_prompt" in prompt_overrides:
        sp = prompt_overrides["system_prompt"]
        if isinstance(sp, str):
            updates["system_prompt"] = sp
    if "phase_prompts" in prompt_overrides:
        pp = prompt_overrides["phase_prompts"]
        if isinstance(pp, dict):
            merged = dict(cfg.phase_prompts)
            for k, v in pp.items():
                if not isinstance(v, str):
                    continue
                key = str(k).strip()
                if not key:
                    continue
                merged[key] = v
            updates["phase_prompts"] = merged
    if not updates:
        return cfg
    return cfg.model_copy(update=updates)


def apply_prompt_overrides_from_attributes(
    cfg: AgentLlmServiceConfig,
    node_attributes: Optional[Dict[str, Any]],
) -> AgentLlmServiceConfig:
    if not node_attributes:
        return cfg
    raw = node_attributes.get("prompt_overrides")
    if not isinstance(raw, dict):
        return cfg
    return apply_prompt_overrides(cfg, raw)


def resolve_agent_llm_config(
    service_id: str,
    *,
    model_config_ref: Optional[str] = None,
    node_attributes: Optional[Dict[str, Any]] = None,
) -> AgentLlmServiceConfig:
    """
    Load merged LLM + prompt defaults for an npc_agent instance.

    Priority: YAML `agents.llm.by_service_id[<model_config_ref>]` if set,
    else `agents.llm.by_service_id[<service_id>]`, else Pydantic defaults;
    then optional nodes.attributes.prompt_overrides (system_prompt / phase_prompts only, F03 §5.4).
    """
    cfg = AgentLlmServiceConfig()
    cm = get_config()
    by_sid = cm.get_nested("agents", "llm", "by_service_id", default=None)
    if isinstance(by_sid, dict):
        ref = model_config_ref or service_id
        raw = by_sid.get(ref)
        if raw is None and ref != service_id:
            raw = by_sid.get(service_id)
        if raw is not None and isinstance(raw, dict):
            cfg = AgentLlmServiceConfig.model_validate(raw)
    return apply_prompt_overrides_from_attributes(cfg, node_attributes)
