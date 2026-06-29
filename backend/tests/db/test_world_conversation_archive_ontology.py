"""No-DB checks for the world_conversation_archive node-type migration.

The archive node type was originally registered with the wrong parent
(``account``) and a classname pointing at a non-existent ORM class, which broke
model discovery and could not be repaired by ``ON CONFLICT DO NOTHING``. These
tests pin the corrected metadata and the upsert-on-conflict repair behavior.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from db.schema_migrations import ensure_world_conversation_archive_ontology


def _capture_executed_statements() -> tuple[list[str], MagicMock]:
    executed: list[str] = []

    class FakeConn:
        def execution_options(self, **kwargs):
            return self

        def execute(self, statement):
            executed.append(str(statement))
            return MagicMock()

        def close(self):
            pass

    conn = FakeConn()
    engine = MagicMock()
    engine.connect.return_value = conn
    return executed, engine


@pytest.mark.unit
def test_archive_node_type_uses_default_object_parent_and_classname():
    statements, engine = _capture_executed_statements()
    ensure_world_conversation_archive_ontology(engine)
    assert statements, "migration must execute at least one statement"
    sql = "\n".join(statements)

    # Archives are not account subtypes; they are generic graph nodes owned via
    # the `owns` relationship, so the parent must be default_object (or NULL),
    # never `account`.
    assert "'world_conversation_archive', 'default_object'" in sql
    assert "'world_conversation_archive', 'account'" not in sql
    # classname / typeclass / module_path must point at the shared DefaultObject
    # model (mirrors the `task` node-type convention), not a repository class.
    assert "app.models.base.DefaultObject" in sql
    assert "'DefaultObject'" in sql
    assert "'app.models.base'" in sql
    assert "WorldConversationArchiveRepository" not in sql
    assert "'WorldConversationArchive'" not in sql


@pytest.mark.unit
def test_archive_node_type_migration_repairs_existing_bad_rows():
    statements, engine = _capture_executed_statements()
    ensure_world_conversation_archive_ontology(engine)
    sql = "\n".join(statements)

    # DO NOTHING would leave pre-existing bad rows in place; the migration must
    # upsert the corrected metadata columns on conflict.
    assert "ON CONFLICT (type_code) DO UPDATE" in sql
    assert "EXCLUDED.parent_type_code" in sql
    assert "EXCLUDED.classname" in sql
    assert "EXCLUDED.typeclass" in sql
    assert "EXCLUDED.module_path" in sql
