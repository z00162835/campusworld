"""CLI and guardrails for db.init_database / db.migrate_report."""

from argparse import Namespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.engine.url import make_url

from db.init_database import _cmd_reset, _parse_args
from db.migrate_report import (
    MigrationStepResult,
    format_migration_report,
    migrations_all_ok,
    reset_explicitly_allowed,
)


def test_parse_args_default_migrate():
    a = _parse_args([])
    assert a.command == "migrate"
    assert a.i_understand is False


def test_parse_args_migrate_explicit():
    a = _parse_args(["migrate"])
    assert a.command == "migrate"


def test_parse_args_reset_with_confirm():
    a = _parse_args(["reset", "--i-understand"])
    assert a.command == "reset"
    assert a.i_understand is True


def test_parse_args_json_report():
    a = _parse_args(["migrate", "--json-report"])
    assert a.json_report is True


def test_migrations_all_ok():
    assert migrations_all_ok(
        [MigrationStepResult("a", True), MigrationStepResult("b", True)]
    )
    assert not migrations_all_ok(
        [MigrationStepResult("a", True), MigrationStepResult("b", False, error="x")]
    )


def test_format_migration_report_json():
    out = format_migration_report(
        [MigrationStepResult("step", False, error="boom")], as_json=True
    )
    assert "step" in out and "boom" in out


def test_reset_explicitly_allowed_via_env(monkeypatch):
    monkeypatch.setenv("CAMPUSWORLD_ALLOW_DB_RESET", "true")
    assert reset_explicitly_allowed() is True
    monkeypatch.delenv("CAMPUSWORLD_ALLOW_DB_RESET", raising=False)


@patch("app.core.config_manager.get_setting", return_value=False)
def test_reset_explicitly_allowed_false_without_env(mock_get, monkeypatch):
    monkeypatch.delenv("CAMPUSWORLD_ALLOW_DB_RESET", raising=False)
    assert reset_explicitly_allowed() is False


@patch("app.core.config_manager.get_setting", return_value=True)
def test_reset_explicitly_allowed_via_config(mock_get, monkeypatch):
    monkeypatch.delenv("CAMPUSWORLD_ALLOW_DB_RESET", raising=False)
    assert reset_explicitly_allowed() is True


def _pg_engine_mock():
    eng = MagicMock()
    eng.url = make_url("postgresql+psycopg2://user:pass@localhost:5432/testdb")
    return eng


@patch("db.migrate_report.reset_explicitly_allowed", return_value=False)
def test_cmd_reset_rejected_when_not_allowed(_mock_allow):
    eng = _pg_engine_mock()
    ns = Namespace(i_understand=True, json_report=False)
    assert _cmd_reset(eng, ns) is False


@patch("db.migrate_report.reset_explicitly_allowed", return_value=True)
def test_cmd_reset_rejects_without_i_understand(_mock_allow):
    eng = _pg_engine_mock()
    ns = Namespace(i_understand=False, json_report=False)
    assert _cmd_reset(eng, ns) is False


@patch("db.migrate_report.reset_explicitly_allowed", return_value=True)
@patch("db.init_database._run_migrate", return_value=(True, []))
@patch("db.init_database._run_seed_if_enabled", return_value=True)
@patch("db.migrate_report.reset_public_schema")
def test_cmd_reset_success_path(mock_drop, _seed, _migrate, _allow):
    eng = _pg_engine_mock()
    ns = Namespace(i_understand=True, json_report=False)
    assert _cmd_reset(eng, ns) is True
    mock_drop.assert_called_once_with(eng)


@pytest.mark.unit
def test_cmd_reset_rejects_non_postgresql():
    eng = MagicMock()
    eng.url = make_url("sqlite:///:memory:")
    ns = Namespace(i_understand=True, json_report=False)
    with patch("db.migrate_report.reset_explicitly_allowed", return_value=True):
        assert _cmd_reset(eng, ns) is False
