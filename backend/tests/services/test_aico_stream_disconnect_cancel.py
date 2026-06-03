from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.commands.base import CommandResult
from app.services.world_interaction.aico_stream_query import AicoStreamQueryService
from app.services.world_interaction.types import WorldActor


@pytest.mark.unit
def test_stream_finally_sets_cancel_event():
    cancel_event_holder: dict = {}

    class _Runner:
        def run(self, session, actor, command_line, *, options=None):
            cancel_event_holder['ev'] = options.stream_cancel_event
            return CommandResult.success_result('', data={'aico_stream_used': True})

    svc = AicoStreamQueryService(
        command_runner=_Runner(),
        build_patch=MagicMock(return_value={'state_patch': {}, 'command_result': None}),
        logger=MagicMock(),
    )
    actor = WorldActor(user_id='1', username='u', permissions=[], roles=[])
    gen = svc.stream(actor, 'hi')
    for _ in gen:
        pass
    assert cancel_event_holder['ev'] is not None
    assert cancel_event_holder['ev'].is_set()
