"""MiniMax Anthropic-compatible Messages API (POST .../anthropic/v1/messages)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.game_engine.agent_runtime.llm_client import LlmCallSpec
from app.game_engine.agent_runtime.llm_providers.http_utils import httpx_post_json


def minimax_anthropic_messages_url(base_url: str) -> str:
    b = (base_url or "").strip().rstrip("/")
    if not b:
        raise ValueError("base_url required for MiniMax Anthropic Messages client")
    if b.endswith("/v1/messages"):
        return b
    if b.endswith("/anthropic"):
        return f"{b}/v1/messages"
    if "/anthropic" in b.lower():
        return f"{b}/v1/messages"
    return f"{b}/anthropic/v1/messages"


def clamp_anthropic_temperature(value: float) -> float:
    """MiniMax Anthropic layer documents temperature in (0, 1]."""
    if value <= 0.0:
        return 0.01
    if value > 1.0:
        return 1.0
    return value


class MinimaxAnthropicMessagesHttpLlmClient:
    """
    MiniMax Anthropic-compatible Messages API.
    See https://platform.minimax.io/docs/api-reference/text-anthropic-api
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
        self._base_url = base_url
        self._api_key = api_key
        self._default_model = default_model
        self._default_temperature = default_temperature
        self._default_max_tokens = default_max_tokens
        self._timeout = timeout_sec

    def complete(self, *, system: str, user: str, call_spec: Optional[LlmCallSpec] = None) -> str:
        spec = call_spec or LlmCallSpec()
        model = (spec.model or self._default_model).strip() or self._default_model
        max_tokens = spec.max_tokens if spec.max_tokens is not None else self._default_max_tokens
        timeout = spec.timeout_sec if spec.timeout_sec is not None else self._timeout
        temp = spec.temperature if spec.temperature is not None else self._default_temperature
        temp = clamp_anthropic_temperature(float(temp))

        url = minimax_anthropic_messages_url(self._base_url)
        body: Dict[str, Any] = {
            "model": model,
            "max_tokens": int(max_tokens),
            "system": system or " ",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": user or " "}],
                }
            ],
            "stream": False,
            "temperature": temp,
        }
        body.update(spec.extra or {})
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        data = httpx_post_json(url, headers=headers, body=body, timeout=timeout)
        err = data.get("error")
        if isinstance(err, dict) and err.get("message"):
            raise RuntimeError(str(err.get("message")))
        parts: list[str] = []
        for block in data.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        return "\n".join(p.strip() for p in parts if p.strip()).strip()
