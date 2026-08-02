"""E2E: require_structured_turn through LlmPDCAFramework with mocked LLM."""
from __future__ import annotations

import json

import pytest

from app.core.settings import AgentLlmServiceConfig, PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
from app.game_engine.agent_runtime.tool_calling import CompleteWithToolsResult, ToolCall
from app.game_engine.agent_runtime.state_machine.react_turn_schema import EMIT_TURN_TOOL_NAME


class _FakeMem:
    def start_run(self, *a, **k):
        import uuid

        return uuid.uuid4()

    def update_run(self, *a, **k):
        return None

    def finish_run(self, *a, **k):
        return None

    def append_raw(self, *a, **k):
        return None


def _valid_payload(answer: str = "structured-ok"):
    return {
        "turn_id": "t1",
        "task_state_summary": "s",
        "reason_summary": "r",
        "proposed_action": {
            "action_type": "final_answer",
            "final_answer_draft": answer,
        },
        "expected_observation": "",
        "success_criteria": ["ok"],
    }


@pytest.mark.unit
def test_require_structured_turn_uses_emit_turn_and_disables_stream_gate():
    class _ToolsLlm:
        def __init__(self) -> None:
            self.tool_calls = 0

        def supports_tools(self) -> bool:
            return True

        def complete(self, **kwargs):
            return "should-not-use-plain-complete"

        def complete_with_tools(self, **kwargs):
            self.tool_calls += 1
            assert any(t.name == EMIT_TURN_TOOL_NAME for t in kwargs["tools"])
            return CompleteWithToolsResult(
                text="",
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name=EMIT_TURN_TOOL_NAME,
                        args=[],
                        input_payload=_valid_payload(),
                    )
                ],
                finish_reason="tool_use",
            )

    llm = _ToolsLlm()
    fw = LlmPDCAFramework(
        memory=_FakeMem(),
        llm_config=AgentLlmServiceConfig(
            system_prompt="Sys.",
            phase_prompts={"plan": "P", "do": "D", "check": "C", "act": "A"},
            extra={"require_structured_turn": True},
        ),
        instance_phase_llm={
            "do": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            "check": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            "act": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
        },
        instance_mode_models={},
        llm=llm,
    )
    ctx = FrameworkRunContext(agent_node_id=1, payload={"message": "hi", "require_structured_turn": True})
    assert fw._should_stream_user_prose(ctx, "plan", stream_prose=True) is False
    out = fw.run(ctx)
    assert out.ok
    assert out.message == "structured-ok"
    assert llm.tool_calls >= 1


@pytest.mark.unit
def test_require_structured_turn_json_fallback_path():
    class _TextLlm:
        def supports_tools(self) -> bool:
            return False

        def complete(self, **kwargs):
            return json.dumps(_valid_payload("json-path"))

    fw = LlmPDCAFramework(
        memory=_FakeMem(),
        llm_config=AgentLlmServiceConfig(
            system_prompt="Sys.",
            phase_prompts={"plan": "P", "do": "D", "check": "C", "act": "A"},
            extra={"require_structured_turn": True},
        ),
        instance_phase_llm={
            "do": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            "check": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            "act": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
        },
        instance_mode_models={},
        llm=_TextLlm(),
    )
    out = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi", "require_structured_turn": True}))
    assert out.ok
    assert out.message == "json-path"
