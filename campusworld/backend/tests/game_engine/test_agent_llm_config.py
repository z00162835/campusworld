"""Unit tests for agent_llm_config (F03 prompt_overrides)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.settings import AgentLlmServiceConfig
from app.game_engine.agent_runtime.agent_llm_config import (
    apply_model_config_from_attributes,
    apply_prompt_overrides,
    apply_prompt_overrides_from_attributes,
    resolve_agent_llm_config,
)


@pytest.mark.unit
def test_apply_prompt_overrides_system_and_phase_prompts():
    base = AgentLlmServiceConfig(
        system_prompt="base_sys",
        phase_prompts={"plan": "p1", "do": "d1"},
    )
    out = apply_prompt_overrides(
        base,
        {
            "system_prompt": "override_sys",
            "phase_prompts": {"plan": "p2", "check": "c2"},
        },
    )
    assert out.system_prompt == "override_sys"
    assert out.phase_prompts["plan"] == "p2"
    assert out.phase_prompts["do"] == "d1"
    assert out.phase_prompts["check"] == "c2"


@pytest.mark.unit
def test_apply_prompt_overrides_ignores_unknown_keys():
    base = AgentLlmServiceConfig(system_prompt="x", model="gpt-4o-mini")
    out = apply_prompt_overrides(
        base,
        {"system_prompt": "y", "model": "should-not-apply", "api_key_env": "SECRET"},
    )
    assert out.system_prompt == "y"
    assert out.model == "gpt-4o-mini"


@pytest.mark.unit
def test_apply_model_config_from_attributes_whitelist():
    base = AgentLlmServiceConfig(
        temperature=0.2,
        max_tokens=4096,
        model="gpt-4o-mini",
        api_key_env="AICO_OPENAI_API_KEY",
    )
    out = apply_model_config_from_attributes(
        base,
        {
            "model_config": {
                "temperature": 0.9,
                "max_tokens": 100,
                "model": "gpt-4o",
                "api_key_env": "SHOULD_NOT_MERGE",
            },
        },
    )
    assert out.temperature == 0.9
    assert out.max_tokens == 100
    assert out.model == "gpt-4o"
    assert out.api_key_env == "AICO_OPENAI_API_KEY"


@pytest.mark.unit
def test_resolve_agent_llm_config_order_yaml_model_config_prompt_overrides(monkeypatch):
    mock_cm = MagicMock()
    mock_cm.get_nested.return_value = {
        "aico": {
            "system_prompt": "yaml_sys",
            "temperature": 0.2,
            "model": "base-model",
        },
    }
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.agent_llm_config.get_config",
        lambda: mock_cm,
    )
    cfg = resolve_agent_llm_config(
        "aico",
        node_attributes={
            "model_config": {"temperature": 0.5},
            "prompt_overrides": {"system_prompt": "final_sys"},
        },
    )
    assert cfg.temperature == 0.5
    assert cfg.system_prompt == "final_sys"
    assert cfg.model == "base-model"


@pytest.mark.unit
def test_apply_prompt_overrides_from_attributes_none():
    cfg = AgentLlmServiceConfig(system_prompt="a")
    assert apply_prompt_overrides_from_attributes(cfg, None) is cfg
    assert apply_prompt_overrides_from_attributes(cfg, {}) is cfg
    assert apply_prompt_overrides_from_attributes(cfg, {"other": 1}) is cfg


@pytest.mark.unit
def test_resolve_agent_llm_config_merges_yaml_then_prompt_overrides(monkeypatch):
    mock_cm = MagicMock()
    mock_cm.get_nested.return_value = {
        "aico": {
            "system_prompt": "from_yaml",
            "phase_prompts": {"plan": "yaml_plan"},
            "model": "gpt-4o-mini",
        }
    }
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.agent_llm_config.get_config",
        lambda: mock_cm,
    )
    cfg = resolve_agent_llm_config(
        "aico",
        node_attributes={
            "prompt_overrides": {
                "system_prompt": "from_node",
                "phase_prompts": {"do": "node_do"},
            },
        },
    )
    assert cfg.system_prompt == "from_node"
    assert cfg.phase_prompts == {"plan": "yaml_plan", "do": "node_do"}
    assert cfg.model == "gpt-4o-mini"


@pytest.mark.unit
def test_resolve_agent_llm_config_prompt_overrides_without_yaml(monkeypatch):
    mock_cm = MagicMock()
    mock_cm.get_nested.return_value = {}
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.agent_llm_config.get_config",
        lambda: mock_cm,
    )
    cfg = resolve_agent_llm_config(
        "aico",
        node_attributes={
            "prompt_overrides": {"system_prompt": "node_only"},
        },
    )
    assert cfg.system_prompt == "node_only"
    assert cfg.model == ""  # Pydantic default
