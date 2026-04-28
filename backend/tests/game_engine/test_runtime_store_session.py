"""Session lifecycle for WorldRuntimeRepository (owns-session branch uses ``with db_session_context``)."""

import uuid
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
def test_upsert_state_without_injected_session_uses_context_and_commits():
    from app.game_engine.runtime_store import WorldRuntimeRepository

    mock_session = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_session)
    mock_ctx.__exit__ = MagicMock(return_value=None)

    with patch("app.game_engine.runtime_store.db_session_context", return_value=mock_ctx):
        WorldRuntimeRepository().upsert_state("w1", "installed", updated_by="tester")

    mock_ctx.__enter__.assert_called_once()
    mock_ctx.__exit__.assert_called_once()
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.unit
def test_create_job_without_injected_session_uses_context():
    from app.game_engine.runtime_store import WorldRuntimeRepository

    mock_session = MagicMock()

    def refresh_side_effect(row):
        # ORM assigns ``job_id`` on flush/DB round-trip; mocks skip that unless simulated.
        if getattr(row, "job_id", None) is None:
            row.job_id = uuid.uuid4()

    mock_session.refresh.side_effect = refresh_side_effect

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_session)
    mock_ctx.__exit__ = MagicMock(return_value=None)

    with patch("app.game_engine.runtime_store.db_session_context", return_value=mock_ctx):
        jid = WorldRuntimeRepository().create_job("w1", "install", requested_by="u1")

    mock_ctx.__exit__.assert_called_once()
    mock_session.commit.assert_called_once()
    mock_session.add.assert_called_once()
    mock_session.refresh.assert_called_once()
    assert len(jid) == 36
