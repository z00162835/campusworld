"""Load a ``StateMachine`` from agent node ``attributes.workflow``."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from app.game_engine.agent_runtime.state_machine.pdca_template import build_pdca_state_machine
from app.game_engine.agent_runtime.state_machine.state_machine import (
    StateDef,
    StateMachine,
    Transition,
)

_PDCA_MODES = frozenset({"pdcp", "pdca"})


def _max_replans_from_workflow(workflow: Mapping[str, Any], default: int = 1) -> int:
    replan = workflow.get("replan")
    if isinstance(replan, Mapping) and replan.get("max") is not None:
        return max(0, int(replan["max"]))
    if workflow.get("max_replans") is not None:
        return max(0, int(workflow["max_replans"]))
    return default


def _parse_stage(raw: Mapping[str, Any]) -> StateDef:
    sid = str(raw.get("id") or "").strip()
    if not sid:
        raise ValueError("workflow stage missing id")
    tools_raw = raw.get("tools")
    tools: Optional[Tuple[str, ...]] = None
    if isinstance(tools_raw, Sequence) and not isinstance(tools_raw, (str, bytes)):
        tools = tuple(str(t) for t in tools_raw)
    skill = raw.get("skill")
    return StateDef(
        id=sid,
        skill=(str(skill) if skill is not None else None),
        tools=tools,
        exit=bool(raw.get("exit", False)),
        phase_llm_key=(str(raw["phase_llm_key"]) if raw.get("phase_llm_key") else None),
    )


def _parse_transition(raw: Mapping[str, Any]) -> Transition:
    frm = str(raw.get("from") or raw.get("from_state") or "").strip()
    to = str(raw.get("to") or raw.get("to_state") or "").strip()
    if not frm or not to:
        raise ValueError(f"workflow transition requires from/to: {raw!r}")
    when = raw.get("when")
    on_event = raw.get("on_event")
    return Transition(
        from_state=frm,
        to_state=to,
        when=(str(when) if when is not None else None),
        on_event=(str(on_event) if on_event is not None else None),
    )


def _linear_transitions(stage_ids: Sequence[str]) -> List[Transition]:
    out: List[Transition] = []
    for i in range(len(stage_ids) - 1):
        out.append(Transition(from_state=stage_ids[i], to_state=stage_ids[i + 1]))
    return out


def _interactions_to_transitions(interactions: Sequence[Any]) -> List[Transition]:
    """Map SPEC ``interactions`` entries to conditional transitions.

    Each interaction may specify ``from`` (default ``*``), ``when``, and
    ``resume_to`` / ``to``.
    """
    out: List[Transition] = []
    for item in interactions:
        if not isinstance(item, Mapping):
            raise ValueError(f"workflow interaction must be a mapping: {item!r}")
        to = str(item.get("resume_to") or item.get("to") or "").strip()
        if not to:
            raise ValueError(f"workflow interaction missing resume_to/to: {item!r}")
        frm = str(item.get("from") or item.get("from_state") or "*").strip() or "*"
        when = item.get("when")
        out.append(
            Transition(
                from_state=frm,
                to_state=to,
                when=(str(when) if when is not None else None),
                on_event=(str(item["on_event"]) if item.get("on_event") else None),
            )
        )
    return out


def load_workflow(workflow: Optional[Mapping[str, Any]]) -> StateMachine:
    """Parse a workflow mapping into a ``StateMachine``.

    Missing/empty → default PDCA. ``mode: pdcp|pdca`` without custom stages also
    returns the PDCA template (optionally with ``replan.max``).
    """
    if not workflow:
        return build_pdca_state_machine()
    if not isinstance(workflow, Mapping):
        raise ValueError("attributes.workflow must be a mapping")

    mode = str(workflow.get("mode") or "pdcp").strip().lower()
    stages_raw = workflow.get("stages")
    max_replans = _max_replans_from_workflow(workflow)

    if mode in _PDCA_MODES and not stages_raw:
        return build_pdca_state_machine(max_replans=max_replans)

    if not isinstance(stages_raw, list) or not stages_raw:
        if mode in _PDCA_MODES:
            return build_pdca_state_machine(max_replans=max_replans)
        raise ValueError("custom workflow requires a non-empty stages list")

    states_list = [_parse_stage(s) for s in stages_raw if isinstance(s, Mapping)]
    if len(states_list) != len(stages_raw):
        raise ValueError("workflow stages entries must be mappings")
    ids = [s.id for s in states_list]
    if len(set(ids)) != len(ids):
        raise ValueError("workflow stage ids must be unique")

    # Ensure success + abort terminals exist for property tests / fail path.
    id_set = set(ids)
    if "end" not in id_set and not any(s.exit for s in states_list):
        states_list.append(StateDef(id="end", exit=True))
        ids.append("end")
        id_set.add("end")
    elif "end" not in id_set and any(s.exit for s in states_list):
        # Keep exit stages; still add end if last non-exit needs a sink via linear edges later.
        pass
    if "fail" not in id_set:
        states_list.append(StateDef(id="fail", exit=True))
        ids.append("fail")
        id_set.add("fail")

    transitions: List[Transition] = []
    explicit = workflow.get("transitions")
    if explicit is not None:
        if not isinstance(explicit, list):
            raise ValueError("workflow.transitions must be a list")
        transitions.extend(_parse_transition(t) for t in explicit if isinstance(t, Mapping))
        if len(transitions) != len(explicit):
            raise ValueError("workflow.transitions entries must be mappings")
    else:
        # Linear chain across non-terminal declared stages; last exit stage stays put.
        non_fail = [s.id for s in states_list if s.id != "fail"]
        transitions.extend(_linear_transitions(non_fail))
        # If last declared stage is not exit and end exists, ensure chain ends at end.
        last_declared = str(stages_raw[-1].get("id") or "").strip()
        if last_declared and "end" in id_set and last_declared != "end":
            last_state = next(s for s in states_list if s.id == last_declared)
            if not last_state.exit and not any(t.from_state == last_declared for t in transitions):
                transitions.append(Transition(from_state=last_declared, to_state="end"))

    interactions = workflow.get("interactions") or []
    if interactions:
        if not isinstance(interactions, list):
            raise ValueError("workflow.interactions must be a list")
        transitions.extend(_interactions_to_transitions(interactions))

    # Abort wildcard if not already present
    if not any(t.from_state == "*" and t.to_state == "fail" for t in transitions):
        transitions.insert(
            0,
            Transition(
                from_state="*",
                to_state="fail",
                when="runtime.cancelled or runtime.draft_incomplete",
            ),
        )

    initial = str(workflow.get("initial") or ids[0]).strip()
    if initial not in id_set:
        raise ValueError(f"workflow.initial unknown state: {initial!r}")

    return StateMachine(
        states=tuple(states_list),
        transitions=tuple(transitions),
        initial=initial,
        max_replans=max_replans,
    )


def load_state_machine_from_attributes(attrs: Optional[Mapping[str, Any]]) -> StateMachine:
    """Load from node attributes; missing ``workflow`` falls back to PDCA."""
    if not attrs:
        return build_pdca_state_machine()
    raw = attrs.get("workflow")
    if raw is None:
        return build_pdca_state_machine()
    if isinstance(raw, str):
        # Allow YAML/JSON string forms in attributes.
        text = raw.strip()
        if not text:
            return build_pdca_state_machine()
        try:
            import json

            parsed = json.loads(text)
        except Exception:
            try:
                import yaml  # type: ignore

                parsed = yaml.safe_load(text)
            except Exception as exc:
                raise ValueError("attributes.workflow string is not valid JSON/YAML") from exc
        if not isinstance(parsed, Mapping):
            raise ValueError("attributes.workflow string must decode to a mapping")
        return load_workflow(parsed)
    if not isinstance(raw, Mapping):
        raise ValueError("attributes.workflow must be a mapping or JSON/YAML string")
    return load_workflow(raw)


def default_pdcp_workflow_attr() -> Dict[str, Any]:
    """Seed-friendly default PDCA workflow attribute."""
    return {"mode": "pdcp"}
