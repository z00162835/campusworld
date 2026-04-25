"""Tests for tick-level caller snapshot and NpcAgentTickInputs (F10)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.commands.base import CommandContext
from app.core.settings import AgentLlmServiceConfig
from app.game_engine.agent_runtime.agent_tick_context import (
    CallerGraphSnapshot,
    NpcAgentTickInputs,
    build_caller_graph_snapshot,
)
from app.game_engine.agent_runtime.llm_client import StubLlmClient
from app.game_engine.agent_runtime.worker import LlmPdcaAssistantWorker


@pytest.mark.unit
def test_build_caller_graph_snapshot_delegates_to_graph_helpers(monkeypatch):
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.command_caller_graph.resolve_caller_node_id",
        lambda s, c: 10,
    )
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.command_caller_graph.resolve_caller_location_id",
        lambda s, cid: 20,
    )
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.command_caller_graph.resolve_room_display_name",
        lambda s, lid: "TestRoom",
    )
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        roles=[],
    )
    snap = build_caller_graph_snapshot(None, ctx)
    assert snap.caller_node_id == 10
    assert snap.caller_location_node_id == 20
    assert snap.caller_location_display_name == "TestRoom"


@pytest.mark.unit
def test_worker_create_tick_inputs_agent_id_mismatch_raises():
    session = MagicMock()
    agent = MagicMock()
    agent.id = 99
    agent.attributes = {"service_id": "aico", "tool_allowlist": []}
    cfg = AgentLlmServiceConfig(system_prompt="sys", use_http_llm=False)
    snap = CallerGraphSnapshot(1, 2, "R")
    ti = NpcAgentTickInputs(
        agent=agent,
        attrs=dict(agent.attributes or {}),
        service_id="aico",
        model_ref_s=None,
        cfg=cfg,
        caller=snap,
    )
    fb = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        roles=[],
        db_session=session,
    )
    with pytest.raises(ValueError, match="does not match"):
        LlmPdcaAssistantWorker.create(
            session,
            7,
            invoker_context=fb,
            llm_client=StubLlmClient(),
            agent_llm_config=cfg,
            tick_inputs=ti,
        )


@pytest.mark.unit
def test_worker_create_with_tick_inputs_skips_resolve_caller(monkeypatch):
    """Tier-1 primer uses snapshot; graph resolve must not run in worker."""
    calls: list[str] = []

    def _boom(*_a, **_k):
        calls.append("resolve_caller_node_id")
        raise AssertionError("resolve_caller_node_id should not run when tick_inputs provided")

    monkeypatch.setattr(
        "app.game_engine.agent_runtime.command_caller_graph.resolve_caller_node_id",
        _boom,
    )
    session = MagicMock()
    agent = MagicMock()
    agent.id = 3
    agent.attributes = {"service_id": "aico", "tool_allowlist": []}
    cfg = AgentLlmServiceConfig(system_prompt="sys", use_http_llm=False)
    snap = CallerGraphSnapshot(1, 2, "SnapRoom")
    ti = NpcAgentTickInputs(
        agent=agent,
        attrs=dict(agent.attributes or {}),
        service_id="aico",
        model_ref_s=None,
        cfg=cfg,
        caller=snap,
    )
    fb = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        roles=[],
        db_session=session,
    )
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.worker.get_config",
        lambda: MagicMock(),
    )
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.worker.is_aico_observability_enabled",
        lambda _cm: False,
    )
    LlmPdcaAssistantWorker.create(
        session,
        3,
        invoker_context=fb,
        llm_client=StubLlmClient(),
        agent_llm_config=cfg,
        tick_inputs=ti,
    )
    assert not calls
