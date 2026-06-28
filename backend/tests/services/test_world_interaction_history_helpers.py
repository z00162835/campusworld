from app.services.world_interaction.service import WorldInteractionService


def test_archived_command_items_skips_leading_system_messages():
    messages = [
        {"id": "s1", "role": "system", "answer": "context"},
        {"id": "u1", "role": "user", "query": "look", "answer": "look"},
        {"id": "a1", "role": "assistant", "answer": "You see a room."},
        {"id": "u2", "role": "user", "query": "go north", "answer": "go north"},
        {"id": "a2", "role": "assistant", "answer": "You go north."},
    ]

    items = WorldInteractionService._archived_command_items("arc", messages, "2026-01-01T00:00:00Z")

    assert len(items) == 2
    assert items[0]["title"] == "go north"
    assert items[1]["title"] == "look"
    assert items[0]["messageCount"] == 2
    assert items[1]["messageCount"] == 2
    assert items[0]["sequence"] == 1
    assert items[1]["sequence"] == 0


def test_archived_command_items_handles_isolated_user_after_system():
    messages = [
        {"id": "u1", "role": "user", "query": "look", "answer": "look"},
        {"id": "a1", "role": "assistant", "answer": "You see a room."},
        {"id": "s1", "role": "system", "answer": "context"},
        {"id": "u2", "role": "user", "query": "inventory", "answer": "inventory"},
    ]

    items = WorldInteractionService._archived_command_items("arc", messages, "2026-01-01T00:00:00Z")

    assert len(items) == 2
    assert items[0]["title"] == "inventory"
    assert items[1]["title"] == "look"
    assert items[0]["messageCount"] == 1
    assert items[1]["messageCount"] == 2


def test_history_preview_prefers_assistant_answer():
    messages = [
        {"id": "u1", "role": "user", "query": "hello", "answer": "hello"},
        {"id": "a1", "role": "assistant", "query": "hello", "answer": "Hi there"},
    ]

    assert WorldInteractionService._history_preview_from_messages(messages) == "Hi there"
