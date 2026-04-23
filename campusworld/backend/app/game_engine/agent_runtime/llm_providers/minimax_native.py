"""MiniMax native Text API (chatcompletion_v2)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.game_engine.agent_runtime.llm_client import LlmCallSpec
from app.game_engine.agent_runtime.llm_providers.http_utils import httpx_post_json


class MinimaxNativeTextHttpLlmClient:
    """MiniMax native Text API chatcompletion_v2 (Bearer)."""

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
        self._base_url = (base_url or "").strip().rstrip("/")
        self._api_key = api_key
        self._default_model = default_model
        self._default_temperature = default_temperature
        self._default_max_tokens = default_max_tokens
        self._timeout = timeout_sec

    def _post_url(self) -> str:
        if "chatcompletion" in self._base_url.lower():
            return self._base_url
        if not self._base_url:
            raise ValueError("base_url required for MiniMax native Text client")
        return f"{self._base_url}/v1/text/chatcompletion_v2"

    def complete(self, *, system: str, user: str, call_spec: Optional[LlmCallSpec] = None) -> str:
        spec = call_spec or LlmCallSpec()
        model = (spec.model or self._default_model).strip() or self._default_model
        max_tokens = spec.max_tokens if spec.max_tokens is not None else self._default_max_tokens
        timeout = spec.timeout_sec if spec.timeout_sec is not None else self._timeout
        temperature = spec.temperature if spec.temperature is not None else self._default_temperature
        body: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system or " "},
                {"role": "user", "content": user or " "},
            ],
            "stream": False,
            "temperature": float(temperature),
            "max_completion_tokens": int(max_tokens),
        }
        body.update(spec.extra or {})
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = self._post_url()
        data = httpx_post_json(url, headers=headers, body=body, timeout=timeout)
        br = data.get("base_resp")
        if isinstance(br, dict) and br.get("status_code") not in (None, 0):
            raise RuntimeError(str(br.get("status_msg") or br.get("status_code")))
        choices = data.get("choices") or []
        if not choices:
            return ""
        msg = (choices[0].get("message") or {})
        return str(msg.get("content") or "").strip()

    def supports_tools(self) -> bool:
        """MiniMax native function-calling is a separate follow-up PR."""
        return False
