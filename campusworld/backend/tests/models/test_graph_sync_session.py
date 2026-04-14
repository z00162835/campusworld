"""GraphSynchronizer session contract: no DB work without ``_transaction`` scope when db_session is None."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
def test_get_db_session_without_scope_raises():
    from app.models.graph_sync import GraphSynchronizer

    with pytest.raises(RuntimeError, match="GraphSynchronizer has no database session"):
        GraphSynchronizer(db_session=None)._get_db_session()


@pytest.mark.unit
def test_get_sync_stats_uses_db_session_context_when_not_injected():
    from app.models.graph_sync import GraphSynchronizer

    inner_session = MagicMock()

    def query_side_effect(*_a, **_k):
        q = MagicMock()
        q.filter.return_value = q
        q.scalar.return_value = 0
        return q

    inner_session.query.side_effect = query_side_effect

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=inner_session)
    mock_ctx.__exit__ = MagicMock(return_value=None)

    with patch("app.models.graph_sync.db_session_context", return_value=mock_ctx):
        stats = GraphSynchronizer(db_session=None).get_sync_stats()

    mock_ctx.__enter__.assert_called_once()
    mock_ctx.__exit__.assert_called_once()
    assert stats["total_nodes"] == 0
    assert stats["total_relationships"] == 0
