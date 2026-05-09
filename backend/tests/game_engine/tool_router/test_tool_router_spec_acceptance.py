"""Acceptance-style tests for the tool-router SPEC (enrich query, router payloads, PDCA wiring).

Hermetic: no network, no DB, fake LLM only.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import pytest

from app.core.settings import AgentLlmServiceConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
from app.game_engine.agent_runtime.tool_calling import ToolSchema
from app.game_engine.agent_runtime.tool_router.enrich_query import build_enrich_query_text
from app.game_engine.agent_runtime.tool_router.router_result import (
    CandidateTier,
    EnforcementLevel,
    RouterCandidate,
    RouterResult,
)


class _FakeMem:
    def __init__(self) -> None:
        self.runs: List[Dict[str, Any]] = []

    def start_run(self, run_id, correlation_id, phase, command_trace, status) -> None:
        self.runs.append({"op": "start", "run_id": run_id, "trace": list(command_trace)})

    def update_run(self, run_id, phase, command_trace, status, graph_ops_summary=None) -> None:
        self.runs.append({"op": "update", "run_id": run_id, "trace": list(command_trace)})

    def finish_run(self, run_id, phase, command_trace, status, graph_ops_summary=None) -> None:
        self.runs.append({"op": "finish", "run_id": run_id, "trace": list(command_trace)})

    def append_raw(self, kind: str, payload: Dict[str, Any], session_id: Optional[uuid.UUID] = None) -> None:
        pass


def _final_trace(mem: _FakeMem) -> List[Dict[str, Any]]:
    for r in reversed(mem.runs):
        if r["op"] == "finish":
            return list(r["trace"])
    return []


def _basic_cfg(**extra: Any) -> AgentLlmServiceConfig:
    return AgentLlmServiceConfig(
        system_prompt="Sys",
        phase_prompts={"plan": "P", "do": "D", "check": "C", "act": "A"},
        extra=dict(extra),
    )


class _RecordingFirstPlanUser:
    """Captures the first ``complete`` user segment (Plan phase, round 1)."""

    def __init__(self) -> None:
        self.first_plan_user: Optional[str] = None
        self._calls = 0

    def complete(self, *, system: str, user: str, call_spec=None) -> str:
        self._calls += 1
        if self._calls == 1:
            self.first_plan_user = user
        return "stub"


class _SeqLlm:
    """Fixed responses in order: Plan, Do, Check, Act (one round each, no tools)."""

    def __init__(self, tail: Optional[List[str]] = None) -> None:
        self._seq = list(tail or ["plan prose", "do draft", "check ok", "act final"])
        self.i = 0

    def complete(self, *, system: str, user: str, call_spec=None) -> str:
        out = self._seq[self.i] if self.i < len(self._seq) else "tail"
        self.i += 1
        return out


@pytest.mark.unit
def test_enrich_query_orders_snapshot_before_stm_before_user() -> None:
    """SPEC: world_snapshot authoritative; STM supplements; both precede raw user line."""
    text = build_enrich_query_text(
        user_message="whoami",
        world_snapshot="room: hub",
        stm_snippet="prior turn summary",
        rule_hints=["movement_tokens:n"],
        entity_spans=["Zone A"],
        lexicon_hits=["hub"],
    )
    i_ws = text.index("World snapshot:")
    i_stm = text.index("STM snippet:")
    i_um = text.index("User message:")
    assert i_ws < i_stm < i_um


@pytest.mark.unit
def test_router_result_payload_and_trace_contract_keys() -> None:
    rr = RouterResult(
        candidates=[RouterCandidate(tool_name="look", score=0.9, tier=CandidateTier.embedding)],
        mandatory_tool_names=["whoami"],
        suggested_tool_names=["help"],
        router_confidence=0.5,
        source="rule+embedding",
        clarify=False,
        lexicon_active_id="lex-1",
        threshold_revision="v2026-01",
        tool_registry_revision="abc123",
        latency_ms=12.3,
        enrich_query_text="",
        enforcement_level=EnforcementLevel.schema_subset,
    )
    payload = rr.to_payload_dict()
    trace = rr.to_trace_dict()
    assert set(payload.keys()) >= {
        "candidates",
        "mandatory_tool_names",
        "suggested_tool_names",
        "router_confidence",
        "source",
        "clarify",
        "lexicon_active_id",
        "threshold_revision",
        "tool_registry_revision",
        "latency_ms",
        "enforcement_level",
    }
    assert set(trace.keys()) >= {
        "tool_router_source",
        "tool_router_confidence",
        "tool_router_clarify",
        "tool_router_lexicon_active_id",
        "tool_router_threshold_revision",
        "tool_router_registry_revision",
        "tool_router_latency_ms",
        "tool_router_enforcement",
        "tool_router_mandatory",
        "tool_router_top_candidates",
    }
    assert trace["tool_router_enforcement"] == EnforcementLevel.schema_subset.value


@pytest.mark.unit
def test_llm_pdca_injects_tool_router_hint_when_enabled() -> None:
    mem = _FakeMem()
    rec = _RecordingFirstPlanUser()
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=_basic_cfg(tool_router={"enabled": True}),
        instance_phase_llm={},
        instance_mode_models={},
        llm=rec,
        tool_schemas=[
            ToolSchema(name="whoami", description="identity"),
            ToolSchema(name="look", description="room"),
        ],
    )
    fw.run(
        FrameworkRunContext(
            agent_node_id=1,
            payload={"message": "whoami", "world_snapshot": ""},
        )
    )
    assert rec.first_plan_user is not None
    assert "Tool router (pre-Plan):" in rec.first_plan_user


@pytest.mark.unit
def test_llm_pdca_mandatory_gap_trace_and_user_notice_when_plan_skips_tools() -> None:
    """When rules mark whoami mandatory but Plan emits no tool observations, trace + suffix."""
    mem = _FakeMem()
    llm = _SeqLlm()
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=_basic_cfg(tool_router={"enabled": True}),
        instance_phase_llm={},
        instance_mode_models={},
        llm=llm,
        tool_schemas=[
            ToolSchema(name="whoami", description="identity"),
            ToolSchema(name="look", description="room"),
        ],
    )
    out = fw.run(
        FrameworkRunContext(
            agent_node_id=1,
            payload={"message": "whoami", "world_snapshot": ""},
        )
    )
    trace = _final_trace(mem)
    steps = [e.get("step") for e in trace if isinstance(e, dict)]
    assert "tool_router" in steps
    assert "mandatory_observation_gap" in steps
    gap = next(e for e in trace if isinstance(e, dict) and e.get("step") == "mandatory_observation_gap")
    assert "whoami" in (gap.get("missing") or []) or "whoami" in (gap.get("failed") or [])
    assert out.ok
    assert "【系统提示】" in (out.message or "")
    assert "whoami" in (out.message or "")


@pytest.mark.unit
def test_llm_pdca_schema_subset_surfaces_enforcement_in_tool_router_trace() -> None:
    mem = _FakeMem()
    llm = _SeqLlm()
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=_basic_cfg(
            tool_router={"enabled": True, "enforcement_level": "schema_subset"}
        ),
        instance_phase_llm={},
        instance_mode_models={},
        llm=llm,
        tool_schemas=[
            ToolSchema(name="whoami", description="identity"),
            ToolSchema(name="look", description="room"),
        ],
    )
    fw.run(
        FrameworkRunContext(
            agent_node_id=1,
            payload={"message": "hello", "world_snapshot": ""},
        )
    )
    trace = _final_trace(mem)
    tr_entry = next(e for e in trace if isinstance(e, dict) and e.get("step") == "tool_router")
    assert tr_entry.get("tool_router_enforcement") == EnforcementLevel.schema_subset.value
