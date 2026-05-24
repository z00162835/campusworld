from __future__ import annotations

import pytest

from app.game_engine.agent_runtime import tool_observation_policy as policy_mod
from app.game_engine.agent_runtime.tool_observation_policy import resolve_tool_observation_policy


@pytest.mark.unit
def test_unknown_or_pending_command_observation_policy_defaults_summary():
    policy = resolve_tool_observation_policy("definitely_unknown_command")
    assert policy.message_mode == "summary"


@pytest.mark.unit
def test_explicit_read_command_observation_policy_defaults_full():
    policy = resolve_tool_observation_policy("find")
    assert policy.message_mode == "full"


@pytest.mark.unit
def test_command_ability_observation_policy_override(monkeypatch):
    monkeypatch.setattr(
        policy_mod,
        "_command_ability_policy",
        lambda session, command_name: {
            "message_mode": "blocked",
            "max_message_chars": 128,
            "trace_preview_chars": 32,
            "data_keys": ["ok"],
        },
    )
    policy = resolve_tool_observation_policy("help", session=object())
    assert policy.message_mode == "blocked"
    assert policy.max_message_chars == 128
    assert policy.trace_preview_chars == 32
    assert policy.data_keys == frozenset({"ok"})
