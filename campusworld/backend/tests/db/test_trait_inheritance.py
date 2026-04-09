"""PostgreSQL: instance traits forced from type tables (triggers)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.database import engine
from app.models.graph import Node, NodeType
from db.schema_migrations import ensure_graph_schema, ensure_graph_seed_ontology


@pytest.mark.integration
def test_node_insert_inherits_traits_from_node_types():
    if engine is None:
        pytest.skip("database engine not configured")
    if "postgresql" not in str(engine.url).lower():
        pytest.skip("PostgreSQL required for trait triggers")

    ensure_graph_schema(engine)
    ensure_graph_seed_ontology(engine)

    Session = sessionmaker(bind=engine)
    session = Session()
    node_id = None
    try:
        nt = session.query(NodeType).filter(NodeType.type_code == "room").first()
        assert nt is not None, "graph seed ontology should define room"

        n = Node(
            type_id=nt.id,
            type_code="room",
            name=f"trait_trigger_test_{uuid.uuid4().hex[:10]}",
            trait_class="AGENT",
            trait_mask=999999,
            attributes={},
            tags=[],
        )
        session.add(n)
        session.commit()
        session.refresh(n)
        node_id = n.id

        assert n.trait_class == nt.trait_class
        assert int(n.trait_mask or 0) == int(nt.trait_mask or 0)
    finally:
        if node_id is not None:
            session.query(Node).filter(Node.id == node_id).delete()
            session.commit()
        session.close()
