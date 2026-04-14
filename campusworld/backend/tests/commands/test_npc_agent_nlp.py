"""Tests for assistant NLP tick (passthrough + CommandResult shape)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.commands.base import CommandContext
from app.commands.npc_agent_nlp import assistant_nlp_command_result, run_npc_agent_nlp_tick
from app.game_engine.agent_runtime.agent_llm_config import invalidate_aico_system_llm_config
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunResult


@pytest.mark.unit
def test_assistant_nlp_command_result_plain_message():
    res = FrameworkRunResult(ok=True, message="  hello  ", final_phase="act")
    r = assistant_nlp_command_result("aico", res, service_id="aico")
    assert r.success
    assert r.message == "hello"
    assert r.data["ok"] is True
    assert r.data["phase"] == "act"
    assert r.data["handle"] == "aico"
    assert r.data["service_id"] == "aico"


@pytest.mark.unit
@patch("app.game_engine.agent_runtime.llm_client.http_llm_available", return_value=False)
def test_run_npc_agent_nlp_tick_passthrough_no_worker(_mock_http, monkeypatch):
    invalidate_aico_system_llm_config()
    mock_cm = MagicMock()
    mock_cm.get_nested.return_value = {}
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.agent_llm_config.get_config",
        lambda: mock_cm,
    )
    node = MagicMock()
    node.id = 1
    node.attributes = {
        "service_id": "aico",
        "decision_mode": "llm",
        "model_config_ref": "aico",
    }
    ctx = CommandContext("u1", "alice", "sess1", [], db_session=MagicMock())
    out = run_npc_agent_nlp_tick(ctx.db_session, node, ctx, "  hi there  ")
    assert out.ok is True
    assert out.message == "hi there"
    assert out.final_phase == "passthrough"
