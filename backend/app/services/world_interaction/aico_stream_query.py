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
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Any, Callable, Dict, Generator, Optional, Tuple

from app.commands.base import CommandResult
from app.commands.npc_agent_nlp import NPC_AGENT_LLM_TIMEOUT_USER_MSG

from .command_runner import CommandRunOptions, CommandRunner
from .types import WorldActor

_HEARTBEAT_INTERVAL_SEC = 15.0
_DEFAULT_THREAD_KEY = '_default'


@dataclass
class _ActiveStreamHandle:
    stream_id: str
    cancel_event: threading.Event
    worker: threading.Thread


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
        self._active_by_user_thread: Dict[Tuple[str, str], _ActiveStreamHandle] = {}
        self._registry_lock = threading.Lock()

    def _worker_join_sec(self) -> float:
        try:
            from app.core.config_manager import get_config
            from app.core.settings import create_settings_from_config

            settings = create_settings_from_config(get_config())
            return float(settings.world_interaction.aico_stream_worker_join_sec)
        except Exception:
            return 30.0

    def _thread_key(self, thread_id: Optional[str]) -> str:
        clean = str(thread_id or '').strip()
        return clean or _DEFAULT_THREAD_KEY

    def _wait_worker_exit(self, handle: _ActiveStreamHandle, *, thread_id: str) -> None:
        join_sec = self._worker_join_sec()
        t0 = time.perf_counter()
        handle.worker.join(timeout=join_sec)
        if handle.worker.is_alive():
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self._logger.warning(
                'AICO stream worker did not exit within join timeout stream_id=%s thread_id=%s elapsed_ms=%.1f',
                handle.stream_id,
                thread_id,
                elapsed_ms,
            )

    def _signal_cancel_active_for_user_thread(
        self, user_id: str, thread_key: str
    ) -> Optional[_ActiveStreamHandle]:
        registry_key = (user_id, thread_key)
        with self._registry_lock:
            handle = self._active_by_user_thread.get(registry_key)
        if handle is None:
            return None
        handle.cancel_event.set()
        self._logger.info(
            'AICO stream cancel requested stream_id=%s thread_id=%s',
            handle.stream_id,
            thread_key,
        )
        return handle

    def _schedule_prior_worker_join(self, handle: _ActiveStreamHandle, *, thread_id: str) -> None:
        threading.Thread(
            target=self._wait_worker_exit,
            args=(handle,),
            kwargs={'thread_id': thread_id},
            daemon=True,
            name=f'aico-stream-join-{handle.stream_id[:8]}',
        ).start()

    def _cancel_active_for_user_thread(self, user_id: str, thread_key: str) -> None:
        """Signal cancel on the prior stream for this user/thread (non-blocking)."""
        prior = self._signal_cancel_active_for_user_thread(user_id, thread_key)
        if prior is not None:
            self._schedule_prior_worker_join(prior, thread_id=thread_key)

    def cancel(self, stream_id: str) -> Dict[str, Any]:
        clean_id = str(stream_id or "").strip()
        event = self._stream_cancels.get(clean_id)
        if event is not None:
            event.set()
            self._logger.info('AICO stream cancel requested stream_id=%s', clean_id)
        return {"ok": True, "stream_id": clean_id}

    def stream(
        self,
        actor: WorldActor,
        query: str,
        *,
        thread_id: Optional[str] = None,
    ) -> Generator[str, None, None]:
        clean = str(query or "").strip()
        if not clean:
            yield self._sse_payload({"kind": "error", "code": "empty_query", "message": "Enter a query."})
            return

        user_id = str(actor.user_id)
        thread_key = self._thread_key(thread_id)
        prior = self._signal_cancel_active_for_user_thread(user_id, thread_key)
        if prior is not None:
            self._schedule_prior_worker_join(prior, thread_id=thread_key)

        stream_id = uuid.uuid4().hex
        cancel_event = threading.Event()
        self._stream_cancels[stream_id] = cancel_event
        line_queue: Queue[Optional[str]] = Queue()
        tick_started_at = time.perf_counter()
        final_phase_holder: Dict[str, str] = {'value': 'unknown'}

        def emit_fn(line: str) -> None:
            if cancel_event.is_set():
                return
            line_queue.put(line)

        def worker() -> None:
            from app.core.database import db_session_context

            try:
                self._logger.info(
                    'aico_tick_start stream_id=%s thread_id=%s user_id=%s',
                    stream_id,
                    thread_key,
                    user_id,
                )
                with db_session_context() as worker_session:
                    result = self._command_runner.run(
                        worker_session,
                        actor,
                        f"aico {clean}",
                        options=CommandRunOptions(
                            stream_emit=emit_fn,
                            supports_aico_stream=True,
                            stream_cancel_event=cancel_event,
                            aico_client_thread_id=thread_key if thread_key != _DEFAULT_THREAD_KEY else None,
                        ),
                    )
                    data = result.data if isinstance(result.data, dict) else {}
                    phase = str(data.get('phase') or '')
                    final_phase_holder['value'] = phase or ('success' if result.success else 'error')
                    if (cancel_event.is_set() or phase == 'cancelled') and not data.get('aico_stream_used'):
                        line_queue.put(json.dumps({"kind": "cancelled"}, ensure_ascii=False))
                    elif not result.success and not data.get('aico_stream_used'):
                        msg = str(result.message or '').strip()
                        code = 'llm_timeout' if phase == 'error' and '超时' in msg else 'tick_failed'
                        if msg == NPC_AGENT_LLM_TIMEOUT_USER_MSG:
                            code = 'llm_timeout'
                        line_queue.put(
                            json.dumps(
                                {"kind": "error", "code": code, "message": msg or 'Stream failed'},
                                ensure_ascii=False,
                            )
                        )
                    else:
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
                import httpx

                self._logger.exception("AICO stream tick failed: %s", exc)
                if isinstance(exc, httpx.ReadTimeout):
                    line_queue.put(
                        json.dumps(
                            {
                                "kind": "error",
                                "code": "llm_timeout",
                                "message": NPC_AGENT_LLM_TIMEOUT_USER_MSG,
                            },
                            ensure_ascii=False,
                        )
                    )
                    final_phase_holder['value'] = 'error'
                else:
                    line_queue.put(
                        json.dumps({"kind": "error", "code": "stream_failed", "message": str(exc)}, ensure_ascii=False)
                    )
                    final_phase_holder['value'] = 'error'
            finally:
                elapsed_ms = (time.perf_counter() - tick_started_at) * 1000.0
                self._logger.info(
                    'AICO tick finished correlation_id=http_%s final_phase=%s elapsed_ms=%.1f stream_id=%s thread_id=%s',
                    user_id,
                    final_phase_holder['value'],
                    elapsed_ms,
                    stream_id,
                    thread_key,
                )
                with self._registry_lock:
                    cur = self._active_by_user_thread.get((user_id, thread_key))
                    if cur is not None and cur.stream_id == stream_id:
                        self._active_by_user_thread.pop((user_id, thread_key), None)
                line_queue.put(None)

        yield self._sse_payload({"kind": "meta", "scope": "stream", "stream_id": stream_id})

        thread = threading.Thread(target=worker, daemon=True)
        with self._registry_lock:
            self._active_by_user_thread[(user_id, thread_key)] = _ActiveStreamHandle(
                stream_id=stream_id,
                cancel_event=cancel_event,
                worker=thread,
            )
        thread.start()

        last_heartbeat = time.monotonic()
        join_sec = self._worker_join_sec()
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
            thread.join(timeout=join_sec)
            if thread.is_alive():
                elapsed_ms = (time.perf_counter() - tick_started_at) * 1000.0
                self._logger.warning(
                    'AICO stream worker did not exit within join timeout stream_id=%s thread_id=%s elapsed_ms=%.1f',
                    stream_id,
                    thread_key,
                    elapsed_ms,
                )

    @staticmethod
    def _sse_payload(obj: Dict[str, Any]) -> str:
        return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"
