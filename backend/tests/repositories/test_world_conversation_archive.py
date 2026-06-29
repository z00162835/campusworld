"""Repository tests for persisted world conversation archives."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.repositories.world_conversation_archive import (
    WorldConversationArchiveRepository,
    WorldHistoryArchiveLimitError,
)


def test_append_raises_when_archive_batch_limit_reached():
    repo = WorldConversationArchiveRepository(max_archives_per_user=2)
    session = MagicMock()
    account = MagicMock(id=10)
    repo.count_for_account = MagicMock(return_value=2)

    with pytest.raises(WorldHistoryArchiveLimitError):
        repo.append_for_account(
            session,
            account,
            {
                "id": "archive_test",
                "archivedAt": "2026-06-27T00:00:00Z",
                "aico_threads": [],
                "command_conversation": [{"id": "m1", "role": "user", "answer": "hi"}],
            },
        )


def test_list_summaries_projects_only_history_summary_path():
    """The summary listing must not hydrate full aico_threads/command_conversation JSONB.

    A regression here would re-introduce the ~25MB read for 50 full archives that
    the JSON-path projection was added to avoid.
    """
    repo = WorldConversationArchiveRepository()
    session = MagicMock()

    class FakeQuery:
        def __init__(self, statement):
            self.statement = statement

        def join(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def offset(self, value):
            return self

        def limit(self, value):
            return self

        def count(self):
            return 1

        def all(self):
            # Return one row shaped like a named tuple from the column projection.
            row = MagicMock()
            row.archive_id = "archive_test"
            row.archived_at = "2026-06-27T00:00:00Z"
            row.created_at = MagicMock()
            row.created_at.isoformat.return_value = "2026-06-27T00:00:00Z"
            row.uuid = "node-uuid"
            row.history_summary = {
                "aico_items": [{"id": "archive_test_t1", "title": "T", "messageCount": 2, "preview": "p", "createdAt": "2026-06-27T00:00:00Z"}],
                "command_items": [],
            }
            return [row]

    captured = {}

    def fake_query(*args):
        captured["args"] = args
        return FakeQuery(args)

    session.query = fake_query

    entries, total = repo.list_summaries_for_account(session, account_node_id=10, limit=50, offset=0)
    assert total == 1
    assert entries[0]["id"] == "archive_test"
    assert entries[0]["history_summary"]["aico_items"][0]["title"] == "T"
    # The summary listing must project individual columns, not the full Node row
    # (which would hydrate aico_threads / command_conversation JSONB per batch).
    # Expected projection: id, uuid, created_at, archive_id, archived_at, history_summary.
    from app.models.graph import Node as NodeModel
    assert len(captured["args"]) == 6
    assert all(arg is not NodeModel for arg in captured["args"])

