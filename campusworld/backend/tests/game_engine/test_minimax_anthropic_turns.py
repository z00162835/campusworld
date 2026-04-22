"""Anthropic-wire mapping from neutral conversation turns."""

from __future__ import annotations

import pytest

from app.game_engine.agent_runtime.llm_providers.minimax_anthropic import (
    _tool_result_content_wire,
    _turns_to_anthropic_messages,
    _validate_anthropic_tool_messages,
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
    assert tr.get("content") == [{"type": "text", "text": "HELP_OUT"}]
    _validate_anthropic_tool_messages(msgs, allowed_tool_names={"help"})


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


@pytest.mark.unit
def test_tool_result_content_wire_empty():
    assert _tool_result_content_wire("") == [{"type": "text", "text": ""}]


@pytest.mark.unit
def test_validate_rejects_tool_result_before_assistant_tool_use():
    with pytest.raises(ValueError, match="no preceding"):
        _validate_anthropic_tool_messages(
            [
                {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": []}]},
            ],
            allowed_tool_names={"help"},
        )


@pytest.mark.unit
def test_validate_rejects_text_before_tool_result_in_same_user_message():
    msgs = _turns_to_anthropic_messages(
        [
            AssistantToolUseTurn(
                text="",
                tool_calls=[ToolCall(id="a", name="help", args=[])],
            ),
        ]
    )
    msgs.append(
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "oops"},
                {"type": "tool_result", "tool_use_id": "a", "content": [{"type": "text", "text": "x"}]},
            ],
        }
    )
    with pytest.raises(ValueError, match="tool_result blocks must come before"):
        _validate_anthropic_tool_messages(msgs, allowed_tool_names={"help"})


@pytest.mark.unit
def test_validate_rejects_unknown_tool_name():
    msgs = _turns_to_anthropic_messages(
        [
            AssistantToolUseTurn(
                text="",
                tool_calls=[ToolCall(id="z", name="help", args=[])],
            ),
        ]
    )
    bad = msgs[0]["content"]
    for b in bad:
        if b.get("type") == "tool_use":
            b["name"] = "not_registered"
    with pytest.raises(ValueError, match="not in request tools"):
        _validate_anthropic_tool_messages(msgs, allowed_tool_names={"help"})
