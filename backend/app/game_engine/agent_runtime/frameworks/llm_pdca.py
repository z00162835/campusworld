from __future__ import annotations
import logging
import re
import time
import uuid
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Sequence, Tuple
from app.commands.base import CommandContext
from app.commands.registry import command_registry
from app.core.config_manager import get_config
from app.core.settings import AgentLlmServiceConfig, PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext, FrameworkRunResult, ThinkingFramework
from app.game_engine.agent_runtime.frameworks.pdca import PDCAPhase
from app.game_engine.agent_runtime.intent_classifier_interface import IntentClassifier, RuleFallbackIntentClassifier, classify_intent
from app.game_engine.agent_runtime.llm_client import AGENT_EXTRA_KEYS_MERGED_INTO_LLM_CALL_SPEC, LlmCallSpec, LlmClient, StubLlmClient, complete, complete_with_tools, supports_tools
from app.game_engine.agent_runtime.llm_providers.http_utils import LlmRequestCancelled
from app.game_engine.agent_runtime.llm_streaming import complete_stream as llm_complete_stream
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
from app.game_engine.agent_runtime.skills import SkillInjection, get_default_skill_registry
from app.game_engine.agent_runtime.policy import PolicyContext, PolicyEngine
from app.game_engine.agent_runtime.policy.check_points import CheckPoint
from app.game_engine.agent_runtime.prompt_fingerprint import compute_npc_prompt_fingerprint
from app.game_engine.agent_runtime.agent_llm_extra import parse_bool_extra
from app.game_engine.agent_runtime.state_machine import (
    StateDef,
    StateExecutionResult,
    StateMachine,
    StateMachineSnapshot,
    TransitionContext,
    build_pdca_state_machine,
)
from app.game_engine.agent_runtime.state_machine.react_turn_schema import emit_structured_turn
from app.game_engine.agent_runtime.agent_loop import (
    AgentLoopConfig,
    DraftCompletenessVerdict,
    build_draft_retry_user_text,
    build_filtered_tool_continuation_turns,
    detect_pending_tool_work,
    should_exit_react_round,
)
from app.game_engine.agent_runtime.agent_loop.draft_gate import assess_draft_completeness_with_budget, is_draft_streamable
from app.game_engine.agent_runtime.agent_loop.signals import DraftReasonContext
_DEFAULT_NPC_AGENT_EMPTY_REPLY = '抱歉，我没有能力处理此问题。你可以换一个问题。'

_INTERNAL_PHASE_TAG_RE = re.compile(r'^\s*\[(?:plan|do|check|act|react|thought|thinking|reasoning)\]\s*', re.IGNORECASE)

def _strip_internal_markers(text: str) -> str:
    """Remove internal reasoning/phase tags that must never reach the user.

    Thin PDCA returns Plan output verbatim when Do is skipped; if Plan's ReAct
    loop terminates with an internal note (e.g. ``[plan] The output was
    truncated. Let me try...``), strip those tagged lines so only user-facing
    prose remains. When everything was internal, an empty string is returned
    and the (non-skipped) Check phase is expected to catch the incomplete
    draft and trigger a re-plan.
    """
    if not text:
        return ''
    kept = []
    for line in text.splitlines():
        if _INTERNAL_PHASE_TAG_RE.match(line):
            continue
        kept.append(line)
    return '\n'.join(kept).strip()

def assemble_plan_skip_do_draft(plan_out: str, _plan_tools_text: str) -> str:
    """Text shown to the user when the Do phase LLM is skipped.

    Tool observations are omitted here; they are appended only to the Check-phase
    prompt for grounding. ``_plan_tools_text`` remains on the signature for stable
    call sites and tests. Internal phase/reasoning tags (e.g. ``[plan] ...``) are
    stripped so Plan's working notes never leak as the user-facing reply.
    """
    return _strip_internal_markers(plan_out)
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
    """Apply ``schema_subset`` allowlist only for Plan-phase tool calls.

    The subset is emitted for the Plan LLM; Do / Check keep the full resolved
    surface so execution and guardrails still see every allowed command on the
    node surface.
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


_POLICY_FALLBACK_PREAMBLE = (
    "\n\n--- Policy Fallback ---\n"
    "The runtime enforces deterministic behavioural gates at the tool-call and "
    "skill-activation check-points. High side-effect writes and restricted data "
    "classifications are blocked automatically. When active skills constrain "
    "tool groups, commands outside those groups are denied. Treat this text as "
    "a backup safety net; the authoritative enforcement happens in the engine, "
    "not in this prompt."
)


def _prompt_fallback_enabled() -> bool:
    """Read ``policy.enable_prompt_fallback`` from config; default True."""
    try:
        from app.core.config_manager import get_config
        return bool(get_config().get_nested('policy', 'enable_prompt_fallback', default=True))
    except Exception:  # noqa: BLE001 — config may be unavailable in unit tests
        return True


def _append_policy_fallback(base_system: str) -> str:
    if not base_system:
        return base_system
    return base_system + _POLICY_FALLBACK_PREAMBLE

def _serialize_tool_calls_for_entry(calls: Sequence[ToolCall]) -> List[Dict[str, Any]]:
    return [{'id': c.id, 'name': c.name, 'args': list(c.args)} for c in calls]


def _tool_calls_from_entry(raw: Any) -> List[ToolCall]:
    if not isinstance(raw, list):
        return []
    out: List[ToolCall] = []
    for item in raw:
        if isinstance(item, ToolCall):
            out.append(item)
        elif isinstance(item, dict):
            out.append(ToolCall(id=str(item.get('id') or ''), name=str(item.get('name') or ''), args=[str(a) for a in (item.get('args') or [])]))
    return out


def _draft_reason_context(ctx: FrameworkRunContext) -> DraftReasonContext:
    hint = ctx.payload.get('intent_hint')
    if isinstance(hint, dict):
        return DraftReasonContext(intent_hint=dict(hint))
    return DraftReasonContext()


def _user_message_from_ctx(ctx: FrameworkRunContext) -> str:
    return str(ctx.payload.get('message') or ctx.payload.get('text') or '').strip()


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
    """Append a small structured row for tick latency analysis."""
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


@dataclass
class _PdcaTickBag:
    """Mutable per-tick workspace for the PDCA state-machine driver."""

    user_msg: str
    mem_for_do: str
    plan_user: str
    plan_sys: str
    do_sys: str
    check_sys: str
    act_sys: str
    do_spec: Any
    act_spec: Any
    chain_criteria_text: str
    merged_phases: Dict[str, str]
    base_system: str
    slim_followup: Optional[str]
    plan_out: str = ''
    plan_tools_text: str = ''
    reply: str = ''
    do_tools_text: str = ''
    check_out: str = ''
    final_text: str = ''
    check_ok: bool = True
    check_skipped: bool = False
    retry_tools: Optional[List[str]] = None
    retry_event: Optional[str] = None
    replan_guardrail_hint: Optional[str] = None
    accumulated_tick_tool_results: List[ToolResult] = field(default_factory=list)
    cancelled: bool = False


class LlmPDCAFramework(ThinkingFramework):
    """PDCA with LLM calls and a ReAct tool loop per phase.

    Behaviour highlights:

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

    def __init__(
        self,
        memory: MemoryPort,
        llm_config: AgentLlmServiceConfig,
        *,
        instance_phase_llm: Dict[str, PhaseLlmPhaseConfig],
        instance_mode_models: Dict[str, str],
        llm: Optional[LlmClient] = None,
        tools: Optional[ToolExecutor] = None,
        tool_command_context: Optional[CommandContext] = None,
        preauthorized_tool_executor: Optional[PreauthorizedToolExecutor] = None,
        tool_gather_budgets: Optional[ToolGatherBudgets] = None,
        tick_hooks: Optional[AgentTickHooks] = None,
        tool_schemas: Optional[Sequence[ToolSchema]] = None,
        intent_classifier: Optional[IntentClassifier] = None,
        observability: Optional[AgentRuntimeObservability] = None,
        skill_refs: Optional[Sequence[str]] = None,
        skill_injection: Optional[SkillInjection] = None,
        state_machine: Optional[StateMachine] = None,
    ):
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
        self._agent_loop_config = AgentLoopConfig.from_agent_extra(getattr(llm_config, 'extra', None))
        self._skill_refs: Tuple[str, ...] = tuple(str(s).strip() for s in (skill_refs or ()) if str(s).strip())
        if skill_injection is not None:
            self._skill_injection: Optional[SkillInjection] = skill_injection
        elif self._skill_refs:
            self._skill_injection = SkillInjection(registry=get_default_skill_registry())
        else:
            self._skill_injection = None
        self._policy_engine: PolicyEngine = PolicyEngine()
        self._state_machine: StateMachine = state_machine or build_pdca_state_machine()

    @property
    def framework_id(self) -> str:
        return 'PDCA_LLM'

    def _spec_for_phase(self, phase: str, ctx: FrameworkRunContext) -> LlmCallSpec:
        pcfg = merge_phase_config(phase, self._instance_phase_llm, ctx.phase_llm_overrides)
        return to_llm_call_spec(pcfg, mode_models=self._instance_mode_models, default_model=(self._cfg.model or '').strip())

    def _augment_spec_from_ctx(self, spec: LlmCallSpec, ctx: FrameworkRunContext, *, phase: Optional[str] = None) -> LlmCallSpec:
        extra = dict(spec.extra or {})
        if phase is not None:
            fp = compute_npc_prompt_fingerprint(
                world_snapshot=str((ctx.payload or {}).get('world_snapshot') or ''),
                tool_manifest_text=str((ctx.payload or {}).get('tool_manifest_text') or ''),
                user_message=str((ctx.payload or {}).get('message') or ''),
                skill_context_text=str((ctx.payload or {}).get('skill_context_text') or '') or None,
                phase=phase,
            )
            extra['prompt_fingerprint'] = fp
        cm_extra = getattr(self._cfg, 'extra', None) or {}
        if isinstance(cm_extra, dict):
            for key in AGENT_EXTRA_KEYS_MERGED_INTO_LLM_CALL_SPEC:
                if key in cm_extra:
                    extra[key] = cm_extra[key]
        skill_ctx = str((ctx.payload or {}).get('skill_context_text') or '').strip() or None
        if extra != (spec.extra or {}) or skill_ctx != spec.skill_context_text:
            return replace(spec, extra=extra, skill_context_text=skill_ctx)
        return spec

    def _prepare_skill_context(self, ctx: FrameworkRunContext, phase: str, trace: List[Dict[str, Any]]) -> None:
        """Compute this phase's skill-context (L1 manifest + L2 body) and trace activations."""
        if self._skill_injection is None or not self._skill_refs:
            ctx.payload['skill_context_text'] = ''
            ctx.payload['active_skill_context'] = None
            return

        blocked_decisions: dict = {}

        def _before_activate(skill_def, ph: str):
            policy_ctx = PolicyContext(
                check_point=CheckPoint.BEFORE_SKILL_ACTIVATION,
                skill_id=skill_def.name,
                skill_allowed_tool_groups=tuple(skill_def.allowed_tool_groups or ()),
                skill_activation_mode=skill_def.activation_mode,
                skill_allowed_in_react_states=tuple(skill_def.allowed_in_react_states or ()),
                current_react_state=ph,
            )
            decision = self._policy_engine.evaluate(policy_ctx)
            if decision.is_block:
                blocked_decisions[skill_def.name] = decision
                return decision.reason_code
            return None

        result = self._skill_injection.inject(self._skill_refs, phase=phase, before_activate=_before_activate)
        ctx.payload['skill_context_text'] = result.text
        allowed_groups = sorted({group for a in result.activations for group in a.allowed_tool_groups})
        ctx.payload['active_skill_context'] = {
            'active_skill_ids': [a.skill_id for a in result.activations],
            'active_skill_allowed_tool_groups': allowed_groups,
        }
        for a in result.activations:
            trace.append({
                'step': 'skill_activated',
                'skill_id': a.skill_id,
                'phase': phase,
                'states': list(self._skill_refs),
                'category': a.category,
                'definition_hash': a.definition_hash,
            })
        for blocked_def, reason_code in zip(result.blocked, result.blocked_reasons):
            dec = blocked_decisions.get(blocked_def.name)
            if dec is not None:
                from app.game_engine.agent_runtime.execution_gate import _policy_decision_to_trace
                trace_row = _policy_decision_to_trace(dec)
            else:
                trace_row = {
                    'step': 'policy_decision',
                    'check_point': CheckPoint.BEFORE_SKILL_ACTIVATION,
                    'decision': 'deny',
                    'reason_code': reason_code,
                    'detector': None,
                    'runtime_action': 'block',
                    'evidence': {},
                }
            evidence = dict(trace_row.get('evidence') or {})
            evidence.setdefault('skill_id', blocked_def.name)
            evidence.setdefault('phase', phase)
            trace_row['evidence'] = evidence
            trace_row['phase'] = phase
            trace_row['skill_id'] = blocked_def.name
            trace.append(trace_row)

    def _effective_tool_schemas(self, ctx: FrameworkRunContext, *, pdca_phase: str) -> List[ToolSchema]:
        """Narrow tool schemas for Plan only when payload carries an allowlist."""
        return resolve_tool_schemas_for_pdca_phase(self._tool_schemas, ctx.payload, pdca_phase)

    def _resolve_presentation_anchor_phase(self, ctx: FrameworkRunContext) -> str:
        """Phase whose output is user-visible ``final_text`` (Act > Do > Plan; Check never)."""
        act_spec = self._augment_spec_from_ctx(self._spec_for_phase(PDCAPhase.act.value, ctx), ctx)
        if act_spec.mode != PhaseLlmMode.skip:
            return PDCAPhase.act.value
        do_spec = self._augment_spec_from_ctx(self._spec_for_phase(PDCAPhase.do.value, ctx), ctx)
        if do_spec.mode != PhaseLlmMode.skip:
            return PDCAPhase.do.value
        return PDCAPhase.plan.value

    def _bind_presentation_anchor(self, ctx: FrameworkRunContext) -> None:
        ctx.presentation_anchor_phase = self._resolve_presentation_anchor_phase(ctx)

    def _is_presentation_safe_prose(self, text: str, calls: Sequence[ToolCall], ctx: FrameworkRunContext) -> bool:
        """Exclude tool JSON, deferral-only interim prose, and incomplete drafts from the user-visible stream."""
        if calls:
            return False
        stripped = (text or '').strip()
        if not stripped:
            return False
        if parse_tool_invocation_plan_from_text(stripped).commands:
            return False
        accumulated = ctx.payload.get('_accumulated_tool_results')
        tool_results: List[ToolResult] = list(accumulated) if isinstance(accumulated, list) else []
        return is_draft_streamable(
            draft_text=text,
            tool_results=tool_results,
            user_message=_user_message_from_ctx(ctx),
            config=self._agent_loop_config,
            reason_context=_draft_reason_context(ctx),
        )

    def _require_structured_turn(self, ctx: FrameworkRunContext) -> bool:
        """Opt-in structured turn (tool-as-schema / JSON). Default off."""
        if parse_bool_extra(ctx.payload, 'require_structured_turn', default=False):
            return True
        return parse_bool_extra(getattr(self._cfg, 'extra', None), 'require_structured_turn', default=False)

    @staticmethod
    def _should_stream_user_prose(ctx: FrameworkRunContext, phase: str, *, stream_prose: bool = False) -> bool:
        """Stream only prose from the tick's presentation anchor (matches ``final_text`` source)."""
        if ctx.user_visible_stream is None:
            return False
        # Structured JSON turns are not incrementally streamable.
        if parse_bool_extra(ctx.payload, 'require_structured_turn', default=False):
            return False
        if phase == PDCAPhase.check.value:
            return False
        anchor = (ctx.presentation_anchor_phase or '').strip()
        if not anchor or phase != anchor:
            return False
        if anchor == PDCAPhase.act.value:
            return True
        return stream_prose

    @staticmethod
    def _tick_cancelled(ctx: FrameworkRunContext) -> bool:
        check = ctx.stream_cancel_check
        return bool(check and check())

    def _finish_tick_fail(
        self,
        run_id: uuid.UUID,
        trace: List[Dict[str, Any]],
        *,
        correlation: Any,
        error_code: str,
        message: str = '',
        graph_ops_summary: Optional[Dict[str, Any]] = None,
    ) -> FrameworkRunResult:
        """Finish a failed tick while preserving its machine-readable reason."""
        if error_code == 'cancelled' and not any(e.get('step') == 'tick_cancelled' for e in trace):
            trace.append({'step': 'tick_cancelled'})
        summary = dict(graph_ops_summary or {})
        summary.setdefault('fail', True)
        summary.setdefault('error_code', error_code)
        mem_status = 'cancelled' if error_code == 'cancelled' else 'failed'
        self._memory.finish_run(
            run_id,
            'fail',
            trace,
            mem_status,
            graph_ops_summary=summary,
        )
        self._memory.append_raw(
            'audit',
            {
                'framework': self.framework_id,
                'run_id': str(run_id),
                'ok': False,
                'final_phase': 'fail',
                'error_code': error_code,
            },
        )
        return FrameworkRunResult(ok=False, message=message or '', final_phase='fail', error_code=error_code)

    def _finish_tick_cancelled(
        self,
        run_id: uuid.UUID,
        trace: List[Dict[str, Any]],
        *,
        correlation: Any,
    ) -> FrameworkRunResult:
        """Back-compat alias — cancel aborts via the ``fail`` terminal."""
        return self._finish_tick_fail(
            run_id,
            trace,
            correlation=correlation,
            error_code='cancelled',
            message='',
            graph_ops_summary={'cancelled': True},
        )

    def _detect_tick_emit_deferral(
        self,
        ctx: FrameworkRunContext,
        bag: '_PdcaTickBag',
        trace: List[Dict[str, Any]],
        user_msg: str,
    ) -> bool:
        """At the act anchor, authoritatively decide draft_incomplete from the final draft.

        A deferral-only final draft with no grounding observations routes the
        tick to fail. A complete (non-empty, non-deferral) final draft clears any
        stale plan/do soft signal so the tick can succeed and the post-loop
        mandatory-gap notice can still apply; detection is anchored
        at act, not plan/do). An empty final draft preserves an existing
        plan/do signal rather than silently succeeding.
        """
        from app.game_engine.agent_runtime.agent_loop.draft_gate import has_successful_grounding_obs, is_deferral_prose
        final_text = bag.final_text or bag.reply
        final_stripped = (final_text or '').strip()
        if (
            user_msg
            and final_stripped
            and is_deferral_prose(final_text, config=self._agent_loop_config)
            and not has_successful_grounding_obs(bag.accumulated_tick_tool_results)
        ):
            _LLM_PDCA_LOG.warning(
                'draft_incomplete_detected anchor_phase=%s draft_chars=%s',
                ctx.presentation_anchor_phase, len(final_stripped),
            )
            trace.append({
                'step': 'draft_incomplete_detected',
                'anchor_phase': ctx.presentation_anchor_phase,
                'reason_codes': ['tick_emit_deferral'],
                'draft_chars': len(final_stripped),
            })
            ctx.payload['_draft_incomplete'] = True
            return True
        if final_stripped:
            ctx.payload.pop('_draft_incomplete', None)
            return False
        return bool(ctx.payload.get('_draft_incomplete'))

    def _evaluate_before_final_answer(
        self,
        ctx: FrameworkRunContext,
        bag: '_PdcaTickBag',
        trace: List[Dict[str, Any]],
    ) -> None:
        """Evaluate the ``before_final_answer`` gate check_point (P4, non-streaming).

        Invoked at the act anchor before ``_detect_tick_emit_deferral``. Under
        default config (``enable_pattern_match_detector=false``) the gate domain
        registers no ``pattern_match`` detector, so ``evaluate`` returns ``allow``
        and this is a no-op (byte-equivalent). On a blocking decision, clear the
        final draft and mark ``_draft_incomplete`` so the tick routes to
        ``fail_fallback`` (v1 synchronous degrade of ``require_approval``).

        Streaming ticks are not intercepted mid-stream (F18 §4.1); for streamed
        drafts the text has already been flushed, but the block still routes the
        tick to fail and records the policy decision for audit.
        """
        draft_text = bag.final_text or bag.reply or ''
        policy_ctx = PolicyContext(
            check_point=CheckPoint.BEFORE_FINAL_ANSWER,
            user_message=bag.user_msg or '',
            draft_text=draft_text,
            payload=ctx.payload,
        )
        decision = self._policy_engine.evaluate(policy_ctx)
        if decision is None or decision.is_allow:
            return
        # Non-allow decision: record trace and route to fail_fallback.
        from app.game_engine.agent_runtime.execution_gate import _policy_decision_to_trace
        trace.append(_policy_decision_to_trace(decision, step='policy_decision'))
        # Clear the draft and mark incomplete so act→fail / fail_fallback fires.
        bag.final_text = ''
        bag.reply = ''
        ctx.payload['_draft_incomplete'] = True
        ctx.payload['_policy_block_final_answer'] = decision.reason_code

    # ------------------------------------------------------------------
    # Quality/stop driver wiring (byte-equiv under default config).
    # ------------------------------------------------------------------

    @staticmethod
    def _update_tool_failure_counter(ctx: FrameworkRunContext, round_results: List[Any]) -> None:
        """Track consecutive ToolResult.ok=False; any success resets to 0."""
        if not round_results:
            return
        current = int(ctx.payload.get('_consecutive_tool_failures', 0))
        for r in round_results:
            if getattr(r, 'ok', True):
                current = 0
            else:
                current += 1
        ctx.payload['_consecutive_tool_failures'] = current

    @staticmethod
    def _append_obs_signatures(ctx: FrameworkRunContext, round_results: List[Any]) -> None:
        """Append per-result obs signatures for stagnation detection."""
        if not round_results:
            return
        sigs: List[str] = ctx.payload.get('_recent_obs_signatures')
        if not isinstance(sigs, list):
            sigs = []
        for r in round_results:
            name = getattr(r, 'name', '') or ''
            text = getattr(r, 'text', '') or ''
            sigs.append(f'{name}:{hash(text)}')
        ctx.payload['_recent_obs_signatures'] = sigs

    def _build_quality_tick_state(
        self,
        *,
        check_point: str,
        ctx: FrameworkRunContext,
        bag: '_PdcaTickBag',
        snapshot: Optional['StateMachineSnapshot'],
        state_id: str,
        trace: List[Dict[str, Any]],
        extra: Optional[Dict[str, Any]] = None,
        gather_counters: Optional['ToolGatherCounters'] = None,
    ) -> Dict[str, Any]:
        """Build the tick_state dict consumed by quality-domain evaluators.

        Under default config (all gates off) only minimal fields are populated
        so every evaluator returns None → no trace row, no control-flow override
        (byte-equivalent). Gate flags and heavy fields (agent_loop_config,
        success_criteria, react_turn) are only populated when their config gate
        is on. ``snapshot`` may be None (per_react_round path); turn/replan
        counts then fall back to values stashed on ctx.payload by the main loop.
        """
        qcfg = self._policy_engine.config.quality
        turn_count = snapshot.turn_count if snapshot is not None else int(ctx.payload.get('_snapshot_turn_count', 0))
        replan_count = snapshot.replan_count if snapshot is not None else int(ctx.payload.get('_snapshot_replan_count', 0))
        ts: Dict[str, Any] = {
            'current_state': state_id,
            'turn_count': turn_count,
            'replan_count': replan_count,
            'draft_text': bag.final_text or bag.reply or '',
            'tool_results': list(bag.accumulated_tick_tool_results),
            'user_message': bag.user_msg or '',
            'consecutive_tool_failures': int(ctx.payload.get('_consecutive_tool_failures', 0)),
            'recent_signatures': list(ctx.payload.get('_recent_obs_signatures') or []),
            # per_react_round verdict passed up for after_state_execute secondary
            # confirmation. None under default config (no react_turn).
            'react_round_decision': ctx.payload.get('react_round_decision'),
            # detect_check_replan inputs routed through stop_evaluator.
            # check_out/check_skipped are check-state specific; tool_router_snapshot
            # and plan_trace feed mandatory_observation_gap.
            'check_out': bag.check_out or '',
            'check_skipped': bool(bag.check_skipped),
            'tool_router_snapshot': ctx.payload.get('tool_router_snapshot'),
            'plan_trace': trace,
        }
        if qcfg.enable_stop_dimensions:
            ts['enable_stop_dimensions'] = True
            ts['max_iterations'] = qcfg.max_iterations
            ts['max_consecutive_tool_failures'] = qcfg.max_consecutive_tool_failures
            ts['stagnation_window'] = qcfg.stagnation_window
            # H7: stop_evaluator's stagnation check consumes the cycle-window
            # multiplier (cycle window = multiplier × stagnation_window). Inject
            # here so the control-flow-driving consumer honors config.
            ts['stagnation_cycle_window_multiplier'] = qcfg.stagnation_cycle_window_multiplier
            # Surface ToolGatherBudgets exhaustion to stop_evaluator as the
            # budget_exceeded condition. Phase-level caps stay inline in the
            # react loop.
            ts['commands_run'] = int(getattr(gather_counters, 'commands_run', 0))
            ts['max_commands_per_tick'] = int(getattr(self._tool_budgets, 'max_commands_per_tick', 0))
            ts['observation_chars'] = int(getattr(gather_counters, 'observation_chars', 0))
            ts['max_chars_observations_per_tick'] = int(
                getattr(self._tool_budgets, 'max_chars_observations_per_tick', 0)
            )
            ts['enable_budget_hard_fail'] = bool(qcfg.enable_budget_hard_fail)
        if qcfg.final_success_drive_mode in ("shadow", "enforce"):
            ts['final_success_drive_mode'] = qcfg.final_success_drive_mode
            ts['agent_loop_config'] = self._agent_loop_config
            ts['reason_context'] = _draft_reason_context(ctx)
            ts['draft_incomplete'] = bool(ctx.payload.get('_draft_incomplete'))
            # S2/S3 hard_gate config (default-off, byte-equiv): surfaced to
            # final_success_evaluator via tick_state.
            ts['enable_obs_grounded_claims_gate'] = qcfg.enable_obs_grounded_claims_gate
            ts['obs_grounded_gte'] = qcfg.obs_grounded_gte
            ts['enable_success_criteria_gate'] = qcfg.enable_success_criteria_gate
            # S3 / react_turn_success N-hit rule threshold (read by final_success
            # S3 gate and react_turn_success_evaluator).
            ts['react_turn_min_criteria_hits'] = qcfg.react_turn_min_criteria_hits
            # success_criteria is needed by the S3 gate; populate it here when the
            # gate is enabled even if quality_score is off.
            if qcfg.enable_success_criteria_gate and 'success_criteria' not in ts:
                ts['success_criteria'] = list(ctx.payload.get('_success_criteria') or [])
        if qcfg.enable_quality_score:
            ts['enable_quality_score'] = True
            ts['success_criteria'] = list(ctx.payload.get('_success_criteria') or [])
            ts['stagnation_window'] = qcfg.stagnation_window
            # react_turn_success_evaluator (per_react_round) reads the same N-hit
            # threshold; surface it whenever quality scoring is on.
            if 'react_turn_min_criteria_hits' not in ts:
                ts['react_turn_min_criteria_hits'] = qcfg.react_turn_min_criteria_hits
            # H6/H7/H8: configurable semantic weights, cycle-window multiplier,
            # and token min length — surfaced to compute_quality_score and the
            # S2/S3 gates via tick_state.
            ts['semantic_weight_grounding'] = qcfg.semantic_weight_grounding
            ts['semantic_weight_criteria'] = qcfg.semantic_weight_criteria
            ts['semantic_weight_progress'] = qcfg.semantic_weight_progress
            ts['stagnation_cycle_window_multiplier'] = qcfg.stagnation_cycle_window_multiplier
            ts['token_min_length'] = qcfg.token_min_length
        # H8: token_min_length is consumed by quality_score_evaluator (under
        # enable_quality_score), final_success_evaluator S2/S3 gates (under
        # final_success_drive_mode), and react_turn_success_evaluator (under
        # require_structured_turn). Inject unconditionally as a lightweight
        # scalar so react_turn_success_evaluator honors config even when the
        # other two gates are off. No evaluator reads it when its own gate is
        # off, so this is byte-equivalent.
        if 'token_min_length' not in ts:
            ts['token_min_length'] = qcfg.token_min_length
        # react_turn_min_criteria_hits is consumed by final_success_evaluator
        # S3 gate (under final_success_drive_mode) and react_turn_success_evaluator
        # (under require_structured_turn). Inject unconditionally so the
        # per_react_round consumer honors config even when final_success_drive_mode
        # and enable_quality_score are off. Byte-equivalent (default 1).
        if 'react_turn_min_criteria_hits' not in ts:
            ts['react_turn_min_criteria_hits'] = qcfg.react_turn_min_criteria_hits
        if extra:
            ts.update(extra)
        return ts

    def _evaluate_quality_check_point(
        self,
        check_point: str,
        *,
        ctx: FrameworkRunContext,
        bag: '_PdcaTickBag',
        snapshot: Optional['StateMachineSnapshot'],
        state_id: str,
        trace: List[Dict[str, Any]],
        extra: Optional[Dict[str, Any]] = None,
        gather_counters: Optional['ToolGatherCounters'] = None,
    ) -> Optional['PolicyDecision']:
        """Call PolicyEngine.evaluate at a quality check_point and record a
        ``quality_decision`` trace row when the decision is non-allow or carries
        a quality_score. Returns the decision (None-safe)."""
        ts = self._build_quality_tick_state(
            check_point=check_point, ctx=ctx, bag=bag, snapshot=snapshot,
            state_id=state_id, trace=trace, extra=extra, gather_counters=gather_counters,
        )
        policy_ctx = PolicyContext(check_point=check_point, extra={'tick_state': ts}, payload=ctx.payload)
        decision = self._policy_engine.evaluate(policy_ctx)
        if decision is None:
            return None
        # Record a trace row for any non-trivial decision (anything other than
        # a plain 'allow') or when a quality_score is attached. Under default
        # config evaluators return None/allow with no score → no row → byte-equiv.
        if decision.decision != 'allow' or decision.quality_score is not None:
            from app.game_engine.agent_runtime.execution_gate import _policy_decision_to_trace
            trace.append(_policy_decision_to_trace(decision, step='quality_decision'))
        return decision

    def _tick_budget_remaining(self, counters: 'ToolGatherCounters') -> bool:
        return (
            counters.commands_run < self._tool_budgets.max_commands_per_tick
            and counters.observation_chars < self._tool_budgets.max_chars_observations_per_tick
        )

    @staticmethod
    def _mark_stop_fail(ctx: FrameworkRunContext, reason_code: str) -> None:
        ctx.payload['_stop_fail'] = True
        ctx.payload.setdefault('_stop_fail_reason', reason_code)

    def _apply_final_success_drive(
        self,
        decision: Optional['PolicyDecision'],
        ctx: FrameworkRunContext,
        trace: List[Dict[str, Any]],
        *,
        bag: '_PdcaTickBag',
        snapshot: Optional['StateMachineSnapshot'],
        sm: 'StateMachine',
        gather_counters: 'ToolGatherCounters',
    ) -> None:
        """Apply the ``before_terminal`` final_success verdict.

        - ``shadow``: record a ``final_success_divergence`` trace row when the
          evaluator's verdict disagrees with the ``_detect_tick_emit_deferral``
          result (``ctx.payload['_draft_incomplete']``). The deferral result stays
          authoritative (no override).
        - ``enforce``: let the verdict drive control flow —
          ``final_success`` clears ``_draft_incomplete`` (→ act→end success);
          ``fail`` sets it (→ act→fail); ``replan`` (retry_loop) drives an outer
          replan via ``act→plan on_event=draft_retry``, counted by
          ``replan_count``/``max_replans``. Over-limit replan → ``runtime.stop_fail``
          (mirrors stagnation over-limit). The driver signals replan by setting
          ``ctx.payload['_draft_retry_event']``; the call site translates it to
          ``event='draft_retry'`` for ``sm.next``. When the evaluator returns
          ``None`` (e.g. no config) or raised (engine safety net returned allow),
          the deferral result stands.
        """
        if decision is None:
            return
        ev = decision.evidence or {}
        drive_mode = str(ev.get('drive_mode') or 'off').strip().lower()
        if drive_mode not in ('shadow', 'enforce'):
            return
        verdict = ev.get('verdict')
        deferral_incomplete = bool(ctx.payload.get('_draft_incomplete'))
        # Map evaluator verdict to the draft_incomplete value it would enforce.
        if decision.decision == 'final_success':
            would_enforce = False
        elif decision.decision == 'fail':
            would_enforce = True
        elif decision.decision == 'replan':
            would_enforce = None
        else:
            return
        # Divergence: a real disagreement on the pass/fail boundary.
        divergent = would_enforce is not None and would_enforce != deferral_incomplete
        # retry_loop is a third state the deferral gate can't express — record as
        # informational divergence regardless (surfaces recoverable cases the
        # binary deferral gate misclassifies).
        if would_enforce is None:
            divergent = True
        if divergent:
            trace.append({
                'step': 'final_success_divergence',
                'drive_mode': drive_mode,
                'verdict': verdict,
                'decision': decision.decision,
                'deferral_draft_incomplete': deferral_incomplete,
                'would_enforce_draft_incomplete': would_enforce,
            })
        if drive_mode == 'enforce':
            if would_enforce is not None:
                # final_success / fail: evaluator drives _draft_incomplete.
                if would_enforce:
                    ctx.payload['_draft_incomplete'] = True
                else:
                    ctx.payload.pop('_draft_incomplete', None)
            else:
                # A retry is valid only when the workflow can consume the event
                # and both outer-loop and tool-gather budgets remain.
                replan_count = snapshot.replan_count if snapshot is not None else 0
                budget_remaining = self._tick_budget_remaining(gather_counters)
                retry_ctx = TransitionContext(
                    snapshot=snapshot or StateMachineSnapshot(current_state=PDCAPhase.act.value),
                    runtime={
                        'budget_remaining': budget_remaining,
                        'cancelled': False,
                        'draft_incomplete': False,
                        'stop_fail': False,
                    },
                    event='draft_retry',
                )
                retry_transition_declared = any(
                    tr.from_state in (PDCAPhase.act.value, '*')
                    and tr.to_state == PDCAPhase.plan.value
                    and tr.on_event == 'draft_retry'
                    for tr in sm.transitions
                )
                try:
                    retry_transition_applicable = (
                        sm.next(PDCAPhase.act.value, retry_ctx) == PDCAPhase.plan.value
                    )
                except LookupError:
                    retry_transition_applicable = False
                if (
                    replan_count < sm.max_replans
                    and budget_remaining
                    and retry_transition_declared
                    and retry_transition_applicable
                ):
                    ctx.payload['_draft_retry_event'] = True
                    ctx.payload.pop('_draft_incomplete', None)
                    prior_draft = (bag.final_text or bag.reply or '').strip()
                    hint = build_draft_retry_user_text()
                    if prior_draft:
                        hint += f'\n\nPrevious rejected draft (reference only):\n{prior_draft[:2000]}'
                    hint += f'\n\nQuality gate reason: {decision.reason_code}.'
                    bag.replan_guardrail_hint = hint
                else:
                    if not retry_transition_declared or (
                        replan_count < sm.max_replans
                        and budget_remaining
                        and not retry_transition_applicable
                    ):
                        reason = 'draft_retry_unsupported'
                    else:
                        reason = 'draft_retry_exhausted'
                    self._mark_stop_fail(ctx, reason)
                    # Keep legacy custom workflows on their draft-incomplete
                    # abort path even when they predate runtime.stop_fail.
                    ctx.payload['_draft_incomplete'] = True
                    trace.append({
                        'step': 'draft_retry_blocked',
                        'reason_code': reason,
                        'replan_count': replan_count,
                        'max_replans': sm.max_replans,
                        'budget_remaining': budget_remaining,
                    })

    @staticmethod
    def _write_user_prose_to_presentation(ctx: FrameworkRunContext, text: str) -> None:
        uvs = ctx.user_visible_stream
        if uvs is None:
            return
        prose = (text or '').strip()
        if prose:
            uvs.write_text(prose)

    def _call_llm(self, phase: str, system: str, user: str, ctx: FrameworkRunContext) -> Tuple[str, Dict[str, Any]]:
        """Single plain-text LLM call (back-compat shape for existing tests)."""
        spec = self._augment_spec_from_ctx(self._spec_for_phase(phase, ctx), ctx, phase=phase)
        cm = get_config()
        if self._observability.should_log_full_chain(cm):
            self._observability.log_llm_call(cm, phase=phase, system=system, user=user, spec=spec, skipped=spec.mode == PhaseLlmMode.skip)
        if spec.mode == PhaseLlmMode.skip:
            return ('', {'step': phase, 'skipped': True, 'mode': spec.mode.value})
        if self._tick_cancelled(ctx):
            return ('', {'step': phase, 'cancelled': True, 'mode': spec.mode.value})
        if self._should_stream_user_prose(ctx, phase):
            uvs = ctx.user_visible_stream
            assert uvs is not None
            out = llm_complete_stream(
                self._llm,
                system=system,
                user=user,
                sink=uvs.coordinator.build_llm_sink(),
                call_spec=spec,
                cancel_check=ctx.stream_cancel_check,
            )
            return (out, {'step': phase, 'llm_output': out, 'mode': spec.mode.value, 'streamed': True})
        try:
            out = complete(self._llm, system=system, user=user, call_spec=spec, cancel_check=ctx.stream_cancel_check)
        except LlmRequestCancelled:
            return ('', {'step': phase, 'cancelled': True, 'mode': spec.mode.value})
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

    def _call_llm_dual_track(self, phase: str, system: str, turns: List[ConversationTurn], ctx: FrameworkRunContext, *, stream_prose: bool=False) -> Tuple[str, List[ToolCall], Dict[str, Any]]:
        """Native ``complete_with_tools`` when available, JSON fallback otherwise.

        Returns ``(text, tool_calls, trace_entry)``. ``tool_calls`` is empty
        when the model chose to answer with prose or when parsing failed.
        """
        spec = self._augment_spec_from_ctx(self._spec_for_phase(phase, ctx), ctx, phase=phase)
        cm = get_config()
        user_text_for_log = _render_turns_as_text(turns)
        if self._observability.should_log_full_chain(cm):
            self._observability.log_llm_call(cm, phase=phase, system=system, user=user_text_for_log, spec=spec, skipped=spec.mode == PhaseLlmMode.skip)
        if spec.mode == PhaseLlmMode.skip:
            return ('', [], {'step': phase, 'skipped': True, 'mode': spec.mode.value})
        if self._tick_cancelled(ctx):
            return ('', [], {'step': phase, 'cancelled': True, 'mode': spec.mode.value})
        if self._require_structured_turn(ctx):
            # Mutually exclusive with native campus-tool tool_use; force emit_turn.
            ctx.payload['require_structured_turn'] = True
            structured = emit_structured_turn(
                self._llm,
                system=system,
                turns=turns,
                call_spec=spec,
                force_tool=True,
                cancel_check=ctx.stream_cancel_check,
            )
            text = structured.text
            calls = list(structured.tool_calls)
            entry: Dict[str, Any] = {
                'step': phase,
                'llm_output': text,
                'mode': spec.mode.value,
                'channel': structured.channel,
                'structured_turn': True,
                'structured_turn_ok': structured.ok,
                'structured_turn_repaired': structured.repaired,
                'structured_turn_degraded': structured.degraded,
                'tool_call_count': len(calls),
                'pre_filter_tool_calls': _serialize_tool_calls_for_entry(calls),
            }
            if structured.turn is not None:
                entry['react_turn'] = structured.turn.model_dump()
            if self._should_stream_user_prose(ctx, phase, stream_prose=stream_prose) and self._is_presentation_safe_prose(text, calls, ctx):
                self._write_user_prose_to_presentation(ctx, text)
                entry['streamed'] = True
            return (text, calls, entry)
        channel = 'text'
        text = ''
        calls: List[ToolCall] = []
        phase_tools = self._effective_tool_schemas(ctx, pdca_phase=phase)
        stream_during_call = self._should_stream_user_prose(ctx, phase, stream_prose=stream_prose) and not (
            stream_prose and phase_tools
        )
        if stream_during_call:
            uvs = ctx.user_visible_stream
            assert uvs is not None
            text = llm_complete_stream(
                self._llm,
                system=system,
                user=user_text_for_log,
                sink=uvs.coordinator.build_llm_sink(),
                call_spec=spec,
                cancel_check=ctx.stream_cancel_check,
            )
            calls = _tool_calls_from_text(text)
            entry: Dict[str, Any] = {
                'step': phase,
                'llm_output': text,
                'mode': spec.mode.value,
                'channel': 'stream',
                'tool_call_count': len(calls),
            }
            if self._is_presentation_safe_prose(text, calls, ctx):
                entry['streamed'] = True
            else:
                uvs.coordinator.body_emitted = False
                entry['channel'] = 'text'
            return (text, calls, entry)
        t_llm = time.perf_counter()
        finish_reason = ''
        try:
            if supports_tools(self._llm) and phase_tools:
                try:
                    res: CompleteWithToolsResult = complete_with_tools(
                        self._llm,
                        system=system,
                        turns=turns,
                        tools=phase_tools,
                        call_spec=spec,
                        cancel_check=ctx.stream_cancel_check,
                    )
                    channel = 'tool_use'
                    text = res.text or ''
                    calls = list(res.tool_calls or [])
                    finish_reason = str(res.finish_reason or '')
                    if not calls and finish_reason.lower() not in ('tool_use', 'tool_calls'):
                        calls = _tool_calls_from_text(text)
                except NotImplementedError:
                    text = complete(self._llm, system=system, user=user_text_for_log, call_spec=spec, cancel_check=ctx.stream_cancel_check)
                    calls = _tool_calls_from_text(text)
            else:
                text = complete(self._llm, system=system, user=user_text_for_log, call_spec=spec, cancel_check=ctx.stream_cancel_check)
                calls = _tool_calls_from_text(text)
        except LlmRequestCancelled:
            return ('', [], {'step': phase, 'cancelled': True, 'mode': spec.mode.value})
        llm_elapsed_ms = (time.perf_counter() - t_llm) * 1000.0
        if phase == PDCAPhase.plan.value and llm_elapsed_ms >= 30000.0:
            _LLM_PDCA_LOG.warning('AICO plan llm slow elapsed_ms=%.1f', llm_elapsed_ms)
        pre_filter_calls = list(calls)
        dropped: List[str] = []
        if phase_tools and calls:
            (calls, dropped) = _filter_tool_calls_to_schemas(calls, phase_tools)
            if dropped:
                _LLM_PDCA_LOG.warning('tool_call_filtered phase=%s dropped=%s', phase, dropped)
        entry: Dict[str, Any] = {
            'step': phase,
            'llm_output': text,
            'mode': spec.mode.value,
            'channel': channel,
            'tool_call_count': len(calls),
            'dropped_tool_names': dropped,
            'finish_reason': finish_reason,
            'pre_filter_tool_calls': _serialize_tool_calls_for_entry(pre_filter_calls),
        }
        if self._should_stream_user_prose(ctx, phase, stream_prose=stream_prose) and self._is_presentation_safe_prose(text, calls, ctx):
            self._write_user_prose_to_presentation(ctx, text)
            entry['streamed'] = True
            entry['channel'] = 'presentation_prose'
        return (text, calls, entry)

    def _phase_react_loop(self, pdca_phase: str, system: str, initial_user: str, ctx: FrameworkRunContext, counters: ToolGatherCounters, trace: List[Dict[str, Any]], bag: Optional['_PdcaTickBag'] = None) -> Tuple[str, str, List[ToolResult], Dict[str, Any]]:
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
        user_message = _user_message_from_ctx(ctx)
        reason_ctx = _draft_reason_context(ctx)
        t_phase = time.perf_counter()
        try:
            for round_idx in range(max_rounds):
                if self._tick_cancelled(ctx):
                    last_entry = {'step': pdca_phase, 'cancelled': True}
                    break
                t_llm = time.perf_counter()
                budget_hint = format_tool_batch_limit_hint(self._tool_budgets, counters)
                system_for_llm = f'{system}\n\n{budget_hint}' if budget_hint else system
                (text, calls, entry) = self._call_llm_dual_track(
                    pdca_phase,
                    system_for_llm,
                    turns,
                    ctx,
                    stream_prose=(round_idx == max_rounds - 1),
                )
                entry = dict(entry)
                entry['round'] = round_idx + 1
                trace.append(entry)
                # per_react_round — react_turn_success_evaluator (opt-in via
                # require_structured_turn). A non-allow
                # verdict breaks the inner loop; the flag is passed to
                # after_state_execute (via ctx.payload['react_round_decision']) for
                # secondary confirmation — per_react_round does not drive sm.next.
                react_turn = entry.get('react_turn')
                if react_turn is not None and bag is not None:
                    rr_decision = self._evaluate_quality_check_point(
                        CheckPoint.PER_REACT_ROUND,
                        ctx=ctx, bag=bag, snapshot=None, state_id=pdca_phase, trace=trace,
                        extra={'react_turn': react_turn},
                    )
                    # Write react_round_decision payload and break the inner loop
                    # on replan/fail (continue keeps looping).
                    if rr_decision is not None and rr_decision.decision != 'allow':
                        ctx.payload['react_round_decision'] = {
                            'decision': rr_decision.decision,
                            'reason_code': rr_decision.reason_code,
                        }
                        if rr_decision.decision in ('replan', 'fail'):
                            trace.append({
                                'step': 'react_round_break',
                                'phase': pdca_phase,
                                'decision': rr_decision.decision,
                                'reason_code': rr_decision.reason_code,
                                'round': round_idx + 1,
                            })
                            break
                dropped_n = list(entry.get('dropped_tool_names') or [])
                if dropped_n:
                    trace.append({'step': 'tool_call_filtered', 'phase': pdca_phase, 'dropped': dropped_n, 'round': round_idx + 1})
                _trace_phase_timing(trace, scope='llm', phase=pdca_phase, elapsed_ms=(time.perf_counter() - t_llm) * 1000.0, round_idx=round_idx + 1, channel=str(entry.get('channel') or '') or None, tool_call_count=int(entry.get('tool_call_count') or 0) or None)
                last_text = text
                last_entry = entry
                if entry.get('skipped'):
                    break
                if entry.get('cancelled'):
                    break
                pre_filter_calls = _tool_calls_from_entry(entry.get('pre_filter_tool_calls'))
                pending = detect_pending_tool_work(
                    calls=calls,
                    dropped_names=dropped_n,
                    finish_reason=str(entry.get('finish_reason') or ''),
                    pre_filter_calls=pre_filter_calls,
                )
                if pending is not None:
                    trace.append({'step': 'agent_loop_pending_tool_work', 'phase': pdca_phase, 'reason_codes': list(pending.reason_codes), 'dropped': list(pending.dropped_names), 'round': round_idx + 1})
                if not should_exit_react_round(calls=calls, pending=pending):
                    if calls:
                        pass
                    elif pending is not None:
                        for turn in build_filtered_tool_continuation_turns(
                            pre_filter_calls=pre_filter_calls,
                            dropped_names=dropped_n or [c.name for c in pre_filter_calls],
                            assistant_text=text or '',
                        ):
                            turns.append(turn)
                        trace.append({'step': 'agent_loop_continuation_injected', 'phase': pdca_phase, 'hint_type': 'tool_filtered', 'round': round_idx + 1})
                        continue
                else:
                    if not self._tool_schemas:
                        break
                    rounds_remaining = max(0, max_rounds - round_idx - 1)
                    verdict = assess_draft_completeness_with_budget(
                        user_message=user_message,
                        draft_text=last_text,
                        tool_results=all_results,
                        config=self._agent_loop_config,
                        reason_context=reason_ctx,
                        rounds_remaining=rounds_remaining,
                    )
                    if verdict == DraftCompletenessVerdict.complete:
                        break
                    if verdict == DraftCompletenessVerdict.retry_loop:
                        trace.append({'step': 'draft_incomplete_detected', 'phase': pdca_phase, 'reason_codes': ['deferral_or_grounding_gap'], 'draft_chars': len((last_text or '').strip()), 'round': round_idx + 1})
                        turns.append(TextTurn(role='user', text=build_draft_retry_user_text()))
                        trace.append({'step': 'agent_loop_continuation_injected', 'phase': pdca_phase, 'hint_type': 'draft_incomplete', 'round': round_idx + 1})
                        continue
                    _LLM_PDCA_LOG.warning('tick_finished_with_deferral_only phase=%s draft_chars=%s', pdca_phase, len((last_text or '').strip()))
                    trace.append({'step': 'draft_incomplete_detected', 'phase': pdca_phase, 'reason_codes': ['budget_exhausted'], 'draft_chars': len((last_text or '').strip()), 'round': round_idx + 1})
                    last_text = ''
                    last_entry = dict(entry)
                    last_entry['draft_incomplete'] = True
                    ctx.payload['_draft_incomplete'] = True
                    break
                if not calls:
                    continue
                base_tool_ctx = self._tool_command_context
                runtime_tool_ctx = base_tool_ctx
                if base_tool_ctx is not None:
                    rt_meta = dict(base_tool_ctx.metadata or {})
                    rt_meta['user_message'] = str(ctx.payload.get('message') or ctx.payload.get('text') or '')
                    active_skill_context = ctx.payload.get('active_skill_context')
                    if active_skill_context is not None:
                        rt_meta['active_skill_context'] = active_skill_context
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
                    if self._tick_cancelled(ctx):
                        last_entry = {'step': pdca_phase, 'cancelled': True}
                        break
                    uvs_tool = ctx.user_visible_stream
                    if uvs_tool is not None:
                        from app.game_engine.agent_runtime.presentation_stream import ActivityKind

                        for tc in calls_to_run:
                            uvs_tool.coordinator.set_activity(ActivityKind.tool, detail=tc.name)
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
                # Collect consecutive-tool-failure counter and obs signatures for
                # stagnation detection. Side-effect-free re: trace; only
                # populates ctx.payload for stop_evaluator to read when enabled.
                self._update_tool_failure_counter(ctx, round_results)
                self._append_obs_signatures(ctx, round_results)
                turns.append(AssistantToolUseTurn(text=text or '', tool_calls=[ToolCall(id=c.id, name=c.name, args=list(c.args)) for c in calls]))
                turns.append(ToolResultsTurn(results=round_results))
                obs_chunks.append(obs_text)
                if counters.commands_run >= self._tool_budgets.max_commands_per_tick or counters.observation_chars >= self._tool_budgets.max_chars_observations_per_tick:
                    break
        finally:
            _trace_phase_timing(trace, scope='phase_total', phase=pdca_phase, elapsed_ms=(time.perf_counter() - t_phase) * 1000.0)
        if (last_text or '').strip() and not last_entry.get('draft_incomplete') and not last_entry.get('cancelled') and self._tool_schemas:
            verdict = assess_draft_completeness_with_budget(
                user_message=user_message,
                draft_text=last_text,
                tool_results=all_results,
                config=self._agent_loop_config,
                reason_context=reason_ctx,
                rounds_remaining=0,
            )
            if verdict != DraftCompletenessVerdict.complete:
                _LLM_PDCA_LOG.warning('tick_finished_with_deferral_only phase=%s draft_chars=%s', pdca_phase, len((last_text or '').strip()))
                trace.append({'step': 'draft_incomplete_detected', 'phase': pdca_phase, 'reason_codes': ['phase_exit_incomplete'], 'draft_chars': len((last_text or '').strip())})
                last_text = ''
                last_entry = dict(last_entry)
                last_entry['draft_incomplete'] = True
                ctx.payload['_draft_incomplete'] = True
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
        self._bind_presentation_anchor(ctx)
        self._memory.start_run(run_id=run_id, correlation_id=correlation if isinstance(correlation, str) else None, phase=PDCAPhase.plan.value, command_trace=list(trace), status='running')
        base_system = (ctx.system_prompt or self._cfg.system_prompt or '').strip()
        if _prompt_fallback_enabled():
            base_system = _append_policy_fallback(base_system)
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
        ctx.payload['intent_hint'] = intent_hint
        ctx.payload['_accumulated_tool_results'] = []
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
        plan_sys = _phase_system(base_system, PDCAPhase.plan.value, merged_phases)
        do_sys = _phase_system_core(base_system, PDCAPhase.do.value, merged_phases, slim_followup)
        check_sys = _phase_system_core(base_system, PDCAPhase.check.value, merged_phases, slim_followup)
        act_sys = _phase_system_core(base_system, PDCAPhase.act.value, merged_phases, slim_followup)
        do_spec = self._augment_spec_from_ctx(self._spec_for_phase(PDCAPhase.do.value, ctx), ctx)
        act_spec = self._augment_spec_from_ctx(self._spec_for_phase(PDCAPhase.act.value, ctx), ctx)
        bag = _PdcaTickBag(
            user_msg=user_msg,
            mem_for_do=mem_for_do,
            plan_user=plan_user,
            plan_sys=plan_sys,
            do_sys=do_sys,
            check_sys=check_sys,
            act_sys=act_sys,
            do_spec=do_spec,
            act_spec=act_spec,
            chain_criteria_text=chain_criteria_text,
            merged_phases=merged_phases,
            base_system=base_system,
            slim_followup=slim_followup,
        )
        sm = self._state_machine
        snapshot = StateMachineSnapshot(current_state=sm.initial)
        state_id = sm.initial
        while True:
            state_def = sm.get_state(state_id)
            if state_def.exit:
                break
            # Stash snapshot counts for per_react_round fallback (no snapshot in scope).
            ctx.payload['_snapshot_turn_count'] = snapshot.turn_count
            ctx.payload['_snapshot_replan_count'] = snapshot.replan_count
            # Pre-state cancel: skip execute and let any→fail route the abort.
            if self._tick_cancelled(ctx):
                bag.cancelled = True
                exec_result = StateExecutionResult()
            else:
                exec_result = self._execute_pdca_state(
                    state_def,
                    ctx=ctx,
                    run_id=run_id,
                    trace=trace,
                    gather_counters=gather_counters,
                    bag=bag,
                    snapshot=snapshot,
                )
            if bag.cancelled or (exec_result.gather_counters or {}).get('cancelled') or self._tick_cancelled(ctx):
                bag.cancelled = True
            event = exec_result.event
            # Deferral-only final drafts are detected after act (presentation anchor),
            # so any→fail can fire before act→end. Runs before after_state_execute so
            # a stop/budget fail can override the draft verdict.
            if state_id == PDCAPhase.act.value:
                # before_final_answer — pattern_match detector (P4, non-streaming).
                # Default-off (byte-equiv): when the detector is disabled or the
                # pattern set is empty, evaluate returns allow and nothing happens.
                # On block, clear the draft and set _draft_incomplete so the tick
                # routes to fail_fallback (v1 synchronous degrade of require_approval).
                self._evaluate_before_final_answer(ctx, bag, trace)
                self._detect_tick_emit_deferral(ctx, bag, trace, user_msg)
            # after_state_execute — stop_evaluator (new dimensions gated, default off).
            stop_decision = self._evaluate_quality_check_point(
                CheckPoint.AFTER_STATE_EXECUTE,
                ctx=ctx, bag=bag, snapshot=snapshot, state_id=state_id, trace=trace,
                gather_counters=gather_counters,
            )
            if stop_decision is not None and stop_decision.decision != 'allow':
                if stop_decision.decision == 'fail':
                    # Map fail (max_iterations / max_consecutive) to
                    # runtime.stop_fail so *→fail routes the abort from any state.
                    self._mark_stop_fail(
                        ctx,
                        stop_decision.reason_code or 'quality_gate_failed',
                    )
                elif stop_decision.decision == 'replan':
                    reason = stop_decision.reason_code
                    ev = stop_decision.evidence or {}
                    if reason in ('check_retry', 'mandatory_gap'):
                        # Apply detect_check_replan side-effects formerly done
                        # inline in _execute_check_state. sm.next handles the
                        # replan cap/budget guard.
                        event = reason
                        retry_tools = ev.get('retry_tools')
                        bag.retry_tools = retry_tools
                        bag.retry_event = reason
                        if reason == 'mandatory_gap' and ev.get('gap_detail') is not None:
                            trace.append({
                                'step': 'mandatory_gap_retry_override',
                                'tools': retry_tools,
                                'details': ev.get('gap_detail'),
                            })
                    elif reason == 'stagnation' and not event:
                        # Stagnation replans when budget remains and the replan
                        # cap allows it; otherwise route to stop_fail.
                        budget_remaining = self._tick_budget_remaining(gather_counters)
                        if snapshot.replan_count < sm.max_replans and budget_remaining:
                            event = 'stagnation'
                        else:
                            self._mark_stop_fail(ctx, 'stagnation_replan_exhausted')
            # react_round_decision is consumed by stop_evaluator above;
            # clear it so the next phase does not see a stale verdict.
            ctx.payload.pop('react_round_decision', None)
            # before_terminal — final_success_evaluator drive mode.
            #   off     → not called (byte-equiv).
            #   shadow  → audit/trace + divergence detection; _detect_tick_emit_deferral
            #             remains authoritative.
            #   enforce → evaluator verdict drives _draft_incomplete; _detect_tick_emit_deferral
            #             is the fallback (used when evaluator returns None/raises). Note:
            #             retry_loop→replan drives a draft_retry event when budget
            #             and replan caps allow it.
            fs_decision = None
            if state_id == PDCAPhase.act.value:
                fs_decision = self._evaluate_quality_check_point(
                    CheckPoint.BEFORE_TERMINAL,
                    ctx=ctx, bag=bag, snapshot=snapshot, state_id=state_id, trace=trace,
                    gather_counters=gather_counters,
                )
                self._apply_final_success_drive(
                    fs_decision,
                    ctx,
                    trace,
                    bag=bag,
                    snapshot=snapshot,
                    sm=sm,
                    gather_counters=gather_counters,
                )
                if ctx.payload.pop('_draft_retry_event', None) and not event:
                    event = 'draft_retry'
            runtime = {
                'do_mode': do_spec.mode.value if hasattr(do_spec.mode, 'value') else str(do_spec.mode),
                'act_mode': act_spec.mode.value if hasattr(act_spec.mode, 'value') else str(act_spec.mode),
                'budget_remaining': self._tick_budget_remaining(gather_counters),
                'mandatory_gap_missing': bool(event == 'mandatory_gap'),
                'cancelled': bool(bag.cancelled),
                'draft_incomplete': bool(ctx.payload.get('_draft_incomplete')),
                'stop_fail': bool(ctx.payload.get('_stop_fail')),
            }
            tctx = TransitionContext(snapshot=snapshot, runtime=runtime, event=event)
            next_id = sm.next(state_id, tctx)
            replan_inc = bool(event in ('check_retry', 'mandatory_gap', 'stagnation', 'draft_retry') and next_id == PDCAPhase.plan.value)
            matched_when = None
            for tr in sm.transitions:
                if tr.from_state in (state_id, '*') and tr.to_state == next_id:
                    if tr.on_event and tr.on_event != event:
                        continue
                    matched_when = tr.when
                    break
            # When the machine jumps over do (skip-do) onto check/act, emit the
            # skipped-do draft/trace so Check sees the same reply as before.
            if (
                state_id == PDCAPhase.plan.value
                and next_id in (PDCAPhase.do.value, PDCAPhase.check.value, PDCAPhase.act.value)
                and next_id != PDCAPhase.do.value
                and do_spec.mode == PhaseLlmMode.skip
            ):
                self._emit_skip_do_draft(bag=bag, trace=trace, after_check_retry=bool(snapshot.replan_count > 0 or bag.retry_tools))
            trace.append({
                'step': 'state_transition',
                'from': state_id,
                'to': next_id,
                'when': matched_when,
                'event': event,
                'replan_count': snapshot.replan_count + (1 if replan_inc else 0),
            })
            snapshot = snapshot.advance(to_state=next_id, event=event, incremented_replan=replan_inc)
            if replan_inc and event == 'draft_retry':
                uvs_retry = ctx.user_visible_stream
                if uvs_retry is not None:
                    uvs_retry.coordinator.on_rewrite()
                trace.append({
                    'step': 'draft_retry_triggered',
                    'reason_code': (fs_decision.reason_code if fs_decision is not None else None),
                })
            if replan_inc and bag.retry_tools:
                # Preserve guardrail hint injection for the subsequent plan state.
                bag.replan_guardrail_hint = (
                    f"Check phase flagged that tool observations are required to answer. "
                    f"Requested tools: {', '.join(bag.retry_tools) or '(any)'}."
                )
                uvs_retry = ctx.user_visible_stream
                if uvs_retry is not None:
                    uvs_retry.coordinator.on_rewrite()
                trace.append({'step': 'check_retry_triggered', 'tools': list(bag.retry_tools)})
            state_id = next_id

        # Abort terminal: preserve the reason that selected the fail state.
        if state_id == 'fail':
            stop_reason = str(ctx.payload.get('_stop_fail_reason') or '').strip()
            if bag.cancelled:
                fail_code = 'cancelled'
            elif stop_reason:
                fail_code = stop_reason
            elif ctx.payload.get('_draft_incomplete'):
                fail_code = 'draft_incomplete'
            else:
                fail_code = 'tick_failed'
            fail_msg = ''
            if fail_code == 'draft_incomplete' and user_msg:
                fail_msg = _resolve_npc_agent_empty_reply_message(self._cfg)
            self._tick_hooks.on_before_phase(ThinkingPhaseId.post, ctx)
            self._tick_hooks.on_after_phase(ThinkingPhaseId.post, ctx, phase_llm_output=fail_msg, skipped=False)
            return self._finish_tick_fail(
                run_id,
                trace,
                correlation=correlation,
                error_code=fail_code,
                message=fail_msg,
                graph_ops_summary={
                    'cancelled': fail_code == 'cancelled',
                    'draft_incomplete': bool(ctx.payload.get('_draft_incomplete')),
                    'stop_reason': stop_reason or None,
                },
            )

        final_text = bag.final_text or bag.reply
        ok = bag.check_ok
        # Post-loop: mandatory notice (success-path only; abort handled above)
        mandatory_notice = ''
        snap_gap = ctx.payload.get('tool_router_snapshot')
        if isinstance(snap_gap, dict):
            mans_gap = list(snap_gap.get('mandatory_tool_names') or [])
            if mans_gap:
                (has_m_gap, gap_detail) = mandatory_observation_gap(
                    mans_gap, bag.accumulated_tick_tool_results, plan_trace=trace,
                )
                if has_m_gap:
                    mandatory_notice = format_mandatory_gap_user_notice(gap_detail)
                    _LLM_PDCA_LOG.warning(
                        'mandatory_fallback',
                        extra={
                            'mandatory_fallback_reason': ','.join(gap_detail.get('reason_codes') or []),
                            'mandatory_missing': gap_detail.get('missing'),
                            'mandatory_failed': gap_detail.get('failed'),
                            'mandatory_permission_denied_tools': gap_detail.get('permission_denied_tools'),
                            'mandatory_gather_budget_limited': gap_detail.get('gather_budget_limited'),
                            'tool_router_threshold_revision': snap_gap.get('threshold_revision'),
                            'tool_router_registry_revision': snap_gap.get('tool_registry_revision'),
                        },
                    )
                    trace.append({'step': 'mandatory_observation_gap', **gap_detail})
                    ctx.payload['mandatory_observation_gap'] = gap_detail
        if user_msg and (not (final_text or '').strip()):
            final_text = _resolve_npc_agent_empty_reply_message(self._cfg)
            trace.append({'step': 'empty_reply_fallback', 'user_message_len': len(user_msg)})
        if mandatory_notice:
            final_text = (final_text or '').rstrip() + mandatory_notice
        self._memory.finish_run(
            run_id, PDCAPhase.act.value, trace, 'success' if ok else 'failed',
            graph_ops_summary={'reply_excerpt': (final_text or '')[:500]},
        )
        self._memory.append_raw('audit', {'framework': self.framework_id, 'run_id': str(run_id), 'ok': ok})
        self._tick_hooks.on_before_phase(ThinkingPhaseId.post, ctx)
        self._tick_hooks.on_after_phase(ThinkingPhaseId.post, ctx, phase_llm_output=final_text, skipped=False)
        return FrameworkRunResult(ok=ok, message=final_text, final_phase=PDCAPhase.act.value, error_code=None)

    def _emit_skip_do_draft(
        self,
        *,
        bag: '_PdcaTickBag',
        trace: List[Dict[str, Any]],
        after_check_retry: bool = False,
    ) -> None:
        reply = assemble_plan_skip_do_draft(bag.plan_out or '', bag.plan_tools_text or '')
        do_entry: Dict[str, Any] = {
            'step': PDCAPhase.do.value,
            'skipped': True,
            'mode': PhaseLlmMode.skip.value,
            'skip_do_draft_chars': len(reply or ''),
        }
        if after_check_retry:
            do_entry['after_check_retry'] = True
        trace.append(do_entry)
        bag.reply = reply or ''
        bag.do_tools_text = ''
        bag.final_text = bag.reply

    def _execute_pdca_state(
        self,
        state_def: StateDef,
        *,
        ctx: FrameworkRunContext,
        run_id: uuid.UUID,
        trace: List[Dict[str, Any]],
        gather_counters: ToolGatherCounters,
        bag: '_PdcaTickBag',
        snapshot: StateMachineSnapshot,
    ) -> StateExecutionResult:
        sid = state_def.id
        if sid == PDCAPhase.plan.value:
            return self._execute_plan_state(ctx=ctx, run_id=run_id, trace=trace, gather_counters=gather_counters, bag=bag, snapshot=snapshot)
        if sid == PDCAPhase.do.value:
            return self._execute_do_state(ctx=ctx, run_id=run_id, trace=trace, gather_counters=gather_counters, bag=bag)
        if sid == PDCAPhase.check.value:
            return self._execute_check_state(ctx=ctx, run_id=run_id, trace=trace, gather_counters=gather_counters, bag=bag)
        if sid == PDCAPhase.act.value:
            return self._execute_act_state(ctx=ctx, run_id=run_id, trace=trace, bag=bag)
        raise ValueError(f'unsupported pdca state: {sid}')

    def _execute_plan_state(
        self,
        *,
        ctx: FrameworkRunContext,
        run_id: uuid.UUID,
        trace: List[Dict[str, Any]],
        gather_counters: ToolGatherCounters,
        bag: '_PdcaTickBag',
        snapshot: StateMachineSnapshot,
    ) -> StateExecutionResult:
        self._tick_hooks.on_before_phase(ThinkingPhaseId.plan, ctx)
        if self._tick_cancelled(ctx):
            bag.cancelled = True
            return StateExecutionResult(gather_counters={'cancelled': True})
        self._prepare_skill_context(ctx, PDCAPhase.plan.value, trace)
        plan_user = bag.plan_user
        if bag.replan_guardrail_hint:
            plan_user = f'{bag.plan_user}\n\nGuardrail note:\n{bag.replan_guardrail_hint}\nEmit a tool call plan now.'
            bag.replan_guardrail_hint = None
        (plan_out, plan_tools_text, plan_tool_results, plan_entry) = self._phase_react_loop(
            PDCAPhase.plan.value, bag.plan_sys, plan_user, ctx, gather_counters, trace, bag=bag,
        )
        if plan_entry.get('cancelled'):
            bag.cancelled = True
            return StateExecutionResult(gather_counters={'cancelled': True})
        bag.plan_out = plan_out or ''
        bag.plan_tools_text = plan_tools_text or ''
        bag.accumulated_tick_tool_results.extend(plan_tool_results)
        ctx.payload['_accumulated_tool_results'] = list(bag.accumulated_tick_tool_results)
        self._memory.update_run(run_id, PDCAPhase.plan.value, trace, 'running')
        self._tick_hooks.on_after_phase(
            ThinkingPhaseId.plan, ctx, phase_llm_output=plan_out or '', skipped=bool(plan_entry.get('skipped')),
        )
        obs_step = 'plan_retry_tool_observations' if snapshot.replan_count > 0 else 'plan_tool_observations'
        if plan_tools_text:
            trace.append({'step': obs_step, 'chars': len(plan_tools_text)})
        return StateExecutionResult(output_text=bag.plan_out, draft_text=bag.plan_out)

    def _execute_do_state(
        self,
        *,
        ctx: FrameworkRunContext,
        run_id: uuid.UUID,
        trace: List[Dict[str, Any]],
        gather_counters: ToolGatherCounters,
        bag: '_PdcaTickBag',
    ) -> StateExecutionResult:
        self._tick_hooks.on_before_phase(ThinkingPhaseId.do, ctx)
        if self._tick_cancelled(ctx):
            bag.cancelled = True
            return StateExecutionResult(gather_counters={'cancelled': True})
        after_retry = bool(bag.retry_tools)
        obs_label = 'plan retry' if after_retry else 'plan phase'
        tool_blocks_plan = (
            f'\n\nTool observations ({obs_label}):\n{bag.plan_tools_text}' if bag.plan_tools_text else ''
        )
        plan_block = (bag.plan_out or '').strip()
        if plan_block:
            do_user = f"User message:\n{bag.user_msg}\n\nPlan:\n{bag.plan_out}\n{tool_blocks_plan}\n\nMemory:\n{bag.mem_for_do or '(none)'}"
        else:
            do_user = f"User message:\n{bag.user_msg}{tool_blocks_plan}\n\nMemory:\n{bag.mem_for_do or '(none)'}"
        self._prepare_skill_context(ctx, PDCAPhase.do.value, trace)
        if bag.do_spec.mode == PhaseLlmMode.skip:
            reply = assemble_plan_skip_do_draft(bag.plan_out or '', bag.plan_tools_text or '')
            do_tools_text = ''
            do_entry: Dict[str, Any] = {
                'step': PDCAPhase.do.value,
                'skipped': True,
                'mode': PhaseLlmMode.skip.value,
                'skip_do_draft_chars': len(reply or ''),
            }
            if after_retry:
                do_entry['after_check_retry'] = True
            trace.append(do_entry)
        else:
            (reply, do_tools_text, do_tool_results, do_entry) = self._phase_react_loop(
                PDCAPhase.do.value, bag.do_sys, do_user, ctx, gather_counters, trace, bag=bag,
            )
            if do_entry.get('cancelled'):
                bag.cancelled = True
                return StateExecutionResult(gather_counters={'cancelled': True})
            bag.accumulated_tick_tool_results.extend(do_tool_results)
        ctx.payload['_accumulated_tool_results'] = list(bag.accumulated_tick_tool_results)
        bag.reply = reply or ''
        bag.do_tools_text = do_tools_text or ''
        bag.final_text = bag.reply
        self._memory.update_run(run_id, PDCAPhase.do.value, trace, 'running')
        self._tick_hooks.on_after_phase(
            ThinkingPhaseId.do, ctx, phase_llm_output=reply or '', skipped=bool(do_entry.get('skipped')),
        )
        obs_step = 'do_retry_tool_observations' if after_retry else 'do_tool_observations'
        if do_tools_text:
            trace.append({'step': obs_step, 'chars': len(do_tools_text)})
        return StateExecutionResult(output_text=bag.reply, draft_text=bag.reply)

    def _execute_check_state(
        self,
        *,
        ctx: FrameworkRunContext,
        run_id: uuid.UUID,
        trace: List[Dict[str, Any]],
        gather_counters: ToolGatherCounters,
        bag: '_PdcaTickBag',
    ) -> StateExecutionResult:
        tool_blocks_do = f'\n\nTool observations (do phase):\n{bag.do_tools_text}' if bag.do_tools_text else ''
        plan_grounding_for_check = ''
        if bag.do_spec.mode == PhaseLlmMode.skip and (bag.plan_tools_text or '').strip():
            plan_grounding_for_check = (
                f'\n\nPlan-phase tool observations (runtime grounding; not shown to user):\n{bag.plan_tools_text}'
            )
        check_user = f'User message:\n{bag.user_msg}\n\nDraft reply:\n{bag.reply}{plan_grounding_for_check}{tool_blocks_do}'
        snap = ctx.payload.get('tool_router_snapshot')
        if getattr(snap, 'get', None) and isinstance(snap, dict) and snap.get('enforcement_level') == EnforcementLevel.hard_must_invoke.value:
            mans = snap.get('mandatory_tool_names') or []
            if mans:
                check_user += '\n\nRouting mandatory tools (verify ToolObservation covers each): ' + ', '.join((str(x) for x in mans))
        if bag.chain_criteria_text:
            check_user += '\n\n' + bag.chain_criteria_text
        self._prepare_skill_context(ctx, PDCAPhase.check.value, trace)
        self._tick_hooks.on_before_phase(ThinkingPhaseId.check, ctx)
        if self._tick_cancelled(ctx):
            bag.cancelled = True
            return StateExecutionResult(gather_counters={'cancelled': True})
        t_check = time.perf_counter()
        (check_out, check_entry) = self._call_llm(PDCAPhase.check.value, bag.check_sys, check_user, ctx)
        if check_entry.get('cancelled'):
            bag.cancelled = True
            return StateExecutionResult(gather_counters={'cancelled': True})
        _trace_phase_timing(trace, scope='llm', phase=PDCAPhase.check.value, elapsed_ms=(time.perf_counter() - t_check) * 1000.0)
        # detect_check_replan is no longer called inline.
        # stop_evaluator (after_state_execute) runs it via PolicyEngine and
        # emits the formal replan decision; the driver applies side-effects
        # (bag.retry_tools, mandatory_gap_retry_override trace row).
        if check_entry.get('skipped'):
            ok = True
        else:
            co = check_out or ''
            ok = 'error' not in co.lower()[:80]
        check_entry['passed'] = ok
        bag.check_out = check_out or ''
        bag.check_ok = ok
        bag.check_skipped = bool(check_entry.get('skipped'))
        bag.final_text = bag.reply
        trace.append(check_entry)
        self._memory.update_run(run_id, PDCAPhase.check.value, trace, 'running')
        self._tick_hooks.on_after_phase(
            ThinkingPhaseId.check, ctx, phase_llm_output=check_out or '', skipped=bool(check_entry.get('skipped')),
        )
        return StateExecutionResult(output_text=bag.check_out, draft_text=bag.reply)

    def _execute_act_state(
        self,
        *,
        ctx: FrameworkRunContext,
        run_id: uuid.UUID,
        trace: List[Dict[str, Any]],
        bag: '_PdcaTickBag',
    ) -> StateExecutionResult:
        self._tick_hooks.on_before_phase(ThinkingPhaseId.action, ctx)
        if self._tick_cancelled(ctx):
            bag.cancelled = True
            return StateExecutionResult(gather_counters={'cancelled': True})
        final_text = bag.final_text or bag.reply
        act_user = f'User message:\n{bag.user_msg}\n\nDraft reply:\n{final_text}\n\nPolish for final user-facing text.'
        self._prepare_skill_context(ctx, PDCAPhase.act.value, trace)
        uvs_act = ctx.user_visible_stream
        if (
            uvs_act is not None
            and bag.act_spec.mode != PhaseLlmMode.skip
            and uvs_act.coordinator.body_emitted
        ):
            uvs_act.coordinator.on_rewrite()
        t_act = time.perf_counter()
        (act_out, act_entry) = self._call_llm(PDCAPhase.act.value, bag.act_sys, act_user, ctx)
        if act_entry.get('cancelled'):
            bag.cancelled = True
            return StateExecutionResult(gather_counters={'cancelled': True})
        _trace_phase_timing(trace, scope='llm', phase=PDCAPhase.act.value, elapsed_ms=(time.perf_counter() - t_act) * 1000.0)
        if not act_entry.get('skipped') and (act_out or '').strip():
            final_text = act_out.strip()
        act_entry['step'] = PDCAPhase.act.value
        act_entry['final_reply'] = final_text
        trace.append(act_entry)
        self._tick_hooks.on_after_phase(
            ThinkingPhaseId.action, ctx, phase_llm_output=act_out or '', skipped=bool(act_entry.get('skipped')),
        )
        bag.final_text = final_text
        return StateExecutionResult(output_text=final_text, draft_text=final_text)

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
