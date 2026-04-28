from __future__ import annotations

from sqlalchemy import create_engine, text

from db.schema_migrations import _must_exec


def test_must_exec_handles_semicolon_inside_line_comment():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        _must_exec(
            conn,
            """
            CREATE TABLE t_comment_semicolon (
                id INTEGER PRIMARY KEY,
                -- this comment contains a semicolon; must not split statement
                name TEXT
            );
            """,
            "should execute sql block with semicolon inside comment",
        )
        exists = conn.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='t_comment_semicolon'"
            )
        ).scalar()
    assert exists == "t_comment_semicolon"


def test_must_exec_splits_real_statement_boundaries_only():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        _must_exec(
            conn,
            """
            CREATE TABLE t_split_guard (id INTEGER PRIMARY KEY, note TEXT);
            INSERT INTO t_split_guard (note) VALUES ('a;literal');
            -- semicolon in comment; still same statement stream
            INSERT INTO t_split_guard (note) VALUES ('b');
            """,
            "should split only on true statement semicolons",
        )
        rows = conn.execute(
            text("SELECT note FROM t_split_guard ORDER BY id")
        ).scalars().all()
    assert rows == ["a;literal", "b"]
