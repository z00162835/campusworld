"""Agent outer-loop state machine — pure data + deterministic transition routing."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

from app.game_engine.agent_runtime.state_machine.condition_evaluators import evaluate_when


@dataclass(frozen=True)
class StateDef:
    id: str
    skill: Optional[str] = None
    tools: Optional[Tuple[str, ...]] = None
    exit: bool = False
    phase_llm_key: Optional[str] = None

    def llm_key(self) -> str:
        return self.phase_llm_key or self.id


@dataclass(frozen=True)
class Transition:
    from_state: str
    to_state: str
    when: Optional[str] = None
    on_event: Optional[str] = None


@dataclass(frozen=True)
class StateMachineSnapshot:
    schema_version: str = "1"
    current_state: str = ""
    turn_count: int = 0
    replan_count: int = 0
    completed_states: Tuple[str, ...] = ()
    last_event: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "current_state": self.current_state,
            "turn_count": self.turn_count,
            "replan_count": self.replan_count,
            "completed_states": list(self.completed_states),
            "last_event": self.last_event,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StateMachineSnapshot":
        completed = data.get("completed_states") or ()
        return cls(
            schema_version=str(data.get("schema_version") or "1"),
            current_state=str(data.get("current_state") or ""),
            turn_count=int(data.get("turn_count") or 0),
            replan_count=int(data.get("replan_count") or 0),
            completed_states=tuple(str(x) for x in completed),
            last_event=(str(data["last_event"]) if data.get("last_event") is not None else None),
        )

    def advance(
        self,
        *,
        to_state: str,
        event: Optional[str] = None,
        incremented_replan: bool = False,
    ) -> "StateMachineSnapshot":
        completed = self.completed_states
        if self.current_state and self.current_state not in completed:
            completed = completed + (self.current_state,)
        return StateMachineSnapshot(
            schema_version=self.schema_version,
            current_state=to_state,
            turn_count=self.turn_count + 1,
            replan_count=self.replan_count + (1 if incremented_replan else 0),
            completed_states=completed,
            last_event=event,
        )


@dataclass(frozen=True)
class TransitionContext:
    """Separates serializable snapshot from ephemeral runtime context."""

    snapshot: StateMachineSnapshot
    runtime: Dict[str, Any] = field(default_factory=dict)
    event: Optional[str] = None


@dataclass(frozen=True)
class StateExecutionResult:
    output_text: str = ""
    event: Optional[str] = None
    draft_text: str = ""
    gather_counters: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class StateMachine:
    states: Tuple[StateDef, ...]
    transitions: Tuple[Transition, ...]
    initial: str
    max_replans: int = 1

    def state_map(self) -> Dict[str, StateDef]:
        return {s.id: s for s in self.states}

    def get_state(self, state_id: str) -> StateDef:
        smap = self.state_map()
        if state_id not in smap:
            raise KeyError(f"unknown state: {state_id}")
        return smap[state_id]

    def next(self, current: str, ctx: TransitionContext) -> str:
        """Pick the first matching transition.

        Evaluation order:
        1. ``any → fail`` (from_state == '*') when condition matches
        2. event-matched transitions (on_event == ctx.event) with when;
           ``*`` wildcards match any current state.
        3. non-event transitions with when
        """
        event = ctx.event
        # 1) Wildcard fail transitions first
        for tr in self.transitions:
            if tr.from_state == "*" and tr.to_state == "fail":
                if evaluate_when(tr.when, ctx, self):
                    return tr.to_state
        # 2) Event-gated transitions from current (``*`` matches any state)
        if event:
            for tr in self.transitions:
                if tr.from_state not in (current, "*") or not tr.on_event:
                    continue
                if tr.on_event == event and evaluate_when(tr.when, ctx, self):
                    return tr.to_state
        # 3) Conditional / default transitions without on_event
        for tr in self.transitions:
            if tr.from_state != current or tr.on_event:
                continue
            if evaluate_when(tr.when, ctx, self):
                return tr.to_state
        raise LookupError(f"no matching transition from state={current!r} event={event!r}")

    def terminal_ids(self) -> Tuple[str, ...]:
        return tuple(s.id for s in self.states if s.exit)

    def has_path_to_terminal(self, start: str) -> bool:
        terminals = set(self.terminal_ids())
        if start in terminals:
            return True
        seen = set()
        stack = [start]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            for tr in self.transitions:
                if tr.from_state not in (cur, "*"):
                    continue
                if tr.to_state in terminals:
                    return True
                if tr.to_state not in seen:
                    stack.append(tr.to_state)
        return False

    def dead_states(self) -> Tuple[str, ...]:
        """Non-terminal states with no outgoing edges (including wildcard)."""
        dead = []
        for s in self.states:
            if s.exit:
                continue
            outs = [tr for tr in self.transitions if tr.from_state in (s.id, "*")]
            if not outs:
                dead.append(s.id)
        return tuple(dead)
