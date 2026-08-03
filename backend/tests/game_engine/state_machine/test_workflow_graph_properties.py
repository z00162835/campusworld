"""Transfer-graph property tests for arbitrary loaded workflows.

Default PDCA template coverage lives in ``test_pdca_template``; this module
covers custom workflows loaded via ``load_workflow`` /
``load_state_machine_from_attributes`` and the ``dead_states`` /
``has_path_to_terminal`` helpers on hand-built graphs (no auto wildcard).
"""
from __future__ import annotations

from typing import Set

import pytest

from app.game_engine.agent_runtime.state_machine import (
    StateDef,
    StateMachine,
    StateMachineSnapshot,
    Transition,
    TransitionContext,
    build_pdca_state_machine,
    load_state_machine_from_attributes,
)
from app.game_engine.agent_runtime.state_machine.workflow_loader import load_workflow


def _reachable_from_initial(sm: StateMachine) -> Set[str]:
    """BFS over transition edges from ``sm.initial`` (ignores conditions)."""
    seen: Set[str] = set()
    stack = [sm.initial]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        for tr in sm.transitions:
            if tr.from_state in (cur, "*") and tr.to_state not in seen:
                stack.append(tr.to_state)
    return seen


# --- Loader-produced workflows: graph invariants ----------------------------


@pytest.mark.unit
def test_default_pdca_via_loader_has_no_dead_states():
    sm = load_state_machine_from_attributes({})
    assert sm.dead_states() == ()


@pytest.mark.unit
def test_linear_custom_workflow_no_dead_states_and_all_reach_terminal():
    sm = load_workflow(
        {
            "mode": "react",
            "stages": [
                {"id": "a"},
                {"id": "b"},
                {"id": "c", "exit": True},
            ],
        }
    )
    assert sm.dead_states() == ()
    for s in sm.states:
        assert sm.has_path_to_terminal(s.id), f"{s.id} has no path to terminal"


@pytest.mark.unit
def test_custom_workflow_with_explicit_transitions_no_dead_states():
    sm = load_workflow(
        {
            "mode": "react",
            "initial": "understand",
            "stages": [
                {"id": "understand", "skill": "problem_framing"},
                {"id": "answer", "skill": "final_synthesis", "exit": True},
            ],
            "transitions": [
                {"from": "understand", "to": "answer", "when": "runtime.confidence >= 0.8"},
                {"from": "understand", "to": "understand", "when": "runtime.confidence < 0.8"},
            ],
        }
    )
    assert sm.dead_states() == ()
    # every non-terminal state reaches a terminal
    for s in sm.states:
        if s.exit:
            continue
        assert sm.has_path_to_terminal(s.id), f"{s.id} has no path to terminal"


@pytest.mark.unit
def test_custom_workflow_all_states_reachable_from_initial():
    """No orphan states: every declared state is reachable from ``initial``."""
    sm = load_workflow(
        {
            "mode": "react",
            "initial": "start",
            "stages": [
                {"id": "start"},
                {"id": "middle"},
                {"id": "done", "exit": True},
            ],
            "transitions": [
                {"from": "start", "to": "middle"},
                {"from": "middle", "to": "done"},
            ],
        }
    )
    reachable = _reachable_from_initial(sm)
    declared = {s.id for s in sm.states}
    # fail is reachable via the auto wildcard; all declared states reachable
    assert declared.issubset(reachable), f"unreachable states: {declared - reachable}"


@pytest.mark.unit
def test_custom_workflow_with_branch_and_loop_preserves_invariants():
    sm = load_workflow(
        {
            "mode": "react",
            "initial": "s1",
            "stages": [
                {"id": "s1"},
                {"id": "s2"},
                {"id": "s3"},
                {"id": "ok", "exit": True},
            ],
            "transitions": [
                {"from": "s1", "to": "s2", "when": "runtime.flag"},
                {"from": "s1", "to": "s3"},
                {"from": "s2", "to": "s1"},  # loop back
                {"from": "s3", "to": "ok"},
            ],
        }
    )
    assert sm.dead_states() == ()
    for s in sm.states:
        if s.exit:
            continue
        assert sm.has_path_to_terminal(s.id), f"{s.id} has no path to terminal"
    reachable = _reachable_from_initial(sm)
    declared = {s.id for s in sm.states}
    assert declared.issubset(reachable), f"unreachable states: {declared - reachable}"


# --- Helper self-tests on hand-built graphs (no auto wildcard) ---------------


@pytest.mark.unit
def test_dead_states_detects_isolated_non_terminal():
    """``dead_states`` reports a non-terminal state with no outgoing edges."""
    sm = StateMachine(
        states=(
            StateDef(id="plan", phase_llm_key="plan"),
            StateDef(id="do", phase_llm_key="do"),
            StateDef(id="end", exit=True),
            StateDef(id="orphan"),  # non-terminal, no edges
        ),
        transitions=(
            Transition(from_state="plan", to_state="do"),
            Transition(from_state="do", to_state="end"),
        ),
        initial="plan",
    )
    assert sm.dead_states() == ("orphan",)


@pytest.mark.unit
def test_has_path_to_terminal_false_for_dead_branch():
    sm = StateMachine(
        states=(
            StateDef(id="plan", phase_llm_key="plan"),
            StateDef(id="end", exit=True),
            StateDef(id="trap"),  # non-terminal, self-loop only, no terminal path
        ),
        transitions=(
            Transition(from_state="plan", to_state="end"),
            Transition(from_state="trap", to_state="trap"),
        ),
        initial="plan",
    )
    assert sm.has_path_to_terminal("plan")
    assert not sm.has_path_to_terminal("trap")


@pytest.mark.unit
def test_wildcard_edge_counts_as_outgoing_for_dead_state_detection():
    """A ``*`` transition gives every non-terminal state an outgoing edge."""
    sm = StateMachine(
        states=(
            StateDef(id="plan", phase_llm_key="plan"),
            StateDef(id="fail", exit=True),
        ),
        transitions=(
            Transition(from_state="*", to_state="fail", when="runtime.cancelled"),
        ),
        initial="plan",
    )
    # plan has the wildcard edge → not dead
    assert sm.dead_states() == ()
    assert sm.has_path_to_terminal("plan")
