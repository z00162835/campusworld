from __future__ import annotations

import json

import pytest

from app.commands.base import CommandContext
from app.game_engine.agent_runtime.aico.profile import AicoRuntimeProfile
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunResult


@pytest.mark.unit
def test_emit_stream_result_skips_ndjson_replay_when_body_already_streamed():
    emitted: list[str] = []
    ctx = CommandContext(user_id='1', username='u', session_id='s', permissions=[], roles=[], metadata={'aico_stream_body_emitted': True})
    ctx.supports_aico_stream = True
    ctx.stream_emit = emitted.append
    profile = AicoRuntimeProfile()
    state = profile.configure_streaming(context=ctx, thread_id=None, correlation_id='corr')
    profile.emit_stream_result(
        state=state,
        result=FrameworkRunResult(ok=True, message='hello world', final_phase='act'),
        thread_id=None,
        correlation_id='corr',
        fallback_message='fallback',
        context=ctx,
    )
    kinds = [json.loads(line)['kind'] for line in emitted]
    assert 'delta' not in kinds
    assert kinds.count('end') == 1
    assert kinds[-1] == 'meta'
    assert json.loads(emitted[-1])['phase'] == 'complete'
