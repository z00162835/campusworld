from __future__ import annotations

from unittest.mock import MagicMock

from db.schema_migrations import ensure_account_permission_defaults


def _mock_conn_with_rows(rows):
    conn = MagicMock()
    select_result = MagicMock()
    select_result.all.return_value = rows
    updates = []

    def _exec(stmt, params=None):
        sql = str(stmt)
        if "SELECT id, name, access_level, attributes" in sql:
            return select_result
        updates.append(params or {})
        return MagicMock()

    conn.execute.side_effect = _exec
    conn._updates = updates
    return conn


def test_account_permission_defaults_repairs_missing_fields_and_adds_task_wildcard():
    rows = [
        (1, "admin", "admin", {"roles": ["admin"], "permissions": ["admin.*"]}),
        (2, "dev", "developer", {"roles": [], "permissions": []}),
    ]
    conn = _mock_conn_with_rows(rows)
    engine = MagicMock()
    engine.connect.return_value.execution_options.return_value = conn

    ensure_account_permission_defaults(engine)

    assert len(conn._updates) == 2
    admin_update = next(u for u in conn._updates if u["id"] == 1)
    dev_update = next(u for u in conn._updates if u["id"] == 2)
    assert '"task.*"' in admin_update["attrs"]
    assert '"access_level": "admin"' in admin_update["attrs"]
    assert '"permissions"' in dev_update["attrs"]
    assert '"roles"' in dev_update["attrs"]


def test_account_permission_defaults_keeps_existing_non_empty_permissions():
    rows = [
        (
            3,
            "campus",
            "normal",
            {"roles": ["campus_user"], "permissions": ["custom.only"], "access_level": "normal"},
        )
    ]
    conn = _mock_conn_with_rows(rows)
    engine = MagicMock()
    engine.connect.return_value.execution_options.return_value = conn

    ensure_account_permission_defaults(engine)

    # Existing non-empty permissions should remain untouched, thus no update.
    assert conn._updates == []
