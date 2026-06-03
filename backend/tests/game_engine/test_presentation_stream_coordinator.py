from __future__ import annotations

import json
import uuid

import pytest

from app.game_engine.agent_runtime.presentation_stream import ActivityKind, StreamCoordinator, UserVisibleStream


@pytest.mark.unit
def test_coordinator_writes_delta_and_end():
    lines: list[str] = []
    md: dict = {}
    coord = StreamCoordinator(lines.append, md)
    uvs = UserVisibleStream(coord)
    uvs.write_text('hi')
    coord.finish('hi', thread_id=uuid.uuid4(), correlation_id='c1', final_phase='action')
    kinds = [json.loads(line)['kind'] for line in lines]
    assert 'delta' in kinds
    assert kinds.count('end') == 1
    assert md.get('aico_stream_body_emitted') is True


@pytest.mark.unit
def test_coordinator_rewrite_resets_body_emitted():
    lines: list[str] = []
    md: dict = {}
    coord = StreamCoordinator(lines.append, md)
    coord.write_text('draft')
    assert md.get('aico_stream_body_emitted') is True
    coord.on_rewrite()
    assert 'aico_stream_body_emitted' not in md
    activities = [
        json.loads(line)['activity']
        for line in lines
        if json.loads(line).get('scope') == 'activity'
    ]
    assert 'rewrite' in activities


@pytest.mark.unit
def test_coordinator_activity_meta():
    lines: list[str] = []
    coord = StreamCoordinator(lines.append, {})
    coord.set_activity(ActivityKind.tool, detail='help')
    payload = json.loads(lines[-1])
    assert payload == {'kind': 'meta', 'scope': 'activity', 'activity': 'tool', 'detail': 'help'}
