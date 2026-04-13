from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from app.core.settings import AgentLlmServiceConfig, PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.frameworks.base import (
    FrameworkRunContext,
    FrameworkRunResult,
    ThinkingFramework,
)
from app.game_engine.agent_runtime.llm_client import LlmCallSpec, LlmClient, StubLlmClient
from app.game_engine.agent_runtime.memory_port import MemoryPort
from app.game_engine.agent_runtime.phase_llm_resolve import merge_phase_config, to_llm_call_spec
from app.game_engine.agent_runtime.tooling import ToolExecutor
from app.game_engine.agent_runtime.frameworks.pdca import PDCAPhase


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
    ):
        self._memory = memory
        self._cfg = llm_config
        self._instance_phase_llm = instance_phase_llm
        self._instance_mode_models = dict(instance_mode_models or {})
        self._llm = llm or StubLlmClient()
        self._tools = tools

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

    def run(self, ctx: FrameworkRunContext) -> FrameworkRunResult:
        run_id = uuid.uuid4()
        trace: List[Dict[str, Any]] = []
        correlation = ctx.correlation_id or ctx.payload.get("correlation_id")
        user_msg = str(ctx.payload.get("message") or ctx.payload.get("text") or "").strip()

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
        plan_user = f"User message:\n{user_msg}\n\nRetrieved memory (may be empty):\n{mem or '(none)'}"
        plan_sys = _phase_system(base_system, PDCAPhase.plan.value, merged_phases)
        plan_out, plan_entry = self._call_llm(PDCAPhase.plan.value, plan_sys, plan_user, ctx)
        trace.append(plan_entry)
        self._memory.update_run(run_id, PDCAPhase.plan.value, trace, "running")

        do_user = (
            f"User message:\n{user_msg}\n\nPlan:\n{plan_out}\n\nMemory:\n{mem or '(none)'}"
        )
        do_sys = _phase_system(base_system, PDCAPhase.do.value, merged_phases)
        reply, do_entry = self._call_llm(PDCAPhase.do.value, do_sys, do_user, ctx)
        trace.append(do_entry)
        self._memory.update_run(run_id, PDCAPhase.do.value, trace, "running")

        check_user = f"User message:\n{user_msg}\n\nDraft reply:\n{reply}"
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

        final_text = reply
        act_user = f"User message:\n{user_msg}\n\nDraft reply:\n{reply}\n\nPolish for final user-facing text."
        act_sys = _phase_system(base_system, PDCAPhase.act.value, merged_phases)
        act_out, act_entry = self._call_llm(PDCAPhase.act.value, act_sys, act_user, ctx)
        if not act_entry.get("skipped") and act_out.strip():
            final_text = act_out.strip()
        act_entry["step"] = PDCAPhase.act.value
        act_entry["final_reply"] = final_text
        trace.append(act_entry)

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

        return FrameworkRunResult(
            ok=ok,
            message=final_text,
            final_phase=PDCAPhase.act.value,
        )
