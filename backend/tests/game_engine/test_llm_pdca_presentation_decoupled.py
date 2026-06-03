from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.core.settings import PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
from app.game_engine.agent_runtime.llm_streaming import LlmStreamSink
from app.game_engine.agent_runtime.presentation_stream import StreamCoordinator, UserVisibleStream
from app.game_engine.agent_runtime.thinking_pipeline import NoOpAgentTickHooks


class _StreamLlm:
    def complete(self, *, system: str, user: str, call_spec=None) -> str:
        return 'check-internal'

    def complete_stream(self, *, system: str, user: str, sink: LlmStreamSink, call_spec=None, cancel_check=None) -> str:
        sink.on_delta('leak')
        return 'leak'


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
def test_check_phase_never_streams_to_presentation_layer():
    md: dict = {}
    coord = StreamCoordinator(lambda _line: None, md)
    uvs = UserVisibleStream(coord)
    fw = LlmPDCAFramework(
        memory=_Mem(),
        llm_config=SimpleNamespace(extra={}, model=''),
        instance_phase_llm={'check': PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan)},
        instance_mode_models={},
        llm=_StreamLlm(),
        tick_hooks=NoOpAgentTickHooks(),
    )
    ctx = FrameworkRunContext(agent_node_id=1, user_visible_stream=uvs)
    out, entry = fw._call_llm('check', 'sys', 'user', ctx)
    assert out == 'check-internal'
    assert entry.get('streamed') is not True
    assert 'aico_stream_body_emitted' not in md


@pytest.mark.unit
def test_act_skip_skips_llm_before_presentation_stream():
    md: dict = {}
    coord = StreamCoordinator(lambda _line: None, md)
    uvs = UserVisibleStream(coord)
    fw = LlmPDCAFramework(
        memory=_Mem(),
        llm_config=SimpleNamespace(extra={}, model=''),
        instance_phase_llm={'act': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip)},
        instance_mode_models={},
        llm=_StreamLlm(),
        tick_hooks=NoOpAgentTickHooks(),
    )
    ctx = FrameworkRunContext(agent_node_id=1, user_visible_stream=uvs)
    assert fw._should_stream_user_prose(ctx, 'act') is True
    out, entry = fw._call_llm('act', 'sys', 'user', ctx)
    assert entry.get('skipped') is True
    assert 'aico_stream_body_emitted' not in md
