"""Unit tests for PDCA prompt tuning (slim follow-up system, schema allowlist helpers)."""

from __future__ import annotations

import pytest

from app.core.settings import AgentLlmServiceConfig
from app.game_engine.agent_runtime.frameworks.llm_pdca import (
    _phase_system_core,
    _resolve_pdca_slim_followup_system,
    _tool_schema_allowlist_from_payload,
)


@pytest.mark.unit
def test_pdca_slim_followup_default_enabled():
    cfg = AgentLlmServiceConfig(extra={})
    assert _resolve_pdca_slim_followup_system(cfg)


@pytest.mark.unit
def test_pdca_slim_followup_can_disable():
    cfg = AgentLlmServiceConfig(extra={"pdca_use_slim_followup_system": False})
    assert _resolve_pdca_slim_followup_system(cfg) is None


@pytest.mark.unit
def test_phase_system_core_uses_slim_for_do_only_when_configured():
    cfg = AgentLlmServiceConfig(extra={})
    slim = _resolve_pdca_slim_followup_system(cfg)
    full = "FULL_SYSTEM_BLOCK"
    phases = {"plan": "p", "do": "d", "check": "c", "act": "a"}
    assert "FULL_SYSTEM_BLOCK" in _phase_system_core(full, "plan", phases, slim)
    plan_do = _phase_system_core(full, "do", phases, slim)
    assert "FULL_SYSTEM_BLOCK" not in plan_do
    assert slim is not None
    assert slim.splitlines()[0] in plan_do


@pytest.mark.unit
def test_phase_system_core_falls_back_to_full_when_slim_disabled():
    cfg = AgentLlmServiceConfig(extra={"pdca_use_slim_followup_system": False})
    slim = _resolve_pdca_slim_followup_system(cfg)
    assert slim is None
    full = "FULL_SYSTEM_BLOCK"
    phases = {"do": "d"}
    body = _phase_system_core(full, "do", phases, slim)
    assert "FULL_SYSTEM_BLOCK" in body


@pytest.mark.unit
def test_tool_schema_allowlist_from_payload():
    assert _tool_schema_allowlist_from_payload({}) is None
    assert _tool_schema_allowlist_from_payload({"pdca_tool_schema_allowlist": []}) is None
    assert _tool_schema_allowlist_from_payload({"pdca_tool_schema_allowlist": ["find", "look"]}) == [
        "find",
        "look",
    ]
