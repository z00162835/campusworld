"""Tests for phase_timing rows appended to command_trace (F10 observability)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from app.core.settings import AgentLlmServiceConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
from app.game_engine.agent_runtime.frameworks.pdca import PDCAPhase
from app.game_engine.agent_runtime.llm_client import StubLlmClient


class _FakeMem:
    def __init__(self) -> None:
        self.runs: List[Dict[str, Any]] = []

    def start_run(self, run_id, correlation_id, phase, command_trace, status) -> None:
        self.runs.append({"op": "start", "trace": list(command_trace)})

    def update_run(self, run_id, phase, command_trace, status, graph_ops_summary=None) -> None:
        self.runs.append({"op": "update", "trace": list(command_trace)})

    def finish_run(self, run_id, phase, command_trace, status, graph_ops_summary=None) -> None:
        self.runs.append({"op": "finish", "trace": list(command_trace)})

    def append_raw(self, kind: str, payload: Dict[str, Any], session_id: Optional[Any] = None) -> None:
        pass


def _timing_rows(trace: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [x for x in trace if isinstance(x, dict) and x.get("step") == "phase_timing"]


@pytest.mark.unit
def test_phase_timing_rows_include_llm_round_and_phase_total():
    mem = _FakeMem()
    cfg = AgentLlmServiceConfig(
        system_prompt="You are a test assistant.",
        phase_prompts={
            "plan": "Plan step.",
            "do": "Answer step.",
            "check": "Check step.",
            "act": "Act step.",
        },
    )
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=cfg,
        instance_phase_llm={},
        instance_mode_models={},
        llm=StubLlmClient(),
    )
    fw.run(
        FrameworkRunContext(
            agent_node_id=1,
            correlation_id="c1",
            payload={"message": "ping"},
        )
    )
    finish = [r for r in mem.runs if r["op"] == "finish"][-1]
    trace = finish["trace"]
    timings = _timing_rows(trace)
    assert timings, "expected phase_timing rows in trace"

    plan_totals = [t for t in timings if t.get("scope") == "phase_total" and t.get("phase") == PDCAPhase.plan.value]
    do_totals = [t for t in timings if t.get("scope") == "phase_total" and t.get("phase") == PDCAPhase.do.value]
    assert len(plan_totals) == 1 and len(do_totals) == 1
    assert plan_totals[0]["elapsed_ms"] >= 0
    assert do_totals[0]["elapsed_ms"] >= 0

    plan_llm = [
        t
        for t in timings
        if t.get("scope") == "llm" and t.get("phase") == PDCAPhase.plan.value and t.get("round") == 1
    ]
    assert plan_llm, "expected plan round-1 llm timing"
    assert plan_llm[0]["elapsed_ms"] >= 0

    check_llm = [t for t in timings if t.get("scope") == "llm" and t.get("phase") == PDCAPhase.check.value]
    act_llm = [t for t in timings if t.get("scope") == "llm" and t.get("phase") == PDCAPhase.act.value]
    assert len(check_llm) == 1 and len(act_llm) == 1
