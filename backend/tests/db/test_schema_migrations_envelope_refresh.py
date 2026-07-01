"""PostgreSQL integration test for ``ensure_command_ability_envelope_refresh``.

Skipped unless ``CAMPUSWORLD_TEST_DATABASE_URL`` points at a writable Postgres
instance. Verifies that the one-shot refresh writes the canonical
``system_command_ability`` schema envelope (with the extended tool-contract
fields) even when the stored envelope already has the JSON Schema object shape
that the idempotent guard in ``ensure_builtin_node_type_schema_envelopes`` would
otherwise skip.
"""

from __future__ import annotations

import json
import os

import pytest
from sqlalchemy import create_engine, text


_DB_URL = os.environ.get("CAMPUSWORLD_TEST_DATABASE_URL", "").strip()


pytestmark = pytest.mark.postgres_integration


@pytest.fixture(scope="module")
def engine():
    if not _DB_URL or not _DB_URL.lower().startswith("postgresql"):
        pytest.skip(
            "CAMPUSWORLD_TEST_DATABASE_URL not set or not postgresql; "
            "skipping envelope refresh DB integration test."
        )
    eng = create_engine(_DB_URL, future=True)
    yield eng
    eng.dispose()


def _exec(engine, sql: str, params=None):
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        return conn.execute(text(sql), params or {})


def _ensure_command_ability_type_row(engine) -> None:
    """Ensure the ``system_command_ability`` node_type row exists so the refresh
    UPDATE has a target. Uses ON CONFLICT DO NOTHING so this is safe on fresh and
    existing DBs. The row is normally created by ``app/commands/ability_sync.py``,
    not by the ontology seed, so each test must guarantee its presence independently.
    """
    _exec(
        engine,
        """
        INSERT INTO node_types (
            type_code, parent_type_code, type_name, typeclass, status,
            classname, module_path, description, schema_definition
        ) VALUES (
            'system_command_ability', NULL, 'SystemCommandAbility',
            'app.models.system.command_ability.SystemCommandAbility', 0,
            'SystemCommandAbility', 'app.models.system.command_ability',
            'Semantic capability node representing a command',
            '{}'::jsonb
        )
        ON CONFLICT (type_code) DO NOTHING;
        """,
    )


def test_ensure_command_ability_envelope_refresh_updates_stale_envelope(engine):
    from db.schema_migrations import ensure_command_ability_envelope_refresh

    _ensure_command_ability_type_row(engine)

    # Force a stale envelope that already looks like a JSON Schema object (so the
    # idempotent guard in ensure_builtin_node_type_schema_envelopes would skip it)
    # but is missing the extended tool-contract fields such as side_effect_level.
    stale = {"type": "object", "properties": {"command_name": {"type": "string"}}}
    _exec(
        engine,
        "UPDATE node_types SET schema_definition = CAST(:js AS jsonb) "
        "WHERE type_code = 'system_command_ability'",
        {"js": json.dumps(stale)},
    )

    ensure_command_ability_envelope_refresh(engine)

    row = _exec(
        engine,
        "SELECT schema_definition FROM node_types WHERE type_code = 'system_command_ability'",
    ).fetchone()
    sd = row[0]
    assert isinstance(sd, dict)
    assert "side_effect_level" in sd["properties"]
    assert "data_classification" in sd["properties"]
    assert "data_scope" in sd["properties"]


def test_ensure_command_ability_envelope_refresh_is_idempotent(engine):
    from db.schema_migrations import ensure_command_ability_envelope_refresh

    _ensure_command_ability_type_row(engine)

    ensure_command_ability_envelope_refresh(engine)
    row = _exec(
        engine,
        "SELECT schema_definition FROM node_types WHERE type_code = 'system_command_ability'",
    ).fetchone()
    after_first = row[0]

    ensure_command_ability_envelope_refresh(engine)
    row = _exec(
        engine,
        "SELECT schema_definition FROM node_types WHERE type_code = 'system_command_ability'",
    ).fetchone()
    after_second = row[0]

    assert isinstance(after_second, dict)
    assert "side_effect_level" in after_second["properties"]
    assert after_second == after_first
