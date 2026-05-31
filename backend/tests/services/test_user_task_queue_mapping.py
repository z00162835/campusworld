"""Unit tests for task-queue → decision-center mapping helpers."""
from unittest.mock import MagicMock

from app.services.task.user_task_queue import QueueTaskRow
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
        "app.services.world_interaction.list_for_principal",
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
