from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest

from app.core.settings import PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
from app.game_engine.agent_runtime.llm_streaming import LlmStreamSink
from app.game_engine.agent_runtime.memory_port import MemoryPort
from app.game_engine.agent_runtime.presentation_stream import StreamCoordinator, UserVisibleStream
from app.game_engine.agent_runtime.thinking_pipeline import NoOpAgentTickHooks


class _StreamOnComplete:
    def complete(self, *, system: str, user: str, call_spec=None) -> str:
        return 'plain'

    def complete_stream(self, *, system: str, user: str, sink: LlmStreamSink, call_spec=None, cancel_check=None) -> str:
        sink.on_delta('X')
        return 'plain'

    def supports_tools(self) -> bool:
        return False


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


def _fw(**phase_llm) -> LlmPDCAFramework:
    return LlmPDCAFramework(
        memory=_Mem(),
        llm_config=SimpleNamespace(extra={}, model=''),
        instance_phase_llm=phase_llm,
        instance_mode_models={},
        llm=_StreamOnComplete(),
        tick_hooks=NoOpAgentTickHooks(),
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ('phase_llm', 'expected'),
    [
        ({'act': PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan)}, 'act'),
        (
            {
                'act': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
                'do': PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan),
            },
            'do',
        ),
        (
            {
                'act': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
                'do': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
                'plan': PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan),
            },
            'plan',
        ),
    ],
)
def test_resolve_presentation_anchor_phase(phase_llm, expected) -> None:
    fw = _fw(**phase_llm)
    ctx = FrameworkRunContext(agent_node_id=1)
    assert fw._resolve_presentation_anchor_phase(ctx) == expected


@pytest.mark.unit
def test_plan_react_last_round_does_not_stream_when_anchor_is_do() -> None:
    emitted: list[str] = []
    md: dict = {}
    coord = StreamCoordinator(emitted.append, md)
    uvs = UserVisibleStream(coord)
    fw = _fw(
        act=PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
        do=PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan),
        plan=PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan),
    )
    ctx = FrameworkRunContext(agent_node_id=1, user_visible_stream=uvs)
    fw._bind_presentation_anchor(ctx)
    assert ctx.presentation_anchor_phase == 'do'
    from app.game_engine.agent_runtime.tool_calling import TextTurn

    fw._call_llm_dual_track('plan', 'sys', [TextTurn(role='user', text='u')], ctx, stream_prose=True)
    assert 'aico_stream_body_emitted' not in md
    fw._call_llm_dual_track('do', 'sys', [TextTurn(role='user', text='u')], ctx, stream_prose=True)
    assert md.get('aico_stream_body_emitted') is True
    assert any('X' in line for line in emitted)


@pytest.mark.unit
def test_json_tool_plan_text_not_written_to_presentation() -> None:
    emitted: list[str] = []
    md: dict = {}
    coord = StreamCoordinator(emitted.append, md)
    uvs = UserVisibleStream(coord)

    class _JsonLlm:
        def complete(self, *, system: str, user: str, call_spec=None) -> str:
            return json.dumps({'commands': [{'name': 'look', 'args': []}]})

        def supports_tools(self) -> bool:
            return False

    from app.game_engine.agent_runtime.tool_calling import ToolSchema

    fw = LlmPDCAFramework(
        memory=_Mem(),
        llm_config=SimpleNamespace(extra={}, model=''),
        instance_phase_llm={
            'act': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            'do': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            'plan': PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan),
        },
        instance_mode_models={},
        llm=_JsonLlm(),
        tool_schemas=[ToolSchema(name='look', description='look')],
        tick_hooks=NoOpAgentTickHooks(),
    )
    ctx = FrameworkRunContext(agent_node_id=1, user_visible_stream=uvs)
    fw._bind_presentation_anchor(ctx)
    from app.game_engine.agent_runtime.tool_calling import TextTurn

    text, calls, entry = fw._call_llm_dual_track(
        'plan',
        'sys',
        [TextTurn(role='user', text='u')],
        ctx,
        stream_prose=True,
    )
    assert calls
    assert entry.get('streamed') is not True
    assert 'aico_stream_body_emitted' not in md
    assert not any('look' in line for line in emitted)
