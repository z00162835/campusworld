"""OpenAI-compatible Chat Completions API (POST /v1/chat/completions)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.game_engine.agent_runtime.llm_client import LlmCallSpec
from app.game_engine.agent_runtime.llm_providers.http_utils import httpx_post_json


class OpenAiCompatibleHttpLlmClient:
    """OpenAI-compatible Chat Completions (POST {base}/chat/completions)."""

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
        extra = dict(spec.extra or {})
        extra.pop("prompt_fingerprint", None)
        body.update(extra)
        url = f"{self._base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        data = httpx_post_json(url, headers=headers, body=body, timeout=timeout)
        choices = data.get("choices") or []
        if not choices:
            return ""
        msg = (choices[0].get("message") or {})
        content = msg.get("content")
        return str(content or "").strip()

    def supports_tools(self) -> bool:
        """Native ``tools`` wiring is tracked as a follow-up.

        Returning ``False`` lets the framework fall back to the JSON
        ``commands`` parser rather than silently calling ``NotImplementedError``.
        """
        return False
