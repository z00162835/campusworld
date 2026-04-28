"""Phase B PR2: structural tests for the task_system schema section.

These tests parse the SQL section out of ``database_schema.sql`` and assert that
the DDL contract from ``docs/task/SPEC/features/F04 §3`` is preserved without
needing to spin up a real PostgreSQL instance. Real DB integration tests live
in ``tests/db/test_task_system_schema_postgres.py`` (postgres_integration).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


_SCHEMA_FILE = (
    Path(__file__).resolve().parents[2] / "db" / "schemas" / "database_schema.sql"
)


def _section() -> str:
    raw = _SCHEMA_FILE.read_text(encoding="utf-8")
    start = "-- BEGIN task_system"
    end = "-- END task_system"
    assert start in raw, "task_system section missing"
    assert end in raw, "task_system section missing closing marker"
    return raw.split(start, 1)[1].split(end, 1)[0]


@pytest.mark.unit
def test_task_system_section_contains_all_eight_tables():
    section = _section()
    expected_tables = [
        "task_workflow_definitions",
        "task_pools",
        "task_details",
        "task_assignments",
        "task_state_transitions",
        "task_runs",
        "task_events",
        "task_outbox",
    ]
    for tbl in expected_tables:
        assert (
            f"CREATE TABLE IF NOT EXISTS {tbl}" in section
        ), f"missing CREATE TABLE for {tbl}"


@pytest.mark.unit
def test_foreign_keys_are_on_delete_restrict():
    """SPEC §1.7: every FK from task_* to nodes must be ON DELETE RESTRICT."""
    section = _section()
    fk_pat = re.compile(r"REFERENCES\s+nodes\s*\(\s*id\s*\)\s+ON\s+DELETE\s+(\w+)")
    matches = fk_pat.findall(section)
    assert matches, "no FKs to nodes(id) found in task_system section"
    for verdict in matches:
        assert verdict.upper() == "RESTRICT", (
            f"task_system FK uses {verdict}; SPEC §1.7 requires RESTRICT only"
        )


@pytest.mark.unit
def test_task_state_transitions_unique_event_seq_constraint():
    section = _section()
    assert "uq_task_transitions_event_seq UNIQUE (task_node_id, event_seq)" in section


@pytest.mark.unit
def test_task_state_transitions_partial_idempotency_unique_index():
    section = _section()
    assert "uq_task_transitions_idempotency" in section
    # Must be a partial unique index (idempotency_key IS NOT NULL).
    assert "WHERE idempotency_key IS NOT NULL" in section


@pytest.mark.unit
def test_task_state_transitions_idempotency_shape_check():
    section = _section()
    assert "chk_task_transitions_idem_shape" in section


@pytest.mark.unit
def test_task_assignments_principal_shape_check():
    section = _section()
    assert "chk_task_assignments_principal_shape" in section
    # Both branches must appear so the check enforces XOR between principal_id / principal_tag.
    assert "principal_kind = 'group'" in section
    assert "principal_kind <> 'group'" in section


@pytest.mark.unit
def test_task_assignments_lease_columns_reserved():
    """OQ-19 method B: v1 reserves the columns; Phase C populates them."""
    section = _section()
    assert "lease_expires_at  TIMESTAMPTZ NULL" in section
    assert "last_heartbeat_at TIMESTAMPTZ NULL" in section
    assert "idx_task_assignments_lease_expiring" in section


@pytest.mark.unit
def test_task_pools_key_format_check():
    section = _section()
    assert "chk_task_pools_key_format" in section
    # Keys must follow the namespaced regex from F05 §3.2.
    assert "^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*){1,3}$" in section


@pytest.mark.unit
def test_nodes_jsonb_expression_indexes_present():
    """F04 §3.9 lists 7 expression indexes (tags GIN is optional / not required)."""
    section = _section()
    expected_indexes = [
        "idx_nodes_task_current_state",
        "idx_nodes_task_pool_id",
        "idx_nodes_task_assignee_kind",
        "idx_nodes_task_visibility",
        "idx_nodes_task_priority_created",
        "idx_nodes_task_workflow_key",
        "idx_nodes_task_due_at",
    ]
    for idx in expected_indexes:
        assert idx in section, f"missing nodes JSONB expression index {idx}"


@pytest.mark.unit
def test_due_at_index_uses_materialized_epoch_ms():
    section = _section()
    assert "idx_nodes_task_due_at" in section
    assert "attributes->>'due_at_epoch_ms'" in section
    assert "::bigint" in section
    assert "attributes ? 'due_at_epoch_ms'" in section


@pytest.mark.unit
def test_outbox_partial_indexes_for_dispatcher_handoff():
    """v1 has no dispatcher; partial indexes pre-create the v2 handoff path."""
    section = _section()
    assert "idx_task_outbox_pending" in section
    assert "idx_task_outbox_pool_pending" in section
    assert "WHERE dispatched_at IS NULL" in section
