from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from app.game_engine.agent_runtime.frameworks.base import (
    FrameworkRunContext,
    FrameworkRunResult,
    ThinkingFramework,
)
from app.game_engine.agent_runtime.memory_port import MemoryPort
from app.game_engine.agent_runtime.tooling import ToolExecutor


class PDCAPhase(str, Enum):
    plan = "plan"
    do = "do"
    check = "check"
    act = "act"


class PDCAFramework(ThinkingFramework):
    """
    Plan → Do → Check → Act. Sample D (rules): high-severity ticket → record
    `graph.patch_device_state` in command_trace (placeholder command name per F02).
    """

    def __init__(self, memory: MemoryPort, tools: Optional[ToolExecutor] = None):
        self._memory = memory
        self._tools = tools

    @property
    def framework_id(self) -> str:
        return "PDCA"

    def run(self, ctx: FrameworkRunContext) -> FrameworkRunResult:
        run_id = uuid.uuid4()
        trace: List[Dict[str, Any]] = []
        correlation = ctx.correlation_id or ctx.payload.get("ticket_id")

        self._memory.start_run(
            run_id=run_id,
            correlation_id=correlation,
            phase=PDCAPhase.plan.value,
            command_trace=list(trace),
            status="running",
        )

        # Plan
        trace.append({"step": "plan", "intent": "evaluate_ticket", "payload": ctx.payload})
        self._memory.update_run(
            run_id,
            PDCAPhase.plan.value,
            trace,
            "running",
        )

        # Do — rules path (F02 sample D)
        severity = str(ctx.payload.get("severity", "")).lower()
        device_node_id = ctx.payload.get("device_node_id")
        patch: Dict[str, Any] = {}
        if severity in ("high", "critical", "sev1"):
            patch = {"operational": False, "reason": "ticket_severity"}
        cmd_entry: Dict[str, Any] = {
            "command": "graph.patch_device_state",
            "args": [str(device_node_id)] if device_node_id is not None else [],
            "patch": patch,
        }
        trace.append(cmd_entry)
        self._memory.update_run(
            run_id,
            PDCAPhase.do.value,
            trace,
            "running",
            graph_ops_summary={"patched_nodes": [device_node_id] if device_node_id else []},
        )

        # Check (minimal rules validation)
        ok = True
        trace.append({"step": "check", "passed": ok})
        self._memory.update_run(
            run_id,
            PDCAPhase.check.value,
            trace,
            "running",
        )

        # Act
        trace.append({"step": "act", "committed": ok})
        summary = {"ticket_id": ctx.payload.get("ticket_id"), "device_node_id": device_node_id}
        self._memory.finish_run(
            run_id,
            PDCAPhase.act.value,
            trace,
            "success" if ok else "failed",
            graph_ops_summary=summary,
        )

        self._memory.append_raw(
            "audit",
            {"framework": "PDCA", "run_id": str(run_id), "result": "success" if ok else "failed"},
        )

        return FrameworkRunResult(ok=ok, message="PDCA completed", final_phase=PDCAPhase.act.value)
