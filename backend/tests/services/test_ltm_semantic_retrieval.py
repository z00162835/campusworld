"""LTM semantic retrieval: vector KNN + link graph (PostgreSQL + pgvector)."""

from __future__ import annotations

import pytest

from app.models.graph import Node, NodeType
from app.models.system import AgentLongTermMemory
from app.services.ltm_semantic_retrieval import (
    EMBEDDING_DIM,
    build_ltm_memory_context_for_tick,
    create_ltm_link,
    expand_ltm_linked_neighbors,
    search_ltm_by_embedding,
    set_ltm_embedding,
)


def _unit_vec(first: float = 1.0) -> list[float]:
    v = [0.0] * EMBEDDING_DIM
    v[0] = first
    return v


@pytest.mark.postgres_integration
def test_ltm_embedding_knn_and_link_expansion():
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
        agent = Node(
            type_id=nt.id,
            type_code="npc_agent",
            name="ltm_semantic_test",
            attributes={
                "agent_role": "sys_worker",
                "service_id": "ltm-semantic-test",
                "decision_mode": "rules",
                "enabled": True,
            },
        )
        session.add(agent)
        session.commit()
        session.refresh(agent)

        ltm_a = AgentLongTermMemory(
            agent_node_id=agent.id,
            summary="building inspection A",
            payload={"k": "a"},
        )
        ltm_b = AgentLongTermMemory(
            agent_node_id=agent.id,
            summary="device batch B",
            payload={"k": "b"},
        )
        session.add(ltm_a)
        session.add(ltm_b)
        session.commit()
        session.refresh(ltm_a)
        session.refresh(ltm_b)

        set_ltm_embedding(
            session,
            ltm_a.id,
            agent.id,
            _unit_vec(1.0),
            embedding_model="test-dim1536",
        )
        set_ltm_embedding(
            session,
            ltm_b.id,
            agent.id,
            _unit_vec(0.0),
            embedding_model="test-dim1536",
        )
        session.commit()

        q = _unit_vec(1.0)
        hits = search_ltm_by_embedding(session, agent.id, q, k=2, embedding_model="test-dim1536")
        assert len(hits) == 2
        assert hits[0][0] == ltm_a.id

        create_ltm_link(
            session,
            agent_node_id=agent.id,
            source_ltm_id=ltm_a.id,
            target_ltm_id=ltm_b.id,
            link_type="related_fact",
        )
        session.commit()

        expanded = expand_ltm_linked_neighbors(session, agent.id, [ltm_a.id], max_depth=2)
        assert ltm_a.id in expanded
        assert ltm_b.id in expanded

        session.delete(agent)
        session.commit()
    finally:
        session.close()


@pytest.mark.unit
def test_search_requires_dimension():
    from unittest.mock import MagicMock

    session = MagicMock()
    with pytest.raises(ValueError, match="1536"):
        search_ltm_by_embedding(session, 1, [0.0] * 10, k=1)


@pytest.mark.unit
def test_build_ltm_memory_context_for_tick_empty():
    from unittest.mock import MagicMock

    from app.models.system import AgentLongTermMemory

    session = MagicMock()
    chain = session.query.return_value
    chain.filter.return_value = chain
    chain.order_by.return_value = chain
    chain.limit.return_value.all.return_value = []
    assert build_ltm_memory_context_for_tick(session, 1, user_message="hi") is None
    session.query.assert_called_once_with(AgentLongTermMemory)


@pytest.mark.unit
def test_build_ltm_memory_context_for_tick_joins_summaries():
    from unittest.mock import MagicMock

    from app.models.system import AgentLongTermMemory

    r1 = MagicMock()
    r1.summary = "alpha"
    r2 = MagicMock()
    r2.summary = "beta"
    session = MagicMock()
    chain = session.query.return_value
    chain.filter.return_value = chain
    chain.order_by.return_value = chain
    chain.limit.return_value.all.return_value = [r1, r2]
    out = build_ltm_memory_context_for_tick(session, 7, user_message="q")
    assert out is not None
    assert "alpha" in out and "beta" in out
    session.query.assert_called_once_with(AgentLongTermMemory)
