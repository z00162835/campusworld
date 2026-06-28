"""Tests for world-history archive request validation."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.world_history import (
    MAX_ARCHIVE_MESSAGES,
    MAX_ARCHIVE_THREADS,
    ConversationArchiveRequest,
)


def _message(index: int) -> dict:
    return {
        "id": f"m{index}",
        "role": "user",
        "mode": "command",
        "answer": f"message {index}",
    }


def test_archive_request_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ConversationArchiveRequest.model_validate(
            {"aico_threads": [], "command_conversation": [], "unexpected": True}
        )


def test_archive_request_rejects_too_many_command_messages():
    payload = {
        "aico_threads": [],
        "command_conversation": [_message(i) for i in range(MAX_ARCHIVE_MESSAGES + 1)],
    }
    with pytest.raises(ValidationError):
        ConversationArchiveRequest.model_validate(payload)


def test_archive_request_rejects_too_many_aico_threads():
    thread = {
        "id": "t1",
        "title": "Test",
        "messages": [_message(0)],
        "updatedAt": "2026-06-27T00:00:00Z",
    }
    payload = {
        "aico_threads": [dict(thread, id=f"t{i}") for i in range(MAX_ARCHIVE_THREADS + 1)],
        "command_conversation": [],
    }
    with pytest.raises(ValidationError):
        ConversationArchiveRequest.model_validate(payload)


def test_archive_request_rejects_thread_with_too_many_messages():
    payload = {
        "aico_threads": [
            {
                "id": "t1",
                "title": "Test",
                "messages": [_message(i) for i in range(MAX_ARCHIVE_MESSAGES + 1)],
                "updatedAt": "2026-06-27T00:00:00Z",
            }
        ],
        "command_conversation": [],
    }
    with pytest.raises(ValidationError):
        ConversationArchiveRequest.model_validate(payload)
