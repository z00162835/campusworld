"""F13: NDJSON stream lines for opt-in AICO assistant output (SSH channel side-write)."""
from __future__ import annotations
import json
import random
import uuid
from typing import Any, Callable, Dict, Optional
AICO_CLIENT_HINTS = frozenset({'running', 'finding', 'looking', 'thinking', 'flying'})

def aico_repl_progress_message() -> str:
    """Plain-text progress for native SSH ``aico -i``.

    Leading ``\\r`` anchors column 0 without an extra line feed (avoids a blank line
    after the ``aico>`` submit); trailing ``\\r\\n`` ends the hint line.
    """
    hint = random.choice(tuple(AICO_CLIENT_HINTS))
    return f'\r[aico] {hint}…\r\n'

def emit_aico_error_ndjson(emit: Optional[Callable[[str], None]], *, code: str, message: str) -> None:
    """Single ``kind=error`` line; safe user-facing message only (no stacks)."""
    if emit is None or not message:
        return
    payload: Dict[str, Any] = {'kind': 'error', 'code': code, 'message': message}
    emit(json.dumps(payload, ensure_ascii=False))

def emit_activity_meta(emit: Optional[Callable[[str], None]], *, activity: str, detail: Optional[str]=None) -> None:
    """``scope=activity`` meta for presentation-layer status (not PDCA phase names)."""
    if emit is None:
        return
    obj: Dict[str, Any] = {'kind': 'meta', 'scope': 'activity', 'activity': activity}
    if detail:
        obj['detail'] = detail
    emit(json.dumps(obj, ensure_ascii=False))

def emit_tick_lifecycle_meta(emit: Optional[Callable[[str], None]], *, phase: str, thread_id: Optional[uuid.UUID]=None, correlation_id: Optional[str]=None, client_hint: Optional[str]=None, ok: Optional[bool]=None, final_phase: Optional[str]=None, empty_reply: Optional[bool]=None) -> None:
    """``scope=tick`` meta for phase=start or phase=complete (§10.5)."""
    if emit is None:
        return
    obj: Dict[str, Any] = {'kind': 'meta', 'scope': 'tick', 'phase': phase}
    if thread_id is not None:
        obj['thread_id'] = str(thread_id)
    if correlation_id:
        obj['correlation_id'] = correlation_id
    if client_hint is not None:
        if client_hint not in AICO_CLIENT_HINTS:
            raise ValueError(f'invalid client_hint: {client_hint!r}')
        obj['client_hint'] = client_hint
    if ok is not None:
        obj['ok'] = ok
    if final_phase:
        obj['final_phase'] = final_phase
    if empty_reply is not None:
        obj['empty_reply'] = empty_reply
    emit(json.dumps(obj, ensure_ascii=False))

def emit_stream_router_meta(emit: Optional[Callable[[str], None]], *, thread_id: Optional[uuid.UUID]=None, correlation_id: Optional[str]=None) -> None:
    """``scope=stream`` meta before assistant deltas (§17.3)."""
    if emit is None:
        return
    meta: Dict[str, Any] = {'kind': 'meta', 'scope': 'stream'}
    if thread_id is not None:
        meta['thread_id'] = str(thread_id)
    if correlation_id:
        meta['correlation_id'] = correlation_id
    emit(json.dumps(meta, ensure_ascii=False))

def emit_assistant_stream_ndjson(emit: Optional[Callable[[str], None]], assistant_text: str, *, thread_id: Optional[uuid.UUID]=None, correlation_id: Optional[str]=None, allow_empty_body: bool=False) -> None:
    """Write stream meta → delta* → end. Empty body only when ``allow_empty_body``."""
    if emit is None:
        return
    text = assistant_text if assistant_text is not None else ''
    if not allow_empty_body and (not (text or '').strip()):
        return
    emit_stream_router_meta(emit, thread_id=thread_id, correlation_id=correlation_id)
    chunk_size = 64
    for i in range(0, len(text), chunk_size):
        emit(json.dumps({'kind': 'delta', 'text': text[i:i + chunk_size]}, ensure_ascii=False))
    emit(json.dumps({'kind': 'end', 'full_text': text}, ensure_ascii=False))
