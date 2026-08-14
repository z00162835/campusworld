"""Default PDCA workflow template — golden-equivalent outer transitions."""
from __future__ import annotations

from typing import List

from app.game_engine.agent_runtime.state_machine.state_machine import (
    StateDef,
    StateMachine,
    Transition,
)


def build_pdca_state_machine(*, max_replans: int = 1) -> StateMachine:
    """Build the default PDCA state machine matching today's outer loop."""
    states = (
        StateDef(id="plan", phase_llm_key="plan"),
        StateDef(id="do", phase_llm_key="do"),
        StateDef(id="check", phase_llm_key="check"),
        StateDef(id="act", phase_llm_key="act"),
        StateDef(id="end", exit=True),
        StateDef(id="fail", exit=True),
    )
    transitions = (
        # Cancel aborts from any state (immediate).
        Transition(
            from_state="*",
            to_state="fail",
            when='runtime.cancelled',
        ),
        # stop_evaluator unrecoverable fail (max_iterations /
        # max_consecutive_tool_failures / stagnation over-limit) routes from
        # any state. Gated by runtime.stop_fail (default false; only set when
        # enable_stop_dimensions is on).
        Transition(
            from_state="*",
            to_state="fail",
            when='runtime.stop_fail',
        ),
        # Deferral-only final drafts are detected after act (presentation
        # anchor), so draft_incomplete routes act→fail before act→end.
        # It must NOT fire from plan/do, or the post-loop mandatory-gap notice
        # and downstream phases become unreachable.
        Transition(
            from_state="act",
            to_state="fail",
            when='runtime.draft_incomplete',
        ),
        # From plan
        Transition(from_state="plan", to_state="do", when='runtime.do_mode != "skip"'),
        Transition(
            from_state="plan",
            to_state="check",
            when='runtime.do_mode == "skip" and state.replan_count == 0',
        ),
        Transition(
            from_state="plan",
            to_state="act",
            when='runtime.do_mode == "skip" and state.replan_count > 0',
        ),
        # From do
        Transition(from_state="do", to_state="check", when="state.replan_count == 0"),
        Transition(from_state="do", to_state="act", when="state.replan_count > 0"),
        # From check — event-gated replans
        Transition(
            from_state="check",
            to_state="plan",
            when="state.replan_count < sm.max_replans and runtime.budget_remaining",
            on_event="check_retry",
        ),
        Transition(
            from_state="check",
            to_state="plan",
            when=(
                "state.replan_count < sm.max_replans and runtime.budget_remaining "
                "and runtime.mandatory_gap_missing"
            ),
            on_event="mandatory_gap",
        ),
        # Stagnation replan only fires when stop_evaluator emits
        # event='stagnation' from plan/do/check; act suppresses the event).
        # Over-limit (replan_count >= max_replans or no budget) is routed by the
        # driver to runtime.stop_fail → *→fail above.
        Transition(
            from_state="*",
            to_state="plan",
            when="state.replan_count < sm.max_replans and runtime.budget_remaining",
            on_event="stagnation",
        ),
        # From check — always enter act so skip-act still emits the act trace
        # entry (mode=skip) matching today's hard-coded _run_inner.
        Transition(from_state="check", to_state="act"),
        # From act — final_success_evaluator retry_loop→replan:
        # recoverable draft detected at before_terminal drives an outer replan
        # back to plan, counted by replan_count / max_replans. Over-limit is
        # routed by the driver to runtime.stop_fail → *→fail (mirrors stagnation).
        Transition(
            from_state="act",
            to_state="plan",
            when="state.replan_count < sm.max_replans and runtime.budget_remaining",
            on_event="draft_retry",
        ),
        # From act
        Transition(from_state="act", to_state="end"),
    )
    return StateMachine(
        states=states,
        transitions=transitions,
        initial="plan",
        max_replans=max_replans,
    )


_PDCA_EXECUTABLE_STATE_IDS = frozenset({"plan", "do", "check", "act", "end", "fail"})


def is_pdca_executable(sm: StateMachine) -> bool:
    """True when every non-exit state id is a PDCA stage the driver can execute.

    Extra exit/terminal states are harmless (the driver loop breaks on them),
    so only non-exit states must belong to the executable set.
    """
    return all(s.id in _PDCA_EXECUTABLE_STATE_IDS for s in sm.states if not s.exit)


def non_pdca_state_ids(sm: StateMachine) -> List[str]:
    """Non-exit state ids the v1 driver cannot execute (for diagnostics)."""
    return sorted({s.id for s in sm.states if not s.exit and s.id not in _PDCA_EXECUTABLE_STATE_IDS})
