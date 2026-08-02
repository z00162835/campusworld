"""Unit tests for workflow_loader."""
from __future__ import annotations

import json

import pytest

from app.game_engine.agent_runtime.state_machine import (
    StateMachineSnapshot,
    TransitionContext,
    build_pdca_state_machine,
    load_state_machine_from_attributes,
)
from app.game_engine.agent_runtime.state_machine.workflow_loader import load_workflow


@pytest.mark.unit
def test_missing_workflow_falls_back_to_pdca():
    sm = load_state_machine_from_attributes({})
    pdca = build_pdca_state_machine()
    assert sm.initial == pdca.initial
    assert {s.id for s in sm.states} == {s.id for s in pdca.states}


@pytest.mark.unit
def test_pdcp_mode_without_stages():
    sm = load_workflow({"mode": "pdcp", "replan": {"max": 2}})
    assert sm.max_replans == 2
    assert sm.initial == "plan"


@pytest.mark.unit
def test_json_string_workflow():
    raw = json.dumps({"mode": "pdcp"})
    sm = load_state_machine_from_attributes({"workflow": raw})
    assert sm.initial == "plan"


@pytest.mark.unit
def test_custom_workflow_condition_transition():
    sm = load_workflow(
        {
            "mode": "react",
            "initial": "understand",
            "stages": [
                {"id": "understand", "skill": "problem_framing"},
                {"id": "answer", "skill": "final_synthesis", "exit": True},
            ],
            "transitions": [
                {
                    "from": "understand",
                    "to": "answer",
                    "when": "runtime.confidence >= 0.8",
                },
                {
                    "from": "understand",
                    "to": "understand",
                    "when": "runtime.confidence < 0.8",
                },
            ],
        }
    )
    assert sm.next(
        "understand",
        TransitionContext(
            snapshot=StateMachineSnapshot(current_state="understand"),
            runtime={"confidence": 0.9},
        ),
    ) == "answer"
    assert sm.next(
        "understand",
        TransitionContext(
            snapshot=StateMachineSnapshot(current_state="understand"),
            runtime={"confidence": 0.5},
        ),
    ) == "understand"


@pytest.mark.unit
def test_malformed_workflow_raises():
    with pytest.raises(ValueError):
        load_workflow({"mode": "react", "stages": "not-a-list"})
    with pytest.raises(ValueError):
        load_state_machine_from_attributes({"workflow": ["bad"]})


@pytest.mark.unit
def test_linear_custom_stages():
    sm = load_workflow(
        {
            "mode": "react",
            "stages": [
                {"id": "a"},
                {"id": "b", "exit": True},
            ],
        }
    )
    nxt = sm.next("a", TransitionContext(snapshot=StateMachineSnapshot(current_state="a"), runtime={}))
    assert nxt == "b"
    assert "fail" in sm.state_map()


@pytest.mark.unit
def test_worker_falls_back_to_pdca_for_non_pdca_workflow():
    """D3-A: non-PDCA workflow is parse-only; worker must execute PDCA."""
    from app.game_engine.agent_runtime.state_machine import (
        build_pdca_state_machine,
        is_pdca_executable,
        load_state_machine_from_attributes,
        non_pdca_state_ids,
    )

    custom = load_state_machine_from_attributes(
        {"workflow": {"mode": "react", "stages": [{"id": "understand"}, {"id": "answer", "exit": True}]}}
    )
    assert not is_pdca_executable(custom)
    assert non_pdca_state_ids(custom) == ["understand"]
    pdca = build_pdca_state_machine()
    assert is_pdca_executable(pdca)
    assert non_pdca_state_ids(pdca) == []
    # Worker guard would pick pdca over custom; this test pins the predicate.
    assert is_pdca_executable(load_state_machine_from_attributes({})) is True
    assert is_pdca_executable(load_state_machine_from_attributes({"workflow": {"mode": "pdcp"}})) is True


@pytest.mark.unit
def test_is_pdca_executable_accepts_extra_exit_state():
    """Extra exit/terminal states are harmless (driver breaks on them)."""
    from app.game_engine.agent_runtime.state_machine import (
        StateDef,
        StateMachine,
        Transition,
        is_pdca_executable,
        non_pdca_state_ids,
    )

    sm = StateMachine(
        states=(
            StateDef(id="plan", phase_llm_key="plan"),
            StateDef(id="do", phase_llm_key="do"),
            StateDef(id="check", phase_llm_key="check"),
            StateDef(id="act", phase_llm_key="act"),
            StateDef(id="end", exit=True),
            StateDef(id="fail", exit=True),
            StateDef(id="aborted", exit=True),  # extra terminal alias
        ),
        transitions=(Transition(from_state="act", to_state="end"),),
        initial="plan",
    )
    assert is_pdca_executable(sm) is True
    assert non_pdca_state_ids(sm) == []
