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
