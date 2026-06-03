"""AICO decision-center queries over HTTP Server-Sent Events.

Threading audit (request ``Session`` must not cross threads):
- This module: worker uses :func:`db_session_context` (not the FastAPI session).
- ``init_commands._schedule_command_ability_sync``: own ``db_session_context`` in thread.
- ``ssh/session._save_session_state``: own ``db_session_context`` in cleanup thread.
- Other ``threading.Thread`` usages: no ORM session (rate limiter, server bootstrap, benches).
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from queue import Empty, Queue
from typing import Any, Callable, Dict, Generator, Optional

from app.commands.base import CommandResult

from .command_runner import CommandRunOptions, CommandRunner
from .types import WorldActor

_HEARTBEAT_INTERVAL_SEC = 15.0


class AicoStreamQueryService:
    """Handles POST /decision-center/query/stream and stream cancel."""

    def __init__(
        self,
        *,
        command_runner: CommandRunner,
        build_patch: Callable[..., Dict[str, Any]],
        logger: Any,
    ) -> None:
        self._command_runner = command_runner
        self._build_patch = build_patch
        self._logger = logger
        self._stream_cancels: Dict[str, threading.Event] = {}

    def cancel(self, stream_id: str) -> Dict[str, Any]:
        clean_id = str(stream_id or "").strip()
        event = self._stream_cancels.get(clean_id)
        if event is not None:
            event.set()
        return {"ok": True, "stream_id": clean_id}

    def stream(self, actor: WorldActor, query: str) -> Generator[str, None, None]:
        clean = str(query or "").strip()
        if not clean:
            yield self._sse_payload({"kind": "error", "code": "empty_query", "message": "Enter a query."})
            return

        stream_id = uuid.uuid4().hex
        cancel_event = threading.Event()
        self._stream_cancels[stream_id] = cancel_event
        line_queue: Queue[Optional[str]] = Queue()

        def emit_fn(line: str) -> None:
            if cancel_event.is_set():
                return
            line_queue.put(line)

        def worker() -> None:
            from app.core.database import db_session_context

            try:
                with db_session_context() as worker_session:
                    result = self._command_runner.run(
                        worker_session,
                        actor,
                        f"aico {clean}",
                        options=CommandRunOptions(
                            stream_emit=emit_fn,
                            supports_aico_stream=True,
                            stream_cancel_event=cancel_event,
                        ),
                    )
                    if cancel_event.is_set() or str(getattr(result, "final_phase", "") or "") == "cancelled":
                        line_queue.put(json.dumps({"kind": "cancelled"}, ensure_ascii=False))
                    else:
                        data = result.data if isinstance(result.data, dict) else {}
                        if not data.get("aico_stream_used") and (result.message or "").strip():
                            from app.commands.aico_stream import emit_assistant_stream_ndjson

                            emit_assistant_stream_ndjson(emit_fn, result.message, allow_empty_body=True)
                        patch_payload = self._build_patch(worker_session, actor, result)
                        line_queue.put(
                            json.dumps(
                                {
                                    "kind": "state_patch",
                                    "state_patch": patch_payload.get("state_patch"),
                                    "command_result": patch_payload.get("command_result"),
                                },
                                ensure_ascii=False,
                            )
                        )
            except Exception as exc:
                self._logger.exception("AICO stream tick failed: %s", exc)
                line_queue.put(
                    json.dumps({"kind": "error", "code": "stream_failed", "message": str(exc)}, ensure_ascii=False)
                )
            finally:
                line_queue.put(None)

        yield self._sse_payload({"kind": "meta", "scope": "stream", "stream_id": stream_id})

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        last_heartbeat = time.monotonic()
        try:
            while True:
                try:
                    item = line_queue.get(timeout=0.05)
                except Empty:
                    if not thread.is_alive():
                        break
                    now = time.monotonic()
                    if now - last_heartbeat >= _HEARTBEAT_INTERVAL_SEC:
                        yield ": ping\n\n"
                        last_heartbeat = now
                    continue
                if item is None:
                    break
                if cancel_event.is_set() and '"kind": "cancelled"' not in item and '"kind": "end"' not in item:
                    continue
                yield f"data: {item}\n\n"
        finally:
            cancel_event.set()
            self._stream_cancels.pop(stream_id, None)
            thread.join(timeout=5.0)
            if thread.is_alive():
                self._logger.warning(
                    "AICO stream worker did not exit within join timeout stream_id=%s",
                    stream_id,
                )

    @staticmethod
    def _sse_payload(obj: Dict[str, Any]) -> str:
        return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"
