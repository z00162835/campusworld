from __future__ import annotations

import pytest

from app.game_engine.agent_runtime.llm_client import StubLlmClient
from app.game_engine.agent_runtime.llm_streaming import LlmStreamSink, complete_stream


@pytest.mark.unit
def test_stub_complete_stream_accepts_cancel_check_kwarg():
    emitted: list[str] = []
    sink = LlmStreamSink(on_delta=emitted.append)
    out = StubLlmClient().complete_stream(system='s', user='hello', sink=sink, cancel_check=None)
    assert out.startswith('[stub_llm')
    assert emitted


@pytest.mark.unit
def test_stub_complete_stream_stops_when_cancel_check_set():
    emitted: list[str] = []
    sink = LlmStreamSink(on_delta=emitted.append)
    cancelled = False

    def cancel_check() -> bool:
        return cancelled

    client = StubLlmClient()
    full = client.complete(system='s', user='0123456789abcdef', call_spec=None)
    cancelled = True
    out = client.complete_stream(system='s', user='0123456789abcdef', sink=sink, cancel_check=cancel_check)
    assert len(''.join(emitted)) < len(full)
    assert out == '' or len(out) < len(full)


@pytest.mark.unit
def test_complete_stream_wrapper_passes_cancel_check_to_stub():
    emitted: list[str] = []
    sink = LlmStreamSink(on_delta=emitted.append)
    cancel = {'n': 0}

    def cancel_check() -> bool:
        cancel['n'] += 1
        return cancel['n'] > 1

    complete_stream(StubLlmClient(), system='s', user='abcdefghijklmnop', sink=sink, cancel_check=cancel_check)
    assert len(emitted) >= 1
