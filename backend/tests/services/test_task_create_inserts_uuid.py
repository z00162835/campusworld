"""create_task must INSERT explicit uuid into nodes (raw SQL bypasses ORM defaults)."""

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from sqlalchemy.sql.elements import TextClause

from app.services.task.permissions import SYSTEM_PRINCIPAL
from app.services.task.task_state_machine import create_task


class _MockFirst:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


@pytest.mark.unit
def test_create_task_insert_nodes_params_include_uuid():
    execute_calls = []

    spec = {"initial_state": "draft"}

    def fake_execute(stmt, params=None):
        execute_calls.append((stmt, params))
        s = stmt if isinstance(stmt, str) else getattr(stmt, "text", str(stmt))
        # Resolve workflow version
        if "task_workflow_definitions" in s and "ORDER BY version DESC" in s:
            return _MockFirst((1,))
        # Load spec
        if "task_workflow_definitions" in s and ":version" in s and "spec" in s:
            return _MockFirst((spec, True))
        # node_types task
        if "node_types" in s and "task" in s:
            return _MockFirst((6448,))
        # INSERT nodes
        if "INSERT INTO nodes" in s and "RETURNING id" in s:
            assert "uuid" in s
            assert params is not None
            assert "uuid" in params and params["uuid"] is not None
            return _MockFirst((999,))
        return _MockFirst(None)

    mock_session = MagicMock()
    mock_session.in_transaction.return_value = True

    @contextmanager
    def _nested():
        yield None

    mock_session.begin_nested.return_value = _nested()
    mock_session.execute.side_effect = fake_execute

    create_task(title="t", actor=SYSTEM_PRINCIPAL, db_session=mock_session)

    insert_nodes = [
        c for c in execute_calls if "INSERT INTO nodes" in (c[0].text if hasattr(c[0], "text") else str(c[0]))
    ]
    assert len(insert_nodes) == 1
    stmt, params = insert_nodes[0]
    assert params.get("uuid") is not None
