from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from app.commands.base import CommandContext
from app.core.settings import AgentLlmServiceConfig, PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.frameworks.base import (
    FrameworkRunContext,
    FrameworkRunResult,
    ThinkingFramework,
)
from app.game_engine.agent_runtime.frameworks.pdca import PDCAPhase
from app.game_engine.agent_runtime.llm_client import LlmClient, StubLlmClient
from app.game_engine.agent_runtime.memory_port import MemoryPort
from app.game_engine.agent_runtime.phase_llm_resolve import merge_phase_config, to_llm_call_spec
from app.game_engine.agent_runtime.resolved_tool_surface import PreauthorizedToolExecutor
from app.game_engine.agent_runtime.thinking_pipeline import AgentTickHooks, NoOpAgentTickHooks, ThinkingPhaseId
from app.game_engine.agent_runtime.tool_gather import (
    ToolGatherBudgets,
    ToolGatherCounters,
    gather_tool_observations,
    parse_tool_invocation_plan_from_text,
    tool_gather_budgets_from_agent_extra,
)
from app.game_engine.agent_runtime.tooling import ToolExecutor


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


class LlmPDCAFramework(ThinkingFramework):
    """
    PDCA with optional LLM calls per phase (assistant / llm decision_mode path).

    Per-phase mode: fast | plan | think | skip from npc_agent.attributes.phase_llm (+ tick overrides).

    When ``preauthorized_tool_executor`` and ``tool_command_context`` are set, ToolGather runs after
    each phase LLM call that returns a JSON tool plan (F08).
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

    @property
    def framework_id(self) -> str:
        return "PDCA_LLM"

    def _call_llm(
        self,
        phase: str,
        system: str,
        user: str,
        ctx: FrameworkRunContext,
    ) -> tuple[str, Dict[str, Any]]:
        pcfg = merge_phase_config(phase, self._instance_phase_llm, ctx.phase_llm_overrides)
        spec = to_llm_call_spec(
            pcfg,
            mode_models=self._instance_mode_models,
            default_model=(self._cfg.model or "").strip(),
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
        if not self._pre_tool or not self._tool_command_context:
            return ""
        plan = parse_tool_invocation_plan_from_text(llm_output or "")
        if not plan.commands:
            return ""
        text, entries = gather_tool_observations(
            self._pre_tool,
            self._tool_command_context,
            plan,
            budgets=self._tool_budgets,
            counters=counters,
            phase_label=pdca_phase,
        )
        trace.extend(entries)
        return text

    def run(self, ctx: FrameworkRunContext) -> FrameworkRunResult:
        run_id = uuid.uuid4()
        trace: List[Dict[str, Any]] = []
        correlation = ctx.correlation_id or ctx.payload.get("correlation_id")
        user_msg = str(ctx.payload.get("message") or ctx.payload.get("text") or "").strip()
        gather_counters = ToolGatherCounters()

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
        self._tick_hooks.on_before_phase(ThinkingPhaseId.plan, ctx)
        plan_user = f"User message:\n{user_msg}\n\nRetrieved memory (may be empty):\n{mem or '(none)'}"
        plan_sys = _phase_system(base_system, PDCAPhase.plan.value, merged_phases)
        plan_out, plan_entry = self._call_llm(PDCAPhase.plan.value, plan_sys, plan_user, ctx)
        trace.append(plan_entry)
        self._memory.update_run(run_id, PDCAPhase.plan.value, trace, "running")
        self._tick_hooks.on_after_phase(ThinkingPhaseId.plan, ctx, phase_llm_output=plan_out or "")

        plan_tools = self._gather_tools_after_llm(
            PDCAPhase.plan.value, plan_out or "", trace, gather_counters
        )
        if plan_tools:
            trace.append({"step": "plan_tool_observations", "chars": len(plan_tools)})

        plan_block = (plan_out or "").strip()
        tool_blocks_plan = f"\n\nTool observations (plan phase):\n{plan_tools}" if plan_tools else ""

        self._tick_hooks.on_before_phase(ThinkingPhaseId.do, ctx)
        if plan_block:
            do_user = (
                f"User message:\n{user_msg}\n\nPlan:\n{plan_out}\n{tool_blocks_plan}\n\n"
                f"Memory:\n{mem or '(none)'}"
            )
        else:
            do_user = (
                f"User message:\n{user_msg}\n{tool_blocks_plan}\n\nMemory:\n{mem or '(none)'}"
            )
        do_sys = _phase_system(base_system, PDCAPhase.do.value, merged_phases)
        reply, do_entry = self._call_llm(PDCAPhase.do.value, do_sys, do_user, ctx)
        trace.append(do_entry)
        self._memory.update_run(run_id, PDCAPhase.do.value, trace, "running")
        self._tick_hooks.on_after_phase(ThinkingPhaseId.do, ctx, phase_llm_output=reply or "")

        do_tools = self._gather_tools_after_llm(PDCAPhase.do.value, reply or "", trace, gather_counters)
        if do_tools:
            trace.append({"step": "do_tool_observations", "chars": len(do_tools)})
        tool_blocks_do = f"\n\nTool observations (do phase):\n{do_tools}" if do_tools else ""

        self._tick_hooks.on_before_phase(ThinkingPhaseId.check, ctx)
        check_user = (
            f"User message:\n{user_msg}\n\nDraft reply:\n{reply}{tool_blocks_do}"
        )
        check_sys = _phase_system(base_system, PDCAPhase.check.value, merged_phases)
        check_out, check_entry = self._call_llm(PDCAPhase.check.value, check_sys, check_user, ctx)
        if check_entry.get("skipped"):
            ok = True
        else:
            co = check_out or ""
            ok = "error" not in co.lower()[:80]
        check_entry["passed"] = ok
        trace.append(check_entry)
        self._memory.update_run(run_id, PDCAPhase.check.value, trace, "running")
        self._tick_hooks.on_after_phase(ThinkingPhaseId.check, ctx, phase_llm_output=check_out or "")

        check_tools = self._gather_tools_after_llm(
            PDCAPhase.check.value, check_out or "", trace, gather_counters
        )
        if check_tools:
            trace.append({"step": "check_tool_observations", "chars": len(check_tools)})
        tool_blocks_check = f"\n\nTool observations (check phase):\n{check_tools}" if check_tools else ""

        final_text = reply
        self._tick_hooks.on_before_phase(ThinkingPhaseId.action, ctx)
        act_user = (
            f"User message:\n{user_msg}\n\nDraft reply:\n{reply}{tool_blocks_check}\n\n"
            f"Polish for final user-facing text."
        )
        act_sys = _phase_system(base_system, PDCAPhase.act.value, merged_phases)
        act_out, act_entry = self._call_llm(PDCAPhase.act.value, act_sys, act_user, ctx)
        if not act_entry.get("skipped") and act_out.strip():
            final_text = act_out.strip()
        act_entry["step"] = PDCAPhase.act.value
        act_entry["final_reply"] = final_text
        trace.append(act_entry)
        self._tick_hooks.on_after_phase(ThinkingPhaseId.action, ctx, phase_llm_output=act_out or "")

        self._memory.finish_run(
            run_id,
            PDCAPhase.act.value,
            trace,
            "success" if ok else "failed",
            graph_ops_summary={"reply_excerpt": final_text[:500]},
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
        self._tick_hooks.on_after_phase(ThinkingPhaseId.post, ctx, phase_llm_output=final_text)

        return FrameworkRunResult(
            ok=ok,
            message=final_text,
            final_phase=PDCAPhase.act.value,
        )
