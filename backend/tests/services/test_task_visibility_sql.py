"""Tests for shared task visibility SQL SSOT."""
from app.commands.game.task.task_command import VISIBILITY_PREDICATE_SQL as cmd_predicate
from app.services.task.task_visibility_sql import VISIBILITY_PREDICATE_SQL


def test_visibility_predicate_includes_pool_open_no_executor_clause():
    assert "pool_open" in VISIBILITY_PREDICATE_SQL
    assert "role = 'executor'" in VISIBILITY_PREDICATE_SQL
    assert "NOT EXISTS" in VISIBILITY_PREDICATE_SQL


def test_task_command_and_queue_share_same_predicate_constant():
    assert cmd_predicate is VISIBILITY_PREDICATE_SQL
