from __future__ import annotations
import logging
import re
import time
import uuid
from dataclasses import replace
from typing import Any, Dict, List, Optional, Sequence, Tuple
from app.commands.base import CommandContext
from app.commands.registry import command_registry
from app.core.config_manager import get_config
from app.core.settings import AgentLlmServiceConfig, PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext, FrameworkRunResult, ThinkingFramework
from app.game_engine.agent_runtime.frameworks.pdca import PDCAPhase
from app.game_engine.agent_runtime.intent_classifier_interface import IntentClassifier, RuleFallbackIntentClassifier, classify_intent
from app.game_engine.agent_runtime.llm_client import AGENT_EXTRA_KEYS_MERGED_INTO_LLM_CALL_SPEC, LlmCallSpec, LlmClient, StubLlmClient, complete_with_tools, supports_tools
from app.game_engine.agent_runtime.memory_port import MemoryPort
from app.game_engine.agent_runtime.observability import AgentRuntimeObservability, NoopAgentRuntimeObservability
from app.game_engine.agent_runtime.phase_llm_resolve import merge_phase_config, to_llm_call_spec
from app.game_engine.agent_runtime.resolved_tool_surface import PreauthorizedToolExecutor
from app.game_engine.agent_runtime.thinking_pipeline import AgentTickHooks, NoOpAgentTickHooks, ThinkingPhaseId
from app.game_engine.agent_runtime.tool_calling import AssistantToolUseTurn, CompleteWithToolsResult, ConversationTurn, TextTurn, ToolCall, ToolResult, ToolResultsTurn, ToolSchema, assistant_tool_use_turn_as_text_block, command_result_to_tool_result, tool_calls_to_invocation_plan, tool_results_turn_as_text_block
from app.game_engine.agent_runtime.tool_router import format_tool_router_hint, parse_tool_router_config, run_tool_router
from app.game_engine.agent_runtime.tool_router.mandatory_gap import format_mandatory_gap_user_notice, mandatory_observation_gap
from app.game_engine.agent_runtime.tool_router.router_result import EnforcementLevel
from app.game_engine.agent_runtime.tool_gather import ToolGatherBudgets, ToolGatherCounters, ToolInvocationPlan, format_tool_batch_limit_hint, format_tool_observation_block, gather_tool_observations, max_executable_commands_this_round, parse_tool_invocation_plan_from_text, tool_gather_budgets_from_agent_extra
from app.game_engine.agent_runtime.tool_runtime_view import resolve_tool_runtime_view
from app.game_engine.agent_runtime.tooling import ToolExecutor
_CHECK_RETRY_RE = re.compile('RETRY\\s*:\\s*need_tools\\s*=\\s*([A-Za-z0-9_.\\-]+(?:\\s*,\\s*[A-Za-z0-9_.\\-]+)*)', flags=re.IGNORECASE)
_DEFAULT_NPC_AGENT_EMPTY_REPLY = '抱歉，我没有能力处理此问题。你可以换一个问题。'

def assemble_plan_skip_do_draft(plan_out: str, _plan_tools_text: str) -> str:
    """Text shown to the user when the Do phase LLM is skipped.

    Tool observations are omitted here; they are appended only to the Check-phase
    prompt for grounding. ``_plan_tools_text`` remains on the signature for stable
    call sites and tests.
    """
    return (plan_out or '').strip()
_DEFAULT_PD_CA_SLIM_FOLLOWUP = 'You are a CampusWorld npc_agent continuing after Plan (Do / Check / Act).\n- Ground factual claims about live graph or command output only in tool observations or text already present in this user turn (Plan, Memory, Draft). Do not invent nodes, locations, or command results.\n- Tool calling: use native tool_use when the runtime supports it; otherwise emit exactly one fenced JSON block of the form {"commands": [{"name": "<registered_tool>", "args": ["..."]}, ...]}. Do not claim a tool ran unless observations include its output. Respect the per-turn tool batch limit in the system prompt.\n- Match the user\'s language; stay concise unless the phase prompt asks otherwise.'

def _resolve_pdca_slim_followup_system(cfg: AgentLlmServiceConfig) -> Optional[str]:
    """Return slim follow-up system text, or None to keep the full base system on every phase.

    YAML ``extra.pdca_use_slim_followup_system: false`` disables slimming.
    ``extra.pdca_followup_system_prompt`` overrides the default slim block.
    """
    extra = getattr(cfg, 'extra', None) or {}
    if not isinstance(extra, dict):
        return _DEFAULT_PD_CA_SLIM_FOLLOWUP
    if extra.get('pdca_use_slim_followup_system') is False:
        return None
    raw = extra.get('pdca_followup_system_prompt')
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return _DEFAULT_PD_CA_SLIM_FOLLOWUP

def _phase_system_core(base_full: str, phase: str, phase_prompts: Dict[str, str], slim_base: Optional[str]) -> str:
    core = slim_base if slim_base and phase in {PDCAPhase.do.value, PDCAPhase.check.value, PDCAPhase.act.value} else base_full
    return _phase_system(core, phase, phase_prompts)

def _tool_schema_allowlist_from_payload(payload: Dict[str, Any]) -> Optional[List[str]]:
    raw = payload.get('pdca_tool_schema_allowlist')
    if not isinstance(raw, list) or not raw:
        return None
    out = [str(x).strip() for x in raw if str(x).strip()]
    return out or None

def resolve_tool_schemas_for_pdca_phase(all_schemas: Sequence[ToolSchema], payload: Optional[Dict[str, Any]], pdca_phase: str) -> List[ToolSchema]:
    """Apply F14 ``schema_subset`` allowlist only for Plan-phase tool calls.

    §5: subset is emitted for the Plan LLM; Do / Check keep the full resolved surface
    so execution and guardrails still see every allowed command on the node surface.
    """
    allow = _tool_schema_allowlist_from_payload(payload or {})
    if not allow or pdca_phase != PDCAPhase.plan.value:
        return list(all_schemas)
    allowed_set = set(allow)
    filtered = [s for s in all_schemas if getattr(s, 'name', None) in allowed_set]
    return filtered if filtered else list(all_schemas)

def _resolve_npc_agent_empty_reply_message(cfg: AgentLlmServiceConfig) -> str:
    """``agents.llm.*.extra.npc_agent_empty_reply_message`` overrides; else default."""
    extra = getattr(cfg, 'extra', None) or {}
    if not isinstance(extra, dict):
        return _DEFAULT_NPC_AGENT_EMPTY_REPLY
    raw = extra.get('npc_agent_empty_reply_message')
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return _DEFAULT_NPC_AGENT_EMPTY_REPLY
_LLM_PDCA_LOG = logging.getLogger(__name__)

def _filter_tool_calls_to_schemas(calls: List[ToolCall], tool_schemas: Sequence[ToolSchema]) -> Tuple[List[ToolCall], List[str]]:
    """Drop tool invocations not present on the resolved schema surface.

    Prevents JSON fallback (or any stray names) from entering ``AssistantToolUseTurn``
    and then failing wire validation (tool_use name not in request ``tools``).
    Normalizes names through the command registry (alias → primary).
    """
    if not calls:
        return ([], [])
    allowed = {str(s.name) for s in tool_schemas if getattr(s, 'name', None)}
    if not allowed:
        return ([], [c.name for c in calls if c.name])
    kept: List[ToolCall] = []
    dropped: List[str] = []
    for c in calls:
        raw = (c.name or '').strip()
        cmd = command_registry.get_command(raw) if raw else None
        primary = (cmd.name if cmd is not None else raw).strip()
        if not primary:
            continue
        if primary in allowed:
            if primary != c.name:
                kept.append(ToolCall(id=c.id, name=primary, args=list(c.args)))
            else:
                kept.append(c)
        else:
            dropped.append(raw or primary)
    return (kept, dropped)

def _trace_phase_timing(trace: List[Dict[str, Any]], *, scope: str, phase: str, elapsed_ms: float, round_idx: Optional[int]=None, channel: Optional[str]=None, tool_call_count: Optional[int]=None) -> None:
    """Append a small structured row for tick latency analysis (F10 observability)."""
    row: Dict[str, Any] = {'step': 'phase_timing', 'scope': scope, 'phase': phase, 'elapsed_ms': round(float(elapsed_ms), 3)}
    if round_idx is not None:
        row['round'] = int(round_idx)
    if channel:
        row['channel'] = channel
    if tool_call_count is not None:
        row['tool_call_count'] = int(tool_call_count)
    trace.append(row)

def _merge_phase_prompts(base: Dict[str, str], overrides: Optional[Dict[str, str]]) -> Dict[str, str]:
    out = dict(base)
    if overrides:
        out.update({k: v for (k, v) in overrides.items() if v})
    return out

def _phase_system(base_system: str, phase: str, phase_prompts: Dict[str, str]) -> str:
    suffix = phase_prompts.get(phase, '').strip()
    if not suffix:
        return base_system
    return f'{base_system.rstrip()}\n\n[{phase}] {suffix}'

def _parse_check_retry_signal(text: str) -> Optional[List[str]]:
    """Return the list of requested tool names from a ``RETRY: need_tools=...`` line.

    Returns ``None`` when no RETRY marker is found. The list may be empty
    when the Check phase asks for a retry without nominating tools.
    """
    if not text:
        return None
    m = _CHECK_RETRY_RE.search(text)
    if not m:
        return None
    raw = m.group(1) or ''
    tools = [t.strip() for t in raw.split(',') if t.strip()]
    return tools

class LlmPDCAFramework(ThinkingFramework):
    """PDCA with LLM calls and a ReAct tool loop per phase.

    Behaviour highlights (F08 / v2 plan):

    * Per-phase **ReAct loop** — after each LLM call, any tool invocations
      are executed and their observations appended to the user turn; the
      loop runs up to ``ToolGatherBudgets.max_tool_rounds_per_phase``
      rounds per phase.
    * **Dual-track tool calling** — clients that implement
      ``supports_tools()`` go through ``complete_with_tools`` with neutral
      ``ToolSchema`` / ``ToolCall`` primitives; otherwise the framework
      falls back to parsing a JSON ``commands`` object from plain text.
    * **Tiered context** — ``FrameworkRunContext.payload`` may contain
      ``world_snapshot`` and ``tool_manifest_text``; both are injected into
      the first Plan user turn only, so Do / Check do not repeat system-level
      knowledge (Anthropic "effective context engineering" guidance).
    * **Native tool transcripts** — after each tool round the framework
      appends :class:`AssistantToolUseTurn` then :class:`ToolResultsTurn` so
      HTTP clients can map to provider-specific ``tool_use`` / ``tool_result``
      ordering without embedding vendor rules here.
    * **Check guardrail** — the Check phase can emit
      ``RETRY: need_tools=a,b`` to request another Plan iteration; the
      framework honours this once per tick if the tool-round budget still
      allows.
    """

    def __init__(self, memory: MemoryPort, llm_config: AgentLlmServiceConfig, *, instance_phase_llm: Dict[str, PhaseLlmPhaseConfig], instance_mode_models: Dict[str, str], llm: Optional[LlmClient]=None, tools: Optional[ToolExecutor]=None, tool_command_context: Optional[CommandContext]=None, preauthorized_tool_executor: Optional[PreauthorizedToolExecutor]=None, tool_gather_budgets: Optional[ToolGatherBudgets]=None, tick_hooks: Optional[AgentTickHooks]=None, tool_schemas: Optional[Sequence[ToolSchema]]=None, intent_classifier: Optional[IntentClassifier]=None, observability: Optional[AgentRuntimeObservability]=None):
        self._memory = memory
        self._cfg = llm_config
        self._instance_phase_llm = instance_phase_llm
        self._instance_mode_models = dict(instance_mode_models or {})
        self._llm = llm or StubLlmClient()
        self._tools = tools
        self._tool_command_context = tool_command_context
        self._pre_tool = preauthorized_tool_executor
        self._tool_budgets = tool_gather_budgets or tool_gather_budgets_from_agent_extra(llm_config.extra)
        self._tick_hooks: AgentTickHooks = tick_hooks or NoOpAgentTickHooks()
        self._tool_schemas: List[ToolSchema] = list(tool_schemas or [])
        self._intent_classifier: Optional[IntentClassifier] = intent_classifier
        self._observability: AgentRuntimeObservability = observability or NoopAgentRuntimeObservability()

    @property
    def framework_id(self) -> str:
        return 'PDCA_LLM'

    def _spec_for_phase(self, phase: str, ctx: FrameworkRunContext) -> LlmCallSpec:
        pcfg = merge_phase_config(phase, self._instance_phase_llm, ctx.phase_llm_overrides)
        return to_llm_call_spec(pcfg, mode_models=self._instance_mode_models, default_model=(self._cfg.model or '').strip())

    def _augment_spec_from_ctx(self, spec: LlmCallSpec, ctx: FrameworkRunContext) -> LlmCallSpec:
        fp = (ctx.payload or {}).get('prompt_fingerprint')
        extra = dict(spec.extra or {})
        if isinstance(fp, str) and fp.strip():
            extra['prompt_fingerprint'] = fp.strip()
        cm_extra = getattr(self._cfg, 'extra', None) or {}
        if isinstance(cm_extra, dict):
            for key in AGENT_EXTRA_KEYS_MERGED_INTO_LLM_CALL_SPEC:
                if key in cm_extra:
                    extra[key] = cm_extra[key]
        if extra != (spec.extra or {}):
            return replace(spec, extra=extra)
        return spec

    def _effective_tool_schemas(self, ctx: FrameworkRunContext, *, pdca_phase: str) -> List[ToolSchema]:
        """Narrow tool schemas for Plan only when F14 ``schema_subset`` set allowlist on payload."""
        return resolve_tool_schemas_for_pdca_phase(self._tool_schemas, ctx.payload, pdca_phase)

    def _call_llm(self, phase: str, system: str, user: str, ctx: FrameworkRunContext) -> Tuple[str, Dict[str, Any]]:
        """Single plain-text LLM call (back-compat shape for existing tests)."""
        spec = self._augment_spec_from_ctx(self._spec_for_phase(phase, ctx), ctx)
        cm = get_config()
        if self._observability.should_log_full_chain(cm):
            self._observability.log_llm_call(cm, phase=phase, system=system, user=user, spec=spec, skipped=spec.mode == PhaseLlmMode.skip)
        if spec.mode == PhaseLlmMode.skip:
            return ('', {'step': phase, 'skipped': True, 'mode': spec.mode.value})
        out = self._llm.complete(system=system, user=user, call_spec=spec)
        return (out, {'step': phase, 'llm_output': out, 'mode': spec.mode.value})

    def _gather_tools_after_llm(self, pdca_phase: str, llm_output: str, trace: List[Dict[str, Any]], counters: ToolGatherCounters) -> str:
        """Back-compat helper used by existing unit tests.

        New code paths go through :meth:`_phase_react_loop` which handles
        both native tool_use calls and JSON fallback uniformly.
        """
        view = resolve_tool_runtime_view(pre_tool=self._pre_tool, tool_command_context=self._tool_command_context, budgets=self._tool_budgets, counters=counters)
        if not view.can_execute:
            trace.append({'step': 'tool_gather_skip', 'phase': pdca_phase, 'reason': view.reason})
            return ''
        plan = parse_tool_invocation_plan_from_text(llm_output or '')
        if not plan.commands:
            return ''
        assert view.executor is not None and view.tool_context is not None
        (text, entries) = gather_tool_observations(view.executor, view.tool_context, plan, budgets=view.budgets, counters=counters, phase_label=pdca_phase)
        trace.extend(entries)
        if text:
            cm = get_config()
            if self._observability.should_log_full_chain(cm):
                self._observability.log_tool_observations_text(cm, phase=pdca_phase, observation_text=text)
        return text

    def _call_llm_dual_track(self, phase: str, system: str, turns: List[ConversationTurn], ctx: FrameworkRunContext) -> Tuple[str, List[ToolCall], Dict[str, Any]]:
        """Native ``complete_with_tools`` when available, JSON fallback otherwise.

        Returns ``(text, tool_calls, trace_entry)``. ``tool_calls`` is empty
        when the model chose to answer with prose or when parsing failed.
        """
        spec = self._augment_spec_from_ctx(self._spec_for_phase(phase, ctx), ctx)
        cm = get_config()
        user_text_for_log = _render_turns_as_text(turns)
        if self._observability.should_log_full_chain(cm):
            self._observability.log_llm_call(cm, phase=phase, system=system, user=user_text_for_log, spec=spec, skipped=spec.mode == PhaseLlmMode.skip)
        if spec.mode == PhaseLlmMode.skip:
            return ('', [], {'step': phase, 'skipped': True, 'mode': spec.mode.value})
        channel = 'text'
        text = ''
        calls: List[ToolCall] = []
        phase_tools = self._effective_tool_schemas(ctx, pdca_phase=phase)
        if supports_tools(self._llm) and phase_tools:
            try:
                res: CompleteWithToolsResult = complete_with_tools(self._llm, system=system, turns=turns, tools=phase_tools, call_spec=spec)
                channel = 'tool_use'
                text = res.text or ''
                calls = list(res.tool_calls or [])
                if not calls and res.finish_reason.lower() not in ('tool_use', 'tool_calls'):
                    calls = _tool_calls_from_text(text)
            except NotImplementedError:
                text = self._llm.complete(system=system, user=user_text_for_log, call_spec=spec)
                calls = _tool_calls_from_text(text)
        else:
            text = self._llm.complete(system=system, user=user_text_for_log, call_spec=spec)
            calls = _tool_calls_from_text(text)
        dropped: List[str] = []
        if phase_tools and calls:
            (calls, dropped) = _filter_tool_calls_to_schemas(calls, phase_tools)
            if dropped:
                _LLM_PDCA_LOG.warning('tool_call_filtered phase=%s dropped=%s', phase, dropped)
        return (text, calls, {'step': phase, 'llm_output': text, 'mode': spec.mode.value, 'channel': channel, 'tool_call_count': len(calls), 'dropped_tool_names': dropped})

    def _phase_react_loop(self, pdca_phase: str, system: str, initial_user: str, ctx: FrameworkRunContext, counters: ToolGatherCounters, trace: List[Dict[str, Any]]) -> Tuple[str, str, List[ToolResult], Dict[str, Any]]:
        """Run up to ``budgets.max_tool_rounds_per_phase`` reason-act-observe cycles.

        Returns ``(final_text, accumulated_observation_text, tool_results, last_entry)``.
        ``final_text`` is the LLM's last textual output (or empty if only
        tool calls were emitted). ``accumulated_observation_text`` is the
        concatenation of all serialized ``ToolResultsTurn`` bodies from
        this phase (used for Do/Check user segments and for trace logs).
        """
        max_rounds = max(1, int(self._tool_budgets.max_tool_rounds_per_phase))
        turns: List[ConversationTurn] = [TextTurn(role='user', text=initial_user)]
        obs_chunks: List[str] = []
        all_results: List[ToolResult] = []
        last_text = ''
        last_entry: Dict[str, Any] = {'step': pdca_phase, 'skipped': False}
        t_phase = time.perf_counter()
        try:
            for round_idx in range(max_rounds):
                t_llm = time.perf_counter()
                budget_hint = format_tool_batch_limit_hint(self._tool_budgets, counters)
                system_for_llm = f'{system}\n\n{budget_hint}' if budget_hint else system
                (text, calls, entry) = self._call_llm_dual_track(pdca_phase, system_for_llm, turns, ctx)
                entry = dict(entry)
                entry['round'] = round_idx + 1
                trace.append(entry)
                dropped_n = list(entry.get('dropped_tool_names') or [])
                if dropped_n:
                    trace.append({'step': 'tool_call_filtered', 'phase': pdca_phase, 'dropped': dropped_n, 'round': round_idx + 1})
                _trace_phase_timing(trace, scope='llm', phase=pdca_phase, elapsed_ms=(time.perf_counter() - t_llm) * 1000.0, round_idx=round_idx + 1, channel=str(entry.get('channel') or '') or None, tool_call_count=int(entry.get('tool_call_count') or 0) or None)
                last_text = text
                last_entry = entry
                if entry.get('skipped'):
                    break
                if not calls:
                    break
                base_tool_ctx = self._tool_command_context
                runtime_tool_ctx = base_tool_ctx
                if base_tool_ctx is not None:
                    rt_meta = dict(base_tool_ctx.metadata or {})
                    rt_meta['user_message'] = str(ctx.payload.get('message') or ctx.payload.get('text') or '')
                    runtime_tool_ctx = CommandContext(user_id=base_tool_ctx.user_id, username=base_tool_ctx.username, session_id=base_tool_ctx.session_id, permissions=list(base_tool_ctx.permissions or []), roles=list(base_tool_ctx.roles or []), db_session=base_tool_ctx.db_session, caller=base_tool_ctx.caller, game_state=base_tool_ctx.game_state, metadata=rt_meta)
                view = resolve_tool_runtime_view(pre_tool=self._pre_tool, tool_command_context=runtime_tool_ctx, budgets=self._tool_budgets, counters=counters)
                if not view.can_execute:
                    trace.append({'step': 'tool_gather_skip', 'phase': pdca_phase, 'reason': view.reason, 'round': round_idx + 1})
                    break
                max_exec = max_executable_commands_this_round(self._tool_budgets, counters)
                calls_to_run = list(calls[:max_exec])
                calls_deferred = list(calls[max_exec:])
                if calls_deferred:
                    trace.append({'step': 'tool_cap_pre_truncated', 'phase': pdca_phase, 'round': round_idx + 1, 'requested': len(calls), 'executed': len(calls_to_run), 'deferred': len(calls_deferred)})
                    _LLM_PDCA_LOG.warning('tool_batch_pre_truncated phase=%s round=%s requested=%s executed=%s', pdca_phase, round_idx + 1, len(calls), len(calls_to_run))
                pre_truncated_reason = 'tick_max_commands' if max_exec <= 0 and counters.commands_run >= self._tool_budgets.max_commands_per_tick else 'phase_max_commands'
                assert view.executor is not None and view.tool_context is not None
                t_gather = time.perf_counter()
                if calls_to_run:
                    plan = tool_calls_to_invocation_plan(calls_to_run)
                    (obs_text, gather_entries) = gather_tool_observations(view.executor, view.tool_context, plan, budgets=view.budgets, counters=counters, phase_label=pdca_phase)
                else:
                    obs_text = ''
                    gather_entries = [{'step': 'tool_cap', 'detail': pre_truncated_reason, 'phase': pdca_phase}]
                trace.extend(gather_entries)
                _trace_phase_timing(trace, scope='tool_gather', phase=pdca_phase, elapsed_ms=(time.perf_counter() - t_gather) * 1000.0, round_idx=round_idx + 1)
                if obs_text:
                    cm = get_config()
                    if self._observability.should_log_full_chain(cm):
                        self._observability.log_tool_observations_text(cm, phase=pdca_phase, observation_text=obs_text)
                exec_entries = [e for e in gather_entries if e.get('step') == 'tool_exec']
                round_results = build_round_tool_results(
                    calls=calls,
                    executed_call_count=len(calls_to_run),
                    exec_entries=exec_entries,
                    obs_text=obs_text,
                    gather_entries=gather_entries,
                    round_idx=round_idx,
                    pre_truncated_reason=pre_truncated_reason,
                )
                if len(round_results) != len(calls):
                    _LLM_PDCA_LOG.warning('tool_result_count_mismatch phase=%s round=%s calls=%s results=%s', pdca_phase, round_idx + 1, len(calls), len(round_results))
                all_results.extend(round_results)
                turns.append(AssistantToolUseTurn(text=text or '', tool_calls=[ToolCall(id=c.id, name=c.name, args=list(c.args)) for c in calls]))
                turns.append(ToolResultsTurn(results=round_results))
                obs_chunks.append(obs_text)
                if counters.commands_run >= self._tool_budgets.max_commands_per_tick or counters.observation_chars >= self._tool_budgets.max_chars_observations_per_tick:
                    break
        finally:
            _trace_phase_timing(trace, scope='phase_total', phase=pdca_phase, elapsed_ms=(time.perf_counter() - t_phase) * 1000.0)
        return (last_text, '\n\n'.join((o for o in obs_chunks if o)), all_results, last_entry)

    def run(self, ctx: FrameworkRunContext) -> FrameworkRunResult:
        run_id = uuid.uuid4()
        trace: List[Dict[str, Any]] = []
        correlation = ctx.correlation_id or ctx.payload.get('correlation_id')
        user_msg = str(ctx.payload.get('message') or ctx.payload.get('text') or '').strip()
        gather_counters = ToolGatherCounters()
        corr_s = correlation if isinstance(correlation, str) else None
        with self._observability.run_scope(run_id=str(run_id), correlation_id=corr_s):
            return self._run_inner(ctx, run_id, trace, user_msg, gather_counters, correlation)

    def _run_inner(self, ctx: FrameworkRunContext, run_id: uuid.UUID, trace: List[Dict[str, Any]], user_msg: str, gather_counters: ToolGatherCounters, correlation: Any) -> FrameworkRunResult:
        self._memory.start_run(run_id=run_id, correlation_id=correlation if isinstance(correlation, str) else None, phase=PDCAPhase.plan.value, command_trace=list(trace), status='running')
        base_system = (ctx.system_prompt or self._cfg.system_prompt or '').strip()
        merged_phases = _merge_phase_prompts(dict(self._cfg.phase_prompts), ctx.phase_prompts)
        slim_followup = _resolve_pdca_slim_followup_system(self._cfg)
        mem = (ctx.memory_context or '').strip()
        mem_for_do = (ctx.memory_context_do or '').strip() if ctx.memory_context_do is not None else mem
        world_snapshot = str(ctx.payload.get('world_snapshot') or '').strip()
        tool_manifest_text = str(ctx.payload.get('tool_manifest_text') or '').strip()
        if isinstance(ctx.payload.get('intent_hint'), dict):
            intent_hint = dict(ctx.payload.get('intent_hint') or {})
        else:
            icls = self._intent_classifier or RuleFallbackIntentClassifier()
            ic = classify_intent(user_msg, agent_id=str(ctx.agent_node_id), metadata={'correlation_id': str(correlation or '')}, classifier=icls)
            ic_extra: Dict[str, Any] = {'intent': ic.intent, 'intent_confidence': float(ic.confidence), 'intent_source': ic.source}
            if ic.latency_ms is not None:
                ic_extra['intent_slm_latency_ms'] = float(ic.latency_ms)
            _LLM_PDCA_LOG.info('intent_classified', extra=ic_extra)
            intent_hint = {'intent': ic.intent, 'reason_tokens': list(ic.reason_tokens or []), 'confidence': float(ic.confidence), 'source': ic.source}
        ctx.payload.pop('tool_router_snapshot', None)
        ctx.payload.pop('pdca_tool_schema_allowlist', None)
        tr_cfg = parse_tool_router_config(dict(self._cfg.extra or {}))
        stm_for_router = None
        if ctx.recent_conversation is not None:
            stm_for_router = (ctx.recent_conversation or '').strip() or None
        rr = run_tool_router(cfg=tr_cfg, user_message=user_msg, world_snapshot=world_snapshot, stm_snippet=stm_for_router, intent_hint=intent_hint, tool_schemas=self._tool_schemas, agent_extra=dict(self._cfg.extra or {}))
        tool_router_hint_text = ''
        if rr is not None:
            trace.append({'step': 'tool_router', **rr.to_trace_dict()})
            ctx.payload['tool_router_snapshot'] = rr.to_payload_dict()
            tool_router_hint_text = format_tool_router_hint(rr)
            if rr.enforcement_level == EnforcementLevel.schema_subset:
                ctx.payload['pdca_tool_schema_allowlist'] = rr.schema_allowlist_names()
        chain_criteria_text = ''
        snap_for_criteria = ctx.payload.get('tool_router_snapshot')
        if isinstance(snap_for_criteria, dict):
            chain_criteria_text = _tool_chain_completion_criteria_text(
                list(snap_for_criteria.get('mandatory_tool_names') or [])
            )
        if ctx.recent_conversation is not None or ctx.retrieved_memory is not None:
            rc = (ctx.recent_conversation or '').strip()
            rm = (ctx.retrieved_memory or '').strip()
            plan_user = _assemble_plan_user(user_msg=user_msg, memory=rm or '(none)', world_snapshot=world_snapshot, tool_manifest_text=tool_manifest_text, intent_hint=intent_hint, recent_conversation=rc if rc else None, tool_router_hint=tool_router_hint_text or None)
        else:
            plan_user = _assemble_plan_user(user_msg=user_msg, memory=mem, world_snapshot=world_snapshot, tool_manifest_text=tool_manifest_text, intent_hint=intent_hint, tool_router_hint=tool_router_hint_text or None)
        if chain_criteria_text:
            plan_user += '\n\n' + chain_criteria_text
        accumulated_tick_tool_results: List[ToolResult] = []
        self._tick_hooks.on_before_phase(ThinkingPhaseId.plan, ctx)
        plan_sys = _phase_system(base_system, PDCAPhase.plan.value, merged_phases)
        (plan_out, plan_tools_text, plan_tool_results, plan_entry) = self._phase_react_loop(PDCAPhase.plan.value, plan_sys, plan_user, ctx, gather_counters, trace)
        accumulated_tick_tool_results.extend(plan_tool_results)
        self._memory.update_run(run_id, PDCAPhase.plan.value, trace, 'running')
        self._tick_hooks.on_after_phase(ThinkingPhaseId.plan, ctx, phase_llm_output=plan_out or '', skipped=bool(plan_entry.get('skipped')))
        if plan_tools_text:
            trace.append({'step': 'plan_tool_observations', 'chars': len(plan_tools_text)})
        plan_block = (plan_out or '').strip()
        tool_blocks_plan = f'\n\nTool observations (plan phase):\n{plan_tools_text}' if plan_tools_text else ''
        self._tick_hooks.on_before_phase(ThinkingPhaseId.do, ctx)
        if plan_block:
            do_user = f"User message:\n{user_msg}\n\nPlan:\n{plan_out}\n{tool_blocks_plan}\n\nMemory:\n{mem_for_do or '(none)'}"
        else:
            do_user = f"User message:\n{user_msg}{tool_blocks_plan}\n\nMemory:\n{mem_for_do or '(none)'}"
        do_sys = _phase_system_core(base_system, PDCAPhase.do.value, merged_phases, slim_followup)
        do_spec = self._augment_spec_from_ctx(self._spec_for_phase(PDCAPhase.do.value, ctx), ctx)
        if do_spec.mode == PhaseLlmMode.skip:
            reply = assemble_plan_skip_do_draft(plan_out or '', plan_tools_text or '')
            do_tools_text = ''
            do_entry: Dict[str, Any] = {'step': PDCAPhase.do.value, 'skipped': True, 'mode': PhaseLlmMode.skip.value, 'skip_do_draft_chars': len(reply or '')}
            trace.append(do_entry)
        else:
            (reply, do_tools_text, do_tool_results, do_entry) = self._phase_react_loop(PDCAPhase.do.value, do_sys, do_user, ctx, gather_counters, trace)
            accumulated_tick_tool_results.extend(do_tool_results)
        self._memory.update_run(run_id, PDCAPhase.do.value, trace, 'running')
        self._tick_hooks.on_after_phase(ThinkingPhaseId.do, ctx, phase_llm_output=reply or '', skipped=bool(do_entry.get('skipped')))
        if do_tools_text:
            trace.append({'step': 'do_tool_observations', 'chars': len(do_tools_text)})
        tool_blocks_do = f'\n\nTool observations (do phase):\n{do_tools_text}' if do_tools_text else ''
        plan_grounding_for_check = ''
        if do_spec.mode == PhaseLlmMode.skip and (plan_tools_text or '').strip():
            plan_grounding_for_check = f'\n\nPlan-phase tool observations (runtime grounding; not shown to user):\n{plan_tools_text}'
        check_user = f'User message:\n{user_msg}\n\nDraft reply:\n{reply}{plan_grounding_for_check}{tool_blocks_do}'
        snap = ctx.payload.get('tool_router_snapshot')
        if isinstance(snap, dict) and snap.get('enforcement_level') == EnforcementLevel.hard_must_invoke.value:
            mans = snap.get('mandatory_tool_names') or []
            if mans:
                check_user += '\n\nRouting mandatory tools (verify ToolObservation covers each): ' + ', '.join((str(x) for x in mans))
        if chain_criteria_text:
            check_user += '\n\n' + chain_criteria_text
        check_sys = _phase_system_core(base_system, PDCAPhase.check.value, merged_phases, slim_followup)
        self._tick_hooks.on_before_phase(ThinkingPhaseId.check, ctx)
        t_check = time.perf_counter()
        (check_out, check_entry) = self._call_llm(PDCAPhase.check.value, check_sys, check_user, ctx)
        _trace_phase_timing(trace, scope='llm', phase=PDCAPhase.check.value, elapsed_ms=(time.perf_counter() - t_check) * 1000.0)
        retry_tools = None if check_entry.get('skipped') else _parse_check_retry_signal(check_out or '')
        if check_entry.get('skipped'):
            ok = True
        else:
            co = check_out or ''
            ok = 'error' not in co.lower()[:80]
        snap_gap_for_retry = ctx.payload.get('tool_router_snapshot')
        if retry_tools is None and isinstance(snap_gap_for_retry, dict):
            mans_retry = [str(x).strip() for x in (snap_gap_for_retry.get('mandatory_tool_names') or []) if str(x).strip()]
            if mans_retry:
                (has_gap_retry, gap_retry_detail) = mandatory_observation_gap(
                    mans_retry,
                    accumulated_tick_tool_results,
                    plan_trace=trace,
                )
                if has_gap_retry:
                    retry_tools = sorted(
                        set(
                            [str(x).strip() for x in (gap_retry_detail.get('missing') or []) if str(x).strip()]
                            + [str(x).strip() for x in (gap_retry_detail.get('failed') or []) if str(x).strip()]
                        )
                    )
                    check_entry['retry_reason'] = 'mandatory_tool_gap'
                    trace.append(
                        {
                            'step': 'mandatory_gap_retry_override',
                            'tools': retry_tools,
                            'details': gap_retry_detail,
                        }
                    )
        check_entry['passed'] = ok
        if retry_tools is not None:
            check_entry['retry_tools'] = retry_tools
        trace.append(check_entry)
        self._memory.update_run(run_id, PDCAPhase.check.value, trace, 'running')
        self._tick_hooks.on_after_phase(ThinkingPhaseId.check, ctx, phase_llm_output=check_out or '', skipped=bool(check_entry.get('skipped')))
        final_text = reply
        if retry_tools is not None and gather_counters.commands_run < self._tool_budgets.max_commands_per_tick:
            retry_hint = f"Check phase flagged that tool observations are required to answer. Requested tools: {', '.join(retry_tools) or '(any)'}."
            trace.append({'step': 'check_retry_triggered', 'tools': retry_tools})
            plan2_user = f'{plan_user}\n\nGuardrail note:\n{retry_hint}\nEmit a tool call plan now.'
            (plan2_out, plan2_tools_text, plan2_tool_results, plan2_entry) = self._phase_react_loop(PDCAPhase.plan.value, plan_sys, plan2_user, ctx, gather_counters, trace)
            accumulated_tick_tool_results.extend(plan2_tool_results)
            if plan2_tools_text:
                trace.append({'step': 'plan_retry_tool_observations', 'chars': len(plan2_tools_text)})
            do2_blocks = f'\n\nTool observations (plan retry):\n{plan2_tools_text}' if plan2_tools_text else ''
            do2_user = f"User message:\n{user_msg}\n\nPlan:\n{plan2_out or plan_out}\n{do2_blocks}\n\nMemory:\n{mem_for_do or '(none)'}"
            reply2 = ''
            do2_tools_text = ''
            if do_spec.mode == PhaseLlmMode.skip:
                reply2 = assemble_plan_skip_do_draft(plan2_out or plan_out or '', plan2_tools_text or '')
                trace.append({'step': PDCAPhase.do.value, 'skipped': True, 'mode': PhaseLlmMode.skip.value, 'after_check_retry': True, 'skip_do_draft_chars': len(reply2 or '')})
            else:
                (reply2, do2_tools_text, do2_tool_results, _de2) = self._phase_react_loop(PDCAPhase.do.value, do_sys, do2_user, ctx, gather_counters, trace)
                accumulated_tick_tool_results.extend(do2_tool_results)
            if reply2.strip():
                final_text = reply2
            if do2_tools_text:
                trace.append({'step': 'do_retry_tool_observations', 'chars': len(do2_tools_text)})
        mandatory_notice = ''
        snap_gap = ctx.payload.get('tool_router_snapshot')
        if isinstance(snap_gap, dict):
            mans_gap = list(snap_gap.get('mandatory_tool_names') or [])
            if mans_gap:
                (has_m_gap, gap_detail) = mandatory_observation_gap(mans_gap, accumulated_tick_tool_results, plan_trace=trace)
                if has_m_gap:
                    mandatory_notice = format_mandatory_gap_user_notice(gap_detail)
                    _LLM_PDCA_LOG.warning('mandatory_fallback', extra={'mandatory_fallback_reason': ','.join(gap_detail.get('reason_codes') or []), 'mandatory_missing': gap_detail.get('missing'), 'mandatory_failed': gap_detail.get('failed'), 'mandatory_permission_denied_tools': gap_detail.get('permission_denied_tools'), 'mandatory_gather_budget_limited': gap_detail.get('gather_budget_limited'), 'tool_router_threshold_revision': snap_gap.get('threshold_revision'), 'tool_router_registry_revision': snap_gap.get('tool_registry_revision')})
                    trace.append({'step': 'mandatory_observation_gap', **gap_detail})
                    ctx.payload['mandatory_observation_gap'] = gap_detail
        self._tick_hooks.on_before_phase(ThinkingPhaseId.action, ctx)
        tool_blocks_check = ''
        act_user = f'User message:\n{user_msg}\n\nDraft reply:\n{final_text}{tool_blocks_check}\n\nPolish for final user-facing text.'
        act_sys = _phase_system_core(base_system, PDCAPhase.act.value, merged_phases, slim_followup)
        t_act = time.perf_counter()
        (act_out, act_entry) = self._call_llm(PDCAPhase.act.value, act_sys, act_user, ctx)
        _trace_phase_timing(trace, scope='llm', phase=PDCAPhase.act.value, elapsed_ms=(time.perf_counter() - t_act) * 1000.0)
        if not act_entry.get('skipped') and (act_out or '').strip():
            final_text = act_out.strip()
        act_entry['step'] = PDCAPhase.act.value
        act_entry['final_reply'] = final_text
        trace.append(act_entry)
        self._tick_hooks.on_after_phase(ThinkingPhaseId.action, ctx, phase_llm_output=act_out or '', skipped=bool(act_entry.get('skipped')))
        if user_msg and (not (final_text or '').strip()):
            final_text = _resolve_npc_agent_empty_reply_message(self._cfg)
            act_entry['final_reply'] = final_text
            trace.append({'step': 'empty_reply_fallback', 'user_message_len': len(user_msg)})
        if mandatory_notice:
            final_text = (final_text or '').rstrip() + mandatory_notice
            act_entry['final_reply'] = final_text
        self._memory.finish_run(run_id, PDCAPhase.act.value, trace, 'success' if ok else 'failed', graph_ops_summary={'reply_excerpt': (final_text or '')[:500]})
        self._memory.append_raw('audit', {'framework': self.framework_id, 'run_id': str(run_id), 'ok': ok})
        self._tick_hooks.on_before_phase(ThinkingPhaseId.post, ctx)
        self._tick_hooks.on_after_phase(ThinkingPhaseId.post, ctx, phase_llm_output=final_text, skipped=False)
        return FrameworkRunResult(ok=ok, message=final_text, final_phase=PDCAPhase.act.value)

def _tool_calls_from_text(text: str) -> List[ToolCall]:
    """Parse JSON ``{"commands": [...]}`` text and convert to neutral ToolCalls."""
    plan: ToolInvocationPlan = parse_tool_invocation_plan_from_text(text or '')
    out: List[ToolCall] = []
    for (i, (name, args)) in enumerate(plan.commands):
        out.append(ToolCall.new(name, args))
    return out

def _render_turns_as_text(turns: Sequence[ConversationTurn]) -> str:
    """Flatten a neutral turn list to a plain-text user segment.

    Used when the client does not support native tool_use — the JSON
    channel only accepts a single string for the ``user`` argument to
    ``complete``. Tool observation turns are serialized with the legacy
    ``Tool observations`` block so existing providers work unchanged.
    """
    parts: List[str] = []
    for t in turns:
        if isinstance(t, TextTurn):
            parts.append(t.text or '')
        elif isinstance(t, AssistantToolUseTurn):
            block = assistant_tool_use_turn_as_text_block(t)
            if block:
                parts.append(block)
        elif isinstance(t, ToolResultsTurn):
            block = tool_results_turn_as_text_block(t)
            if block:
                parts.append('Tool observations:\n' + block)
    return '\n\n'.join((p for p in parts if p.strip()))

def _gather_cap_reason(gather_entries: Sequence[Dict[str, Any]]) -> str:
    for entry in gather_entries:
        if entry.get('step') == 'tool_cap':
            return str(entry.get('detail') or 'budget_exhausted')
    return 'budget_exhausted'


def _skip_tool_result(call: ToolCall, reason: str, *, round_idx: int, index: int) -> ToolResult:
    call_id = (call.id or '').strip() or f'call_{round_idx}_{index}'
    return ToolResult(id=call_id, name=call.name, ok=False, text=f'[tool skipped: {reason}; not executed]')


def build_round_tool_results(*, calls: Sequence[ToolCall], executed_call_count: int, exec_entries: Sequence[Dict[str, Any]], obs_text: str, gather_entries: Sequence[Dict[str, Any]], round_idx: int, pre_truncated_reason: str='phase_max_commands') -> List[ToolResult]:
    """Build one :class:`ToolResult` per ``ToolCall``, preserving call order."""
    cap_reason = _gather_cap_reason(gather_entries)
    results: List[ToolResult] = []
    exec_n = len(exec_entries)
    for (i, call) in enumerate(calls):
        if i < executed_call_count and i < exec_n:
            results.append(ToolResult(id=(call.id or '').strip() or f'call_{round_idx}_{i}', name=call.name, ok=bool(exec_entries[i].get('success', False)), text=_extract_observation_text_for_call(obs_text, i + 1)))
        elif i < executed_call_count:
            results.append(_skip_tool_result(call, cap_reason, round_idx=round_idx, index=i))
        else:
            results.append(_skip_tool_result(call, pre_truncated_reason, round_idx=round_idx, index=i))
    return results


def _extract_observation_text_for_call(full_text: str, index: int) -> str:
    """Slice a single observation block out of the concatenated gather text.

    ``gather_tool_observations`` emits one block per call delimited by
    ``--- tool_observation begin ---`` / ``--- tool_observation end ---``
    and numbered ``[<i>]``. For the ReAct loop we need each call's text
    attached to its ``ToolResult`` id, so we re-slice by index.
    """
    if not full_text:
        return ''
    marker = f'[{index}]'
    start = full_text.find(marker)
    if start < 0:
        return full_text
    end_marker = '--- tool_observation end ---'
    end = full_text.find(end_marker, start)
    if end < 0:
        return full_text[start:]
    return full_text[start:end + len(end_marker)]

def _assemble_plan_user(*, user_msg: str, memory: str, world_snapshot: str, tool_manifest_text: str, intent_hint: Optional[Dict[str, Any]]=None, recent_conversation: Optional[str]=None, tool_router_hint: Optional[str]=None) -> str:
    """Build the first Plan user turn.

    Order (cache-friendly: slower-changing blocks before the user line):

    1. Tools available (manifest; stable for a given worker).
    2. World snapshot (caller identity, location, installed worlds).
    3. Intent hint when present (pre-classifier label, confidence, source).
    4. Recent conversation (STM) when provided.
    5. Retrieved memory (LTM or empty).
    6. Tool router hint when provided.
    7. User message.
    """
    segments: List[str] = []
    if tool_manifest_text:
        segments.append(f'Tools available:\n{tool_manifest_text}')
    if world_snapshot:
        segments.append(f'World snapshot:\n{world_snapshot}')
    if intent_hint:
        segments.append(f"Intent hint (runtime pre-classifier):\n  intent: {intent_hint.get('intent') or 'informational'}\n  confidence: {intent_hint.get('confidence')}\n  source: {intent_hint.get('source') or 'unknown'}\n  reason_tokens: {intent_hint.get('reason_tokens') or []}")
    if recent_conversation:
        segments.append(f'Recent conversation:\n{recent_conversation}')
    segments.append(f"Retrieved memory (may be empty):\n{memory or '(none)'}")
    if tool_router_hint:
        segments.append(tool_router_hint)
    segments.append(f'User message:\n{user_msg}')
    return '\n\n'.join(segments)


def _tool_chain_completion_criteria_text(mandatory_tools: Sequence[str]) -> str:
    """Structured completion criteria for multi-tool routing chains.

    Keep this compact so it can be safely appended to Plan/Check user turns.
    """
    tools = [str(t).strip() for t in mandatory_tools if str(t).strip()]
    if not tools:
        return ''
    joined = ', '.join(tools)
    return (
        'Tool-chain completion criteria:\n'
        f'1) Mandatory chain tools must be observed in this tick: {joined}\n'
        '2) If a mandatory tool has no successful ToolObservation, request retry and do not finalize.\n'
        '3) Final answer must be grounded in observed tool output for chain-dependent claims.'
    )
