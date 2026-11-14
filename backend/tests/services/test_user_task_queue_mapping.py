"""Unit tests for task-queue → decision-center mapping helpers."""
from unittest.mock import MagicMock

from app.services.task.user_task_queue import QueueTaskRow
from app.services.task.permissions import Principal, TASK_READ
from app.services.task.errors import ReferenceNotFound
from app.services.world_interaction import world_interaction_service


def test_options_for_claimed_task_offers_start():
    row = QueueTaskRow(
        id=42,
        state="claimed",
        title="Explore CampusWorld",
        priority="normal",
        pool_key=None,
        visibility="private",
        assignee_kind="user",
    )
    options = world_interaction_service._options_for_queue_task(row)
    assert options[0]["id"] == "task_start_42"
    assert options[0]["label"] == "Start task"
    assert options[0]["command"] == "task start 42"


def test_task_queue_event_uses_task_id():
    row = QueueTaskRow(
        id=7,
        state="in_progress",
        title="Review room",
        priority="high",
        pool_key=None,
        visibility="private",
        assignee_kind="user",
    )
    event = world_interaction_service._task_queue_event(row)
    assert event["id"] == "task_7"
    assert event["type"] == "task"
    assert event["options"][0]["command"] == "task complete 7"


def test_open_non_pool_task_does_not_emit_unimplemented_start():
    row = QueueTaskRow(
        id=8,
        state="open",
        title="Review draft",
        priority="normal",
        pool_key=None,
        visibility="private",
        assignee_kind="user",
    )
    options = world_interaction_service._options_for_queue_task(row)
    assert options[0]["command"] == "task show 8"


def test_decision_center_prefers_queue_over_navigation(monkeypatch):
    row = QueueTaskRow(
        id=1,
        state="claimed",
        title="Demo",
        priority="normal",
        pool_key=None,
        visibility="private",
        assignee_kind="user",
    )
    monkeypatch.setattr(
        "app.services.world_interaction.service.list_for_principal",
        lambda *args, **kwargs: [row],
    )
    session = MagicMock()
    location = MagicMock()
    location.id = 10
    world_interaction_service._display_name = lambda node: "Singularity Room"
    payload = world_interaction_service._decision_center(
        session,
        MagicMock(id=1, kind="user"),
        location,
        None,
        [{"world_id": "hicampus", "name": "HiCampus", "is_recommended": True}],
        {"edges": [], "nodes": []},
    )
    assert payload["decisionEvents"][0]["id"] == "task_1"
    assert payload["activeTask"]["title"] == "Demo"


def test_active_task_includes_quest_context():
    row = QueueTaskRow(
        id=2,
        state="claimed",
        title="Linked objective",
        priority="normal",
        pool_key=None,
        visibility="private",
        assignee_kind="user",
        quest_id=77,
        quest_title="Restore AC comfort",
    )
    payload = world_interaction_service._active_task_from_queue([row], None)
    assert payload["questId"] == "77"
    assert payload["questTitle"] == "Restore AC comfort"


def test_quest_context_projects_situation_goal_and_governance(monkeypatch):
    row = QueueTaskRow(
        id=2,
        state="claimed",
        title="Inspect bearing",
        priority="high",
        pool_key=None,
        visibility="private",
        assignee_kind="user",
        quest_id=77,
        quest_title="Restore safe operation",
    )
    monkeypatch.setattr(
        "app.services.world_interaction.service.show_quest",
        lambda **_kwargs: {
          "quest": {"id": 77, "title": "Restore safe operation", "attributes": {
            "current_state": "executing",
            "risk_level": "high",
            "policy_refs": ["policy:maintenance@3"],
            "process_refs": ["process:ahu-bearing@2"],
            "quality_refs": ["quality:vibration@1"],
          }},
          "situation": {"id": 75, "title": "Bearing anomaly", "attributes": {
            "assertion": "Vibration exceeds safe band", "subject_ref": 501,
            "trigger_kind": "mixed", "confidence": 0.92, "severity": "high",
          }},
          "goal": {"id": 76, "title": "Safe operation", "attributes": {
            "desired_state": "AHU returns to safe operation",
          }},
          "objectives": [],
        },
    )
    session = MagicMock()
    principal = Principal(id=1, kind="user", permissions=frozenset({TASK_READ}))

    payload = world_interaction_service._active_task_from_queue(
        [row], None, session=session, principal=principal,
    )

    assert payload["questContext"]["situation"]["triggerKind"] == "mixed"
    assert payload["questContext"]["situation"]["subjectRef"] == "501"
    assert payload["questContext"]["goal"]["desiredState"] == "AHU returns to safe operation"
    assert payload["questContext"]["governanceRefs"] == ["policy:maintenance@3"]


def test_quest_context_is_omitted_when_linked_quest_is_not_readable(monkeypatch):
    row = QueueTaskRow(
        id=2,
        state="open",
        title="Pool-visible objective",
        priority="normal",
        pool_key="shared",
        visibility="pool_open",
        assignee_kind="pool",
        quest_id=77,
        quest_title="Private Quest",
    )
    monkeypatch.setattr(
        "app.services.world_interaction.service.show_quest",
        lambda **_kwargs: (_ for _ in ()).throw(ReferenceNotFound("quest 77 not found")),
    )
    payload = world_interaction_service._active_task_from_queue(
        [row],
        None,
        session=MagicMock(),
        principal=Principal(id=2, kind="user", permissions=frozenset({TASK_READ})),
    )
    assert payload["questContext"] is None
