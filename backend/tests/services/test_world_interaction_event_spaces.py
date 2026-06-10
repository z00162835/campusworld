"""Unit tests for decision-event space id extraction used by event map mode."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.world_interaction.service import WorldInteractionService
from app.services.world_interaction.types import WorldActor


def test_decision_event_space_ids_uses_navigation_exit_when_queue_empty():
    location = SimpleNamespace(id=1)
    actor = WorldActor(user_id="1", username="admin", permissions=[], roles=[])
    service = WorldInteractionService()
    session = MagicMock()

    with patch(
        "app.services.world_interaction.service.list_for_principal",
        return_value=[],
    ), patch(
        "app.services.world_interaction.service.connects_to_exits_from_room",
        return_value=[{"target_id": 42, "direction": "north"}],
    ):
        ids = service._decision_event_space_ids(session, actor, location)

    assert ids == ["42"]


def test_decision_event_space_ids_reads_task_location_and_related_space():
    location = SimpleNamespace(id=1)
    actor = WorldActor(user_id="1", username="admin", permissions=[], roles=[])
    service = WorldInteractionService()
    session = MagicMock()
    queue_row = SimpleNamespace(
        id=7,
        state="open",
        title="Inspect bridge",
        priority="normal",
        pool_key=None,
        visibility="assigned",
        assignee_kind="user",
    )
    task_node = SimpleNamespace(id=7, type_code="task", location_id=55, is_active=True)
    node_query = MagicMock()
    node_query.filter.return_value.first.return_value = task_node
    session.query.return_value = node_query

    with patch(
        "app.services.world_interaction.service.list_for_principal",
        return_value=[queue_row],
    ):
        ids = service._decision_event_space_ids(session, actor, location)

    assert "55" in ids
