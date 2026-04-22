"""Anthropic-wire mapping from neutral conversation turns."""

from __future__ import annotations

import pytest

from app.game_engine.agent_runtime.llm_providers.minimax_anthropic import (
    _turns_to_anthropic_messages,
)
from app.game_engine.agent_runtime.tool_calling import (
    AssistantToolUseTurn,
    TextTurn,
    ToolCall,
    ToolResult,
    ToolResultsTurn,
)


@pytest.mark.unit
def test_turns_include_assistant_tool_use_before_tool_result():
    tid = "call_function_u84xhcfw9uj4_1"
    msgs = _turns_to_anthropic_messages(
        [
            TextTurn(role="user", text="hi"),
            AssistantToolUseTurn(
                text="",
                tool_calls=[ToolCall(id=tid, name="help", args=[])],
            ),
            ToolResultsTurn(
                results=[ToolResult(id=tid, name="help", ok=True, text="HELP_OUT")]
            ),
        ]
    )
    assert len(msgs) == 3
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    kinds = [b.get("type") for b in msgs[1]["content"]]
    assert "tool_use" in kinds
    tu = next(b for b in msgs[1]["content"] if b.get("type") == "tool_use")
    assert tu.get("id") == tid
    assert tu.get("name") == "help"
    assert msgs[2]["role"] == "user"
    tr = msgs[2]["content"][0]
    assert tr.get("type") == "tool_result"
    assert tr.get("tool_use_id") == tid


@pytest.mark.unit
def test_assistant_tool_use_turn_may_include_leading_text():
    msgs = _turns_to_anthropic_messages(
        [
            AssistantToolUseTurn(
                text="I'll check.",
                tool_calls=[ToolCall(id="t1", name="look", args=[])],
            ),
            ToolResultsTurn(
                results=[ToolResult(id="t1", name="look", ok=True, text="ROOM")]
            ),
        ]
    )
    assert msgs[0]["role"] == "assistant"
    types = [b.get("type") for b in msgs[0]["content"]]
    assert types[0] == "text"
    assert types[1] == "tool_use"
