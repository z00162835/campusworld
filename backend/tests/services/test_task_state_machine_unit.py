"""Phase B PR4: pure-unit tests for ``task_state_machine`` non-DB logic.

These tests cover:
- Phase B event whitelist (SPEC §6).
- ``create`` event routing (must use ``create_task``, not ``transition``).
- ``Principal.has_permission`` semantics piped into the state machine.

DB-backed transitional behaviour (I1/I3/I4/I5/I6) is exercised in
``tests/services/test_task_state_machine_postgres.py``.
"""

from __future__ import annotations

import pytest

from app.services.task import task_state_machine as tsm
from app.services.task.errors import WorkflowEventNotAllowed
from app.services.task.permissions import Principal


@pytest.mark.unit
def test_phase_b_events_whitelist_exact():
    assert tsm._PHASE_B_EVENTS == {
        "create",
        "publish",
        "claim",
        "assign",
        "complete",
    }


@pytest.mark.unit
def test_outbox_event_kind_mapping_complete():
    assert tsm._OUTBOX_EVENT_KIND == {
        "create": "task.created",
        "publish": "task.published",
        "claim": "task.claimed",
        "assign": "task.assigned",
        "complete": "task.completed",
    }


@pytest.mark.unit
def test_event_handler_registry_matches_phase_b_transition_events():
    assert set(tsm._EVENT_HANDLERS.keys()) == {"publish", "claim", "assign", "complete"}


@pytest.mark.unit
def test_transition_rejects_create_event_explicitly():
    """``create`` must go through ``create_task`` to allocate a node row."""
    actor = Principal(id=1, kind="user")
    with pytest.raises(WorkflowEventNotAllowed) as ei:
        tsm.transition(
            task_id=999,
            event="create",
            actor_principal=actor,
            expected_version=0,
        )
    assert "create_task" in str(ei.value)


@pytest.mark.unit
@pytest.mark.parametrize(
    "phase_c_event",
    [
        "start",
        "submit-review",
        "approve",
        "reject",
        "handoff",
        "fail",
        "cancel",
        # Garbage event: must also reject.
        "totally-bogus",
    ],
)
def test_transition_rejects_phase_c_events(phase_c_event):
    actor = Principal(id=1, kind="user")
    with pytest.raises(WorkflowEventNotAllowed):
        tsm.transition(
            task_id=1,
            event=phase_c_event,
            actor_principal=actor,
            expected_version=0,
        )


@pytest.mark.unit
def test_stage_mapping_exhaustive_for_all_default_v1_states():
    from db.seeds.task_seed import DEFAULT_WORKFLOW_SEED

    for state in DEFAULT_WORKFLOW_SEED["spec"]["states"].keys():
        assert state in tsm._STAGE_BY_TO_STATE, f"missing stage for {state}"


@pytest.mark.unit
def test_transition_result_dataclass_is_frozen():
    res = tsm.TransitionResult(
        task_id=1,
        from_state="draft",
        to_state="open",
        event="publish",
        event_seq=1,
        state_version=1,
        idempotent_replay=False,
        correlation_id="corr-1",
        trace_id="trace-1",
    )
    with pytest.raises(Exception):
        res.task_id = 2  # type: ignore[misc]


@pytest.mark.unit
def test_check_required_role_skips_db_lookup_for_system_actor():
    class BombSession:
        def execute(self, *args, **kwargs):  # pragma: no cover - should never run
            raise AssertionError("system actor must bypass assignment role lookup")

    tsm._check_required_role(
        BombSession(),
        task_id=123,
        actor=Principal(id=0, kind="system"),
        required_role="owner",
    )
