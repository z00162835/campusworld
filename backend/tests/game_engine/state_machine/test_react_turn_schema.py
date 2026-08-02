"""Unit tests for react_turn_schema parse / repair / degrade."""
from __future__ import annotations

import json

import pytest

from app.game_engine.agent_runtime.tool_calling import (
    CompleteWithToolsResult,
    TextTurn,
    ToolCall,
)
from app.game_engine.agent_runtime.state_machine.react_turn_schema import (
    EMIT_TURN_TOOL_NAME,
    ReactTurn,
    emit_structured_turn,
    parse_react_turn,
    text_from_react_turn,
    tool_calls_from_react_turn,
)


def _valid_payload(**overrides):
    base = {
        "turn_id": "t1",
        "task_state_summary": "s",
        "reason_summary": "r",
        "selected_skill": "problem_framing",
        "proposed_action": {
            "action_type": "final_answer",
            "final_answer_draft": "hello",
        },
        "expected_observation": "",
        "success_criteria": ["done"],
    }
    base.update(overrides)
    return base


@pytest.mark.unit
def test_parse_and_text_from_react_turn():
    turn = parse_react_turn(_valid_payload())
    assert isinstance(turn, ReactTurn)
    assert text_from_react_turn(turn) == "hello"


@pytest.mark.unit
def test_tool_calls_from_react_turn():
    turn = parse_react_turn(
        _valid_payload(
            proposed_action={
                "action_type": "tool_call",
                "tool_name": "help",
                "tool_args": {"args": []},
            }
        )
    )
    calls = tool_calls_from_react_turn(turn)
    assert len(calls) == 1
    assert calls[0].name == "help"


@pytest.mark.unit
def test_emit_structured_turn_tool_as_schema():
    payload = _valid_payload()

    class _ToolsLlm:
        def supports_tools(self) -> bool:
            return True

        def complete(self, **kwargs):
            raise AssertionError("complete should not be used")

        def complete_with_tools(self, **kwargs):
            assert kwargs["tools"][0].name == EMIT_TURN_TOOL_NAME
            assert kwargs["call_spec"].extra.get("tool_choice", {}).get("name") == EMIT_TURN_TOOL_NAME
            return CompleteWithToolsResult(
                text="",
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name=EMIT_TURN_TOOL_NAME,
                        args=[],
                        input_payload=payload,
                    )
                ],
                finish_reason="tool_use",
            )

    out = emit_structured_turn(
        _ToolsLlm(),
        system="sys",
        turns=[TextTurn(role="user", text="hi")],
        force_tool=True,
    )
    assert out.ok
    assert out.channel == "tool_as_schema"
    assert out.text == "hello"
    assert not out.degraded


@pytest.mark.unit
def test_emit_structured_turn_json_repair_then_ok():
    class _TextLlm:
        def __init__(self) -> None:
            self.calls = 0

        def supports_tools(self) -> bool:
            return False

        def complete(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return "not-json"
            return json.dumps(_valid_payload())

    llm = _TextLlm()
    out = emit_structured_turn(
        llm,
        system="sys",
        turns=[TextTurn(role="user", text="hi")],
        force_tool=True,
    )
    assert out.ok
    assert out.repaired
    assert out.channel == "json"
    assert llm.calls == 2


@pytest.mark.unit
def test_emit_structured_turn_degrades_after_repair_fail():
    class _TextLlm:
        def supports_tools(self) -> bool:
            return False

        def complete(self, **kwargs):
            return "still broken prose"

    out = emit_structured_turn(
        _TextLlm(),
        system="sys",
        turns=[TextTurn(role="user", text="hi")],
        force_tool=True,
    )
    assert not out.ok
    assert out.degraded
    assert out.channel == "free_text"
    assert "still broken" in out.text


@pytest.mark.unit
def test_tool_args_flat_dict_rejected_routes_to_repair():
    """D2 (方案 A): flat flag dict is invalid; parse_react_turn raises so repair/degrade runs."""
    from pydantic import ValidationError

    with pytest.raises((ValidationError, ValueError)):
        parse_react_turn(
            _valid_payload(
                proposed_action={
                    "action_type": "tool_call",
                    "tool_name": "look",
                    "tool_args": {"-n": "hicampus"},
                }
            )
        )


@pytest.mark.unit
def test_tool_args_explicit_array_preserved():
    """D2: {"args": ["-n", "hicampus"]} is preserved verbatim as argv."""
    turn = parse_react_turn(
        _valid_payload(
            proposed_action={
                "action_type": "tool_call",
                "tool_name": "look",
                "tool_args": {"args": ["-n", "hicampus"]},
            }
        )
    )
    calls = tool_calls_from_react_turn(turn)
    assert len(calls) == 1
    assert calls[0].name == "look"
    assert calls[0].args == ["-n", "hicampus"]


@pytest.mark.unit
def test_emit_structured_turn_reraises_llm_cancel():
    """D1: LlmRequestCancelled must propagate (no repair/degrade) so the PDCA cancel path runs."""
    from app.game_engine.agent_runtime.llm_providers.http_utils import LlmRequestCancelled

    class _CancelLlm:
        def supports_tools(self) -> bool:
            return True

        def complete(self, **kwargs):
            raise AssertionError("complete should not be used")

        def complete_with_tools(self, **kwargs):
            raise LlmRequestCancelled()

    with pytest.raises(LlmRequestCancelled):
        emit_structured_turn(
            _CancelLlm(),
            system="sys",
            turns=[TextTurn(role="user", text="hi")],
            force_tool=True,
        )


@pytest.mark.unit
def test_emit_structured_turn_reraises_llm_cancel_json_path():
    """D1: cancel on the JSON (non-tool) path also propagates without repair."""
    from app.game_engine.agent_runtime.llm_providers.http_utils import LlmRequestCancelled

    class _CancelJsonLlm:
        def supports_tools(self) -> bool:
            return False

        def complete(self, **kwargs):
            raise LlmRequestCancelled()

    with pytest.raises(LlmRequestCancelled):
        emit_structured_turn(
            _CancelJsonLlm(),
            system="sys",
            turns=[TextTurn(role="user", text="hi")],
            force_tool=True,
        )
