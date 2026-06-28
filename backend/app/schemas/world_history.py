"""Structured schemas for world-history conversation archives."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

MAX_ARCHIVE_THREADS = 20
MAX_ARCHIVE_MESSAGES = 50
MAX_ARCHIVE_TEXT = 8000
MAX_ARCHIVE_ID_LENGTH = 128
MAX_ARCHIVE_TITLE_LENGTH = 256
MAX_ARCHIVE_TIMESTAMP_LENGTH = 64
MAX_ARCHIVE_BATCH_BYTES = 512_000
DEFAULT_HISTORY_SUMMARY_LIMIT = 50
MAX_HISTORY_SUMMARY_LIMIT = 100


class ArchivedConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, max_length=MAX_ARCHIVE_ID_LENGTH)
    role: Literal["user", "assistant", "system"]
    mode: Literal["command", "aico"] = "command"
    query: Optional[str] = Field(default=None, max_length=MAX_ARCHIVE_TEXT)
    answer: str = Field(..., max_length=MAX_ARCHIVE_TEXT)


class ArchivedAicoThread(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1, max_length=MAX_ARCHIVE_ID_LENGTH)
    title: str = Field(default="", max_length=MAX_ARCHIVE_TITLE_LENGTH)
    messages: list[ArchivedConversationMessage] = Field(default_factory=list, max_length=MAX_ARCHIVE_MESSAGES)
    updatedAt: str = Field(..., min_length=1, max_length=MAX_ARCHIVE_TIMESTAMP_LENGTH)


class ConversationArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aico_threads: list[ArchivedAicoThread] = Field(default_factory=list, max_length=MAX_ARCHIVE_THREADS)
    command_conversation: list[ArchivedConversationMessage] = Field(
        default_factory=list,
        max_length=MAX_ARCHIVE_MESSAGES,
    )
