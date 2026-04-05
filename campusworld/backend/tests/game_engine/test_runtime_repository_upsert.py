"""WorldRuntimeRepository.upsert_state PostgreSQL statement shape (regression: ORM excluded.state_metadata)."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.game_engine.runtime_store import WorldRuntimeRepository


@pytest.mark.unit
def test_upsert_state_uses_excluded_metadata_column():
    repo = WorldRuntimeRepository()
    session = MagicMock()
    captured = {}

    def _capture(stmt, *a, **kw):
        captured["stmt"] = stmt

    session.execute.side_effect = _capture

    repo.upsert_state(
        "w1",
        "loading",
        version="1.0",
        last_error_code=None,
        last_error_message=None,
        metadata={"k": 1},
        updated_by="tester",
        session=session,
    )

    assert "stmt" in captured
    sql = str(captured["stmt"].compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT" in sql
    assert "excluded.metadata" in sql or "excluded.\"metadata\"" in sql.replace(" ", "")


@pytest.mark.unit
def test_upsert_state_insert_lists_metadata_column():
    repo = WorldRuntimeRepository()
    session = MagicMock()
    captured = {}

    def _capture(stmt, *a, **kw):
        captured["stmt"] = stmt

    session.execute.side_effect = _capture
    repo.upsert_state("w2", "installed", session=session)
    sql = str(captured["stmt"].compile(dialect=postgresql.dialect())).lower()
    assert "metadata" in sql
