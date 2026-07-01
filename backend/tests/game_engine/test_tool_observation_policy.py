from __future__ import annotations

import pytest

from app.game_engine.agent_runtime import tool_observation_policy as policy_mod
from app.game_engine.agent_runtime.tool_observation_policy import resolve_tool_observation_policy


@pytest.mark.unit
def test_unknown_or_pending_command_observation_policy_defaults_summary():
    policy = resolve_tool_observation_policy("definitely_unknown_command")
    assert policy.message_mode == "summary"


@pytest.mark.unit
def test_read_commands_including_space_use_full_observation():
    from app.commands.init_commands import initialize_commands

    initialize_commands(force_reinit=True)
    for name in ("find", "space"):
        policy = resolve_tool_observation_policy(name)
        assert policy.message_mode == "full", name


@pytest.mark.unit
def test_mutate_movement_command_uses_summary_observation():
    from app.commands.init_commands import initialize_commands

    initialize_commands(force_reinit=True)
    # ``go`` mutates character location (write_low) so its observation policy
    # collapses to summary for LLM context, unlike pure read commands.
    policy = resolve_tool_observation_policy("go")
    assert policy.message_mode == "summary"


@pytest.mark.unit
def test_mutate_command_observation_summary():
    policy = resolve_tool_observation_policy("create")
    assert policy.message_mode == "summary"


@pytest.mark.unit
def test_agent_list_full_tool_add_summary():
    assert resolve_tool_observation_policy("agent", args=["list"]).message_mode == "full"
    assert resolve_tool_observation_policy("agent", args=["tool", "add"]).message_mode == "summary"


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
