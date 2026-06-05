from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

import app.core.database as database_module
from app.commands.base import CommandResult
from app.services.world_interaction.aico_stream_query import AicoStreamQueryService, _ActiveStreamHandle
from app.services.world_interaction.types import WorldActor


@contextmanager
def _fake_db_session():
    yield MagicMock()


@pytest.mark.unit
def test_cancel_active_for_user_thread_sets_cancel_event():
    svc = AicoStreamQueryService(
        command_runner=MagicMock(),
        build_patch=MagicMock(),
        logger=MagicMock(),
    )
    ev = threading.Event()
    worker = MagicMock()
    worker.is_alive.return_value = False
    with svc._registry_lock:
        svc._active_by_user_thread[('u1', 't1')] = _ActiveStreamHandle('s1', ev, worker)
    svc._cancel_active_for_user_thread('u1', 't1')
    assert ev.is_set()


@pytest.mark.unit
def test_new_stream_on_same_thread_cancels_previous(monkeypatch):
    monkeypatch.setattr(database_module, 'db_session_context', _fake_db_session)

    first_cancel: dict[str, threading.Event] = {}
    started = threading.Event()
    release = threading.Event()

    class _Runner:
        def run(self, session, actor, command_line, *, options=None):
            if options is not None and options.stream_cancel_event is not None:
                if command_line == 'aico first query':
                    first_cancel['ev'] = options.stream_cancel_event
                    started.set()
                    release.wait(timeout=2.0)
                    return CommandResult.success_result('', data={'aico_stream_used': True, 'phase': 'cancelled'})
            return CommandResult.success_result('ok', data={'aico_stream_used': True, 'phase': 'action'})

    svc = AicoStreamQueryService(
        command_runner=_Runner(),
        build_patch=MagicMock(return_value={'state_patch': {}, 'command_result': None}),
        logger=MagicMock(),
    )
    actor = WorldActor(user_id='42', username='u', permissions=[], roles=[])
    thread_id = 'thread_a'

    gen1 = svc.stream(actor, 'first query', thread_id=thread_id)

    def _consume_first() -> None:
        for _ in gen1:
            pass

    consumer = threading.Thread(target=_consume_first, daemon=True)
    consumer.start()
    assert started.wait(timeout=3.0)
    assert 'ev' in first_cancel

    gen2 = svc.stream(actor, 'second query', thread_id=thread_id)
    for _ in gen2:
        pass
    assert first_cancel['ev'].is_set()
    release.set()
    consumer.join(timeout=3.0)


@pytest.mark.unit
def test_different_threads_do_not_cancel_each_other(monkeypatch):
    monkeypatch.setattr(database_module, 'db_session_context', _fake_db_session)

    cancels: dict[str, threading.Event] = {}
    started_t1 = threading.Event()

    class _Runner:
        def run(self, session, actor, command_line, *, options=None):
            key = options.aico_client_thread_id if options else 'x'
            if options and options.stream_cancel_event is not None:
                cancels[key] = options.stream_cancel_event
                if key == 't1':
                    started_t1.set()
            time.sleep(0.05)
            return CommandResult.success_result('ok', data={'aico_stream_used': True, 'phase': 'action'})

    svc = AicoStreamQueryService(
        command_runner=_Runner(),
        build_patch=MagicMock(return_value={'state_patch': {}, 'command_result': None}),
        logger=MagicMock(),
    )
    actor = WorldActor(user_id='7', username='u', permissions=[], roles=[])

    gen_a = svc.stream(actor, 'a', thread_id='t1')

    def _consume_a() -> None:
        for _ in gen_a:
            pass

    consumer_a = threading.Thread(target=_consume_a, daemon=True)
    consumer_a.start()
    assert started_t1.wait(timeout=3.0)
    ev_t1 = cancels['t1']
    assert not ev_t1.is_set()

    gen_b = svc.stream(actor, 'b', thread_id='t2')
    for _ in gen_b:
        pass
    assert not ev_t1.is_set()
    consumer_a.join(timeout=3.0)
