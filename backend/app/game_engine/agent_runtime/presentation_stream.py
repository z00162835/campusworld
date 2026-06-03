"""Presentation-layer streaming: user-visible text and activity meta (PDCA-decoupled)."""
from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any, Callable, Dict, Optional

_LOG = logging.getLogger(__name__)

from app.game_engine.agent_runtime.llm_streaming import LlmStreamSink


class ActivityKind(str, Enum):
    working = 'working'
    tool = 'tool'
    writing = 'writing'
    rewrite = 'rewrite'


class StreamCoordinator:
    """Tick-level presentation stream: text deltas, activity meta, finish/fallback."""

    def __init__(
        self,
        emit_fn: Callable[[str], None],
        metadata: Dict[str, Any],
        *,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        self._emit = emit_fn
        self._metadata = metadata
        self.cancel_check = cancel_check
        self._writing_activity_sent = False
        self._current_activity: Optional[ActivityKind] = None

    @property
    def body_emitted(self) -> bool:
        return bool(self._metadata.get('aico_stream_body_emitted'))

    @body_emitted.setter
    def body_emitted(self, value: bool) -> None:
        if value:
            self._metadata['aico_stream_body_emitted'] = True
        else:
            self._metadata.pop('aico_stream_body_emitted', None)

    def set_activity(self, activity: ActivityKind, *, detail: Optional[str] = None) -> None:
        if self._current_activity == activity and activity != ActivityKind.tool:
            return
        self._current_activity = activity
        from app.commands.aico_stream import emit_activity_meta

        act = activity.value if isinstance(activity, ActivityKind) else str(activity)
        emit_activity_meta(self._emit, activity=act, detail=detail)

    def on_tick_start(self) -> None:
        self.set_activity(ActivityKind.working, detail='gathering_context')

    def on_rewrite(self) -> None:
        self.body_emitted = False
        self._writing_activity_sent = False
        self._current_activity = None
        self.set_activity(ActivityKind.rewrite)

    def write_text(self, chunk: str) -> None:
        if not chunk:
            return
        if not self._writing_activity_sent:
            self._writing_activity_sent = True
            self.set_activity(ActivityKind.writing)
        if not self.body_emitted:
            self.body_emitted = True
            _LOG.info('aico_presentation_first_delta')
        self._emit(json.dumps({'kind': 'delta', 'text': chunk}, ensure_ascii=False))

    def build_llm_sink(self) -> LlmStreamSink:
        return LlmStreamSink(on_delta=self.write_text)

    def finish(
        self,
        full_text: str,
        *,
        thread_id: Any = None,
        correlation_id: Optional[str] = None,
        final_phase: Optional[str] = None,
        ok: bool = True,
        empty_reply: bool = False,
    ) -> None:
        from app.commands.aico_stream import emit_assistant_stream_ndjson, emit_tick_lifecycle_meta

        text = str(full_text or '')
        if self.body_emitted:
            self._emit(json.dumps({'kind': 'end', 'full_text': text}, ensure_ascii=False))
        else:
            emit_assistant_stream_ndjson(
                self._emit,
                text,
                thread_id=thread_id,
                correlation_id=correlation_id,
                allow_empty_body=True,
            )
        emit_tick_lifecycle_meta(
            self._emit,
            phase='complete',
            thread_id=thread_id,
            correlation_id=correlation_id,
            ok=ok,
            final_phase=final_phase,
            empty_reply=empty_reply,
        )


class UserVisibleStream:
    """Facade for PDCA to write user-facing prose without phase parameters."""

    def __init__(self, coordinator: StreamCoordinator) -> None:
        self._coordinator = coordinator

    def write_text(self, chunk: str) -> None:
        self._coordinator.write_text(chunk)

    @property
    def coordinator(self) -> StreamCoordinator:
        return self._coordinator
