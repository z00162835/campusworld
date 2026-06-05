from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest

from app.core.settings import PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
from app.game_engine.agent_runtime.llm_providers.http_utils import LlmRequestCancelled
from app.game_engine.agent_runtime.thinking_pipeline import NoOpAgentTickHooks
from app.game_engine.agent_runtime.tool_calling import CompleteWithToolsResult, ToolSchema


class _BlockingToolsLlm:
    started = threading.Event()

    def supports_tools(self) -> bool:
        return True

    def complete(self, *, system: str, user: str, call_spec=None, cancel_check=None) -> str:
        raise AssertionError('plain complete should not run')

    def complete_with_tools(self, *, system: str, turns, tools, call_spec=None, cancel_check=None):
        _BlockingToolsLlm.started.set()
        while cancel_check is not None and not cancel_check():
            time.sleep(0.02)
        if cancel_check is not None and cancel_check():
            raise LlmRequestCancelled()
        return CompleteWithToolsResult(text='plan', tool_calls=[], finish_reason='stop')


class _Mem:
    finished: list[str] = []

    def start_run(self, *args, **kwargs) -> None:
        return None

    def update_run(self, *args, **kwargs) -> None:
        return None

    def finish_run(self, *args, **kwargs) -> None:
        _Mem.finished.append(kwargs.get('status') or args[3] if len(args) > 3 else '')

    def append_raw(self, *args, **kwargs) -> None:
        return None


@pytest.mark.unit
def test_run_returns_cancelled_when_cancel_during_plan_tools_call():
    _Mem.finished = []
    _BlockingToolsLlm.started.clear()
    cancel = threading.Event()
    fw = LlmPDCAFramework(
        memory=_Mem(),
        llm_config=SimpleNamespace(extra={}, model='', system_prompt='test', phase_prompts={}),
        instance_phase_llm={
            'plan': PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan),
            'do': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            'check': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            'act': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
        },
        instance_mode_models={},
        llm=_BlockingToolsLlm(),
        tick_hooks=NoOpAgentTickHooks(),
        tool_schemas=[ToolSchema(name='look', description='look', input_schema={'type': 'object'})],
    )

    def trigger_cancel() -> None:
        assert _BlockingToolsLlm.started.wait(timeout=2.0)
        cancel.set()

    threading.Thread(target=trigger_cancel, daemon=True).start()
    ctx = FrameworkRunContext(agent_node_id=1, stream_cancel_check=cancel.is_set)
    res = fw.run(ctx)
    assert res.final_phase == 'cancelled'
    assert res.ok is False
