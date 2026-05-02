"""F12 STM helpers (unit, no database)."""

from __future__ import annotations

import pytest

from unittest.mock import MagicMock

from app.game_engine.agent_runtime.conversation_stm_service import (
    apply_compaction_truncate,
    append_turns_to_messages,
    finalize_daemon_possession_after_success,
    format_stm_for_prompt,
    normalize_messages,
    stm_should_compact_after_append,
)
from app.game_engine.agent_runtime.frameworks.llm_pdca import _assemble_plan_user


@pytest.mark.unit
def test_assemble_plan_user_puts_recent_conversation_before_retrieved_memory():
    text = _assemble_plan_user(
        user_msg="hi",
        memory="LTM_BLOCK",
        world_snapshot="",
        tool_manifest_text="",
        intent_hint=None,
        recent_conversation="STM_BLOCK",
    )
    assert text.index("Recent conversation") < text.index("Retrieved memory")
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
