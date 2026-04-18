"""
Core LLM types and wiring for agent runtime.

- ``LlmCallSpec`` / ``LlmClient`` / ``StubLlmClient`` — shared contracts
- ``http_llm_available`` / ``build_llm_client_from_service_config`` — config + env gate

Vendor-specific HTTP clients live under ``llm_providers/``; routing is in ``llm_providers/factory.py``.
Shared HTTP helpers: ``llm_providers/http_utils.py``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from app.core.settings import PhaseLlmMode


@dataclass
class LlmCallSpec:
    """Per-call options for one PDCA phase (merged from YAML + tick overrides)."""

    mode: PhaseLlmMode = PhaseLlmMode.plan
    model: str = ""
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout_sec: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LlmClient(Protocol):
    """LLM surface for agent frameworks; supports per-phase call_spec."""

    def complete(self, *, system: str, user: str, call_spec: Optional[LlmCallSpec] = None) -> str:
        """Return assistant text for one user turn (non-streaming)."""
        ...


class StubLlmClient:
    """Deterministic stub when no provider is configured (tests and dev)."""

    def complete(self, *, system: str, user: str, call_spec: Optional[LlmCallSpec] = None) -> str:
        u = (user or "").strip()
        mode = (call_spec.mode.value if call_spec else "plan") if call_spec else "plan"
        if len(u) > 400:
            u = u[:400] + "…"
        return f"[stub_llm mode={mode}] {u}"


def http_llm_available(cfg) -> bool:
    """True when config requests HTTP LLM and the referenced API key env var is non-empty."""
    from app.core.settings import AgentLlmServiceConfig

    if not isinstance(cfg, AgentLlmServiceConfig):
        return False
    env_name = (cfg.api_key_env or "").strip()
    key = os.environ.get(env_name, "").strip() if env_name else ""
    return bool(cfg.use_http_llm and env_name and key)


def build_llm_client_from_service_config(cfg) -> LlmClient:
    """
    Resolve Stub vs HTTP from ``AgentLlmServiceConfig`` + environment.

    HTTP implementation is selected in ``llm_providers.factory.build_http_llm_client``.
    """
    from app.core.settings import AgentLlmServiceConfig

    if not isinstance(cfg, AgentLlmServiceConfig):
        return StubLlmClient()
    if http_llm_available(cfg):
        env_name = (cfg.api_key_env or "").strip()
        key = os.environ.get(env_name, "").strip() if env_name else ""
        from app.game_engine.agent_runtime.llm_providers.factory import build_http_llm_client

        return build_http_llm_client(cfg, key)
    return StubLlmClient()
