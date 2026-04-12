"""Unit tests for PDCA framework (no database)."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import pytest

from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks.pdca import PDCAFramework, PDCAPhase
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
def test_pdca_high_severity_adds_patch_command():
    mem = _FakeMem()
    fw = PDCAFramework(memory=mem)
    ctx = FrameworkRunContext(
        agent_node_id=1,
        correlation_id="T-1001",
        payload={"ticket_id": "T-1001", "severity": "high", "device_node_id": 42},
    )
    res = fw.run(ctx)
    assert res.ok
    finish = [r for r in mem.runs if r["op"] == "finish"][-1]
    assert finish["phase"] == PDCAPhase.act.value
    cmds = [x for x in finish["trace"] if x.get("command") == "graph.patch_device_state"]
    assert cmds
    assert cmds[0]["patch"] == {"operational": False, "reason": "ticket_severity"}


@pytest.mark.unit
def test_pdca_low_severity_empty_patch():
    mem = _FakeMem()
    fw = PDCAFramework(memory=mem)
    ctx = FrameworkRunContext(
        agent_node_id=1,
        payload={"ticket_id": "T-2", "severity": "low", "device_node_id": 1},
    )
    fw.run(ctx)
    finish = [r for r in mem.runs if r["op"] == "finish"][-1]
    cmd = next(x for x in finish["trace"] if x.get("command") == "graph.patch_device_state")
    assert cmd.get("patch") == {}
