"""F02 agent commands integration (PostgreSQL)."""

from __future__ import annotations

import json

import pytest

from app.commands.agent_commands import AgentCapabilitiesCommand, AgentNlpCommand, AgentRunCommand
from app.commands.base import CommandContext
from app.models.graph import Node, NodeType
from app.models.system import AgentRunRecord


@pytest.mark.postgres_integration
def test_agent_run_creates_run_record():
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
        svc = "knowledge-collector-test-f02"
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
        cap = AgentCapabilitiesCommand()
        r1 = cap.execute(ctx, [svc])
        assert r1.success
        data = json.loads(r1.message)
        assert data["service_id"] == svc

        run_cmd = AgentRunCommand()
        r2 = run_cmd.execute(ctx, [svc, "T-1001", "high", str(agent.id)])
        assert r2.success
        out = json.loads(r2.message)
        assert out["ok"] is True

        row = (
            session.query(AgentRunRecord)
            .filter(AgentRunRecord.agent_node_id == agent.id)
            .order_by(AgentRunRecord.started_at.desc())
            .first()
        )
        assert row is not None
        assert row.phase == "act"
        assert row.status == "success"
        assert any(
            isinstance(x, dict) and x.get("command") == "graph.patch_device_state" for x in (row.command_trace or [])
        )

        session.delete(agent)
        session.commit()
    finally:
        session.close()


@pytest.mark.postgres_integration
def test_agent_nlp_llm_pdca_creates_run_record():
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
        svc = "aico-nlp-test-f03"
        agent = Node(
            type_id=nt.id,
            type_code="npc_agent",
            name="aico_nlp_test",
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
        nlp = AgentNlpCommand()
        r = nlp.execute(ctx, [svc, "hello", "world"])
        assert r.success
        out = json.loads(r.message)
        assert out["ok"] is True
        assert "phase" in out

        row = (
            session.query(AgentRunRecord)
            .filter(AgentRunRecord.agent_node_id == agent.id)
            .order_by(AgentRunRecord.started_at.desc())
            .first()
        )
        assert row is not None
        assert row.phase == "act"
        trace = row.command_trace or []
        assert any(isinstance(x, dict) and x.get("step") == "plan" for x in trace)

        session.delete(agent)
        session.commit()
    finally:
        session.close()
