"""Shared NLP tick for npc_agent: used by `aico` and line-prefix `@<handle>` dispatch."""
from __future__ import annotations
import os
from typing import Any, Dict, Optional
from app.commands.base import CommandContext, CommandResult
from app.core.log import get_logger
from app.models.graph import Node
_NPC_AGENT_NLP_LOG = get_logger('app.commands.npc_agent_nlp')
NPC_AGENT_LLM_FAILURE_USER_MSG = '我这边暂时无法处理，请再描述一下你的目标。'

def _stm_llm_merge_rolling_summary(llm, cfg, previous_rs: str, transcript_excerpt: str) -> str:
    """Optional STM compaction merge via LLM; failures leave ``previous_rs`` unchanged."""
    extra = dict(cfg.extra or {}) if isinstance(cfg.extra, dict) else {}
    model_raw = extra.get('stm_compaction_model') or cfg.model
    model_s = str(model_raw).strip() if model_raw else ''
    sys_s = str(extra.get('stm_compaction_system_prompt') or '').strip()
    if not sys_s:
        sys_s = 'Merge the previous rolling summary with the conversation excerpt into a short factual summary for an assistant context. Keep user goals, named entities, and open tasks. Max about 800 characters. Plain text only, no markdown fences.'
    user_blob = f"Previous summary:\n{previous_rs or '(none)'}\n\nTranscript:\n{transcript_excerpt[:12000]}"
    try:
        from app.game_engine.agent_runtime.llm_client import LlmCallSpec
        mtok = cfg.max_tokens if cfg.max_tokens is not None else 512
        spec = LlmCallSpec(model=model_s or None, max_tokens=min(512, int(mtok)), temperature=0.2)
        out = llm.complete(system=sys_s, user=user_blob, call_spec=spec)
        return (out or '').strip()
    except Exception:
        _NPC_AGENT_NLP_LOG.warning('stm rolling_summary LLM merge failed', exc_info=True)
        return (previous_rs or '').strip()

def _apply_stm_compaction_with_optional_llm(extra: Dict[str, Any], llm, cfg, msgs, rs: str, *, max_turns: int, max_chars: int):
    from app.game_engine.agent_runtime.agent_llm_extra import parse_bool_extra
    from app.game_engine.agent_runtime.conversation_stm_service import apply_compaction_truncate, format_stm_for_prompt
    if parse_bool_extra(extra, 'enable_stm_llm_compaction', False):
        blob = format_stm_for_prompt(msgs, rs)
        merged = _stm_llm_merge_rolling_summary(llm, cfg, rs, blob)
        if merged:
            rs = merged
    return apply_compaction_truncate(msgs, rs, stm_max_turns=max_turns, stm_max_chars=max_chars)

def maybe_ltm_memory_context(session, agent_node_id: int, user_message: str, cfg_extra: Dict[str, Any], *, caller_account_node_id: Optional[int]=None, conversation_thread_id=None) -> Optional[str]:
    """
    Optional LTM injection. Disabled unless extra.enable_ltm is true in agents.llm YAML extra.
    """
    if not cfg_extra.get('enable_ltm'):
        return None
    if not user_message.strip():
        return None
    if os.environ.get('AICO_SKIP_LTM_PLACEHOLDER'):
        return None
    from app.services.ltm_semantic_retrieval import build_ltm_memory_context_for_tick
    return build_ltm_memory_context_for_tick(session, agent_node_id, user_message=user_message, caller_account_node_id=caller_account_node_id, conversation_thread_id=conversation_thread_id)

def run_npc_agent_nlp_tick(session, node: Node, context: CommandContext, message: str, *, memory_context: Optional[str]=None, phase_llm_overrides: Optional[Dict[str, Any]]=None):
    """Run one LlmPdcaAssistantWorker tick; caller commits session."""
    from app.game_engine.agent_runtime.agent_llm_config import resolve_agent_llm_config_for_npc_tick
    from app.game_engine.agent_runtime.agent_llm_extra import parse_bool_extra
    from app.game_engine.agent_runtime.agent_tick_context import NpcAgentTickInputs, build_caller_graph_snapshot
    from app.game_engine.agent_runtime.aico_world_context import build_world_snapshot_from_session
    from app.game_engine.agent_runtime.conversation_stm_service import CONV_SCOPE_SYSTEM_SHARED_EXCLUSIVE, append_turns_to_messages, format_stm_for_prompt, load_or_create_conversation_stm, normalize_messages, parse_conversation_scope_mode, refresh_daemon_success_tick, stm_should_compact_after_append, touch_thread_metadata, try_acquire_daemon_possession, finalize_daemon_possession_after_success, ensure_conversation_thread_id, try_acquire_conversation_thread_tick_lock
    from app.game_engine.agent_runtime.frameworks.base import FrameworkRunResult
    from app.game_engine.agent_runtime.llm_client import build_llm_client_from_service_config, http_llm_available
    from app.game_engine.agent_runtime.profiles import resolve_agent_runtime_profile
    from app.game_engine.agent_runtime.prompt_fingerprint import compute_npc_prompt_fingerprint
    from app.game_engine.agent_runtime.worker import LlmPdcaAssistantWorker
    from app.core.config_manager import get_config
    attrs = node.attributes or {}
    service_id = str(attrs.get('service_id') or 'aico')
    model_ref = attrs.get('model_config_ref')
    model_ref_s = str(model_ref) if model_ref else None
    cfg = resolve_agent_llm_config_for_npc_tick(service_id, model_config_ref=model_ref_s, node_attributes=attrs)
    if not http_llm_available(cfg):
        return FrameworkRunResult(ok=True, message=str(message).strip(), final_phase='passthrough')
    extra = dict(cfg.extra or {})
    cm = get_config()
    profile = resolve_agent_runtime_profile(service_id)
    caller_snap = build_caller_graph_snapshot(session, context)
    caller_id = caller_snap.caller_node_id
    llm = build_llm_client_from_service_config(cfg)
    tick_inputs = NpcAgentTickInputs(agent=node, attrs=dict(attrs), service_id=service_id, model_ref_s=model_ref_s, cfg=cfg, caller=caller_snap)
    w = LlmPdcaAssistantWorker.create(session, node.id, invoker_context=context, llm_client=llm, agent_llm_config=cfg, tick_inputs=tick_inputs, tick_hooks=profile.build_tick_hooks(config=cm), runtime_observability=profile.build_framework_observability(config=cm))
    world_snapshot_text = ''
    try:
        caller_username = getattr(context, 'username', None)
        caller_roles = getattr(context, 'roles', ()) or ()
        caller_location_node_id = caller_snap.caller_location_node_id
        world_snapshot_text = build_world_snapshot_from_session(session, caller_username=caller_username, caller_roles=list(caller_roles), caller_location_node_id=caller_location_node_id, agent_node_attrs=attrs, tool_surface_count=len(getattr(w, 'tool_schemas', []) or []), recent_commands=())
    except Exception:
        world_snapshot_text = ''
    stm_on = parse_bool_extra(extra, 'enable_conversation_stm', default=False)
    scope_mode = parse_conversation_scope_mode(attrs)
    max_turns = int(extra.get('stm_max_turns') or 20)
    max_chars = int(extra.get('stm_max_chars') or 32000)
    trig = float(extra.get('compaction_trigger_ratio') or 0.9)
    idle_release = int(extra.get('possession_idle_release_seconds') or 60)
    mem_ctx = memory_context
    recent_conv: Optional[str] = None
    retrieved_mem: Optional[str] = None
    mem_do: Optional[str] = None
    daemon_row = None
    conversation_stm_row = None
    thread_id = None
    if stm_on and caller_id is not None:
        if scope_mode == CONV_SCOPE_SYSTEM_SHARED_EXCLUSIVE:
            (ok_poss, err_poss, daemon_row) = try_acquire_daemon_possession(session, agent_node_id=node.id, caller_account_node_id=caller_id, transport_session_id=str(context.session_id or ''), idle_release_seconds=idle_release, username_for_bound=str(context.username or ''))
            if not ok_poss:
                return FrameworkRunResult(ok=False, message=err_poss or NPC_AGENT_LLM_FAILURE_USER_MSG, final_phase='gate')
            msgs = normalize_messages(daemon_row.messages)
            rs = daemon_row.rolling_summary or ''
            if stm_should_compact_after_append(msgs, rs, stm_max_chars=max_chars, compaction_trigger_ratio=trig):
                (msgs, rs) = _apply_stm_compaction_with_optional_llm(extra, llm, cfg, msgs, rs, max_turns=max_turns, max_chars=max_chars)
                daemon_row.messages = msgs
                daemon_row.rolling_summary = rs
            stm_text = format_stm_for_prompt(msgs, rs)
        else:
            thread_id = ensure_conversation_thread_id(session, context=context, caller_account_node_id=caller_id, agent_node_id=node.id)
            conversation_stm_row = load_or_create_conversation_stm(session, caller_account_node_id=caller_id, transport_session_id=str(context.session_id or ''), agent_node_id=node.id, conversation_thread_id=thread_id)
            if not try_acquire_conversation_thread_tick_lock(session, thread_id):
                return FrameworkRunResult(ok=False, message='Another session is using this conversation thread. Wait and retry.', final_phase='gate')
            msgs = normalize_messages(conversation_stm_row.messages)
            rs = conversation_stm_row.rolling_summary or ''
            if stm_should_compact_after_append(msgs, rs, stm_max_chars=max_chars, compaction_trigger_ratio=trig):
                (msgs, rs) = _apply_stm_compaction_with_optional_llm(extra, llm, cfg, msgs, rs, max_turns=max_turns, max_chars=max_chars)
                conversation_stm_row.messages = msgs
                conversation_stm_row.rolling_summary = rs
            stm_text = format_stm_for_prompt(msgs, rs)
        ltm_scope = str(extra.get('ltm_retrieval_scope') or 'user_agent').strip().lower()
        tid_filter = thread_id if ltm_scope == 'thread' else None
        if mem_ctx is None:
            mem_ctx = maybe_ltm_memory_context(session, node.id, message, extra, caller_account_node_id=caller_id, conversation_thread_id=tid_filter)
        recent_conv = stm_text if stm_text else None
        retrieved_mem = mem_ctx or ''
        mem_do = 'Recent conversation and retrieved memory were provided only in the Plan phase; use the Plan section and tool observations below.'
    elif mem_ctx is None:
        mem_ctx = maybe_ltm_memory_context(session, node.id, message, extra)
    with profile.enter_tick_scope(config=cm):
        payload: Dict[str, Any] = {'message': message}
        if world_snapshot_text:
            payload['world_snapshot'] = world_snapshot_text
        payload.update(profile.prepare_payload_overrides(session=session, node=node, context=context, message=message, attrs=attrs, cfg=cfg, worker=w))
        manifest_for_fp = str(payload.get('tool_manifest_text') or w.tool_manifest_text or '')
        payload['prompt_fingerprint'] = compute_npc_prompt_fingerprint(world_snapshot=world_snapshot_text, tool_manifest_text=manifest_for_fp, user_message=message)
        corr_s = str(context.session_id or '')
        if context.metadata is None:
            context.metadata = {}
        stream_state = profile.configure_streaming(context=context, thread_id=thread_id, correlation_id=corr_s or None)
        user_visible_stream = None
        stream_cancel_check = None
        cancel_ev = (context.metadata or {}).get('aico_stream_cancel_event')
        if cancel_ev is not None and hasattr(cancel_ev, 'is_set'):
            stream_cancel_check = cancel_ev.is_set
        if stream_state.stream_on and stream_state.emit is not None:
            from app.game_engine.agent_runtime.presentation_stream import StreamCoordinator, UserVisibleStream

            coordinator = StreamCoordinator(stream_state.emit, context.metadata, cancel_check=stream_cancel_check)
            context.metadata['_aico_presentation_coordinator'] = coordinator
            user_visible_stream = UserVisibleStream(coordinator)
            coordinator.on_tick_start()
            payload['_aico_stream_emit_fn'] = stream_state.emit
        if not stream_state.stream_on:
            profile.emit_progress(context=context)
        try:
            res = w.tick(
                payload,
                correlation_id=context.session_id,
                memory_context=mem_ctx if recent_conv is None else None,
                recent_conversation=recent_conv,
                retrieved_memory=retrieved_mem if recent_conv is not None else None,
                memory_context_do=mem_do,
                phase_llm_overrides=phase_llm_overrides,
                user_visible_stream=user_visible_stream,
                stream_cancel_check=stream_cancel_check,
            )
        except Exception:
            _NPC_AGENT_NLP_LOG.exception('npc_agent_nlp tick failed: service_id=%s session=%s', service_id, context.session_id)
            profile.emit_stream_error(state=stream_state, code='tick_exception', message=NPC_AGENT_LLM_FAILURE_USER_MSG)
            return FrameworkRunResult(ok=False, message=NPC_AGENT_LLM_FAILURE_USER_MSG, final_phase='error')
        profile.emit_stream_result(
            state=stream_state,
            result=res,
            thread_id=thread_id,
            correlation_id=corr_s or None,
            fallback_message=NPC_AGENT_LLM_FAILURE_USER_MSG,
            context=context,
        )
        if stm_on and caller_id is not None and res.ok:
            assistant_reply = str(res.message or '').strip()
            if scope_mode == CONV_SCOPE_SYSTEM_SHARED_EXCLUSIVE and daemon_row is not None:
                finalize_daemon_possession_after_success(session, daemon_row, caller_account_node_id=caller_id, transport_session_id=str(context.session_id or ''), username_for_bound=str(context.username or ''))
                msgs = append_turns_to_messages(normalize_messages(daemon_row.messages), user_text=message, assistant_text=assistant_reply)
                rs = daemon_row.rolling_summary or ''
                if stm_should_compact_after_append(msgs, rs, stm_max_chars=max_chars, compaction_trigger_ratio=trig):
                    (msgs, rs) = _apply_stm_compaction_with_optional_llm(extra, llm, cfg, msgs, rs, max_turns=max_turns, max_chars=max_chars)
                daemon_row.messages = msgs
                daemon_row.rolling_summary = rs
                daemon_row.stm_generation = int(daemon_row.stm_generation or 0) + 1
                refresh_daemon_success_tick(session, daemon_row)
            elif conversation_stm_row is not None:
                msgs = append_turns_to_messages(normalize_messages(conversation_stm_row.messages), user_text=message, assistant_text=assistant_reply)
                rs = conversation_stm_row.rolling_summary or ''
                if stm_should_compact_after_append(msgs, rs, stm_max_chars=max_chars, compaction_trigger_ratio=trig):
                    (msgs, rs) = _apply_stm_compaction_with_optional_llm(extra, llm, cfg, msgs, rs, max_turns=max_turns, max_chars=max_chars)
                conversation_stm_row.messages = msgs
                conversation_stm_row.rolling_summary = rs
                conversation_stm_row.stm_generation = int(conversation_stm_row.stm_generation or 0) + 1
                if thread_id is not None:
                    touch_thread_metadata(session, thread_id, message)
        return res

def assistant_nlp_command_result(handle: str, res, *, service_id: Optional[str]=None, context: Optional[Any]=None) -> CommandResult:
    """Assistant NLP tick → CommandResult: human text in message; machine fields in data."""
    msg = str(res.message or '').strip()
    data: Dict[str, Any] = {'ok': res.ok, 'phase': res.final_phase, 'handle': handle}
    if service_id:
        data['service_id'] = service_id
    if context is not None and (context.metadata or {}).get('_aico_stream_emitted'):
        data['aico_stream_used'] = True
    if res.ok:
        return CommandResult.success_result(msg, data=data)
    return CommandResult(success=False, message=msg or NPC_AGENT_LLM_FAILURE_USER_MSG, data=data, error='aico_tick_failed')
