"""Agent memory tables: migration + ORM roundtrip."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.models.graph import Node
from app.models.system import AgentMemoryEntry, AgentRunRecord, AgentLongTermMemory


@pytest.mark.postgres_integration
def test_f02_agent_memory_schema_and_orm_roundtrip():
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
        nt = session.execute(
            text("SELECT id FROM node_types WHERE type_code = 'npc_agent' LIMIT 1")
        ).fetchone()
        if nt is None:
            pytest.skip("npc_agent node_types row missing")

        n = Node(
            type_id=nt[0],
            type_code="npc_agent",
            name="test_sys_worker_agent",
            attributes={
                "agent_role": "sys_worker",
                "service_id": "test-svc-f02",
                "decision_mode": "rules",
                "enabled": True,
            },
        )
        session.add(n)
        session.commit()
        session.refresh(n)

        mem = AgentMemoryEntry(
            agent_node_id=n.id,
            session_id=uuid.uuid4(),
            kind="raw",
            payload={"note": "unit test"},
        )
        session.add(mem)
        session.commit()
        session.refresh(mem)

        run = AgentRunRecord(
            agent_node_id=n.id,
            run_id=uuid.uuid4(),
            correlation_id="T-1001",
            phase="plan",
            command_trace=[{"command": "noop", "args": []}],
            status="running",
            graph_ops_summary={},
        )
        session.add(run)
        session.commit()

        ltm = AgentLongTermMemory(
            agent_node_id=n.id,
            summary="curated",
            payload={"k": "v"},
            source_memory_entry_id=mem.id,
        )
        session.add(ltm)
        session.commit()

        got = (
            session.query(AgentRunRecord)
            .filter(AgentRunRecord.agent_node_id == n.id)
            .first()
        )
        assert got is not None
        assert got.phase == "plan"
        assert got.command_trace[0]["command"] == "noop"

        session.delete(ltm)
        session.delete(run)
        session.delete(mem)
        session.delete(n)
        session.commit()
    finally:
        session.close()
