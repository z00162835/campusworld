from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.config_manager import get_config
from app.core.settings import AgentLlmServiceConfig

# Materialized YAML slice for default AICO (service_id / model_config_ref both aico); refreshed on config load/reload.
_aico_system_llm_base: Optional[AgentLlmServiceConfig] = None


def apply_model_config_from_attributes(
    cfg: AgentLlmServiceConfig,
    node_attributes: Optional[Dict[str, Any]],
) -> AgentLlmServiceConfig:
    """
    Merge ``nodes.attributes.model_config`` (non-secret whitelist only).

    Allowed keys: temperature, max_tokens, model. Applied after YAML, before prompt_overrides.
    """
    if not node_attributes:
        return cfg
    raw = node_attributes.get("model_config")
    if not isinstance(raw, dict):
        return cfg
    updates: Dict[str, Any] = {}
    if "temperature" in raw and raw["temperature"] is not None:
        try:
            updates["temperature"] = float(raw["temperature"])
        except (TypeError, ValueError):
            pass
    if "max_tokens" in raw and raw["max_tokens"] is not None:
        try:
            updates["max_tokens"] = int(raw["max_tokens"])
        except (TypeError, ValueError):
            pass
    if "model" in raw and isinstance(raw["model"], str) and raw["model"].strip():
        updates["model"] = raw["model"].strip()
    if not updates:
        return cfg
    return cfg.model_copy(update=updates)


def apply_prompt_overrides(cfg: AgentLlmServiceConfig, prompt_overrides: Dict[str, Any]) -> AgentLlmServiceConfig:
    """
    Merge ``nodes.attributes.prompt_overrides`` into YAML-resolved config.

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


def yaml_llm_base_from_by_service_id(
    service_id: str,
    model_config_ref: Optional[str] = None,
) -> AgentLlmServiceConfig:
    """
    Parse ``agents.llm.by_service_id`` for one logical service (no node merge).

    Same key resolution as the YAML half of ``resolve_agent_llm_config``.
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
            raw_for_llm = dict(raw)
            raw_for_llm.pop("observability", None)
            cfg = AgentLlmServiceConfig.model_validate(raw_for_llm)
    return cfg


def refresh_aico_system_llm_config() -> None:
    """Re-read AICO YAML base from current ConfigManager cache (call after load/reload)."""
    global _aico_system_llm_base
    _aico_system_llm_base = yaml_llm_base_from_by_service_id("aico", "aico")


def invalidate_aico_system_llm_config() -> None:
    """Clear cached AICO YAML base (tests / forced cold read)."""
    global _aico_system_llm_base
    _aico_system_llm_base = None


def merge_aico_system_llm_with_node(
    node_attributes: Optional[Dict[str, Any]],
) -> AgentLlmServiceConfig:
    """Merge materialized AICO YAML base with node whitelist (model_config, prompt_overrides)."""
    base = _aico_system_llm_base
    if base is None:
        base = yaml_llm_base_from_by_service_id("aico", "aico")
    cfg = base.model_copy(deep=True)
    cfg = apply_model_config_from_attributes(cfg, node_attributes)
    return apply_prompt_overrides_from_attributes(cfg, node_attributes)


def uses_aico_materialized_yaml_base(service_id: str, model_config_ref: Optional[str]) -> bool:
    """True when tick can use init-time AICO YAML materialization (default built-in assistant keys)."""
    sid = (service_id or "").strip().lower()
    ref = (str(model_config_ref).strip().lower() if model_config_ref else None) or sid
    return sid == "aico" and ref == "aico"


def resolve_agent_llm_config_for_npc_tick(
    service_id: str,
    *,
    model_config_ref: Optional[str] = None,
    node_attributes: Optional[Dict[str, Any]] = None,
) -> AgentLlmServiceConfig:
    """Hot path: AICO default uses materialized YAML + node merge; other agents use full resolve."""
    if uses_aico_materialized_yaml_base(service_id, model_config_ref):
        return merge_aico_system_llm_with_node(node_attributes)
    return resolve_agent_llm_config(
        service_id,
        model_config_ref=model_config_ref,
        node_attributes=node_attributes,
    )


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
    then nodes.attributes.model_config (whitelist: temperature, max_tokens, model);
    then nodes.attributes.prompt_overrides (system_prompt / phase_prompts only).
    """
    cfg = yaml_llm_base_from_by_service_id(service_id, model_config_ref)
    cfg = apply_model_config_from_attributes(cfg, node_attributes)
    return apply_prompt_overrides_from_attributes(cfg, node_attributes)
