"""F12 STM helpers (unit, no database)."""

from __future__ import annotations

import uuid

import pytest

from unittest.mock import MagicMock

from app.commands.base import CommandContext
from app.game_engine.agent_runtime.conversation_stm_service import (
    apply_compaction_truncate,
    append_turns_to_messages,
    clear_conversation_thread_for_transport,
    ensure_conversation_thread_id,
    finalize_daemon_possession_after_success,
    format_stm_for_prompt,
    get_thread_id_from_context,
    normalize_messages,
    persist_conversation_thread_for_transport,
    stm_should_compact_after_append,
    try_restore_conversation_thread_from_transport,
    _conversation_thread_ephemeral_storage_key,
)
from app.game_engine.agent_runtime.frameworks.llm_pdca import _assemble_plan_user


@pytest.mark.unit
def test_assemble_plan_user_orders_tools_world_stm_memory_user():
    text = _assemble_plan_user(
        user_msg="hi",
        memory="LTM_BLOCK",
        world_snapshot="WORLD_BLOCK",
        tool_manifest_text="TOOLS_BLOCK",
        intent_hint=None,
        recent_conversation="STM_BLOCK",
    )
    assert text.index("Tools available") < text.index("World snapshot")
    assert text.index("World snapshot") < text.index("Recent conversation")
    assert text.index("Recent conversation") < text.index("Retrieved memory")
    assert text.index("Retrieved memory") < text.index("User message")
    assert "TOOLS_BLOCK" in text and "WORLD_BLOCK" in text
    assert "STM_BLOCK" in text and "LTM_BLOCK" in text


@pytest.mark.unit
def test_compaction_truncates_oldest_messages():
    msgs = []
    for i in range(10):
        msgs.append({"role": "user", "content": f"u{i}", "ts": "t"})
        msgs.append({"role": "assistant", "content": f"a{i}", "ts": "t"})
    out, _rs = apply_compaction_truncate(
        msgs,
        "",
        stm_max_turns=2,
        stm_max_chars=100000,
    )
    assert len(out) <= 4


@pytest.mark.unit
def test_stm_should_compact_when_over_ratio():
    msgs = [{"role": "user", "content": "a", "ts": "1"}]
    assert stm_should_compact_after_append(
        msgs,
        "",
        stm_max_chars=100,
        compaction_trigger_ratio=0.5,
    ) is False
    big = [{"role": "user", "content": "x" * 200, "ts": "1"}]
    assert stm_should_compact_after_append(
        big,
        "",
        stm_max_chars=100,
        compaction_trigger_ratio=0.5,
    ) is True


@pytest.mark.unit
def test_append_turns_roundtrip():
    m = append_turns_to_messages([], user_text="u", assistant_text="a")
    assert len(m) == 2
    assert m[0]["role"] == "user"
    assert normalize_messages(m) == m


@pytest.mark.unit
def test_finalize_daemon_possession_sets_holder_once():
    row = MagicMock()
    row.locked_by_account_node_id = None
    row.lock_transport_session_id = None
    row.bound_username = None
    row.possession_generation = 0
    finalize_daemon_possession_after_success(
        MagicMock(),
        row,
        caller_account_node_id=42,
        transport_session_id="ssh_sess_1",
        username_for_bound="alice",
    )
    assert row.locked_by_account_node_id == 42
    assert row.lock_transport_session_id == "ssh_sess_1"
    assert row.bound_username == "alice"
    assert row.possession_generation == 1

    finalize_daemon_possession_after_success(
        MagicMock(),
        row,
        caller_account_node_id=42,
        transport_session_id="ssh_sess_2",
        username_for_bound="alice",
    )
    assert row.possession_generation == 1
    assert row.lock_transport_session_id == "ssh_sess_2"


@pytest.mark.unit
def test_try_restore_conversation_thread_validates_db_row():
    tid = uuid.uuid4()
    ssh = MagicMock()
    ssh.command_ephemeral = {_conversation_thread_ephemeral_storage_key(7): str(tid)}
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="transport-a",
        permissions=[],
        session=ssh,
        metadata={},
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = object()
    assert (
        try_restore_conversation_thread_from_transport(
            db,
            ctx,
            caller_account_node_id=5,
            agent_node_id=7,
        )
        == tid
    )


@pytest.mark.unit
def test_try_restore_conversation_thread_bad_uuid_clears_ephemeral():
    ssh = MagicMock()
    key = _conversation_thread_ephemeral_storage_key(7)
    ssh.command_ephemeral = {key: "not-a-uuid"}
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="transport-a",
        permissions=[],
        session=ssh,
        metadata={},
    )
    db = MagicMock()
    assert try_restore_conversation_thread_from_transport(db, ctx, caller_account_node_id=5, agent_node_id=7) is None
    assert key not in ssh.command_ephemeral


@pytest.mark.unit
def test_try_restore_conversation_thread_missing_row_clears_ephemeral():
    tid = uuid.uuid4()
    ssh = MagicMock()
    key = _conversation_thread_ephemeral_storage_key(7)
    ssh.command_ephemeral = {key: str(tid)}
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="transport-a",
        permissions=[],
        session=ssh,
        metadata={},
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    assert try_restore_conversation_thread_from_transport(db, ctx, caller_account_node_id=5, agent_node_id=7) is None
    assert key not in ssh.command_ephemeral


@pytest.mark.unit
def test_ensure_conversation_thread_id_restores_without_db_insert():
    tid = uuid.uuid4()
    ssh = MagicMock()
    ssh.command_ephemeral = {_conversation_thread_ephemeral_storage_key(99): str(tid)}
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="tr1",
        permissions=[],
        session=ssh,
        metadata=None,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = object()
    out = ensure_conversation_thread_id(
        db,
        context=ctx,
        caller_account_node_id=10,
        agent_node_id=99,
    )
    assert out == tid
    assert get_thread_id_from_context(ctx) == tid
    db.add.assert_not_called()


@pytest.mark.unit
def test_ensure_conversation_thread_id_creates_and_sets_ephemeral(monkeypatch):
    fixed = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.conversation_stm_service.uuid.uuid4",
        lambda: fixed,
    )
    ssh = MagicMock()
    ssh.command_ephemeral = {}
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="tr2",
        permissions=[],
        session=ssh,
        metadata=None,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    out = ensure_conversation_thread_id(
        db,
        context=ctx,
        caller_account_node_id=10,
        agent_node_id=42,
    )
    assert out == fixed
    assert ssh.command_ephemeral[_conversation_thread_ephemeral_storage_key(42)] == str(fixed)
    db.add.assert_called_once()
    db.flush.assert_called_once()


@pytest.mark.unit
def test_clear_conversation_thread_for_transport():
    tid = uuid.uuid4()
    ssh = MagicMock()
    key = _conversation_thread_ephemeral_storage_key(3)
    ssh.command_ephemeral = {key: str(tid)}
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="x",
        permissions=[],
        session=ssh,
        metadata={},
    )
    clear_conversation_thread_for_transport(ctx, 3)
    assert key not in ssh.command_ephemeral


@pytest.mark.unit
def test_persist_conversation_thread_for_transport():
    tid = uuid.uuid4()
    ssh = MagicMock()
    ssh.command_ephemeral = {}
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="x",
        permissions=[],
        session=ssh,
        metadata={},
    )
    persist_conversation_thread_for_transport(ctx, 5, tid)
    assert ssh.command_ephemeral[_conversation_thread_ephemeral_storage_key(5)] == str(tid)
