"""
Per-vendor HTTP LLM implementations.

- ``openai_compatible``: OpenAI Chat Completions shape
- ``minimax_anthropic``: MiniMax Anthropic-compatible Messages API
- ``minimax_native``: MiniMax native Text API (chatcompletion_v2)
- ``factory``: ``build_http_llm_client`` — routing from ``AgentLlmServiceConfig``
- ``http_utils``: shared httpx POST + JSON

Import ``LlmCallSpec`` / ``LlmClient`` / ``StubLlmClient`` from ``llm_client`` (core types).
"""

from app.game_engine.agent_runtime.llm_providers.factory import build_http_llm_client

__all__ = ["build_http_llm_client"]
