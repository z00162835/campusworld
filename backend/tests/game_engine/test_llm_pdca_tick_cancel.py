from __future__ import annotations

import threading
import uuid
from types import SimpleNamespace

import pytest

from app.core.settings import PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
from app.game_engine.agent_runtime.memory_port import MemoryPort
from app.game_engine.agent_runtime.thinking_pipeline import NoOpAgentTickHooks


class _SlowLlm:
    def complete(self, *, system: str, user: str, call_spec=None) -> str:
        return 'should not reach'

    def supports_tools(self) -> bool:
        return False


class _Mem:
    def __init__(self) -> None:
        self._agent_node_id = 1
        self.finished: list[str] = []

    def start_run(self, run_id: uuid.UUID, correlation_id, phase, command_trace, status) -> None:
        return None

    def update_run(self, run_id: uuid.UUID, phase, command_trace, status, graph_ops_summary=None) -> None:
        return None

    def finish_run(self, run_id: uuid.UUID, phase, command_trace, status, graph_ops_summary=None) -> None:
        self.finished.append(phase)

    def append_raw(self, kind, payload, session_id=None) -> None:
        return None


@pytest.mark.unit
def test_run_returns_cancelled_when_cancel_check_set_before_plan():
    cancel = threading.Event()
    mem = _Mem()
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=SimpleNamespace(extra={}, model='', system_prompt='test', phase_prompts={}),
        instance_phase_llm={
            'plan': PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan),
            'do': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            'check': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            'act': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
        },
        instance_mode_models={},
        llm=_SlowLlm(),
        tick_hooks=NoOpAgentTickHooks(),
    )
    cancel.set()
    ctx = FrameworkRunContext(agent_node_id=1, stream_cancel_check=cancel.is_set)
    res = fw.run(ctx)
    assert res.final_phase == 'cancelled'
    assert res.ok is False
    assert 'cancelled' in mem.finished
