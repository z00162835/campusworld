from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.core.settings import AgentLlmServiceConfig, PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
from app.game_engine.agent_runtime.llm_client import StubLlmClient
from app.game_engine.agent_runtime.tool_calling import CompleteWithToolsResult, ToolCall, ToolSchema
from app.game_engine.agent_runtime.tool_gather import ToolGatherCounters
from app.game_engine.agent_runtime.thinking_pipeline import NoOpAgentTickHooks


class _FakeMem:
    def start_run(self, *args, **kwargs) -> None:
        return None

    def update_run(self, *args, **kwargs) -> None:
        return None

    def finish_run(self, *args, **kwargs) -> None:
        return None

    def append_raw(self, *args, **kwargs) -> None:
        return None


class _FilteredThenAnswerLlm:
    def __init__(self) -> None:
        self.calls = 0

    def supports_tools(self) -> bool:
        return True

    def complete_with_tools(self, *, system: str, turns, tools, call_spec=None, cancel_check=None) -> CompleteWithToolsResult:
        self.calls += 1
        if self.calls == 1:
            return CompleteWithToolsResult(
                text='我先查询一下 Hicampus 世界包的状态。',
                tool_calls=[ToolCall(id='t1', name='world', args=['list'])],
                finish_reason='tool_use',
            )
        body = 'HiCampus 已安装。' + ('包含多栋建筑。' * 20)
        return CompleteWithToolsResult(text=body, tool_calls=[], finish_reason='stop')


@pytest.mark.unit
def test_react_loop_continues_after_filtered_tool_use():
    fw = LlmPDCAFramework(
        memory=_FakeMem(),
        llm_config=AgentLlmServiceConfig(system_prompt='test', extra={'agent_loop_min_complete_chars': 80}),
        instance_phase_llm={
            'plan': PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan),
            'do': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            'check': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            'act': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
        },
        instance_mode_models={},
        llm=_FilteredThenAnswerLlm(),
        tool_schemas=[ToolSchema(name='find', description='find'), ToolSchema(name='describe', description='describe')],
        tick_hooks=NoOpAgentTickHooks(),
    )
    ctx = FrameworkRunContext(agent_node_id=1, payload={'message': '介绍Hicampus'})
    trace: list = []
    counters = ToolGatherCounters()
    (plan_out, _obs, _results, entry) = fw._phase_react_loop(
        'plan',
        'sys',
        'User message:\n介绍Hicampus',
        ctx,
        counters,
        trace,
    )
    steps = [x.get('step') for x in trace if isinstance(x, dict)]
    assert 'agent_loop_pending_tool_work' in steps
    assert 'agent_loop_continuation_injected' in steps
    assert '我先查询' not in (plan_out or '')
    assert len((plan_out or '').strip()) >= 80
    assert entry.get('draft_incomplete') is not True


@pytest.mark.unit
def test_tick_emits_draft_incomplete_when_only_deferral():
    class _DeferOnlyLlm(_FilteredThenAnswerLlm):
        def complete_with_tools(self, *, system: str, turns, tools, call_spec=None, cancel_check=None) -> CompleteWithToolsResult:
            return CompleteWithToolsResult(
                text='我先查询一下 Hicampus 世界包的状态。',
                tool_calls=[ToolCall(id='t1', name='world', args=['list'])],
                finish_reason='tool_use',
            )

    fw = LlmPDCAFramework(
        memory=_FakeMem(),
        llm_config=AgentLlmServiceConfig(
            system_prompt='test',
            extra={'agent_loop_min_complete_chars': 80, 'tool_gather_max_rounds_per_phase': 1},
        ),
        instance_phase_llm={
            'plan': PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan),
            'do': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            'check': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            'act': PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
        },
        instance_mode_models={},
        llm=_DeferOnlyLlm(),
        tool_schemas=[ToolSchema(name='find', description='find')],
        tick_hooks=NoOpAgentTickHooks(),
    )
    ctx = FrameworkRunContext(agent_node_id=1, payload={'message': '介绍Hicampus'})
    res = fw.run(ctx)
    assert res.error_code == 'draft_incomplete'
    assert res.ok is False
    assert '抱歉' in res.message or '能力' in res.message


@pytest.mark.unit
def test_stub_four_phase_tick_still_ok():
    fw = LlmPDCAFramework(
        memory=_FakeMem(),
        llm_config=SimpleNamespace(extra={}, model='', system_prompt='test', phase_prompts={}),
        instance_phase_llm={},
        instance_mode_models={},
        llm=StubLlmClient(),
    )
    ctx = FrameworkRunContext(agent_node_id=1, payload={'message': 'What is CampusWorld?'})
    res = fw.run(ctx)
    assert res.ok
    assert res.message
