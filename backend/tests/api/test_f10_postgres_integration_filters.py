"""
PostgreSQL integration tests for graph list filter semantics.

These tests validate SQL-level behavior on a real database:
- ILIKE name_like
- tags_any JSONB contains behavior
- trait mask bitwise filters
"""

import sys
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.api.v1.api import api_router
from app.api.v1.dependencies import APIPrincipal, get_api_principal
from app.constants.data_access_defaults import ADMIN_DATA_ACCESS
from app.core.database import db_session_context, engine


def _require_postgres():
    if engine is None:
        pytest.skip("database engine not configured")
    if "postgresql" not in str(engine.url).lower():
        pytest.skip("PostgreSQL required for integration filter tests")


@pytest.fixture(scope="module", autouse=True)
def _setup_schema_once():
    """
    Keep integration tests fast/stable:
    - verify PostgreSQL once
    - avoid DDL in test path (DDL can wait on locks and hang)
    """
    _require_postgres()
    with db_session_context() as session:
        # serialize this module in shared dev DB to avoid lock storms
        locked = session.execute(
            text("SELECT pg_try_advisory_lock(:k)"),
            {"k": 1042010},
        ).scalar()
        if not locked:
            pytest.skip("another integration session holds advisory lock")
        try:
            session.execute(text("SET statement_timeout = '10s'"))
            session.execute(text("SET lock_timeout = '5s'"))
            session.execute(text("SELECT 1"))
            # Ensure required tables exist; skip gracefully in uninitialized DB.
            for table_name in ("node_types", "relationship_types", "nodes", "relationships"):
                exists = session.execute(
                    text(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM information_schema.tables
                            WHERE table_schema = 'public' AND table_name = :t
                        )
                        """
                    ),
                    {"t": table_name},
                ).scalar()
                if not exists:
                    pytest.skip(f"table `{table_name}` not found; initialize DB schema first")
        finally:
            session.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": 1042010})


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")

    async def _mock_principal():
        return APIPrincipal(
            subject="itest",
            auth_type="jwt",
            roles=["admin"],
            permissions=["ontology.read", "ontology.write", "graph.read", "graph.write"],
            user_attrs={"data_access": ADMIN_DATA_ACCESS},
            scopes=[],
            api_key_kid=None,
        )

    app.dependency_overrides[get_api_principal] = _mock_principal
    return TestClient(app, raise_server_exceptions=False)


def _cleanup(seed: str) -> None:
    # lock contention is expected in shared local DB; retry briefly instead of hanging
    for _ in range(3):
        try:
            with db_session_context() as session:
                session.execute(text("SET LOCAL statement_timeout = '15s'"))
                session.execute(text("SET LOCAL lock_timeout = '5s'"))
                session.execute(
                    text("DELETE FROM relationships WHERE type_code LIKE :p"),
                    {"p": f"itest_rel_{seed}%"},
                )
                session.execute(
                    text("DELETE FROM nodes WHERE type_code LIKE :p"),
                    {"p": f"itest_node_{seed}%"},
                )
                session.execute(
                    text("DELETE FROM relationship_types WHERE type_code LIKE :p"),
                    {"p": f"itest_rel_{seed}%"},
                )
                session.execute(
                    text("DELETE FROM node_types WHERE type_code LIKE :p"),
                    {"p": f"itest_node_{seed}%"},
                )
                session.commit()
            return
        except OperationalError:
            continue


def _seed_data(seed: str) -> dict:
    node_type_code = f"itest_node_{seed}"
    rel_type_code = f"itest_rel_{seed}"
    world_id = f"itest_world_{seed}"
    with db_session_context() as session:
        session.execute(text("SET LOCAL statement_timeout = '15s'"))
        session.execute(text("SET LOCAL lock_timeout = '5s'"))
        session.execute(
            text(
                """
                INSERT INTO node_types (
                    type_code, type_name, typeclass, status, classname, module_path,
                    schema_definition, schema_default, inferred_rules, tags, ui_config,
                    trait_class, trait_mask
                )
                VALUES (
                    :tc, :tn, :tclass, 0, 'ITestNode', 'tests',
                    '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, '[]'::jsonb, '{}'::jsonb,
                    'ROOM', 2
                )
                """
            ),
            {"tc": node_type_code, "tn": "Integration Test Node", "tclass": "tests.Node"},
        )
        session.execute(
            text(
                """
                INSERT INTO relationship_types (
                    type_code, type_name, typeclass, status, constraints,
                    schema_definition, inferred_rules, tags, ui_config,
                    is_directed, is_symmetric, is_transitive
                )
                VALUES (
                    :tc, :tn, :tclass, 0, '{}'::jsonb,
                    '{}'::jsonb, '{}'::jsonb, '[]'::jsonb, '{}'::jsonb,
                    TRUE, FALSE, FALSE
                )
                """
            ),
            {"tc": rel_type_code, "tn": "Located In Test", "tclass": "tests.Rel"},
        )

        node_type_id = session.execute(
            text("SELECT id FROM node_types WHERE type_code = :tc"),
            {"tc": node_type_code},
        ).scalar_one()
        rel_type_id = session.execute(
            text("SELECT id FROM relationship_types WHERE type_code = :tc"),
            {"tc": rel_type_code},
        ).scalar_one()

        n1 = session.execute(
            text(
                """
                INSERT INTO nodes (uuid, type_id, type_code, name, is_active, is_public, trait_class, trait_mask, attributes, tags)
                VALUES (uuid_generate_v4(), :tid, :tc, 'AlphaRoom', TRUE, TRUE, 'ROOM', 2, CAST(:attrs AS jsonb), CAST(:tags AS jsonb))
                RETURNING id
                """
            ),
            {"tid": node_type_id, "tc": node_type_code, "attrs": f'{{"world_id":"{world_id}"}}', "tags": '["hicampus","room"]'},
        ).scalar_one()
        n2 = session.execute(
            text(
                """
                INSERT INTO nodes (uuid, type_id, type_code, name, is_active, is_public, trait_class, trait_mask, attributes, tags)
                VALUES (uuid_generate_v4(), :tid, :tc, 'beta-room', TRUE, FALSE, 'ROOM', 3, CAST(:attrs AS jsonb), CAST(:tags AS jsonb))
                RETURNING id
                """
            ),
            {"tid": node_type_id, "tc": node_type_code, "attrs": f'{{"world_id":"{world_id}"}}', "tags": '["lab"]'},
        ).scalar_one()
        n3 = session.execute(
            text(
                """
                INSERT INTO nodes (uuid, type_id, type_code, name, is_active, is_public, trait_class, trait_mask, attributes, tags)
                VALUES (uuid_generate_v4(), :tid, :tc, 'Gamma', TRUE, TRUE, 'ROOM', 0, CAST(:attrs AS jsonb), CAST(:tags AS jsonb))
                RETURNING id
                """
            ),
            {"tid": node_type_id, "tc": node_type_code, "attrs": f'{{"world_id":"other_{world_id}"}}', "tags": '["misc"]'},
        ).scalar_one()

        session.execute(
            text(
                """
                INSERT INTO relationships (uuid, type_id, type_code, source_id, target_id, is_active, trait_class, trait_mask, tags, attributes)
                VALUES (uuid_generate_v4(), :rtid, :tc, :s, :t, TRUE, 'LINK', 1, CAST(:tags AS jsonb), '{}'::jsonb)
                """
            ),
            {"rtid": rel_type_id, "tc": rel_type_code, "s": n1, "t": n2, "tags": '["hicampus"]'},
        )
        session.commit()
    return {"node_type_code": node_type_code, "rel_type_code": rel_type_code, "world_id": world_id}


@pytest.mark.integration
@pytest.mark.postgres_integration
def test_graph_nodes_filters_ilike_tags_and_trait_masks_postgres():
    seed = uuid.uuid4().hex[:8]
    data = _seed_data(seed)
    try:
        with _client() as client:
            r = client.get(
                "/api/v1/graph/nodes",
                params={
                    "type_code": data["node_type_code"],
                    "name_like": "alpha",
                    "tags_any": "hicampus, unknown",
                    "required_any_mask": 2,
                    "required_all_mask": 2,
                },
            )
            assert r.status_code == 200
            body = r.json()
            assert body["page"]["total"] == 1
            assert body["items"][0]["name"] == "AlphaRoom"
    finally:
        _cleanup(seed)


@pytest.mark.integration
@pytest.mark.postgres_integration
def test_world_nodes_filters_ilike_tags_and_is_public_postgres():
    seed = uuid.uuid4().hex[:8]
    data = _seed_data(seed)
    try:
        with _client() as client:
            r = client.get(
                f"/api/v1/worlds/{data['world_id']}/nodes",
                params={"name_like": "ROOM", "tags_any": " room, hicampus ", "is_public": "true"},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["page"]["total"] == 1
            assert body["items"][0]["name"] == "AlphaRoom"
    finally:
        _cleanup(seed)


@pytest.mark.integration
@pytest.mark.postgres_integration
def test_world_relationships_name_like_join_and_tags_any_postgres():
    seed = uuid.uuid4().hex[:8]
    data = _seed_data(seed)
    try:
        with _client() as client:
            r = client.get(
                f"/api/v1/worlds/{data['world_id']}/relationships",
                params={"name_like": "located", "tags_any": "hicampus"},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["page"]["total"] == 1
            assert body["items"][0]["type_code"] == data["rel_type_code"]
    finally:
        _cleanup(seed)
