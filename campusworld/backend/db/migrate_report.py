"""
Structured runner for schema_migrations.ensure_* and optional PostgreSQL public reset.

Used by db.init_database (migrate / reset modes).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Callable, List, Optional

from sqlalchemy import text


@dataclass
class MigrationStepResult:
    name: str
    ok: bool
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


def reset_explicitly_allowed() -> bool:
    if os.getenv("CAMPUSWORLD_ALLOW_DB_RESET", "").lower() == "true":
        return True
    try:
        from app.core.config_manager import get_setting

        return bool(get_setting("development.allow_db_reset", False))
    except Exception:
        return False


def is_postgresql_engine(engine) -> bool:
    return "postgresql" in str(engine.url).lower()


def database_target_summary(engine) -> str:
    u = engine.url
    host = getattr(u, "host", None) or "?"
    port = getattr(u, "port", None) or "?"
    db = getattr(u, "database", None) or "?"
    user = getattr(u, "username", None) or "?"
    return f"host={host} port={port} database={db} user={user}"


def reset_public_schema(engine) -> None:
    """Drop and recreate public schema (PostgreSQL only). Destroys all objects in public."""
    if not is_postgresql_engine(engine):
        raise RuntimeError("reset only supports PostgreSQL database URLs")
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO PUBLIC"))
    finally:
        conn.close()


def run_schema_migrations(engine) -> List[MigrationStepResult]:
    from db.schema_migrations import (
        SchemaMigrationError,
        ensure_account_data_access_defaults,
        ensure_builtin_node_type_schema_envelopes,
        ensure_command_policy_schema,
        ensure_content_visibility_backfill,
        ensure_f02_agent_memory_schema,
        ensure_f02_ltm_semantic_extension,
        ensure_graph_schema,
        ensure_graph_seed_ontology,
        ensure_nodes_world_id_index,
        ensure_task_system_schema,
        ensure_task_system_seed,
        ensure_world_runtime_schema,
    )

    steps: List[tuple[str, Callable]] = [
        ("ensure_graph_schema", ensure_graph_schema),
        ("ensure_command_policy_schema", ensure_command_policy_schema),
        ("ensure_world_runtime_schema", ensure_world_runtime_schema),
        ("ensure_f02_agent_memory_schema", ensure_f02_agent_memory_schema),
        ("ensure_f02_ltm_semantic_extension", ensure_f02_ltm_semantic_extension),
        ("ensure_content_visibility_backfill", ensure_content_visibility_backfill),
        ("ensure_graph_seed_ontology", ensure_graph_seed_ontology),
        ("ensure_builtin_node_type_schema_envelopes", ensure_builtin_node_type_schema_envelopes),
        ("ensure_account_data_access_defaults", ensure_account_data_access_defaults),
        ("ensure_nodes_world_id_index", ensure_nodes_world_id_index),
        ("ensure_task_system_schema", ensure_task_system_schema),
        ("ensure_task_system_seed", ensure_task_system_seed),
    ]
    results: List[MigrationStepResult] = []
    for name, fn in steps:
        try:
            fn(engine)
            results.append(MigrationStepResult(name=name, ok=True))
        except SchemaMigrationError as e:
            results.append(MigrationStepResult(name=name, ok=False, error=str(e)))
        except Exception as e:
            results.append(MigrationStepResult(name=name, ok=False, error=str(e)))
    return results


def migrations_all_ok(results: List[MigrationStepResult]) -> bool:
    return all(r.ok for r in results)


def format_migration_report(results: List[MigrationStepResult], *, as_json: bool) -> str:
    if as_json:
        return json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False)
    lines = ["--- schema migration report ---"]
    for r in results:
        st = "OK" if r.ok else "FAIL"
        lines.append(f"  [{st}] {r.name}")
        if r.error:
            lines.append(f"         error: {r.error}")
        for w in r.warnings:
            lines.append(f"         warn: {w}")
    return "\n".join(lines)
