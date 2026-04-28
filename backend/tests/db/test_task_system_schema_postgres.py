"""Phase B PR2: real PostgreSQL integration test for task_system schema apply.

Skipped unless ``CAMPUSWORLD_TEST_DATABASE_URL`` is set to a writable Postgres
instance. Asserts that ``ensure_task_system_schema`` + ``ensure_task_system_seed``
are idempotent and that key CHECK / UNIQUE / partial-index contracts behave as
documented in F04 §3.
"""

from __future__ import annotations

import json
import os
import uuid

import pytest
from sqlalchemy import create_engine, text


_DB_URL = os.environ.get("CAMPUSWORLD_TEST_DATABASE_URL", "").strip()


pytestmark = pytest.mark.postgres_integration


@pytest.fixture(scope="module")
def engine():
    if not _DB_URL or not _DB_URL.lower().startswith("postgresql"):
        pytest.skip(
            "CAMPUSWORLD_TEST_DATABASE_URL not set or not postgresql; "
            "skipping task_system DB integration test."
        )
    eng = create_engine(_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture
def applied_schema(engine):
    from db.schema_migrations import (
        ensure_task_system_schema,
        ensure_task_system_seed,
    )

    ensure_task_system_schema(engine)
    ensure_task_system_seed(engine)
    # Second invocation must remain a no-op.
    ensure_task_system_schema(engine)
    ensure_task_system_seed(engine)
    return engine


def _exec(engine, sql: str, params=None):
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        return conn.execute(text(sql), params or {})


def test_all_eight_tables_exist_after_apply(applied_schema):
    expected = (
        "task_workflow_definitions",
        "task_pools",
        "task_details",
        "task_assignments",
        "task_state_transitions",
        "task_runs",
        "task_events",
        "task_outbox",
    )
    for tbl in expected:
        rel = _exec(applied_schema, f"select to_regclass('public.{tbl}');").scalar()
        assert rel == tbl, f"table {tbl} missing after ensure_task_system_schema"


def test_default_v1_workflow_seeded_idempotent(applied_schema):
    rows = _exec(
        applied_schema,
        "select count(*) from task_workflow_definitions where key='default_v1' and version=1",
    ).scalar()
    assert rows == 1


def test_three_seed_pools_present_idempotent(applied_schema):
    rows = (
        _exec(
            applied_schema,
            "select key from task_pools where key like 'hicampus.%' order by key",
        )
        .scalars()
        .all()
    )
    assert rows == ["hicampus.cleaning", "hicampus.maintenance", "hicampus.security"]


def test_task_pools_key_format_check_rejects_invalid(applied_schema):
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        _exec(
            applied_schema,
            """
            INSERT INTO task_pools
                (key, display_name, default_workflow_ref,
                 default_visibility, publish_acl, consume_acl, attributes)
            VALUES (:k, 'invalid', '{"_schema_version":1,"key":"default_v1","version":1}'::jsonb,
                    'pool_open',
                    '{"_schema_version":1}'::jsonb,
                    '{"_schema_version":1}'::jsonb,
                    '{"_schema_version":1}'::jsonb)
            """,
            {"k": "InvalidKey"},
        )


def test_task_assignments_principal_shape_check_xor(applied_schema):
    """principal_kind='group' must use principal_tag; otherwise principal_id."""
    from sqlalchemy.exc import IntegrityError

    # Create a real task node first so the FK is satisfied.
    node_id = _exec(
        applied_schema,
        """
        INSERT INTO nodes (type_id, type_code, name, attributes)
        SELECT id, 'task', :name, '{}'::jsonb FROM node_types WHERE type_code='task'
        RETURNING id
        """,
        {"name": f"check-shape-{uuid.uuid4()}"},
    ).scalar()
    assert node_id

    with pytest.raises(IntegrityError):
        _exec(
            applied_schema,
            """
            INSERT INTO task_assignments
                (task_node_id, principal_id, principal_kind, principal_tag, role, stage)
            VALUES (:tid, 1, 'group', NULL, 'executor', 'open')
            """,
            {"tid": node_id},
        )


def test_task_state_transitions_event_seq_unique(applied_schema):
    from sqlalchemy.exc import IntegrityError

    node_id = _exec(
        applied_schema,
        """
        INSERT INTO nodes (type_id, type_code, name, attributes)
        SELECT id, 'task', :name, '{}'::jsonb FROM node_types WHERE type_code='task'
        RETURNING id
        """,
        {"name": f"unique-seq-{uuid.uuid4()}"},
    ).scalar()

    insert = """
        INSERT INTO task_state_transitions
            (task_node_id, event_seq, from_state, to_state, event,
             actor_principal_kind, stage)
        VALUES (:tid, :seq, 'draft', 'open', 'open', 'user', 'open')
    """
    _exec(applied_schema, insert, {"tid": node_id, "seq": 1})
    with pytest.raises(IntegrityError):
        _exec(applied_schema, insert, {"tid": node_id, "seq": 1})


def test_task_state_transitions_idempotency_partial_unique(applied_schema):
    """Same (task, idempotency_key) must collide; NULL keys must be ignored by the unique."""
    from sqlalchemy.exc import IntegrityError

    node_id = _exec(
        applied_schema,
        """
        INSERT INTO nodes (type_id, type_code, name, attributes)
        SELECT id, 'task', :name, '{}'::jsonb FROM node_types WHERE type_code='task'
        RETURNING id
        """,
        {"name": f"idem-{uuid.uuid4()}"},
    ).scalar()

    base_payload = {
        "tid": node_id,
        "key": "idem-A",
        "expires": "2099-01-01T00:00:00Z",
    }
    _exec(
        applied_schema,
        """
        INSERT INTO task_state_transitions
            (task_node_id, event_seq, idempotency_key, idempotency_expires_at,
             from_state, to_state, event, actor_principal_kind, stage)
        VALUES (:tid, 10, :key, :expires, 'draft','open','open','user','open')
        """,
        base_payload,
    )
    with pytest.raises(IntegrityError):
        _exec(
            applied_schema,
            """
            INSERT INTO task_state_transitions
                (task_node_id, event_seq, idempotency_key, idempotency_expires_at,
                 from_state, to_state, event, actor_principal_kind, stage)
            VALUES (:tid, 11, :key, :expires, 'open','claimed','claim','user','claimed')
            """,
            base_payload,
        )

    # Two NULL idempotency keys for the same task must be allowed.
    null_payload = {"tid": node_id}
    _exec(
        applied_schema,
        """
        INSERT INTO task_state_transitions
            (task_node_id, event_seq, from_state, to_state, event, actor_principal_kind, stage)
        VALUES (:tid, 20, 'draft','open','open','user','open')
        """,
        null_payload,
    )
    _exec(
        applied_schema,
        """
        INSERT INTO task_state_transitions
            (task_node_id, event_seq, from_state, to_state, event, actor_principal_kind, stage)
        VALUES (:tid, 21, 'open','claimed','claim','user','claimed')
        """,
        null_payload,
    )


def test_nodes_task_pool_id_index_used_for_filter(applied_schema):
    """EXPLAIN must show the partial expression index when filtering by pool_id."""
    plan = _exec(
        applied_schema,
        """
        EXPLAIN
        SELECT id FROM nodes
         WHERE type_code = 'task'
           AND (attributes->>'pool_id')::bigint = 1
        """,
    ).fetchall()
    plan_text = "\n".join(row[0] for row in plan)
    # Either Bitmap Index Scan or Index Scan referencing our index name.
    assert "idx_nodes_task_pool_id" in plan_text or "task_pool_id" in plan_text, plan_text
