from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.commands.base import CommandResult
from app.services.world_interaction.aico_stream_query import AicoStreamQueryService
from app.services.world_interaction.types import WorldActor


@pytest.mark.unit
def test_stream_worker_uses_fresh_db_session_context(monkeypatch):
    contexts: list[str] = []
    mock_session = MagicMock(name='worker_session')

    class _Ctx:
        def __enter__(self):
            contexts.append('enter')
            return mock_session

        def __exit__(self, *args):
            contexts.append('exit')
            return False

    monkeypatch.setattr('app.core.database.db_session_context', lambda: _Ctx())

    runner = MagicMock()
    runner.run.return_value = CommandResult(success=True, message='ok', data={'aico_stream_used': True})

    build_patch = MagicMock(return_value={'state_patch': {}, 'command_result': None})
    svc = AicoStreamQueryService(command_runner=runner, build_patch=build_patch, logger=MagicMock())
    actor = WorldActor(user_id='1', username='u', permissions=[], roles=[])

    gen = svc.stream(actor, 'hello')
    first = next(gen)
    assert 'stream_id' in first

    for _ in range(200):
        try:
            chunk = next(gen)
        except StopIteration:
            break
        if 'state_patch' in chunk or '"kind": "error"' in chunk:
            break

    assert contexts == ['enter', 'exit']
    runner.run.assert_called_once()
    assert runner.run.call_args[0][0] is mock_session
    build_patch.assert_called_once()
    assert build_patch.call_args[0][0] is mock_session
