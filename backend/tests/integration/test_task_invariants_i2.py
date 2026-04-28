"""Phase B PR6: I2 — assignment role conformance integration test.

I2 (`SPEC.md` §1 — invariants): for any task in state ``S``, the set of
``role`` values in active rows of ``task_assignments`` is a subset of
``workflow_definition.states[S].expected_roles``.

Phase B can drive a task through ``draft → open → claimed → done`` (5 events).
This test exercises that path against a real PostgreSQL and asserts I2 at
each reachable state. ``in_progress`` / ``pending_review`` / ``approved`` /
``rejected`` are deferred to Phase C; the assertion infrastructure here is
written so they trivially extend in PR-C1.

Skipped unless ``CAMPUSWORLD_TEST_DATABASE_URL`` is set.
"""

from __future__ import annotations

import os
import uuid
from typing import Generator, Set

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


_DB_URL = os.environ.get("CAMPUSWORLD_TEST_DATABASE_URL", "").strip()


pytestmark = pytest.mark.postgres_integration


@pytest.fixture(scope="module")
def engine():
    if not _DB_URL or not _DB_URL.lower().startswith("postgresql"):
        pytest.skip("CAMPUSWORLD_TEST_DATABASE_URL not set; skipping I2 test")
    eng = create_engine(_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture(scope="module")
def schema_ready(engine):
    from db.schema_migrations import (
        ensure_graph_seed_ontology,
        ensure_task_system_schema,
        ensure_task_system_seed,
    )

    ensure_graph_seed_ontology(engine)
    ensure_task_system_schema(engine)
    ensure_task_system_seed(engine)
    return engine


@pytest.fixture()
def session(schema_ready) -> Generator:
    Session = sessionmaker(bind=schema_ready, future=True, expire_on_commit=False)
    s = Session()
    try:
        yield s
    finally:
        s.close()


def _make_actor(session, *, name: str) -> int:
    row = session.execute(
        text(
            """
            INSERT INTO nodes (type_id, type_code, name, attributes, is_active, is_public)
            SELECT id, type_code, :name, '{}'::jsonb, TRUE, FALSE
              FROM node_types WHERE type_code = 'default_object'
            RETURNING id
            """
        ),
        {"name": name},
    ).first()
    session.commit()
    return int(row[0])


def _active_roles(session, task_id: int) -> Set[str]:
    rows = session.execute(
        text(
            "SELECT role FROM task_assignments WHERE task_node_id = :tid AND is_active = TRUE"
        ),
        {"tid": task_id},
    ).all()
    return {r[0] for r in rows}


def _expected_roles(session, state: str) -> Set[str]:
    spec = session.execute(
        text(
            "SELECT spec FROM task_workflow_definitions "
            "WHERE key = 'default_v1' AND version = 1"
        )
    ).scalar()
    return set(spec["states"][state]["expected_roles"])


def _assert_i2(session, task_id: int, state: str) -> None:
    active = _active_roles(session, task_id)
    expected = _expected_roles(session, state)
    assert active.issubset(expected), (
        f"I2 violation in state={state}: active={active}, expected={expected}"
    )


def test_i2_holds_through_phase_b_path(session):
    """draft → open → claimed → done — each state's active roles ⊆ expected."""
    from app.services.task.permissions import Principal
    from app.services.task.task_state_machine import create_task, transition

    owner_id = _make_actor(session, name=f"i2-owner-{uuid.uuid4()}")
    executor_id = _make_actor(session, name=f"i2-exec-{uuid.uuid4()}")
    owner = Principal(id=owner_id, kind="user")
    executor = Principal(id=executor_id, kind="user")

    pool_id = int(
        session.execute(
            text("SELECT id FROM task_pools WHERE key = 'hicampus.cleaning'")
        ).scalar()
    )

    created = create_task(title="i2 probe", actor=owner, db_session=session)
    _assert_i2(session, created.task_id, "draft")

    published = transition(
        task_id=created.task_id,
        event="publish",
        actor_principal=owner,
        expected_version=created.state_version,
        payload={"pool_id": pool_id},
        db_session=session,
    )
    assert published.to_state == "open"
    _assert_i2(session, created.task_id, "open")

    claimed = transition(
        task_id=created.task_id,
        event="claim",
        actor_principal=executor,
        expected_version=published.state_version,
        db_session=session,
    )
    assert claimed.to_state == "claimed"
    _assert_i2(session, created.task_id, "claimed")
    assert "executor" in _active_roles(session, created.task_id)

    completed = transition(
        task_id=created.task_id,
        event="complete",
        actor_principal=executor,
        expected_version=claimed.state_version,
        db_session=session,
    )
    assert completed.to_state == "done"

    # Terminal state ``done`` has ``expected_roles=[]`` and state machine
    # retires owner/executor/approver on complete; active set must be empty.
    active = _active_roles(session, created.task_id)
    assert active == set(), f"on terminal `done` active assignments must be empty; got {active}"
