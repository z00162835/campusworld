"""Contract tests for optional LTM hook in npc_agent_nlp."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.commands.npc_agent_nlp import maybe_ltm_memory_context


@pytest.mark.unit
def test_maybe_ltm_disabled_without_enable_ltm():
    session = MagicMock()
    assert maybe_ltm_memory_context(session, 1, "hi", {}) is None


@pytest.mark.unit
def test_maybe_ltm_calls_build_when_enabled():
    session = MagicMock()
    with patch(
        "app.commands.npc_agent_nlp.build_ltm_memory_context_for_tick",
        return_value="mem",
    ) as m:
        out = maybe_ltm_memory_context(session, 42, "hello", {"enable_ltm": True})
    assert out == "mem"
    m.assert_called_once()
    call_kw = m.call_args.kwargs
    assert call_kw["user_message"] == "hello"


@pytest.mark.unit
def test_maybe_ltm_disabled_when_placeholder_skip(monkeypatch):
    monkeypatch.setenv("AICO_SKIP_LTM_PLACEHOLDER", "1")
    session = MagicMock()
    with patch("app.commands.npc_agent_nlp.build_ltm_memory_context_for_tick") as m:
        out = maybe_ltm_memory_context(session, 1, "hi", {"enable_ltm": True})
    assert out is None
    m.assert_not_called()
