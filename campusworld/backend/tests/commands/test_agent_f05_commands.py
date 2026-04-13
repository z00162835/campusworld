"""`agent list` / `agent status` (PostgreSQL integration + light unit checks)."""

from __future__ import annotations

import json
import uuid

import pytest

from app.commands.agent_commands import (
    AgentCommand,
    AGENT_STATUS_ACCESS_ERROR,
    derive_agent_status,
)
from app.commands.base import CommandContext
from app.models.graph import Node, NodeType
from app.models.system import AgentRunRecord


def test_agent_command_requires_db_session():
    cmd = AgentCommand()
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        db_session=None,
    )
    r = cmd.execute(ctx, [])
    assert not r.success
    assert "database session required" in r.message


def test_agent_command_usage_no_subcommand():
    cmd = AgentCommand()
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        db_session=object(),
    )
    r = cmd.execute(ctx, [])
    assert not r.success
    assert "agent" in r.message.lower()


def test_agent_command_unknown_subcommand():
    cmd = AgentCommand()
    ctx = CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        db_session=object(),
    )
    r = cmd.execute(ctx, ["nope"])
    assert not r.success
    assert "agent" in r.message.lower()


@pytest.mark.postgres_integration
def test_agent_list_and_status_consistency():
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
        svc = "f05-agent-list-test"
        agent = Node(
            type_id=nt.id,
            type_code="npc_agent",
            name="f05_test_agent",
            attributes={
                "service_id": svc,
                "decision_mode": "rules",
                "enabled": True,
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
        ac = AgentCommand()
        r_list = ac.execute(ctx, ["list"])
        assert r_list.success
        data = json.loads(r_list.message)
        assert "agents" in data
        mine = next((a for a in data["agents"] if a.get("service_id") == svc), None)
        assert mine is not None
        assert mine["status"] == "idle"
        assert mine["agent_node_id"] == agent.id

        r_st = ac.execute(ctx, ["status", svc])
        assert r_st.success
        one = json.loads(r_st.message)
        assert one["status"] == mine["status"]
        assert one["service_id"] == svc

        r_bad = ac.execute(ctx, ["status", "no-such-service-id-f05"])
        assert not r_bad.success
        assert r_bad.message == AGENT_STATUS_ACCESS_ERROR

        session.delete(agent)
        session.commit()
    finally:
        session.close()


@pytest.mark.postgres_integration
def test_agent_list_includes_disabled_as_unavailable():
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
        svc = "f05-disabled-test"
        agent = Node(
            type_id=nt.id,
            type_code="npc_agent",
            name="f05_disabled",
            attributes={
                "service_id": svc,
                "enabled": False,
            },
        )
        session.add(agent)
        session.commit()
        session.refresh(agent)

        ctx = CommandContext(
            user_id="1",
            username="test",
            session_id="s1",
            permissions=["admin.system"],
            db_session=session,
        )
        ac = AgentCommand()
        r_list = ac.execute(ctx, ["list"])
        assert r_list.success
        data = json.loads(r_list.message)
        row = next((a for a in data["agents"] if a.get("service_id") == svc), None)
        assert row is not None
        assert row["status"] == "unavailable"

        r_st = ac.execute(ctx, ["status", svc])
        assert r_st.success
        one = json.loads(r_st.message)
        assert one["status"] == "unavailable"

        session.delete(agent)
        session.commit()
    finally:
        session.close()


@pytest.mark.postgres_integration
def test_derive_working_when_run_record_running():
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
        svc = "f05-working-test"
        agent = Node(
            type_id=nt.id,
            type_code="npc_agent",
            name="f05_working",
            attributes={"service_id": svc, "enabled": True},
        )
        session.add(agent)
        session.commit()
        session.refresh(agent)

        assert derive_agent_status(agent, session) == "idle"

        run = AgentRunRecord(
            agent_node_id=agent.id,
            run_id=uuid.uuid4(),
            phase="plan",
            status="running",
            command_trace=[],
        )
        session.add(run)
        session.commit()

        assert derive_agent_status(agent, session) == "working"

        run.ended_at = run.started_at
        run.status = "success"
        session.commit()
        assert derive_agent_status(agent, session) == "idle"

        session.delete(run)
        session.delete(agent)
        session.commit()
    finally:
        session.close()
