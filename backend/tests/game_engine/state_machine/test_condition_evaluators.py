"""Unit tests for condition_evaluators expression grammar."""
from __future__ import annotations

import pytest

from app.game_engine.agent_runtime.state_machine import (
    StateDef,
    StateMachine,
    StateMachineSnapshot,
    Transition,
    TransitionContext,
)
from app.game_engine.agent_runtime.state_machine.condition_evaluators import evaluate_when


def _sm(max_replans: int = 1) -> StateMachine:
    return StateMachine(
        states=(StateDef(id="a"), StateDef(id="end", exit=True)),
        transitions=(Transition(from_state="a", to_state="end"),),
        initial="a",
        max_replans=max_replans,
    )


def _ctx(*, replan_count=0, runtime=None) -> TransitionContext:
    return TransitionContext(
        snapshot=StateMachineSnapshot(current_state="a", replan_count=replan_count),
        runtime=dict(runtime or {}),
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "expr,runtime,replan,expected",
    [
        ('runtime.do_mode == "skip"', {"do_mode": "skip"}, 0, True),
        ('runtime.do_mode != "skip"', {"do_mode": "fast"}, 0, True),
        ("state.replan_count < 1", {}, 0, True),
        ("state.replan_count > 0", {}, 1, True),
        ("state.replan_count <= 1", {}, 1, True),
        ("state.replan_count >= 1", {}, 1, True),
        ('runtime.do_mode in ["skip", "fast"]', {"do_mode": "fast"}, 0, True),
        ('runtime.do_mode in ["skip"]', {"do_mode": "fast"}, 0, False),
        ("runtime.budget_remaining and state.replan_count < 1", {"budget_remaining": True}, 0, True),
        ("runtime.budget_remaining or state.replan_count > 0", {"budget_remaining": False}, 0, False),
        ("not runtime.cancelled", {"cancelled": False}, 0, True),
        ("not runtime.cancelled", {"cancelled": True}, 0, False),
        ("state.replan_count < sm.max_replans", {}, 0, True),
        ("state.replan_count < sm.max_replans", {}, 1, False),
        (None, {}, 0, True),
        ("", {}, 0, True),
    ],
)
def test_evaluate_when_ops(expr, runtime, replan, expected):
    assert evaluate_when(expr, _ctx(replan_count=replan, runtime=runtime), _sm()) is expected


@pytest.mark.unit
def test_unsupported_call_raises():
    with pytest.raises(ValueError):
        evaluate_when("len(runtime.x) > 0", _ctx(runtime={"x": [1]}), _sm())
