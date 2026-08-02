"""PDCA template transition coverage via StateMachine.next + framework fail path."""
from __future__ import annotations

import pytest

from app.core.settings import AgentLlmServiceConfig, PhaseLlmMode, PhaseLlmPhaseConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
from app.game_engine.agent_runtime.state_machine import (
    StateMachineSnapshot,
    TransitionContext,
    build_pdca_state_machine,
)


CASES = [
    ("plan", "do", {"do_mode": "fast"}, None, 0),
    ("plan", "check", {"do_mode": "skip"}, None, 0),
    ("plan", "act", {"do_mode": "skip"}, None, 1),
    ("do", "check", {}, None, 0),
    ("do", "act", {}, None, 1),
    ("check", "plan", {"budget_remaining": True}, "check_retry", 0),
    ("check", "plan", {"budget_remaining": True, "mandatory_gap_missing": True}, "mandatory_gap", 0),
    ("check", "act", {}, None, 0),
    ("act", "end", {}, None, 0),
    ("plan", "fail", {"cancelled": True}, None, 0),
    ("do", "fail", {"cancelled": True}, None, 0),
    # draft_incomplete aborts only from act (presentation anchor, SPEC §7.1);
    # from plan/do it must continue so downstream phases + mandatory-gap notice
    # remain reachable.
    ("act", "fail", {"draft_incomplete": True}, None, 0),
    ("plan", "do", {"draft_incomplete": True}, None, 0),
    ("do", "check", {"draft_incomplete": True}, None, 0),
]


@pytest.mark.unit
@pytest.mark.parametrize("frm,to,runtime,event,replan", CASES)
def test_pdca_transition_table(frm, to, runtime, event, replan):
    sm = build_pdca_state_machine()
    ctx = TransitionContext(
        snapshot=StateMachineSnapshot(current_state=frm, replan_count=replan),
        runtime=dict(runtime),
        event=event,
    )
    assert sm.next(frm, ctx) == to


class _FakeMem:
    def __init__(self) -> None:
        self.last_finish: tuple | None = None

    def start_run(self, *a, **k):
        import uuid

        return uuid.uuid4()

    def update_run(self, *a, **k):
        return None

    def finish_run(self, run_id, phase, command_trace, status, graph_ops_summary=None):
        self.last_finish = (phase, list(command_trace or []), status)

    def append_raw(self, *a, **k):
        return None


@pytest.mark.unit
def test_cancel_mid_tick_routes_through_fail_terminal():
    class _Slow:
        def complete(self, **kwargs):
            return "plan-text"

    mem = _FakeMem()
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=AgentLlmServiceConfig(
            system_prompt="Sys.",
            phase_prompts={"plan": "P", "do": "D", "check": "C", "act": "A"},
        ),
        instance_phase_llm={
            "do": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            "check": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            "act": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
        },
        instance_mode_models={},
        llm=_Slow(),
    )
    out = fw.run(
        FrameworkRunContext(
            agent_node_id=1,
            payload={"message": "hi"},
            stream_cancel_check=lambda: True,
        )
    )
    assert out.ok is False
    assert out.final_phase == "fail"
    assert out.error_code == "cancelled"
    assert mem.last_finish is not None
    phase, trace, status = mem.last_finish
    assert phase == "fail"
    assert status == "cancelled"
    assert any(e.get("step") == "state_transition" and e.get("to") == "fail" for e in trace)


@pytest.mark.unit
def test_deterministic_trace_for_same_scripted_llm():
    class _Scripted:
        def complete(self, **kwargs):
            return "same"

    def run_once():
        fw = LlmPDCAFramework(
            memory=_FakeMem(),
            llm_config=AgentLlmServiceConfig(
                system_prompt="Sys.",
                phase_prompts={"plan": "P", "do": "D", "check": "C", "act": "A"},
            ),
            instance_phase_llm={
                "do": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
                "check": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
                "act": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            },
            instance_mode_models={},
            llm=_Scripted(),
        )
        out = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
        return out.message

    assert run_once() == run_once()


@pytest.mark.unit
def test_state_transition_replan_count_on_check_retry():
    """D8: a replan transition's state_transition row records replan_count=1."""
    class _Scripted:
        def __init__(self, script: list[str]) -> None:
            self._script = list(script)
            self.calls = 0

        def complete(self, *, system: str, user: str, call_spec=None) -> str:
            if self.calls < len(self._script):
                out = self._script[self.calls]
            else:
                out = ""
            self.calls += 1
            return out

    script = ["plan-a", "RETRY: need_tools=whoami", "plan-retry-b"]
    mem = _FakeMem()
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=AgentLlmServiceConfig(
            system_prompt="Sys.",
            phase_prompts={"plan": "P", "do": "D", "check": "C", "act": "A"},
        ),
        instance_phase_llm={
            "do": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
        },
        instance_mode_models={},
        llm=_Scripted(script),
    )
    out = fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert out.ok
    assert mem.last_finish is not None
    _phase, trace, _status = mem.last_finish
    replan_rows = [
        e for e in trace
        if e.get("step") == "state_transition" and e.get("to") == "plan" and e.get("event") == "check_retry"
    ]
    assert replan_rows, "expected a check_retry replan transition"
    assert replan_rows[0].get("replan_count") == 1


@pytest.mark.unit
def test_fail_path_writes_audit_with_error_code():
    """D1-A: fail terminal writes audit payload with final_phase=fail + error_code."""
    mem = _FakeMem()
    audited: list = []
    mem.append_raw = lambda kind, payload, session_id=None: audited.append((kind, payload))
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=AgentLlmServiceConfig(
            system_prompt="Sys.",
            phase_prompts={"plan": "P", "do": "D", "check": "C", "act": "A"},
        ),
        instance_phase_llm={
            "do": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            "check": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            "act": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
        },
        instance_mode_models={},
        llm=type("_L", (), {"complete": staticmethod(lambda **k: "x")})(),
    )
    out = fw.run(
        FrameworkRunContext(
            agent_node_id=1,
            payload={"message": "hi"},
            stream_cancel_check=lambda: True,
        )
    )
    assert out.final_phase == "fail"
    assert out.error_code == "cancelled"
    audit = [p for (_k, p) in audited if isinstance(p, dict) and p.get("final_phase") == "fail"]
    assert audit, "audit must record final_phase=fail"
    assert audit[0]["error_code"] == "cancelled"


@pytest.mark.unit
def test_abort_path_does_not_emit_skip_do_draft():
    """P1b: abort (cancel) routes to fail without a synthetic do skipped draft."""
    mem = _FakeMem()

    class _Llm:
        def complete(self, **kwargs):
            return "plan prose"

    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=AgentLlmServiceConfig(
            system_prompt="Sys.",
            phase_prompts={"plan": "P", "do": "D", "check": "C", "act": "A"},
        ),
        instance_phase_llm={
            "do": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            "check": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
            "act": PhaseLlmPhaseConfig(mode=PhaseLlmMode.skip),
        },
        instance_mode_models={},
        llm=_Llm(),
    )
    out = fw.run(
        FrameworkRunContext(
            agent_node_id=1,
            payload={"message": "hi"},
            stream_cancel_check=lambda: True,
        )
    )
    assert out.final_phase == "fail"
    _phase, trace, _status = mem.last_finish
    # Abort must not synthesize a skipped `do` draft entry.
    assert not any(e.get("step") == "do" and e.get("skipped") for e in trace)
