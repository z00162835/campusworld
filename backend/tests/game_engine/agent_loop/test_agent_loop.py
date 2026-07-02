from __future__ import annotations

import pytest

from app.game_engine.agent_runtime.agent_loop.config import AgentLoopConfig
from app.game_engine.agent_runtime.agent_loop.draft_gate import (
    assess_draft_completeness,
    assess_draft_completeness_with_budget,
    is_deferral_prose,
    is_draft_streamable,
)
from app.game_engine.agent_runtime.agent_loop.policy import detect_pending_tool_work, should_exit_react_round
from app.game_engine.agent_runtime.agent_loop.signals import DraftCompletenessVerdict
from app.game_engine.agent_runtime.tool_calling import ToolCall, ToolResult


@pytest.mark.unit
def test_detect_pending_tool_work_when_filtered_empty():
    pending = detect_pending_tool_work(
        calls=[],
        dropped_names=['world'],
        finish_reason='tool_use',
        pre_filter_calls=[ToolCall(id='c1', name='world', args=['list'])],
    )
    assert pending is not None
    assert 'tools_filtered' in pending.reason_codes


@pytest.mark.unit
def test_should_exit_react_round_when_prose_only():
    assert should_exit_react_round(calls=[], pending=None) is True
    assert should_exit_react_round(calls=[ToolCall(id='1', name='find', args=[])], pending=None) is False


@pytest.mark.unit
def test_deferral_prose_without_grounding_is_incomplete():
    cfg = AgentLoopConfig()
    assert is_deferral_prose('我先查询一下 Hicampus 世界包的状态。', config=cfg)
    verdict = assess_draft_completeness(
        user_message='介绍Hicampus',
        draft_text='我先查询一下 Hicampus 世界包的状态。',
        tool_results=[],
        config=cfg,
    )
    assert verdict == DraftCompletenessVerdict.retry_loop


@pytest.mark.unit
def test_grounded_draft_is_complete():
    cfg = AgentLoopConfig(min_complete_chars=80)
    obs = [ToolResult(id='1', name='describe', ok=True, text='world node 1184')]
    draft = 'HiCampus 是一个已安装的世界包。' * 5
    verdict = assess_draft_completeness(
        user_message='介绍Hicampus',
        draft_text=draft,
        tool_results=obs,
        config=cfg,
    )
    assert verdict == DraftCompletenessVerdict.complete
    assert is_draft_streamable(
        draft_text=draft,
        tool_results=obs,
        user_message='介绍Hicampus',
        config=cfg,
    )


@pytest.mark.unit
def test_budget_exhausted_becomes_fail_fallback():
    cfg = AgentLoopConfig()
    verdict = assess_draft_completeness_with_budget(
        user_message='介绍Hicampus',
        draft_text='我先查询一下。',
        tool_results=[],
        config=cfg,
        rounds_remaining=0,
    )
    assert verdict == DraftCompletenessVerdict.fail_fallback


@pytest.mark.unit
def test_deferral_prose_catches_internal_reasoning_leaks():
    """Expanded deferral patterns must catch Plan-phase internal reasoning
    that leaked as the draft (e.g. ``[plan] The output was truncated. Let me
    try to get more detail.``) so the Check gate can trigger a re-plan."""
    cfg = AgentLoopConfig()
    assert is_deferral_prose('The output was truncated. Let me try to get more detail.', config=cfg)
    assert is_deferral_prose("I'll try to get the detail.", config=cfg)
    assert is_deferral_prose('让我再试一试。', config=cfg)
    assert is_deferral_prose('Let me try again.', config=cfg)


@pytest.mark.unit
def test_assemble_plan_skip_do_draft_strips_internal_plan_tag():
    """Internal phase tags such as ``[plan]`` must never reach the user."""
    from app.game_engine.agent_runtime.frameworks.llm_pdca import (
        assemble_plan_skip_do_draft,
    )
    assert assemble_plan_skip_do_draft('[plan] The output was truncated. Let me try.', '') == ''
    assert assemble_plan_skip_do_draft('[plan] thinking...\nHere is the answer.', '') == 'Here is the answer.'
    assert assemble_plan_skip_do_draft('[PLAN] internal note\n[do] also internal\nFinal reply.', '') == 'Final reply.'
    assert assemble_plan_skip_do_draft('[thought] reasoning\n[check] verifying\nVisible prose.', '') == 'Visible prose.'
