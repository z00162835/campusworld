"""PDCA template transition table property + coverage tests."""
from __future__ import annotations

import pytest

from app.game_engine.agent_runtime.state_machine import (
    StateMachineSnapshot,
    TransitionContext,
    build_pdca_state_machine,
)


def _ctx(
    state: str,
    *,
    do_mode: str = "skip",
    act_mode: str = "skip",
    replan_count: int = 0,
    budget_remaining: bool = True,
    mandatory_gap_missing: bool = False,
    cancelled: bool = False,
    draft_incomplete: bool = False,
    stop_fail: bool = False,
    event: str | None = None,
) -> TransitionContext:
    return TransitionContext(
        snapshot=StateMachineSnapshot(current_state=state, replan_count=replan_count),
        runtime={
            "do_mode": do_mode,
            "act_mode": act_mode,
            "budget_remaining": budget_remaining,
            "mandatory_gap_missing": mandatory_gap_missing,
            "cancelled": cancelled,
            "draft_incomplete": draft_incomplete,
            "stop_fail": stop_fail,
        },
        event=event,
    )


@pytest.mark.unit
def test_pdca_no_dead_states():
    sm = build_pdca_state_machine()
    assert sm.dead_states() == ()


@pytest.mark.unit
def test_pdca_every_state_reaches_terminal():
    sm = build_pdca_state_machine()
    for s in sm.states:
        assert sm.has_path_to_terminal(s.id), f"{s.id} has no path to terminal"


@pytest.mark.unit
def test_thin_pdca_happy_path():
    sm = build_pdca_state_machine()
    assert sm.next("plan", _ctx("plan", do_mode="skip", act_mode="skip")) == "check"
    assert sm.next("check", _ctx("check", act_mode="skip")) == "act"
    assert sm.next("act", _ctx("act", act_mode="skip")) == "end"


@pytest.mark.unit
def test_plan_to_do_when_not_skip():
    sm = build_pdca_state_machine()
    assert sm.next("plan", _ctx("plan", do_mode="plan")) == "do"
    assert sm.next("do", _ctx("do", replan_count=0)) == "check"


@pytest.mark.unit
def test_check_retry_replans_then_skips_second_check():
    sm = build_pdca_state_machine()
    # check → plan on check_retry
    assert sm.next(
        "check",
        _ctx("check", event="check_retry", budget_remaining=True, replan_count=0),
    ) == "plan"
    # after replan_count incremented: plan(skip-do) → act (skip second check)
    assert sm.next(
        "plan",
        _ctx("plan", do_mode="skip", replan_count=1),
    ) == "act"
    # do path after replan also skips check
    assert sm.next("do", _ctx("do", replan_count=1)) == "act"


@pytest.mark.unit
def test_mandatory_gap_event():
    sm = build_pdca_state_machine()
    assert sm.next(
        "check",
        _ctx(
            "check",
            event="mandatory_gap",
            budget_remaining=True,
            mandatory_gap_missing=True,
            replan_count=0,
        ),
    ) == "plan"


@pytest.mark.unit
def test_budget_blocks_replan():
    sm = build_pdca_state_machine()
    # event matches but when fails → fall through to act
    assert sm.next(
        "check",
        _ctx("check", event="check_retry", budget_remaining=False, act_mode="skip"),
    ) == "act"


@pytest.mark.unit
def test_max_replans_blocks_second_replan():
    sm = build_pdca_state_machine(max_replans=1)
    assert sm.next(
        "check",
        _ctx("check", event="check_retry", budget_remaining=True, replan_count=1, act_mode="skip"),
    ) == "act"


@pytest.mark.unit
def test_fail_on_cancel_and_draft_incomplete():
    sm = build_pdca_state_machine()
    # Cancel aborts from any state.
    assert sm.next("plan", _ctx("plan", cancelled=True)) == "fail"
    assert sm.next("check", _ctx("check", cancelled=True)) == "fail"
    # draft_incomplete aborts only from act (presentation anchor, SPEC §7.1);
    # from plan/do/check it must continue so downstream phases + the
    # mandatory-gap notice stay reachable.
    assert sm.next("act", _ctx("act", draft_incomplete=True)) == "fail"
    assert sm.next("plan", _ctx("plan", draft_incomplete=True)) == "check"
    assert sm.next("plan", _ctx("plan", draft_incomplete=True, do_mode="plan")) == "do"
    assert sm.next("check", _ctx("check", draft_incomplete=True)) == "act"


@pytest.mark.unit
def test_check_always_to_act():
    sm = build_pdca_state_machine()
    assert sm.next("check", _ctx("check", act_mode="plan")) == "act"
    assert sm.next("check", _ctx("check", act_mode="skip")) == "act"
    assert sm.next("act", _ctx("act")) == "end"


@pytest.mark.unit
def test_stop_fail_aborts_from_any_state():
    """D1: runtime.stop_fail routes *→fail from any state (non-act included)."""
    sm = build_pdca_state_machine()
    assert sm.next("plan", _ctx("plan", stop_fail=True)) == "fail"
    assert sm.next("do", _ctx("do", stop_fail=True)) == "fail"
    assert sm.next("check", _ctx("check", stop_fail=True)) == "fail"
    assert sm.next("act", _ctx("act", stop_fail=True)) == "fail"


@pytest.mark.unit
def test_stop_fail_takes_precedence_over_draft_incomplete():
    """stop_fail (phase 1) wins over act→fail on draft_incomplete (phase 3)."""
    sm = build_pdca_state_machine()
    assert sm.next("act", _ctx("act", stop_fail=True, draft_incomplete=True)) == "fail"


@pytest.mark.unit
def test_stagnation_replans_to_plan():
    """D2: event=stagnation under replan cap + budget → *→plan (replan)."""
    sm = build_pdca_state_machine(max_replans=1)
    assert sm.next(
        "plan", _ctx("plan", event="stagnation", replan_count=0, budget_remaining=True)
    ) == "plan"
    assert sm.next(
        "do", _ctx("do", event="stagnation", replan_count=0, budget_remaining=True)
    ) == "plan"
    assert sm.next(
        "check", _ctx("check", event="stagnation", replan_count=0, budget_remaining=True)
    ) == "plan"


@pytest.mark.unit
def test_stagnation_over_replan_cap_falls_through():
    """D2: stagnation over replan cap → *→plan when fails; driver sets stop_fail
    for over-limit, so the template alone falls through to the default edge
    (the driver is responsible for routing over-limit to fail)."""
    sm = build_pdca_state_machine(max_replans=1)
    # Over cap, no stop_fail set by template → falls through to default edge.
    assert sm.next(
        "check",
        _ctx("check", event="stagnation", replan_count=1, budget_remaining=True, act_mode="skip"),
    ) == "act"
    # Driver sets stop_fail for over-limit → *→fail.
    assert sm.next(
        "check",
        _ctx("check", event="stagnation", replan_count=1, budget_remaining=True, stop_fail=True),
    ) == "fail"


@pytest.mark.unit
def test_stagnation_no_budget_falls_through():
    """D2: stagnation with no budget → *→plan when fails; driver routes to
    stop_fail. Template alone falls through to default edge."""
    sm = build_pdca_state_machine(max_replans=1)
    assert sm.next(
        "check",
        _ctx("check", event="stagnation", replan_count=0, budget_remaining=False, act_mode="skip"),
    ) == "act"


@pytest.mark.unit
def test_stagnation_suppressed_when_no_event():
    """Default (no stagnation event) → byte-equivalent default edges."""
    sm = build_pdca_state_machine(max_replans=1)
    assert sm.next("plan", _ctx("plan", do_mode="skip", replan_count=0)) == "check"
    assert sm.next("check", _ctx("check", act_mode="skip")) == "act"
