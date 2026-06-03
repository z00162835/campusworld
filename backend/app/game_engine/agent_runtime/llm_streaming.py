"""LLM provider streaming contracts and AICO NDJSON sink wiring."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol, runtime_checkable

from app.game_engine.agent_runtime.llm_client import LlmCallSpec


@dataclass(frozen=True)
class LlmStreamSink:
    """Receives UTF-8 text fragments as the provider generates them."""

    on_delta: Callable[[str], None]


@runtime_checkable
class StreamingLlmClient(Protocol):
    def complete_stream(
        self,
        *,
        system: str,
        user: str,
        sink: LlmStreamSink,
        call_spec: Optional[LlmCallSpec] = None,
    ) -> str:
        ...


def complete_stream(
    client: Any,
    *,
    system: str,
    user: str,
    sink: LlmStreamSink,
    call_spec: Optional[LlmCallSpec] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> str:
    """Invoke provider streaming when available; otherwise emit one delta after ``complete``."""
    fn = getattr(client, 'complete_stream', None)
    if callable(fn):
        return str(
            fn(
                system=system,
                user=user,
                sink=sink,
                call_spec=call_spec,
                cancel_check=cancel_check,
            )
            or ''
        )
    full = str(client.complete(system=system, user=user, call_spec=call_spec) or '')
    if full:
        sink.on_delta(full)
    return full


def build_aico_llm_stream_sink(
    emit_fn: Callable[[str], None],
    metadata: Dict[str, Any],
) -> LlmStreamSink:
    """Wrap tick ``stream_emit`` so PDCA deltas become F13 ``kind=delta`` lines."""

    def on_delta(text: str) -> None:
        if not text:
            return
        if not metadata.get('aico_stream_body_emitted'):
            metadata['aico_stream_body_emitted'] = True
        emit_fn(json.dumps({'kind': 'delta', 'text': text}, ensure_ascii=False))

    return LlmStreamSink(on_delta=on_delta)
