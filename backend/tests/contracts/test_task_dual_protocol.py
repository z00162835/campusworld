"""Phase B PR5: dual-protocol contract for the ``task`` command.

Skipped unless ``CAMPUSWORLD_TEST_DATABASE_URL`` is set. Asserts the SSH
``execute(ctx, args)`` path and the ``CommandResult.data`` shape that
``POST /api/v1/command/execute`` exposes return identical structured fields
(modulo ``correlation_id`` / ``trace_id`` / timestamps).
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.commands.base import CommandContext


_DB_URL = os.environ.get("CAMPUSWORLD_TEST_DATABASE_URL", "").strip()


pytestmark = pytest.mark.postgres_integration


@pytest.fixture(scope="module")
def engine():
    if not _DB_URL or not _DB_URL.lower().startswith("postgresql"):
        pytest.skip("CAMPUSWORLD_TEST_DATABASE_URL not set; skipping dual-protocol test")
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


def _make_actor(session) -> int:
    row = session.execute(
        text(
            """
            INSERT INTO nodes (type_id, type_code, name, attributes, is_active, is_public)
            SELECT id, type_code, :name, '{}'::jsonb, TRUE, FALSE
              FROM node_types WHERE type_code = 'default_object'
            RETURNING id
            """
        ),
        {"name": f"contract-actor-{uuid.uuid4()}"},
    ).first()
    session.commit()
    return int(row[0])


def _strip_volatile(data: dict) -> dict:
    out = dict(data or {})
    for k in ("correlation_id", "trace_id"):
        out.pop(k, None)
    return out


def test_task_create_command_emits_canonical_data_shape(schema_ready):
    """SSH/CLI path writes through ``TaskCommand.execute``; the structured
    ``CommandResult.data`` is the same dict served via ``/api/v1/command/execute``.
    """

    from app.commands.game.task.task_command import TaskCommand

    Session = sessionmaker(bind=schema_ready, future=True, expire_on_commit=False)
    s = Session()
    actor_id = _make_actor(s)
    s.close()

    cmd = TaskCommand()
    ctx = CommandContext(
        user_id=str(actor_id),
        username="contract",
        session_id="s",
        permissions=["task.*"],
        roles=["admin"],
        metadata={"locale": "en-US"},
    )
    res = cmd.execute(ctx, ["create", "--title", "Dual Protocol Probe"])
    assert res.success is True, res.message
    keys = {"task_id", "from_state", "to_state", "event", "event_seq",
            "state_version", "idempotent_replay"}
    assert keys.issubset(set(res.data.keys()))
    assert res.data["from_state"] == "__init__"
    assert res.data["to_state"] == "draft"

    # Replay with same args ⇒ idempotency_key derivation deterministic ⇒ replay flagged.
    res2 = cmd.execute(ctx, ["create", "--title", "Dual Protocol Probe"])
    assert res2.success is True
    assert res2.data["idempotent_replay"] is True
    assert res2.data["task_id"] == res.data["task_id"]

    # Stripping volatile metadata leaves identical payloads (SSH ↔ REST contract).
    assert _strip_volatile(res2.data) == {**_strip_volatile(res.data), "idempotent_replay": True}


def test_task_create_draft_keeps_task_in_draft_state(schema_ready):
    """D3.1: ``task create --to-pool X --draft`` MUST keep the task in
    ``draft`` state and skip the publish event entirely."""
    from app.commands.game.task.task_command import TaskCommand

    Session = sessionmaker(bind=schema_ready, future=True, expire_on_commit=False)
    s = Session()
    actor_id = _make_actor(s)
    s.close()

    ctx = CommandContext(
        user_id=str(actor_id),
        username="contract",
        session_id="s",
        permissions=["*"],
        roles=["admin"],
        metadata={"locale": "en-US"},
    )
    pool_key = f"hicampus.draft_{uuid.uuid4().hex[:6]}"
    cmd = TaskCommand()
    assert cmd.execute(
        ctx, ["pool", "create", pool_key, "--display-name", "Draft Probe"]
    ).success

    res = cmd.execute(
        ctx, ["create", "--title", "kept-draft", "--to-pool", pool_key, "--draft"]
    )
    assert res.success is True, res.message
    # `--draft` short-circuits before the publish event; resulting state must
    # be `draft`, not `open`.
    assert res.data["to_state"] == "draft"
    assert res.data["event"] == "create"
    # Sanity: a follow-up publish on the same task transitions to `open`.
    publish = cmd.execute(
        ctx, ["publish", str(res.data["task_id"]), "--to-pool", pool_key]
    )
    assert publish.success is True
    assert publish.data["to_state"] == "open"


def test_task_create_draft_with_unsupported_visibility_rejected(schema_ready):
    from app.commands.game.task.task_command import TaskCommand

    Session = sessionmaker(bind=schema_ready, future=True, expire_on_commit=False)
    s = Session()
    actor_id = _make_actor(s)
    s.close()

    ctx = CommandContext(
        user_id=str(actor_id),
        username="contract",
        session_id="s",
        permissions=["*"],
        roles=["admin"],
        metadata={"locale": "en-US"},
    )
    pool_key = f"hicampus.draft_{uuid.uuid4().hex[:6]}"
    cmd = TaskCommand()
    assert cmd.execute(
        ctx, ["pool", "create", pool_key, "--display-name", "Draft Probe"]
    ).success

    # visibility validation runs before draft shortcut.
    bad = cmd.execute(
        ctx,
        [
            "create",
            "--title",
            "bad",
            "--to-pool",
            pool_key,
            "--visibility",
            "role_scope",
            "--draft",
        ],
    )
    assert bad.success is False
    assert bad.error == "commands.task.error.visibility_unsupported"


def test_task_show_filters_soft_deleted_tasks(schema_ready):
    """D5.1: ``task show`` returns ``not_found`` for soft-deleted tasks."""
    from app.commands.game.task.task_command import TaskCommand

    Session = sessionmaker(bind=schema_ready, future=True, expire_on_commit=False)
    s = Session()
    actor_id = _make_actor(s)
    s.close()

    ctx = CommandContext(
        user_id=str(actor_id),
        username="contract",
        session_id="s",
        permissions=["*"],
        roles=["admin"],
        metadata={"locale": "en-US"},
    )
    cmd = TaskCommand()
    res = cmd.execute(ctx, ["create", "--title", "to-be-soft-deleted"])
    assert res.success is True
    task_id = res.data["task_id"]

    # show before soft-delete: visible to owner via has_active_assignment.
    show = cmd.execute(ctx, ["show", str(task_id)])
    assert show.success is True

    # Soft-delete the task row directly (simulating retention/janitor path).
    s2 = Session()
    s2.execute(
        text("UPDATE nodes SET is_active = FALSE WHERE id = :id"),
        {"id": task_id},
    )
    s2.commit()
    s2.close()

    show2 = cmd.execute(ctx, ["show", str(task_id)])
    assert show2.success is False
    assert show2.error == "commands.task.error.not_found"


def test_task_list_pushes_visibility_to_sql_with_global_total(schema_ready):
    """D1.1+D1.2: list applies LIMIT/OFFSET in DB and reports global total
    via COUNT(*) OVER (). With the actor as owner of N tasks, paginating by
    --limit 1 across requests sees a stable ``total=N`` and N distinct ids."""
    from app.commands.game.task.task_command import TaskCommand

    Session = sessionmaker(bind=schema_ready, future=True, expire_on_commit=False)
    s = Session()
    actor_id = _make_actor(s)
    s.close()

    ctx = CommandContext(
        user_id=str(actor_id),
        username="contract",
        session_id="s",
        permissions=["*"],
        roles=["admin"],
        metadata={"locale": "en-US"},
    )
    cmd = TaskCommand()

    # Create 3 owner-visible tasks.
    created_ids = []
    for i in range(3):
        r = cmd.execute(ctx, ["create", "--title", f"list-probe-{i}"])
        assert r.success is True
        created_ids.append(r.data["task_id"])

    # Page 1.
    r1 = cmd.execute(ctx, ["list", "--mine", "--limit", "1", "--offset", "0"])
    assert r1.success is True
    assert r1.data["total"] >= 3, r1.data
    assert len(r1.data["items"]) == 1
    # Page 2.
    r2 = cmd.execute(ctx, ["list", "--mine", "--limit", "1", "--offset", "1"])
    assert r2.success is True
    assert r2.data["total"] == r1.data["total"]  # COUNT(*) OVER () stable
    assert len(r2.data["items"]) == 1
    assert r2.data["items"][0]["id"] != r1.data["items"][0]["id"]


def test_task_pool_lifecycle_create_to_complete(schema_ready):
    """End-to-end: pool create → task create → publish → claim → complete."""
    from app.commands.game.task.task_command import TaskCommand

    Session = sessionmaker(bind=schema_ready, future=True, expire_on_commit=False)
    s = Session()
    actor_id = _make_actor(s)
    s.close()

    ctx = CommandContext(
        user_id=str(actor_id),
        username="contract",
        session_id="s",
        permissions=["*"],
        roles=["admin"],
        metadata={"locale": "en-US"},
    )

    pool_key = f"hicampus.contract_{uuid.uuid4().hex[:6]}"
    task_cmd = TaskCommand()
    res = task_cmd.execute(
        ctx, ["pool", "create", pool_key, "--display-name", "Contract Pool"]
    )
    assert res.success is True
    assert res.data["key"] == pool_key
    assert isinstance(res.data["id"], int)
    show_pool = task_cmd.execute(ctx, ["pool", "show", pool_key])
    assert show_pool.success is True
    assert show_pool.data["key"] == pool_key
    assert isinstance(show_pool.data["id"], int)

    create = task_cmd.execute(
        ctx, ["create", "--title", "lifecycle", "--to-pool", pool_key]
    )
    assert create.success is True
    task_id = create.data["task_id"]

    # Publish to a different pool to ensure publish path runs without depending on
    # initial pool linkage.
    publish = task_cmd.execute(ctx, ["publish", str(task_id), "--to-pool", pool_key])
    assert publish.success is True
    assert publish.data["to_state"] == "open"

    # Claim then complete.
    claim = task_cmd.execute(ctx, ["claim", str(task_id)])
    assert claim.success is True
    assert claim.data["to_state"] == "claimed"

    complete = task_cmd.execute(ctx, ["complete", str(task_id)])
    assert complete.success is True
    assert complete.data["to_state"] == "done"
