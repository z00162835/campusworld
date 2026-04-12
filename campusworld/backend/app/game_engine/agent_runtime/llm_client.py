from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, runtime_checkable

import httpx

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


class OpenAiCompatibleHttpLlmClient:
    """
    OpenAI-compatible Chat Completions (POST /v1/chat/completions).
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        default_model: str,
        default_temperature: float = 0.2,
        default_max_tokens: int = 4096,
        timeout_sec: float = 120.0,
    ):
        self._base = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._api_key = api_key
        self._default_model = default_model
        self._default_temperature = default_temperature
        self._default_max_tokens = default_max_tokens
        self._timeout = timeout_sec

    def complete(self, *, system: str, user: str, call_spec: Optional[LlmCallSpec] = None) -> str:
        spec = call_spec or LlmCallSpec()
        model = (spec.model or self._default_model).strip() or self._default_model
        temperature = (
            spec.temperature if spec.temperature is not None else self._default_temperature
        )
        max_tokens = spec.max_tokens if spec.max_tokens is not None else self._default_max_tokens
        timeout = spec.timeout_sec if spec.timeout_sec is not None else self._timeout
        body: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system or " "},
                {"role": "user", "content": user or " "},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        body.update(spec.extra or {})
        url = f"{self._base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
        choices = data.get("choices") or []
        if not choices:
            return ""
        msg = (choices[0].get("message") or {})
        content = msg.get("content")
        return str(content or "").strip()


def build_llm_client_from_service_config(cfg) -> LlmClient:
    """
    Resolve Stub vs HTTP from AgentLlmServiceConfig + environment.
    """
    from app.core.settings import AgentLlmServiceConfig

    if not isinstance(cfg, AgentLlmServiceConfig):
        return StubLlmClient()
    env_name = (cfg.api_key_env or "").strip()
    key = os.environ.get(env_name, "").strip() if env_name else ""
    if cfg.use_http_llm and key and env_name:
        return OpenAiCompatibleHttpLlmClient(
            base_url=cfg.base_url or "https://api.openai.com/v1",
            api_key=key,
            default_model=cfg.model or "gpt-4o-mini",
            default_temperature=cfg.temperature,
            default_max_tokens=cfg.max_tokens,
        )
    return StubLlmClient()
