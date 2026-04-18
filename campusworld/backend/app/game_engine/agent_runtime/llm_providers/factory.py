"""Select concrete HTTP LLM client from ``AgentLlmServiceConfig`` (by base_url shape)."""

from __future__ import annotations

from app.core.settings import AgentLlmServiceConfig
from app.game_engine.agent_runtime.llm_client import LlmClient, StubLlmClient
from app.game_engine.agent_runtime.llm_providers.minimax_anthropic import (
    MinimaxAnthropicMessagesHttpLlmClient,
)
from app.game_engine.agent_runtime.llm_providers.minimax_native import MinimaxNativeTextHttpLlmClient
from app.game_engine.agent_runtime.llm_providers.openai_compatible import OpenAiCompatibleHttpLlmClient


def build_http_llm_client(cfg: AgentLlmServiceConfig, api_key: str) -> LlmClient:
    """
    Route by ``base_url`` — extend here when adding providers.

    - ``/anthropic`` in URL → MiniMax Anthropic Messages API
    - ``chatcompletion`` or ``/text/`` in URL → MiniMax native Text API
    - else → OpenAI-compatible ``/v1/chat/completions``
    """
    if not isinstance(cfg, AgentLlmServiceConfig):
        return StubLlmClient()
    base = (cfg.base_url or "").strip()
    low = base.lower()
    if "/anthropic" in low:
        return MinimaxAnthropicMessagesHttpLlmClient(
            base_url=base,
            api_key=api_key,
            default_model=cfg.model or "MiniMax-M2.7",
            default_temperature=cfg.temperature,
            default_max_tokens=cfg.max_tokens,
        )
    if "chatcompletion" in low or "/text/" in low:
        return MinimaxNativeTextHttpLlmClient(
            base_url=base,
            api_key=api_key,
            default_model=cfg.model or "MiniMax-M2.7",
            default_temperature=cfg.temperature,
            default_max_tokens=cfg.max_tokens,
        )
    return OpenAiCompatibleHttpLlmClient(
        base_url=base or "https://api.openai.com/v1",
        api_key=api_key,
        default_model=cfg.model or "gpt-4o-mini",
        default_temperature=cfg.temperature,
        default_max_tokens=cfg.max_tokens,
    )
