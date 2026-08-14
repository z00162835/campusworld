"""Unit tests for StateMachine.next() transition routing."""
from __future__ import annotations

import pytest

from app.game_engine.agent_runtime.state_machine import (
    StateDef,
    StateMachine,
    StateMachineSnapshot,
    Transition,
    TransitionContext,
)


def _sm() -> StateMachine:
    return StateMachine(
        states=(
            StateDef(id="a"),
            StateDef(id="b"),
            StateDef(id="end", exit=True),
            StateDef(id="fail", exit=True),
        ),
        transitions=(
            Transition(from_state="*", to_state="fail", when="runtime.cancelled"),
            Transition(from_state="a", to_state="b", when='runtime.mode == "go"'),
            Transition(from_state="a", to_state="end", when='runtime.mode == "stop"'),
            Transition(from_state="b", to_state="a", when="runtime.budget_remaining", on_event="retry"),
            Transition(from_state="b", to_state="end"),
        ),
        initial="a",
        max_replans=1,
    )


def _ctx(state: str = "a", *, runtime=None, event=None, replan_count=0) -> TransitionContext:
    return TransitionContext(
        snapshot=StateMachineSnapshot(current_state=state, replan_count=replan_count),
        runtime=dict(runtime or {}),
        event=event,
    )


@pytest.mark.unit
def test_when_condition_selects_transition():
    sm = _sm()
    assert sm.next("a", _ctx(runtime={"mode": "go"})) == "b"
    assert sm.next("a", _ctx(runtime={"mode": "stop"})) == "end"


@pytest.mark.unit
def test_fail_wildcard_takes_priority():
    sm = _sm()
    assert sm.next("a", _ctx(runtime={"mode": "go", "cancelled": True})) == "fail"


@pytest.mark.unit
def test_event_gated_transition():
    sm = _sm()
    assert sm.next("b", _ctx(state="b", runtime={"budget_remaining": True}, event="retry")) == "a"
    assert sm.next("b", _ctx(state="b", runtime={"budget_remaining": False}, event="retry")) == "end"
    assert sm.next("b", _ctx(state="b", runtime={"budget_remaining": True})) == "end"


@pytest.mark.unit
def test_snapshot_last_event_does_not_drive_current_transition():
    sm = _sm()
    ctx = TransitionContext(
        snapshot=StateMachineSnapshot(current_state="b", last_event="retry"),
        runtime={"budget_remaining": True},
        event=None,
    )
    assert sm.next("b", ctx) == "end"


@pytest.mark.unit
def test_no_match_raises():
    sm = _sm()
    with pytest.raises(LookupError):
        sm.next("a", _ctx(runtime={"mode": "unknown"}))


@pytest.mark.unit
def test_snapshot_advance():
    snap = StateMachineSnapshot(current_state="plan")
    nxt = snap.advance(to_state="check", event="check_retry", incremented_replan=True)
    assert nxt.current_state == "check"
    assert nxt.turn_count == 1
    assert nxt.replan_count == 1
    assert nxt.completed_states == ("plan",)
    assert nxt.last_event == "check_retry"
