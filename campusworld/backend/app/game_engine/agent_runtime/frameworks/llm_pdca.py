from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.commands.base import CommandContext
from app.commands.registry import command_registry
from app.core.config_manager import get_config
from app.core.log.aico_observability import (
    clear_aico_observability_context,
    log_aico_llm_call,
    log_aico_tool_observations_text,
    set_aico_observability_context,
    should_emit_aico_full_chain_logs,
)
from app.core.settings import AgentLlmServiceConfig, PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.frameworks.base import (
    FrameworkRunContext,
    FrameworkRunResult,
    ThinkingFramework,
)
from app.game_engine.agent_runtime.frameworks.pdca import PDCAPhase
from app.game_engine.agent_runtime.llm_client import (
    LlmCallSpec,
    LlmClient,
    StubLlmClient,
    complete_with_tools,
    supports_tools,
)
from app.game_engine.agent_runtime.memory_port import MemoryPort
from app.game_engine.agent_runtime.phase_llm_resolve import merge_phase_config, to_llm_call_spec
from app.game_engine.agent_runtime.resolved_tool_surface import PreauthorizedToolExecutor
from app.game_engine.agent_runtime.thinking_pipeline import AgentTickHooks, NoOpAgentTickHooks, ThinkingPhaseId
from app.game_engine.agent_runtime.tool_calling import (
    AssistantToolUseTurn,
    CompleteWithToolsResult,
    ConversationTurn,
    TextTurn,
    ToolCall,
    ToolResult,
    ToolResultsTurn,
    ToolSchema,
    assistant_tool_use_turn_as_text_block,
    command_result_to_tool_result,
    tool_calls_to_invocation_plan,
    tool_results_turn_as_text_block,
)
from app.game_engine.agent_runtime.tool_gather import (
    ToolGatherBudgets,
    ToolGatherCounters,
    ToolInvocationPlan,
    format_tool_observation_block,
    gather_tool_observations,
    parse_tool_invocation_plan_from_text,
    tool_gather_budgets_from_agent_extra,
)
from app.game_engine.agent_runtime.tool_runtime_view import resolve_tool_runtime_view
from app.game_engine.agent_runtime.tooling import ToolExecutor


# Match a RETRY signal emitted by the Check phase.
# Example: ``RETRY: need_tools=look,whoami`` or ``RETRY: need_tools=whoami``.
# The tool-name list must be a single physical line — we stop at the first
# newline or any character that cannot appear in a command identifier.
_CHECK_RETRY_RE = re.compile(
    r"RETRY\s*:\s*need_tools\s*=\s*([A-Za-z0-9_.\-]+(?:\s*,\s*[A-Za-z0-9_.\-]+)*)",
    flags=re.IGNORECASE,
)

# When Plan/Do/Act complete without error but produce no user-visible text.
_DEFAULT_NPC_AGENT_EMPTY_REPLY = "抱歉，我没有能力处理此问题。你可以换一个问题。"


def _resolve_npc_agent_empty_reply_message(cfg: AgentLlmServiceConfig) -> str:
    """``agents.llm.*.extra.npc_agent_empty_reply_message`` overrides; else default."""
    extra = getattr(cfg, "extra", None) or {}
    if not isinstance(extra, dict):
        return _DEFAULT_NPC_AGENT_EMPTY_REPLY
    raw = extra.get("npc_agent_empty_reply_message")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return _DEFAULT_NPC_AGENT_EMPTY_REPLY

_LLM_PDCA_LOG = logging.getLogger(__name__)


def _filter_tool_calls_to_schemas(
    calls: List[ToolCall],
    tool_schemas: Sequence[ToolSchema],
) -> Tuple[List[ToolCall], List[str]]:
    """Drop tool invocations not present on the resolved schema surface.

    Prevents JSON fallback (or any stray names) from entering ``AssistantToolUseTurn``
    and then failing wire validation (tool_use name not in request ``tools``).
    Normalizes names through the command registry (alias → primary).
    """
    if not calls:
        return [], []
    allowed = {str(s.name) for s in tool_schemas if getattr(s, "name", None)}
    if not allowed:
        return [], [c.name for c in calls if c.name]
    kept: List[ToolCall] = []
    dropped: List[str] = []
    for c in calls:
        raw = (c.name or "").strip()
        cmd = command_registry.get_command(raw) if raw else None
        primary = (cmd.name if cmd is not None else raw).strip()
        if not primary:
            continue
        if primary in allowed:
            if primary != c.name:
                kept.append(
                    ToolCall(
                        id=c.id,
                        name=primary,
                        args=list(c.args),
                    )
                )
            else:
                kept.append(c)
        else:
            dropped.append(raw or primary)
    return kept, dropped


def _trace_phase_timing(
    trace: List[Dict[str, Any]],
    *,
    scope: str,
    phase: str,
    elapsed_ms: float,
    round_idx: Optional[int] = None,
    channel: Optional[str] = None,
    tool_call_count: Optional[int] = None,
) -> None:
    """Append a small structured row for tick latency analysis (F10 observability)."""
    row: Dict[str, Any] = {
        "step": "phase_timing",
        "scope": scope,
        "phase": phase,
        "elapsed_ms": round(float(elapsed_ms), 3),
    }
    if round_idx is not None:
        row["round"] = int(round_idx)
    if channel:
        row["channel"] = channel
    if tool_call_count is not None:
        row["tool_call_count"] = int(tool_call_count)
    trace.append(row)


def _merge_phase_prompts(
    base: Dict[str, str],
    overrides: Optional[Dict[str, str]],
) -> Dict[str, str]:
    out = dict(base)
    if overrides:
        out.update({k: v for k, v in overrides.items() if v})
    return out


def _phase_system(base_system: str, phase: str, phase_prompts: Dict[str, str]) -> str:
    suffix = phase_prompts.get(phase, "").strip()
    if not suffix:
        return base_system
    return f"{base_system.rstrip()}\n\n[{phase}] {suffix}"


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
    raw = m.group(1) or ""
    tools = [t.strip() for t in raw.split(",") if t.strip()]
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
    ):
        self._memory = memory
        self._cfg = llm_config
        self._instance_phase_llm = instance_phase_llm
        self._instance_mode_models = dict(instance_mode_models or {})
        self._llm = llm or StubLlmClient()
        self._tools = tools
        self._tool_command_context = tool_command_context
        self._pre_tool = preauthorized_tool_executor
        self._tool_budgets = tool_gather_budgets or tool_gather_budgets_from_agent_extra(
            llm_config.extra
        )
        self._tick_hooks: AgentTickHooks = tick_hooks or NoOpAgentTickHooks()
        self._tool_schemas: List[ToolSchema] = list(tool_schemas or [])

    @property
    def framework_id(self) -> str:
        return "PDCA_LLM"

    def _spec_for_phase(self, phase: str, ctx: FrameworkRunContext) -> LlmCallSpec:
        pcfg = merge_phase_config(phase, self._instance_phase_llm, ctx.phase_llm_overrides)
        return to_llm_call_spec(
            pcfg,
            mode_models=self._instance_mode_models,
            default_model=(self._cfg.model or "").strip(),
        )

    # -------------------- low-level LLM invocation (text) --------------------

    def _call_llm(
        self,
        phase: str,
        system: str,
        user: str,
        ctx: FrameworkRunContext,
    ) -> Tuple[str, Dict[str, Any]]:
        """Single plain-text LLM call (back-compat shape for existing tests)."""
        spec = self._spec_for_phase(phase, ctx)
        cm = get_config()
        if should_emit_aico_full_chain_logs(cm):
            log_aico_llm_call(
                cm,
                phase=phase,
                system=system,
                user=user,
                spec=spec,
                skipped=spec.mode == PhaseLlmMode.skip,
            )
        if spec.mode == PhaseLlmMode.skip:
            return "", {"step": phase, "skipped": True, "mode": spec.mode.value}
        out = self._llm.complete(system=system, user=user, call_spec=spec)
        return out, {"step": phase, "llm_output": out, "mode": spec.mode.value}

    def _gather_tools_after_llm(
        self,
        pdca_phase: str,
        llm_output: str,
        trace: List[Dict[str, Any]],
        counters: ToolGatherCounters,
    ) -> str:
        """Back-compat helper used by existing unit tests.

        New code paths go through :meth:`_phase_react_loop` which handles
        both native tool_use calls and JSON fallback uniformly.
        """
        view = resolve_tool_runtime_view(
            pre_tool=self._pre_tool,
            tool_command_context=self._tool_command_context,
            budgets=self._tool_budgets,
            counters=counters,
        )
        if not view.can_execute:
            trace.append(
                {"step": "tool_gather_skip", "phase": pdca_phase, "reason": view.reason}
            )
            return ""
        plan = parse_tool_invocation_plan_from_text(llm_output or "")
        if not plan.commands:
            return ""
        assert view.executor is not None and view.tool_context is not None
        text, entries = gather_tool_observations(
            view.executor,
            view.tool_context,
            plan,
            budgets=view.budgets,
            counters=counters,
            phase_label=pdca_phase,
        )
        trace.extend(entries)
        if text:
            cm = get_config()
            if should_emit_aico_full_chain_logs(cm):
                log_aico_tool_observations_text(cm, phase=pdca_phase, observation_text=text)
        return text

    # -------------------- dual-track LLM call --------------------

    def _call_llm_dual_track(
        self,
        phase: str,
        system: str,
        turns: List[ConversationTurn],
        ctx: FrameworkRunContext,
    ) -> Tuple[str, List[ToolCall], Dict[str, Any]]:
        """Native ``complete_with_tools`` when available, JSON fallback otherwise.

        Returns ``(text, tool_calls, trace_entry)``. ``tool_calls`` is empty
        when the model chose to answer with prose or when parsing failed.
        """
        spec = self._spec_for_phase(phase, ctx)
        cm = get_config()
        user_text_for_log = _render_turns_as_text(turns)
        if should_emit_aico_full_chain_logs(cm):
            log_aico_llm_call(
                cm,
                phase=phase,
                system=system,
                user=user_text_for_log,
                spec=spec,
                skipped=spec.mode == PhaseLlmMode.skip,
            )
        if spec.mode == PhaseLlmMode.skip:
            return "", [], {"step": phase, "skipped": True, "mode": spec.mode.value}

        channel = "text"
        text = ""
        calls: List[ToolCall] = []
        if supports_tools(self._llm) and self._tool_schemas:
            try:
                res: CompleteWithToolsResult = complete_with_tools(
                    self._llm,
                    system=system,
                    turns=turns,
                    tools=self._tool_schemas,
                    call_spec=spec,
                )
                channel = "tool_use"
                text = res.text or ""
                calls = list(res.tool_calls or [])
                # If provider explicitly flagged tool_use but returned no calls,
                # do NOT also run JSON fallback — avoids double-execution.
                if not calls and res.finish_reason.lower() not in ("tool_use", "tool_calls"):
                    calls = _tool_calls_from_text(text)
            except NotImplementedError:
                text = self._llm.complete(
                    system=system, user=user_text_for_log, call_spec=spec
                )
                calls = _tool_calls_from_text(text)
        else:
            text = self._llm.complete(system=system, user=user_text_for_log, call_spec=spec)
            calls = _tool_calls_from_text(text)

        dropped: List[str] = []
        if self._tool_schemas and calls:
            calls, dropped = _filter_tool_calls_to_schemas(calls, self._tool_schemas)
            if dropped:
                _LLM_PDCA_LOG.warning(
                    "tool_call_filtered phase=%s dropped=%s",
                    phase,
                    dropped,
                )

        return text, calls, {
            "step": phase,
            "llm_output": text,
            "mode": spec.mode.value,
            "channel": channel,
            "tool_call_count": len(calls),
            "dropped_tool_names": dropped,
        }

    # -------------------- ReAct per-phase loop --------------------

    def _phase_react_loop(
        self,
        pdca_phase: str,
        system: str,
        initial_user: str,
        ctx: FrameworkRunContext,
        counters: ToolGatherCounters,
        trace: List[Dict[str, Any]],
    ) -> Tuple[str, str, List[ToolResult], Dict[str, Any]]:
        """Run up to ``budgets.max_tool_rounds_per_phase`` reason-act-observe cycles.

        Returns ``(final_text, accumulated_observation_text, tool_results, last_entry)``.
        ``final_text`` is the LLM's last textual output (or empty if only
        tool calls were emitted). ``accumulated_observation_text`` is the
        concatenation of all serialized ``ToolResultsTurn`` bodies from
        this phase (used for Do/Check user segments and for trace logs).
        """
        max_rounds = max(1, int(self._tool_budgets.max_tool_rounds_per_phase))
        turns: List[ConversationTurn] = [TextTurn(role="user", text=initial_user)]
        obs_chunks: List[str] = []
        all_results: List[ToolResult] = []
        last_text = ""
        last_entry: Dict[str, Any] = {"step": pdca_phase, "skipped": False}
        t_phase = time.perf_counter()
        try:
            for round_idx in range(max_rounds):
                t_llm = time.perf_counter()
                text, calls, entry = self._call_llm_dual_track(pdca_phase, system, turns, ctx)
                entry = dict(entry)
                entry["round"] = round_idx + 1
                trace.append(entry)
                dropped_n = list(entry.get("dropped_tool_names") or [])
                if dropped_n:
                    trace.append(
                        {
                            "step": "tool_call_filtered",
                            "phase": pdca_phase,
                            "dropped": dropped_n,
                            "round": round_idx + 1,
                        }
                    )
                _trace_phase_timing(
                    trace,
                    scope="llm",
                    phase=pdca_phase,
                    elapsed_ms=(time.perf_counter() - t_llm) * 1000.0,
                    round_idx=round_idx + 1,
                    channel=str(entry.get("channel") or "") or None,
                    tool_call_count=int(entry.get("tool_call_count") or 0) or None,
                )
                last_text = text
                last_entry = entry

                if entry.get("skipped"):
                    break

                if not calls:
                    break

                view = resolve_tool_runtime_view(
                    pre_tool=self._pre_tool,
                    tool_command_context=self._tool_command_context,
                    budgets=self._tool_budgets,
                    counters=counters,
                )
                if not view.can_execute:
                    trace.append(
                        {
                            "step": "tool_gather_skip",
                            "phase": pdca_phase,
                            "reason": view.reason,
                            "round": round_idx + 1,
                        }
                    )
                    break

                plan = tool_calls_to_invocation_plan(calls)
                assert view.executor is not None and view.tool_context is not None
                t_gather = time.perf_counter()
                obs_text, gather_entries = gather_tool_observations(
                    view.executor,
                    view.tool_context,
                    plan,
                    budgets=view.budgets,
                    counters=counters,
                    phase_label=pdca_phase,
                )
                trace.extend(gather_entries)
                _trace_phase_timing(
                    trace,
                    scope="tool_gather",
                    phase=pdca_phase,
                    elapsed_ms=(time.perf_counter() - t_gather) * 1000.0,
                    round_idx=round_idx + 1,
                )
                if obs_text:
                    cm = get_config()
                    if should_emit_aico_full_chain_logs(cm):
                        log_aico_tool_observations_text(
                            cm, phase=pdca_phase, observation_text=obs_text
                        )

                # Build ToolResults for the next round, mirroring executed calls.
                round_results: List[ToolResult] = []
                # Rebuild from per-call by replaying the executor would duplicate work,
                # so we reuse the gather_tool_observations trace entries — it preserves
                # the execution order and success flag.
                exec_entries = [
                    e for e in gather_entries if e.get("step") == "tool_exec"
                ]
                for i, e in enumerate(exec_entries):
                    if i >= len(calls):
                        break
                    c = calls[i]
                    round_results.append(
                        ToolResult(
                            id=c.id or f"call_{round_idx}_{i}",
                            name=c.name,
                            ok=bool(e.get("success", False)),
                            text=_extract_observation_text_for_call(obs_text, i + 1),
                        )
                    )
                all_results.extend(round_results)

                # Record assistant tool choices in a provider-neutral turn so HTTP
                # adapters can emit valid assistant tool_use / tool_result pairs
                # (Anthropic-style APIs reject tool_result without matching tool_use).
                turns.append(
                    AssistantToolUseTurn(
                        text=text or "",
                        tool_calls=[ToolCall(id=c.id, name=c.name, args=list(c.args)) for c in calls],
                    )
                )
                turns.append(ToolResultsTurn(results=round_results))
                obs_chunks.append(obs_text)

                # Budget exhaustion in mid-loop: stop before next LLM call.
                if (
                    counters.commands_run >= self._tool_budgets.max_commands_per_tick
                    or counters.observation_chars
                    >= self._tool_budgets.max_chars_observations_per_tick
                ):
                    break
        finally:
            _trace_phase_timing(
                trace,
                scope="phase_total",
                phase=pdca_phase,
                elapsed_ms=(time.perf_counter() - t_phase) * 1000.0,
            )

        return last_text, "\n\n".join(o for o in obs_chunks if o), all_results, last_entry

    # -------------------- top-level run --------------------

    def run(self, ctx: FrameworkRunContext) -> FrameworkRunResult:
        run_id = uuid.uuid4()
        trace: List[Dict[str, Any]] = []
        correlation = ctx.correlation_id or ctx.payload.get("correlation_id")
        user_msg = str(ctx.payload.get("message") or ctx.payload.get("text") or "").strip()
        gather_counters = ToolGatherCounters()
        corr_s = correlation if isinstance(correlation, str) else None
        set_aico_observability_context(run_id=str(run_id), correlation_id=corr_s)
        try:
            return self._run_inner(ctx, run_id, trace, user_msg, gather_counters, correlation)
        finally:
            clear_aico_observability_context()

    def _run_inner(
        self,
        ctx: FrameworkRunContext,
        run_id: uuid.UUID,
        trace: List[Dict[str, Any]],
        user_msg: str,
        gather_counters: ToolGatherCounters,
        correlation: Any,
    ) -> FrameworkRunResult:
        self._memory.start_run(
            run_id=run_id,
            correlation_id=correlation if isinstance(correlation, str) else None,
            phase=PDCAPhase.plan.value,
            command_trace=list(trace),
            status="running",
        )

        base_system = (ctx.system_prompt or self._cfg.system_prompt or "").strip()
        merged_phases = _merge_phase_prompts(dict(self._cfg.phase_prompts), ctx.phase_prompts)

        mem = (ctx.memory_context or "").strip()
        world_snapshot = str(ctx.payload.get("world_snapshot") or "").strip()
        tool_manifest_text = str(ctx.payload.get("tool_manifest_text") or "").strip()

        plan_user = _assemble_plan_user(
            user_msg=user_msg,
            memory=mem,
            world_snapshot=world_snapshot,
            tool_manifest_text=tool_manifest_text,
        )

        # ---------------- PLAN ----------------
        self._tick_hooks.on_before_phase(ThinkingPhaseId.plan, ctx)
        plan_sys = _phase_system(base_system, PDCAPhase.plan.value, merged_phases)
        plan_out, plan_tools_text, _plan_results, plan_entry = self._phase_react_loop(
            PDCAPhase.plan.value, plan_sys, plan_user, ctx, gather_counters, trace
        )
        self._memory.update_run(run_id, PDCAPhase.plan.value, trace, "running")
        self._tick_hooks.on_after_phase(
            ThinkingPhaseId.plan,
            ctx,
            phase_llm_output=plan_out or "",
            skipped=bool(plan_entry.get("skipped")),
        )
        if plan_tools_text:
            trace.append({"step": "plan_tool_observations", "chars": len(plan_tools_text)})

        # ---------------- DO ----------------
        plan_block = (plan_out or "").strip()
        tool_blocks_plan = (
            f"\n\nTool observations (plan phase):\n{plan_tools_text}" if plan_tools_text else ""
        )
        self._tick_hooks.on_before_phase(ThinkingPhaseId.do, ctx)
        if plan_block:
            do_user = (
                f"User message:\n{user_msg}\n\nPlan:\n{plan_out}\n{tool_blocks_plan}\n\n"
                f"Memory:\n{mem or '(none)'}"
            )
        else:
            do_user = (
                f"User message:\n{user_msg}{tool_blocks_plan}\n\nMemory:\n{mem or '(none)'}"
            )
        do_sys = _phase_system(base_system, PDCAPhase.do.value, merged_phases)
        reply, do_tools_text, _do_results, do_entry = self._phase_react_loop(
            PDCAPhase.do.value, do_sys, do_user, ctx, gather_counters, trace
        )
        self._memory.update_run(run_id, PDCAPhase.do.value, trace, "running")
        self._tick_hooks.on_after_phase(
            ThinkingPhaseId.do,
            ctx,
            phase_llm_output=reply or "",
            skipped=bool(do_entry.get("skipped")),
        )
        if do_tools_text:
            trace.append({"step": "do_tool_observations", "chars": len(do_tools_text)})

        # ---------------- CHECK (guardrail + optional RETRY) ----------------
        tool_blocks_do = (
            f"\n\nTool observations (do phase):\n{do_tools_text}" if do_tools_text else ""
        )
        check_user = (
            f"User message:\n{user_msg}\n\nDraft reply:\n{reply}{tool_blocks_do}"
        )
        check_sys = _phase_system(base_system, PDCAPhase.check.value, merged_phases)
        self._tick_hooks.on_before_phase(ThinkingPhaseId.check, ctx)
        t_check = time.perf_counter()
        check_out, check_entry = self._call_llm(
            PDCAPhase.check.value, check_sys, check_user, ctx
        )
        _trace_phase_timing(
            trace,
            scope="llm",
            phase=PDCAPhase.check.value,
            elapsed_ms=(time.perf_counter() - t_check) * 1000.0,
        )
        retry_tools = (
            None if check_entry.get("skipped") else _parse_check_retry_signal(check_out or "")
        )
        if check_entry.get("skipped"):
            ok = True
        else:
            co = check_out or ""
            # Presence of RETRY is itself not a failure of the reply; failure
            # is literal "error" at the head of the check message.
            ok = "error" not in co.lower()[:80]
        check_entry["passed"] = ok
        if retry_tools is not None:
            check_entry["retry_tools"] = retry_tools
        trace.append(check_entry)
        self._memory.update_run(run_id, PDCAPhase.check.value, trace, "running")
        self._tick_hooks.on_after_phase(
            ThinkingPhaseId.check,
            ctx,
            phase_llm_output=check_out or "",
            skipped=bool(check_entry.get("skipped")),
        )

        final_text = reply

        # If Check asked for a retry and budget allows, re-run Plan → Do once.
        if (
            retry_tools is not None
            and gather_counters.commands_run < self._tool_budgets.max_commands_per_tick
        ):
            retry_hint = (
                "Check phase flagged that tool observations are required to answer. "
                f"Requested tools: {', '.join(retry_tools) or '(any)'}."
            )
            trace.append({"step": "check_retry_triggered", "tools": retry_tools})
            plan2_user = (
                f"{plan_user}\n\nGuardrail note:\n{retry_hint}\nEmit a tool call plan now."
            )
            plan2_out, plan2_tools_text, _pr2, plan2_entry = self._phase_react_loop(
                PDCAPhase.plan.value, plan_sys, plan2_user, ctx, gather_counters, trace
            )
            if plan2_tools_text:
                trace.append({"step": "plan_retry_tool_observations", "chars": len(plan2_tools_text)})
            do2_blocks = (
                f"\n\nTool observations (plan retry):\n{plan2_tools_text}"
                if plan2_tools_text
                else ""
            )
            do2_user = (
                f"User message:\n{user_msg}\n\nPlan:\n{plan2_out or plan_out}\n{do2_blocks}\n\n"
                f"Memory:\n{mem or '(none)'}"
            )
            reply2, do2_tools_text, _dr2, _de2 = self._phase_react_loop(
                PDCAPhase.do.value, do_sys, do2_user, ctx, gather_counters, trace
            )
            if reply2.strip():
                final_text = reply2
            if do2_tools_text:
                trace.append({"step": "do_retry_tool_observations", "chars": len(do2_tools_text)})

        # ---------------- ACT ----------------
        self._tick_hooks.on_before_phase(ThinkingPhaseId.action, ctx)
        tool_blocks_check = (
            ""  # Check itself no longer triggers its own tool loop — guardrail only.
        )
        act_user = (
            f"User message:\n{user_msg}\n\nDraft reply:\n{final_text}{tool_blocks_check}\n\n"
            f"Polish for final user-facing text."
        )
        act_sys = _phase_system(base_system, PDCAPhase.act.value, merged_phases)
        t_act = time.perf_counter()
        act_out, act_entry = self._call_llm(PDCAPhase.act.value, act_sys, act_user, ctx)
        _trace_phase_timing(
            trace,
            scope="llm",
            phase=PDCAPhase.act.value,
            elapsed_ms=(time.perf_counter() - t_act) * 1000.0,
        )
        if not act_entry.get("skipped") and (act_out or "").strip():
            final_text = act_out.strip()
        act_entry["step"] = PDCAPhase.act.value
        act_entry["final_reply"] = final_text
        trace.append(act_entry)
        self._tick_hooks.on_after_phase(
            ThinkingPhaseId.action,
            ctx,
            phase_llm_output=act_out or "",
            skipped=bool(act_entry.get("skipped")),
        )

        if user_msg and not (final_text or "").strip():
            final_text = _resolve_npc_agent_empty_reply_message(self._cfg)
            act_entry["final_reply"] = final_text
            trace.append(
                {
                    "step": "empty_reply_fallback",
                    "user_message_len": len(user_msg),
                }
            )

        self._memory.finish_run(
            run_id,
            PDCAPhase.act.value,
            trace,
            "success" if ok else "failed",
            graph_ops_summary={"reply_excerpt": (final_text or "")[:500]},
        )

        self._memory.append_raw(
            "audit",
            {
                "framework": self.framework_id,
                "run_id": str(run_id),
                "ok": ok,
            },
        )

        self._tick_hooks.on_before_phase(ThinkingPhaseId.post, ctx)
        self._tick_hooks.on_after_phase(
            ThinkingPhaseId.post,
            ctx,
            phase_llm_output=final_text,
            skipped=False,
        )

        return FrameworkRunResult(
            ok=ok,
            message=final_text,
            final_phase=PDCAPhase.act.value,
        )


# ----------------------- module-local helpers -----------------------


def _tool_calls_from_text(text: str) -> List[ToolCall]:
    """Parse JSON ``{"commands": [...]}`` text and convert to neutral ToolCalls."""
    plan: ToolInvocationPlan = parse_tool_invocation_plan_from_text(text or "")
    out: List[ToolCall] = []
    for i, (name, args) in enumerate(plan.commands):
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
            parts.append(t.text or "")
        elif isinstance(t, AssistantToolUseTurn):
            block = assistant_tool_use_turn_as_text_block(t)
            if block:
                parts.append(block)
        elif isinstance(t, ToolResultsTurn):
            block = tool_results_turn_as_text_block(t)
            if block:
                parts.append("Tool observations:\n" + block)
    return "\n\n".join(p for p in parts if p.strip())


def _extract_observation_text_for_call(full_text: str, index: int) -> str:
    """Slice a single observation block out of the concatenated gather text.

    ``gather_tool_observations`` emits one block per call delimited by
    ``--- tool_observation begin ---`` / ``--- tool_observation end ---``
    and numbered ``[<i>]``. For the ReAct loop we need each call's text
    attached to its ``ToolResult`` id, so we re-slice by index.
    """
    if not full_text:
        return ""
    marker = f"[{index}]"
    start = full_text.find(marker)
    if start < 0:
        return full_text
    end_marker = "--- tool_observation end ---"
    end = full_text.find(end_marker, start)
    if end < 0:
        return full_text[start:]
    return full_text[start : end + len(end_marker)]


def _assemble_plan_user(
    *,
    user_msg: str,
    memory: str,
    world_snapshot: str,
    tool_manifest_text: str,
) -> str:
    """Build the first Plan user turn.

    Order (Anthropic's "place the most actionable facts nearest the user
    instruction" guidance):

    1. World snapshot (caller identity, location, installed worlds).
    2. Tools available (manifest summary).
    3. Retrieved memory (LTM or empty).
    4. User message.
    """
    segments: List[str] = []
    if world_snapshot:
        segments.append(f"World snapshot:\n{world_snapshot}")
    if tool_manifest_text:
        segments.append(f"Tools available:\n{tool_manifest_text}")
    segments.append(f"Retrieved memory (may be empty):\n{memory or '(none)'}")
    segments.append(f"User message:\n{user_msg}")
    return "\n\n".join(segments)
