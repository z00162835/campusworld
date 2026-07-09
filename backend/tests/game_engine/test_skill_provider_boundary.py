"""Provider boundary: skill-context injected into user/input context, never system."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.game_engine.agent_runtime.llm_client import LlmCallSpec
from app.game_engine.agent_runtime.llm_providers.minimax_anthropic import (
    MinimaxAnthropicMessagesHttpLlmClient,
    _anthropic_user_blocks,
    _inject_skill_context_into_messages,
)
from app.game_engine.agent_runtime.llm_providers.openai_compatible import (
    OpenAiCompatibleHttpLlmClient,
    _openai_user_content,
)
from app.game_engine.agent_runtime.tool_calling import TextTurn


class TestAnthropicUserBlocks:
    def test_skill_context_is_leading_separate_block(self):
        blocks = _anthropic_user_blocks("hello", "SKILL CONTEXT")
        assert len(blocks) == 2
        assert blocks[0] == {"type": "text", "text": "SKILL CONTEXT"}
        assert blocks[1] == {"type": "text", "text": "hello"}

    def test_no_skill_context_single_block(self):
        blocks = _anthropic_user_blocks("hello", None)
        assert blocks == [{"type": "text", "text": "hello"}]

    def test_empty_skill_context_collapses(self):
        blocks = _anthropic_user_blocks("hello", "  ")
        assert blocks == [{"type": "text", "text": "hello"}]


class TestAnthropicMessageInjection:
    def test_prepend_to_first_user_message(self):
        messages = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
        _inject_skill_context_into_messages(messages, "SKILL CONTEXT")
        assert messages[0]["role"] == "user"
        assert messages[0]["content"][0] == {"type": "text", "text": "SKILL CONTEXT"}
        assert messages[0]["content"][1] == {"type": "text", "text": "hi"}

    def test_inserts_leading_user_when_none(self):
        messages = [{"role": "assistant", "content": [{"type": "text", "text": "x"}]}]
        _inject_skill_context_into_messages(messages, "SKILL CONTEXT")
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == [{"type": "text", "text": "SKILL CONTEXT"}]

    def test_noop_when_empty(self):
        messages = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
        _inject_skill_context_into_messages(messages, "")
        assert messages[0]["content"] == [{"type": "text", "text": "hi"}]


class TestOpenAiUserContent:
    def test_skill_context_prepended_to_user(self):
        out = _openai_user_content("hello", "SKILL CONTEXT")
        assert out.startswith("SKILL CONTEXT")
        assert "hello" in out

    def test_no_skill_context_returns_user(self):
        assert _openai_user_content("hello", None) == "hello"

    def test_empty_skill_context_returns_user(self):
        assert _openai_user_content("hello", "  ") == "hello"


class _FakeHttp:
    """Captures the request body instead of doing HTTP."""

    def __init__(self) -> None:
        self.bodies: List[Dict[str, Any]] = []

    def post_json(self, url, headers, body, timeout, cancel_check=None):
        self.bodies.append(body)
        # Minimal valid Anthropic-style success response.
        return {"content": [{"type": "text", "text": "ok"}]}


def _anthropic_client(fake: _FakeHttp) -> MinimaxAnthropicMessagesHttpLlmClient:
    c = MinimaxAnthropicMessagesHttpLlmClient(
        base_url="https://x", api_key="k", default_model="m",
    )
    c._post = fake.post_json  # type: ignore[attr-defined]
    return c


class TestAnthropicCompleteBoundary:
    def test_skill_context_in_user_content_not_system(self, monkeypatch):
        import app.game_engine.agent_runtime.llm_providers.minimax_anthropic as mod

        fake = _FakeHttp()
        monkeypatch.setattr(mod, "httpx_post_json", fake.post_json)
        client = MinimaxAnthropicMessagesHttpLlmClient(base_url="https://x", api_key="k", default_model="m")
        spec = LlmCallSpec(skill_context_text="SKILL CONTEXT HERE")
        client.complete(system="PLATFORM SYSTEM", user="hello", call_spec=spec)
        assert fake.bodies, "expected one HTTP call"
        body = fake.bodies[0]
        # system must contain only the platform system text
        assert body["system"] == "PLATFORM SYSTEM"
        # user message content blocks: skill context first, then user
        user_blocks = body["messages"][0]["content"]
        assert user_blocks[0]["text"] == "SKILL CONTEXT HERE"
        assert user_blocks[1]["text"] == "hello"
        assert "SKILL CONTEXT HERE" not in str(body["system"])

    def test_no_skill_context_keeps_single_user_block(self, monkeypatch):
        import app.game_engine.agent_runtime.llm_providers.minimax_anthropic as mod

        fake = _FakeHttp()
        monkeypatch.setattr(mod, "httpx_post_json", fake.post_json)
        client = MinimaxAnthropicMessagesHttpLlmClient(base_url="https://x", api_key="k", default_model="m")
        client.complete(system="PLATFORM SYSTEM", user="hello", call_spec=LlmCallSpec())
        body = fake.bodies[0]
        assert body["messages"][0]["content"] == [{"type": "text", "text": "hello"}]


class TestOpenAiCompleteBoundary:
    def test_skill_context_in_user_content_not_system(self, monkeypatch):
        import app.game_engine.agent_runtime.llm_providers.openai_compatible as mod

        fake = _FakeHttp()
        monkeypatch.setattr(mod, "httpx_post_json", fake.post_json)
        client = OpenAiCompatibleHttpLlmClient(base_url="https://x/v1", api_key="k", default_model="m")
        spec = LlmCallSpec(skill_context_text="SKILL CONTEXT HERE")
        client.complete(system="PLATFORM SYSTEM", user="hello", call_spec=spec)
        body = fake.bodies[0]
        messages = body["messages"]
        # system message is platform-only
        assert messages[0] == {"role": "system", "content": "PLATFORM SYSTEM"}
        # user message carries skill context + user text
        assert "SKILL CONTEXT HERE" in messages[1]["content"]
        assert "hello" in messages[1]["content"]
        assert "SKILL CONTEXT HERE" not in messages[0]["content"]
