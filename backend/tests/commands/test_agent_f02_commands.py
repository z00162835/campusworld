"""Agent commands integration: capabilities and NLP tick + run audit (PostgreSQL)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.commands.agent_commands import AgentCommand
from app.commands.base import CommandContext
from app.commands.npc_agent_nlp import run_npc_agent_nlp_tick
from app.game_engine.agent_runtime.agent_llm_config import invalidate_aico_system_llm_config
from app.game_engine.agent_runtime.llm_client import StubLlmClient
from app.models.graph import Node, NodeType
from app.models.system import AgentRunRecord


@pytest.mark.postgres_integration
def test_agent_show_resolves_service_id():
    from app.core.database import SessionLocal, engine
    from db.migrate_report import is_postgresql_engine
    from db.schema_migrations import (
        ensure_f02_agent_memory_schema,
        ensure_f02_ltm_semantic_extension,
        ensure_graph_schema,
        ensure_graph_seed_ontology,
    )

    if not is_postgresql_engine(engine):
        pytest.skip("PostgreSQL only")

    ensure_graph_schema(engine)
    ensure_graph_seed_ontology(engine)
    ensure_f02_agent_memory_schema(engine)
    ensure_f02_ltm_semantic_extension(engine)

    session = SessionLocal()
    try:
        nt = session.query(NodeType).filter(NodeType.type_code == "npc_agent").first()
        assert nt is not None
        svc = "knowledge-collector-test-capabilities"
        agent = Node(
            type_id=nt.id,
            type_code="npc_agent",
            name="sys_worker_test",
            attributes={
                "agent_role": "sys_worker",
                "service_id": svc,
                "decision_mode": "rules",
                "enabled": True,
                "tool_allowlist": ["help"],
            },
        )
        session.add(agent)
        session.commit()
        session.refresh(agent)

        ctx = CommandContext(
            user_id=str(agent.id),
            username="test",
            session_id="s1",
            permissions=["admin.system"],
            db_session=session,
        )
        ag = AgentCommand()
        r1 = ag.execute(ctx, ["show", svc])
        assert r1.success
        data = json.loads(r1.message)
        assert data["id"] == svc
        assert data["agent_node_id"] == agent.id

        session.delete(agent)
        session.commit()
    finally:
        session.close()


@pytest.mark.postgres_integration
def test_npc_agent_nlp_tick_stub_llm_writes_run_record(monkeypatch):
    """
    With HTTP LLM gated on but client stubbed, run_npc_agent_nlp_tick persists agent_run_records
    (same engine as aico / @handle; no real provider calls).
    """
    from app.core.database import SessionLocal, engine
    from db.migrate_report import is_postgresql_engine
    from db.schema_migrations import (
        ensure_f02_agent_memory_schema,
        ensure_f02_ltm_semantic_extension,
        ensure_graph_schema,
        ensure_graph_seed_ontology,
    )

    if not is_postgresql_engine(engine):
        pytest.skip("PostgreSQL only")

    invalidate_aico_system_llm_config()
    mock_cm = MagicMock()
    mock_cm.get_nested.return_value = {}
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.agent_llm_config.get_config",
        lambda: mock_cm,
    )
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.llm_client.http_llm_available",
        lambda _cfg: True,
    )
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.llm_client.build_llm_client_from_service_config",
        lambda _cfg: StubLlmClient(),
    )

    ensure_graph_schema(engine)
    ensure_graph_seed_ontology(engine)
    ensure_f02_agent_memory_schema(engine)
    ensure_f02_ltm_semantic_extension(engine)

    session = SessionLocal()
    try:
        nt = session.query(NodeType).filter(NodeType.type_code == "npc_agent").first()
        assert nt is not None
        svc = "aico-nlp-pg-integration"
        agent = Node(
            type_id=nt.id,
            type_code="npc_agent",
            name="aico_nlp_pg",
            attributes={
                "agent_role": "narrative_npc",
                "service_id": svc,
                "decision_mode": "llm",
                "enabled": True,
                "cognition_profile_ref": "pdca_v1",
                "model_config_ref": "aico",
                "tool_allowlist": ["help"],
            },
        )
        session.add(agent)
        session.commit()
        session.refresh(agent)

        ctx = CommandContext(
            user_id=str(agent.id),
            username="test",
            session_id="s1",
            permissions=["admin.system"],
            db_session=session,
        )
        res = run_npc_agent_nlp_tick(session, agent, ctx, "hello world")
        session.commit()
        assert res.ok is True
        assert res.final_phase == "act"

        row = (
            session.query(AgentRunRecord)
            .filter(AgentRunRecord.agent_node_id == agent.id)
            .order_by(AgentRunRecord.started_at.desc())
            .first()
        )
        assert row is not None
        assert row.phase == "act"
        assert row.status == "success"
        trace = row.command_trace or []
        assert any(isinstance(x, dict) and x.get("step") == "plan" for x in trace)

        session.delete(agent)
        session.commit()
    finally:
        session.close()
        invalidate_aico_system_llm_config()
