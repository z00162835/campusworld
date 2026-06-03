from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.core.settings import PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
from app.game_engine.agent_runtime.llm_streaming import LlmStreamSink
from app.game_engine.agent_runtime.tool_calling import CompleteWithToolsResult, TextTurn, ToolSchema
from app.game_engine.agent_runtime.memory_port import MemoryPort
from app.game_engine.agent_runtime.presentation_stream import StreamCoordinator, UserVisibleStream
from app.game_engine.agent_runtime.thinking_pipeline import NoOpAgentTickHooks


class _ChunkingLlm:
    def complete(self, *, system: str, user: str, call_spec=None) -> str:
        return 'fallback'

    def complete_stream(self, *, system: str, user: str, sink: LlmStreamSink, call_spec=None, cancel_check=None) -> str:
        raise AssertionError('B1: last round with tools must not token-stream during call')

    def supports_tools(self) -> bool:
        return True

    def complete_with_tools(self, *, system: str, turns, tools, call_spec=None) -> CompleteWithToolsResult:
        return CompleteWithToolsResult(text='user-facing answer', tool_calls=[], finish_reason='stop')


class _Mem:
    def __init__(self) -> None:
        self._agent_node_id = 1

    def start_run(self, run_id: uuid.UUID, correlation_id, phase, command_trace, status) -> None:
        return None

    def update_run(self, run_id: uuid.UUID, phase, command_trace, status, graph_ops_summary=None) -> None:
        return None

    def finish_run(self, run_id: uuid.UUID, phase, command_trace, status, graph_ops_summary=None) -> None:
        return None

    def append_raw(self, kind, payload, session_id=None) -> None:
        return None


@pytest.mark.unit
def test_dual_track_last_round_with_tools_emits_prose_after_call_not_during():
    emitted: list[str] = []
    md: dict = {}
    coord = StreamCoordinator(emitted.append, md)
    uvs = UserVisibleStream(coord)
    fw = LlmPDCAFramework(
        memory=_Mem(),
        llm_config=SimpleNamespace(extra={}, model=''),
        instance_phase_llm={'plan': PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan)},
        instance_mode_models={},
        llm=_ChunkingLlm(),
        tool_schemas=[ToolSchema(name='help', description='help')],
        tick_hooks=NoOpAgentTickHooks(),
    )
    ctx = FrameworkRunContext(agent_node_id=1, user_visible_stream=uvs, payload={'pdca_tool_schema_allowlist': ['help']})
    text, calls, entry = fw._call_llm_dual_track(
        'plan',
        'sys',
        [TextTurn(role='user', text='hello')],
        ctx,
        stream_prose=True,
    )
    assert text == 'user-facing answer'
    assert calls == []
    assert entry.get('streamed') is True
    assert entry.get('channel') == 'presentation_prose'
    assert md.get('aico_stream_body_emitted') is True
    assert any('user-facing answer' in line for line in emitted)
