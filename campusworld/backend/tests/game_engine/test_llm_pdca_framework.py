"""Unit tests for LlmPDCAFramework (no database, stub LLM)."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import pytest

from app.core.settings import AgentLlmServiceConfig, PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
from app.game_engine.agent_runtime.frameworks.pdca import PDCAPhase
from app.game_engine.agent_runtime.llm_client import StubLlmClient


class _FakeMem:
    def __init__(self) -> None:
        self.runs: List[Dict[str, Any]] = []
        self.raw: List[Dict[str, Any]] = []

    def start_run(self, run_id, correlation_id, phase, command_trace, status) -> None:
        self.runs.append(
            {"op": "start", "run_id": run_id, "phase": phase, "trace": list(command_trace), "status": status}
        )

    def update_run(self, run_id, phase, command_trace, status, graph_ops_summary=None) -> None:
        self.runs.append(
            {
                "op": "update",
                "run_id": run_id,
                "phase": phase,
                "trace": list(command_trace),
                "status": status,
                "graph_ops_summary": graph_ops_summary,
            }
        )

    def finish_run(self, run_id, phase, command_trace, status, graph_ops_summary=None) -> None:
        self.runs.append(
            {
                "op": "finish",
                "run_id": run_id,
                "phase": phase,
                "trace": list(command_trace),
                "status": status,
                "graph_ops_summary": graph_ops_summary,
            }
        )

    def append_raw(self, kind: str, payload: Dict[str, Any], session_id: Optional[uuid.UUID] = None) -> None:
        self.raw.append({"kind": kind, "payload": payload})


@pytest.mark.unit
def test_llm_pdca_runs_four_phases_and_returns_reply():
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
    ctx = FrameworkRunContext(
        agent_node_id=1,
        correlation_id="c1",
        payload={"message": "What is CampusWorld?"},
        memory_context="prior note about rooms",
    )
    res = fw.run(ctx)
    assert res.ok
    assert res.final_phase == PDCAPhase.act.value
    assert "[stub_llm" in res.message
    finish = [r for r in mem.runs if r["op"] == "finish"][-1]
    steps = [x.get("step") for x in finish["trace"] if isinstance(x, dict) and "step" in x]
    assert "plan" in steps and "do" in steps and "check" in steps and "act" in steps


class _RecordingLlm:
    def __init__(self) -> None:
        self.systems: List[str] = []
        self.calls = 0

    def complete(self, *, system: str, user: str, call_spec=None) -> str:
        self.calls += 1
        self.systems.append(system)
        return "ok"


@pytest.mark.unit
def test_llm_pdca_ctx_overrides_system_prompt():
    mem = _FakeMem()
    rec = _RecordingLlm()
    cfg = AgentLlmServiceConfig(system_prompt="BASE_ONLY")
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=cfg,
        instance_phase_llm={},
        instance_mode_models={},
        llm=rec,
    )
    ctx = FrameworkRunContext(
        agent_node_id=1,
        payload={"message": "hi"},
        system_prompt="CTX_OVERRIDE",
        phase_prompts={"plan": "suffix_plan"},
    )
    fw.run(ctx)
    assert rec.systems
    assert "CTX_OVERRIDE" in rec.systems[0]
    assert "suffix_plan" in rec.systems[0]


@pytest.mark.unit
def test_phase_llm_check_skip_skips_llm_call():
    mem = _FakeMem()
    rec = _RecordingLlm()
    cfg = AgentLlmServiceConfig(system_prompt="sys")
    instance_phase_llm = {
        "plan": PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan),
        "do": PhaseLlmPhaseConfig(mode=PhaseLlmMode.plan),
        "check": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
        "act": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
    }
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=cfg,
        instance_phase_llm=instance_phase_llm,
        instance_mode_models={},
        llm=rec,
    )
    fw.run(
        FrameworkRunContext(
            agent_node_id=1,
            payload={"message": "hello"},
        )
    )
    assert rec.calls == 2
    finish = [r for r in mem.runs if r["op"] == "finish"][-1]
    chk = next(x for x in finish["trace"] if isinstance(x, dict) and x.get("step") == "check")
    assert chk.get("skipped") is True
