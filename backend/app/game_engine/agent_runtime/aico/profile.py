"""AICO-specific strategy hooks for the shared npc_agent NLP runtime."""
from __future__ import annotations
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

from app.commands.base import CommandContext
from app.core.log import LoggerNames
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunResult
from app.game_engine.agent_runtime.observability import AgentRuntimeObservability, agent_runtime_observability_context
from app.game_engine.agent_runtime.profiles.base import ProfileStreamState


class AicoFrameworkObservability:
    """AICO adapter behind the generic framework observability interface."""

    @contextmanager
    def run_scope(self, *, run_id: str, correlation_id: Optional[str]) -> Iterator[None]:
        from app.core.log.aico_observability import clear_aico_observability_context, set_aico_observability_context
        with agent_runtime_observability_context(run_id=run_id, correlation_id=correlation_id, logger_name=LoggerNames.AICO_AGENT, http_exchange_logger=self.log_http_exchange):
            set_aico_observability_context(run_id=run_id, correlation_id=correlation_id)
            try:
                yield
            finally:
                clear_aico_observability_context()

    def should_log_full_chain(self, config: Any) -> bool:
        from app.core.log.aico_observability import should_emit_aico_full_chain_logs
        return should_emit_aico_full_chain_logs(config)

    def log_llm_call(self, config: Any, *, phase: str, system: str, user: str, spec: Any, skipped: bool) -> None:
        from app.core.log.aico_observability import log_aico_llm_call
        log_aico_llm_call(config, phase=phase, system=system, user=user, spec=spec, skipped=skipped)

    def log_tool_observations_text(self, config: Any, *, phase: str, observation_text: str) -> None:
        from app.core.log.aico_observability import log_aico_tool_observations_text
        log_aico_tool_observations_text(config, phase=phase, observation_text=observation_text)

    def log_http_exchange(self, config: Any, *, url: str, status_code: int, elapsed_ms: float, request_body: Any, response_data: Any) -> None:
        from app.core.log.aico_observability import log_aico_http_exchange
        log_aico_http_exchange(config, url=url, status_code=status_code, elapsed_ms=elapsed_ms, request_body=request_body, response_data=response_data)


class AicoRuntimeProfile:
    service_id = 'aico'

    def prepare_payload_overrides(self, *, session: Any, node: Any, context: CommandContext, message: str, attrs: Dict[str, Any], cfg: Any, worker: Any) -> Dict[str, Any]:
        from app.game_engine.agent_runtime.agent_llm_extra import parse_bool_extra
        extra = dict(getattr(cfg, 'extra', None) or {})
        if not parse_bool_extra(extra, 'enable_intent_tool_manifest_subset', False):
            return {}
        from app.commands.registry import command_registry
        from app.game_engine.agent_runtime.aico_world_context import build_llm_tool_manifest
        from app.game_engine.agent_runtime.intent_classifier_interface import RuleFallbackIntentClassifier, classify_intent
        ic = classify_intent(message, agent_id=str(node.id), metadata={'correlation_id': str(context.session_id or '')}, classifier=RuleFallbackIntentClassifier())
        if ic.intent != 'informational':
            return {}
        surface = getattr(worker, 'resolved_tool_surface', None)
        if surface is None:
            return {}
        loc = None
        md = context.metadata or {}
        v = md.get('locale')
        if isinstance(v, str) and v.strip():
            loc = v.strip()
        (mtext, mschemas) = build_llm_tool_manifest(surface, command_registry, session=session, locale=loc, manifest_interaction_filter='informational')
        return {'tool_manifest_text': mtext, 'pdca_tool_schema_allowlist': [s.name for s in mschemas]}

    def build_tick_hooks(self, *, config: Any):
        from app.core.log import get_logger
        from app.core.log.aico_observability import get_aico_max_phase_output_chars, is_aico_observability_enabled
        if not is_aico_observability_enabled(config):
            return None
        from app.game_engine.agent_runtime.aico_observability_hooks import AicoObservabilityTickHooks
        return AicoObservabilityTickHooks(get_logger(LoggerNames.AICO_AGENT), max_phase_output_chars=get_aico_max_phase_output_chars(config))

    def build_framework_observability(self, *, config: Any) -> AgentRuntimeObservability:
        _ = config
        return AicoFrameworkObservability()

    @contextmanager
    def enter_tick_scope(self, *, config: Any) -> Iterator[None]:
        from app.core.log.aico_observability import clear_aico_full_chain_tick, set_aico_full_chain_tick
        set_aico_full_chain_tick(self.enable_full_chain_logs(config=config))
        try:
            yield
        finally:
            clear_aico_full_chain_tick()

    def enable_full_chain_logs(self, *, config: Any) -> bool:
        from app.core.log.aico_observability import is_aico_dev_chain_verbose
        return is_aico_dev_chain_verbose(config)

    def configure_streaming(self, *, context: CommandContext, thread_id: Any, correlation_id: Optional[str]) -> ProfileStreamState:
        emit_fn = getattr(context, 'stream_emit', None)
        stream_on = bool(getattr(context, 'supports_aico_stream', False) and emit_fn)
        state = ProfileStreamState(stream_on=stream_on, tick_started=False, emit=emit_fn if stream_on else None)
        if not stream_on or emit_fn is None:
            return state
        from app.commands.aico_stream import emit_tick_lifecycle_meta
        if context.metadata is None:
            context.metadata = {}
        emit_tick_lifecycle_meta(emit_fn, phase='start', thread_id=thread_id, correlation_id=correlation_id, client_hint='running')
        context.metadata['_aico_stream_emitted'] = True
        state.tick_started = True
        return state

    def emit_progress(self, *, context: CommandContext) -> None:
        progress_emit = getattr(context, 'aico_progress_emit', None)
        if not progress_emit:
            return
        from app.commands.aico_stream import aico_repl_progress_message
        progress_emit(aico_repl_progress_message())

    def emit_stream_error(self, *, state: ProfileStreamState, code: str, message: str) -> None:
        if not state.tick_started or state.emit is None:
            return
        from app.commands.aico_stream import emit_aico_error_ndjson
        emit_aico_error_ndjson(state.emit, code=code, message=message)

    def emit_stream_result(self, *, state: ProfileStreamState, result: FrameworkRunResult, thread_id: Any, correlation_id: Optional[str], fallback_message: str) -> None:
        if not state.tick_started or state.emit is None:
            return
        from app.commands.aico_stream import emit_aico_error_ndjson, emit_assistant_stream_ndjson, emit_tick_lifecycle_meta
        if not result.ok:
            fail_msg = str(result.message or '').strip() or fallback_message
            emit_aico_error_ndjson(state.emit, code='tick_failed', message=fail_msg)
            return
        assistant_reply = str(result.message or '').strip()
        emit_assistant_stream_ndjson(state.emit, assistant_reply, thread_id=thread_id, correlation_id=correlation_id, allow_empty_body=True)
        emit_tick_lifecycle_meta(state.emit, phase='complete', thread_id=thread_id, correlation_id=correlation_id, ok=True, final_phase=result.final_phase, empty_reply=not bool(assistant_reply))
