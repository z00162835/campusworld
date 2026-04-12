"""
轻量 schema 兼容迁移（非 Alembic）

目的：在已有老库（仅包含最初字段）的情况下，让 ORM 新增字段可用，
避免 `create_all()` 不会 alter table 导致的运行时报错。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy import text

from app.constants.trait_mask import LOCATION_RELATIONSHIP_EDGE
from db.ontology.load import load_graph_seed_node_type_overrides, node_type_jsonb_params


# Graph-seed node_types rows: order satisfies FK parent_type_code; parents match
# docs/ontology/GRAPH_SEED_NODE_TYPES_MATRIX.md (target table).
GRAPH_SEED_ONTOLOGY_NODE_ROWS: Tuple[Tuple[str, Optional[str], str, str, str, str], ...] = (
    ("default_object", None, "默认对象", "app.models.base.DefaultObject", "DefaultObject", "app.models.base"),
    ("world_thing", "default_object", "世界物（WorldThing）", "app.models.things.base.WorldThing", "WorldThing", "app.models.things.base"),
    ("world", "default_object", "世界", "app.models.world.World", "World", "app.models.world"),
    ("world_object", "default_object", "世界对象", "app.models.world.WorldObject", "WorldObject", "app.models.world"),
    ("building", "default_object", "建筑", "app.models.building.Building", "Building", "app.models.building"),
    ("building_floor", "default_object", "楼层", "app.models.building.BuildingFloor", "BuildingFloor", "app.models.building"),
    ("room", "default_object", "房间", "app.models.room.Room", "Room", "app.models.room"),
    ("world_entrance", "default_object", "世界入口（Evennia Exit）", "app.models.world_entrance.WorldEntrance", "WorldEntrance", "app.models.world_entrance"),
    ("furniture", "world_thing", "家具", "app.models.things.furniture.Furniture", "Furniture", "app.models.things.furniture"),
    ("npc_agent", "world_thing", "NPC代理", "app.models.things.agents.NpcAgent", "NpcAgent", "app.models.things.agents"),
    (
        "access_terminal",
        "world_thing",
        "访问终端",
        "app.models.things.terminals.AccessTerminal",
        "AccessTerminal",
        "app.models.things.terminals",
    ),
    (
        "logical_zone",
        "world_thing",
        "逻辑分区",
        "app.models.things.zones.LogicalZone",
        "LogicalZone",
        "app.models.things.zones",
    ),
    (
        "network_access_point",
        "world_thing",
        "无线接入点",
        "app.models.things.devices.NetworkAccessPoint",
        "NetworkAccessPoint",
        "app.models.things.devices",
    ),
    (
        "av_display",
        "world_thing",
        "音视频大屏",
        "app.models.things.devices.AvDisplay",
        "AvDisplay",
        "app.models.things.devices",
    ),
    (
        "lighting_fixture",
        "world_thing",
        "照明灯具",
        "app.models.things.devices.LightingFixture",
        "LightingFixture",
        "app.models.things.devices",
    ),
    (
        "conference_seating",
        "furniture",
        "会议座椅",
        "app.models.things.seating.ConferenceSeating",
        "ConferenceSeating",
        "app.models.things.seating",
    ),
    (
        "lounge_furniture",
        "furniture",
        "休闲家具",
        "app.models.things.seating.LoungeFurniture",
        "LoungeFurniture",
        "app.models.things.seating",
    ),
)


class SchemaMigrationError(RuntimeError):
    pass


def _try_exec(conn, sql: str) -> None:
    try:
        conn.execute(text(sql))
    except Exception:
        # 保持幂等/兼容：缺扩展/权限/旧版本语法等都不阻断整体 init
        pass


def _must_exec(conn, sql: str, err: str) -> None:
    try:
        # Some SQL sections include multiple statements; split naively by ';'
        # and execute non-empty statements.
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            conn.execute(text(stmt))
    except Exception as e:
        raise SchemaMigrationError(f"{e}") from e


def _try_exec_mapped(conn, sql: str, params: dict) -> None:
    try:
        conn.execute(text(sql), params)
    except Exception:
        pass


def _ensure_pg_extensions(conn) -> None:
    """
    Create PostGIS / pgvector / related extensions so ORM create_all can use
    geometry(...) and vector(...) column types. Must run before create_all on
    empty databases (migrations previously ran only after create_all).
    """
    _try_exec(conn, 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    _try_exec(conn, 'CREATE EXTENSION IF NOT EXISTS "vector";')
    _try_exec(conn, 'CREATE EXTENSION IF NOT EXISTS "postgis";')
    _try_exec(conn, 'CREATE EXTENSION IF NOT EXISTS "pg_trgm";')

    ext_rows = conn.execute(
        text("select extname from pg_extension where extname in ('postgis','vector')")
    ).fetchall()
    installed = {r[0] for r in ext_rows}
    if "postgis" not in installed or "vector" not in installed:
        raise SchemaMigrationError(
            f"missing required extensions: {sorted({'postgis','vector'} - installed)}. "
            "Install postgis and vector on PostgreSQL (e.g. postgresql-XX-postgis-3, pgvector) "
            "or use an image that includes them."
        )


def ensure_required_extensions(engine) -> None:
    """Public entry: ensure extensions exist (PostgreSQL). Raises SchemaMigrationError if missing."""
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        _ensure_pg_extensions(conn)
    finally:
        conn.close()


def ensure_graph_schema(engine) -> None:
    """
    对 graph schema 做最小增量迁移：
    - node_types / relationship_types 增加本体字段与 status/parent
    - nodes 增加 GIS/向量/时序引用字段
    - relationships 增加 role/tags 字段
    """
    # 使用 AUTOCOMMIT，避免某条语句失败导致整个事务进入 aborted 状态
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        _ensure_pg_extensions(conn)

        # node_types（关键列：ORM 依赖）
        _must_exec(conn, "ALTER TABLE node_types ADD COLUMN IF NOT EXISTS parent_type_code VARCHAR(128);", "add node_types.parent_type_code failed")
        _must_exec(conn, "ALTER TABLE node_types ADD COLUMN IF NOT EXISTS status SMALLINT NOT NULL DEFAULT 0;", "add node_types.status failed")
        _try_exec(conn, "ALTER TABLE node_types ADD COLUMN IF NOT EXISTS schema_default JSONB NOT NULL DEFAULT '{}'::jsonb;")
        _try_exec(conn, "ALTER TABLE node_types ADD COLUMN IF NOT EXISTS inferred_rules JSONB NOT NULL DEFAULT '{}'::jsonb;")
        _try_exec(conn, "ALTER TABLE node_types ADD COLUMN IF NOT EXISTS tags JSONB NOT NULL DEFAULT '[]'::jsonb;")
        _try_exec(conn, "ALTER TABLE node_types ADD COLUMN IF NOT EXISTS ui_config JSONB NOT NULL DEFAULT '{}'::jsonb;")
        _try_exec(conn, "ALTER TABLE node_types ADD COLUMN IF NOT EXISTS trait_class VARCHAR(64) NOT NULL DEFAULT 'UNKNOWN';")
        _try_exec(conn, "ALTER TABLE node_types ADD COLUMN IF NOT EXISTS trait_mask BIGINT NOT NULL DEFAULT 0;")
        _try_exec(conn, "ALTER TABLE node_types DROP CONSTRAINT IF EXISTS chk_node_types_trait_mask_non_negative;")
        _try_exec(conn, "ALTER TABLE node_types ADD CONSTRAINT chk_node_types_trait_mask_non_negative CHECK (trait_mask >= 0);")
        _try_exec(conn, "ALTER TABLE node_types ALTER COLUMN type_code TYPE VARCHAR(128);")
        _try_exec(
            conn,
            "ALTER TABLE node_types ADD CONSTRAINT IF NOT EXISTS fk_node_types_parent "
            "FOREIGN KEY (parent_type_code) REFERENCES node_types(type_code) ON DELETE RESTRICT;",
        )

        # relationship_types（关键列：ORM 依赖）
        _must_exec(conn, "ALTER TABLE relationship_types ADD COLUMN IF NOT EXISTS status SMALLINT NOT NULL DEFAULT 0;", "add relationship_types.status failed")
        _must_exec(conn, "ALTER TABLE relationship_types ADD COLUMN IF NOT EXISTS constraints JSONB NOT NULL DEFAULT '{}'::jsonb;", "add relationship_types.constraints failed")
        _try_exec(conn, "ALTER TABLE relationship_types ADD COLUMN IF NOT EXISTS inferred_rules JSONB NOT NULL DEFAULT '{}'::jsonb;")
        _try_exec(conn, "ALTER TABLE relationship_types ADD COLUMN IF NOT EXISTS tags JSONB NOT NULL DEFAULT '[]'::jsonb;")
        _try_exec(conn, "ALTER TABLE relationship_types ADD COLUMN IF NOT EXISTS ui_config JSONB NOT NULL DEFAULT '{}'::jsonb;")
        _try_exec(conn, "ALTER TABLE relationship_types ADD COLUMN IF NOT EXISTS trait_class VARCHAR(64) NOT NULL DEFAULT 'UNKNOWN';")
        _try_exec(conn, "ALTER TABLE relationship_types ADD COLUMN IF NOT EXISTS trait_mask BIGINT NOT NULL DEFAULT 0;")
        _try_exec(conn, "ALTER TABLE relationship_types DROP CONSTRAINT IF EXISTS chk_relationship_types_trait_mask_non_negative;")
        _try_exec(conn, "ALTER TABLE relationship_types ADD CONSTRAINT chk_relationship_types_trait_mask_non_negative CHECK (trait_mask >= 0);")
        _try_exec(conn, "ALTER TABLE relationship_types ALTER COLUMN type_code TYPE VARCHAR(128);")

        # nodes
        _try_exec(conn, "ALTER TABLE nodes ALTER COLUMN type_code TYPE VARCHAR(128);")
        _try_exec(conn, "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS location_geom geometry(Geometry, 4326);")
        _try_exec(conn, "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS home_geom geometry(Geometry, 4326);")
        _try_exec(conn, "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS geom_geojson JSONB;")
        _try_exec(conn, "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS semantic_embedding vector(1536);")
        _try_exec(conn, "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS structure_embedding vector(256);")
        _try_exec(conn, "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS ts_data_ref_id UUID UNIQUE;")
        _try_exec(conn, "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS trait_class VARCHAR(64) NOT NULL DEFAULT 'UNKNOWN';")
        _try_exec(conn, "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS trait_mask BIGINT NOT NULL DEFAULT 0;")
        _try_exec(conn, "ALTER TABLE nodes DROP CONSTRAINT IF EXISTS chk_nodes_trait_mask_non_negative;")
        _try_exec(conn, "ALTER TABLE nodes ADD CONSTRAINT chk_nodes_trait_mask_non_negative CHECK (trait_mask >= 0);")
        _try_exec(conn, "CREATE INDEX IF NOT EXISTS idx_nodes_active_trait_class ON nodes (is_active, trait_class);")

        # relationships
        _try_exec(conn, "ALTER TABLE relationships ALTER COLUMN type_code TYPE VARCHAR(128);")
        _try_exec(conn, "ALTER TABLE relationships ADD COLUMN IF NOT EXISTS source_role VARCHAR(128);")
        _try_exec(conn, "ALTER TABLE relationships ADD COLUMN IF NOT EXISTS target_role VARCHAR(128);")
        _try_exec(conn, "ALTER TABLE relationships ADD COLUMN IF NOT EXISTS tags JSONB NOT NULL DEFAULT '[]'::jsonb;")
        _try_exec(conn, "ALTER TABLE relationships ADD COLUMN IF NOT EXISTS trait_class VARCHAR(64) NOT NULL DEFAULT 'UNKNOWN';")
        _try_exec(conn, "ALTER TABLE relationships ADD COLUMN IF NOT EXISTS trait_mask BIGINT NOT NULL DEFAULT 0;")
        _try_exec(conn, "ALTER TABLE relationships DROP CONSTRAINT IF EXISTS chk_relationships_trait_mask_non_negative;")
        _try_exec(conn, "ALTER TABLE relationships ADD CONSTRAINT chk_relationships_trait_mask_non_negative CHECK (trait_mask >= 0);")
        _try_exec(
            conn,
            "CREATE INDEX IF NOT EXISTS idx_relationships_active_trait_class ON relationships (is_active, trait_class);",
        )

        # trait sync jobs
        _try_exec(
            conn,
            """
CREATE TABLE IF NOT EXISTS trait_sync_jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain VARCHAR(32) NOT NULL,
    type_code VARCHAR(128) NOT NULL,
    reason VARCHAR(64) NOT NULL DEFAULT 'type_trait_changed',
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    retries INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 5,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_trait_sync_jobs_status_created_at ON trait_sync_jobs (status, created_at);
CREATE INDEX IF NOT EXISTS ix_trait_sync_jobs_type_code ON trait_sync_jobs (domain, type_code);
            """.strip(),
        )

        _try_exec(
            conn,
            """
CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    kid VARCHAR(64) UNIQUE NOT NULL,
    owner_account_id INTEGER NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
    key_hash VARCHAR(256) NOT NULL,
    salt VARCHAR(128) NOT NULL,
    algorithm VARCHAR(32) NOT NULL DEFAULT 'pbkdf2_sha256',
    iterations INTEGER NOT NULL DEFAULT 210000,
    name VARCHAR(128),
    scopes JSONB NOT NULL DEFAULT '[]'::jsonb,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    last_used_ip VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_api_keys_owner_account_id ON api_keys (owner_account_id);
CREATE INDEX IF NOT EXISTS ix_api_keys_owner_revoked ON api_keys (owner_account_id, revoked);
CREATE INDEX IF NOT EXISTS ix_api_keys_expires_at ON api_keys (expires_at);
CREATE INDEX IF NOT EXISTS ix_api_keys_last_used_at ON api_keys (last_used_at);
            """.strip(),
        )

        # trigger functions: instance inherits trait by type_code
        _try_exec(
            conn,
            """
CREATE OR REPLACE FUNCTION sync_node_traits_from_type()
RETURNS TRIGGER AS $$
DECLARE
    nt_trait_class VARCHAR(64);
    nt_trait_mask BIGINT;
BEGIN
    SELECT trait_class, trait_mask INTO nt_trait_class, nt_trait_mask
      FROM node_types WHERE type_code = NEW.type_code LIMIT 1;
    IF nt_trait_class IS NULL THEN
        RAISE EXCEPTION 'node_types.type_code % not found for node trait sync', NEW.type_code;
    END IF;
    NEW.trait_class := nt_trait_class;
    NEW.trait_mask := nt_trait_mask;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
            """.strip(),
        )
        _try_exec(
            conn,
            """
CREATE OR REPLACE FUNCTION sync_relationship_traits_from_type()
RETURNS TRIGGER AS $$
DECLARE
    rt_trait_class VARCHAR(64);
    rt_trait_mask BIGINT;
BEGIN
    SELECT trait_class, trait_mask INTO rt_trait_class, rt_trait_mask
      FROM relationship_types WHERE type_code = NEW.type_code LIMIT 1;
    IF rt_trait_class IS NULL THEN
        RAISE EXCEPTION 'relationship_types.type_code % not found for relationship trait sync', NEW.type_code;
    END IF;
    NEW.trait_class := rt_trait_class;
    NEW.trait_mask := rt_trait_mask;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
            """.strip(),
        )
        _try_exec(
            conn,
            """
DROP TRIGGER IF EXISTS trigger_sync_node_traits_from_type ON nodes;
CREATE TRIGGER trigger_sync_node_traits_from_type
    BEFORE INSERT OR UPDATE OF type_code, trait_class, trait_mask ON nodes
    FOR EACH ROW EXECUTE PROCEDURE sync_node_traits_from_type();
            """.strip(),
        )
        _try_exec(
            conn,
            """
DROP TRIGGER IF EXISTS trigger_sync_relationship_traits_from_type ON relationships;
CREATE TRIGGER trigger_sync_relationship_traits_from_type
    BEFORE INSERT OR UPDATE OF type_code, trait_class, trait_mask ON relationships
    FOR EACH ROW EXECUTE PROCEDURE sync_relationship_traits_from_type();
            """.strip(),
        )

        # enqueue sync jobs on type change (eventual consistency)
        _try_exec(
            conn,
            """
CREATE OR REPLACE FUNCTION enqueue_node_trait_sync_job()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.trait_class IS DISTINCT FROM NEW.trait_class)
       OR (OLD.trait_mask IS DISTINCT FROM NEW.trait_mask) THEN
        INSERT INTO trait_sync_jobs(domain, type_code, reason, payload)
        VALUES ('node', NEW.type_code, 'type_trait_changed',
            jsonb_build_object(
                'before_trait_class', OLD.trait_class,
                'after_trait_class', NEW.trait_class,
                'before_trait_mask', OLD.trait_mask,
                'after_trait_mask', NEW.trait_mask
            ));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
            """.strip(),
        )
        _try_exec(
            conn,
            """
CREATE OR REPLACE FUNCTION enqueue_relationship_trait_sync_job()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.trait_class IS DISTINCT FROM NEW.trait_class)
       OR (OLD.trait_mask IS DISTINCT FROM NEW.trait_mask) THEN
        INSERT INTO trait_sync_jobs(domain, type_code, reason, payload)
        VALUES ('relationship', NEW.type_code, 'type_trait_changed',
            jsonb_build_object(
                'before_trait_class', OLD.trait_class,
                'after_trait_class', NEW.trait_class,
                'before_trait_mask', OLD.trait_mask,
                'after_trait_mask', NEW.trait_mask
            ));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
            """.strip(),
        )
        _try_exec(
            conn,
            """
DROP TRIGGER IF EXISTS trigger_enqueue_node_trait_sync_job ON node_types;
CREATE TRIGGER trigger_enqueue_node_trait_sync_job
    AFTER UPDATE OF trait_class, trait_mask ON node_types
    FOR EACH ROW EXECUTE PROCEDURE enqueue_node_trait_sync_job();
            """.strip(),
        )
        _try_exec(
            conn,
            """
DROP TRIGGER IF EXISTS trigger_enqueue_relationship_trait_sync_job ON relationship_types;
CREATE TRIGGER trigger_enqueue_relationship_trait_sync_job
    AFTER UPDATE OF trait_class, trait_mask ON relationship_types
    FOR EACH ROW EXECUTE PROCEDURE enqueue_relationship_trait_sync_job();
            """.strip(),
        )

        # one-time backfill to align instance copy with type source of truth
        _try_exec(
            conn,
            """
UPDATE nodes n
SET trait_class = nt.trait_class,
    trait_mask = nt.trait_mask
FROM node_types nt
WHERE nt.type_code = n.type_code
  AND (n.trait_class IS DISTINCT FROM nt.trait_class OR n.trait_mask IS DISTINCT FROM nt.trait_mask);
            """.strip(),
        )
        _try_exec(
            conn,
            """
UPDATE relationships r
SET trait_class = rt.trait_class,
    trait_mask = rt.trait_mask
FROM relationship_types rt
WHERE rt.type_code = r.type_code
  AND (r.trait_class IS DISTINCT FROM rt.trait_class OR r.trait_mask IS DISTINCT FROM rt.trait_mask);
            """.strip(),
        )
    finally:
        conn.close()


def ensure_command_policy_schema(engine) -> None:
    """
    Ensure command policy schema exists for old databases.

    Source of truth is `db/schemas/database_schema.sql` (command_policies section).
    """
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        table_ok = bool(conn.execute(text("select to_regclass('public.command_policies');")).scalar())
        col_ok = bool(
            conn.execute(
                text(
                    "select 1 from information_schema.columns "
                    "where table_schema='public' and table_name='command_policies' and column_name='policy_expr' "
                    "limit 1;"
                )
            ).fetchone()
        )
        if table_ok and col_ok:
            return

        sql_path = Path(__file__).parent / "schemas" / "database_schema.sql"
        schema_sql = sql_path.read_text(encoding="utf-8")
        start = "-- BEGIN command_policies"
        end = "-- END command_policies"
        if start not in schema_sql or end not in schema_sql:
            raise SchemaMigrationError("command_policies section not found in database_schema.sql")

        section = schema_sql.split(start, 1)[1].split(end, 1)[0].strip()
        if not section:
            raise SchemaMigrationError("command_policies section is empty")

        # Execute the section (should be idempotent via IF NOT EXISTS).
        _must_exec(conn, section, "apply command_policies schema from database_schema.sql failed")
    finally:
        conn.close()


def ensure_world_runtime_schema(engine) -> None:
    """
    Ensure world runtime state/job schema exists for old databases.

    Source of truth is `db/schemas/database_schema.sql` (world_runtime section).
    """
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        runtime_ok = bool(conn.execute(text("select to_regclass('public.world_runtime_states');")).scalar())
        jobs_ok = bool(conn.execute(text("select to_regclass('public.world_install_jobs');")).scalar())
        if runtime_ok and jobs_ok:
            _try_exec(
                conn,
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_world_install_jobs_running_action "
                "ON world_install_jobs (world_id, action) WHERE status = 'running';",
            )
            return

        sql_path = Path(__file__).parent / "schemas" / "database_schema.sql"
        schema_sql = sql_path.read_text(encoding="utf-8")
        start = "-- BEGIN world_runtime"
        end = "-- END world_runtime"
        if start not in schema_sql or end not in schema_sql:
            raise SchemaMigrationError("world_runtime section not found in database_schema.sql")

        section = schema_sql.split(start, 1)[1].split(end, 1)[0].strip()
        if not section:
            raise SchemaMigrationError("world_runtime section is empty")

        _must_exec(conn, section, "apply world_runtime schema from database_schema.sql failed")
        _try_exec(
            conn,
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_world_install_jobs_running_action "
            "ON world_install_jobs (world_id, action) WHERE status = 'running';",
        )
    finally:
        conn.close()


def ensure_f02_agent_memory_schema(engine) -> None:
    """
    F02: agent_memory_entries, agent_run_records, agent_long_term_memory.

    Source of truth: `db/schemas/database_schema.sql` (f02_agent_memory section).
    """
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        mem_ok = bool(conn.execute(text("select to_regclass('public.agent_memory_entries');")).scalar())
        run_ok = bool(conn.execute(text("select to_regclass('public.agent_run_records');")).scalar())
        ltm_ok = bool(conn.execute(text("select to_regclass('public.agent_long_term_memory');")).scalar())
        if mem_ok and run_ok and ltm_ok:
            return

        sql_path = Path(__file__).parent / "schemas" / "database_schema.sql"
        schema_sql = sql_path.read_text(encoding="utf-8")
        start = "-- BEGIN f02_agent_memory"
        end = "-- END f02_agent_memory"
        if start not in schema_sql or end not in schema_sql:
            raise SchemaMigrationError("f02_agent_memory section not found in database_schema.sql")

        section = schema_sql.split(start, 1)[1].split(end, 1)[0].strip()
        if not section:
            raise SchemaMigrationError("f02_agent_memory section is empty")

        _must_exec(conn, section, "apply f02_agent_memory schema from database_schema.sql failed")
    finally:
        conn.close()


def ensure_f02_ltm_semantic_extension(engine) -> None:
    """
    F02 extension: LTM embedding columns + agent_long_term_memory_links + indexes.

    Idempotent for existing DBs that only had base f02_agent_memory tables.
    HNSW index is best-effort (_try_exec) for older pgvector builds.
    """
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        _try_exec(conn, "ALTER TABLE agent_long_term_memory ADD COLUMN IF NOT EXISTS embedding vector(1536);")
        _try_exec(conn, "ALTER TABLE agent_long_term_memory ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(64);")
        _try_exec(conn, "ALTER TABLE agent_long_term_memory ADD COLUMN IF NOT EXISTS embedding_updated_at TIMESTAMPTZ;")

        _try_exec(
            conn,
            """
CREATE TABLE IF NOT EXISTS agent_long_term_memory_links (
    id BIGSERIAL PRIMARY KEY,
    agent_node_id INTEGER NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
    source_ltm_id BIGINT NOT NULL REFERENCES agent_long_term_memory (id) ON DELETE CASCADE,
    target_ltm_id BIGINT NOT NULL REFERENCES agent_long_term_memory (id) ON DELETE CASCADE,
    link_type VARCHAR(64) NOT NULL,
    weight REAL DEFAULT 1.0,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_agent_ltm_link_distinct CHECK (source_ltm_id <> target_ltm_id)
);
            """.strip(),
        )
        _try_exec(
            conn,
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_ltm_links_src_tgt_type "
            "ON agent_long_term_memory_links (source_ltm_id, target_ltm_id, link_type);",
        )
        _try_exec(
            conn,
            "CREATE INDEX IF NOT EXISTS ix_ltm_links_agent_source "
            "ON agent_long_term_memory_links (agent_node_id, source_ltm_id);",
        )
        _try_exec(
            conn,
            "CREATE INDEX IF NOT EXISTS ix_ltm_links_agent_target "
            "ON agent_long_term_memory_links (agent_node_id, target_ltm_id);",
        )
        _try_exec(
            conn,
            """
CREATE INDEX IF NOT EXISTS ix_agent_ltm_embedding_hnsw
    ON agent_long_term_memory USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;
            """.strip(),
        )
    finally:
        conn.close()


def ensure_content_visibility_backfill(engine) -> None:
    """
    Backfill semantic content visibility attributes for existing nodes.

    - system_command_ability: entity_kind=ability, presentation_domains=[help,npc]
    - system_bulletin_board: entity_kind=item, presentation_domains=[room]
    """
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        _try_exec(
            conn,
            """
UPDATE nodes
SET attributes = COALESCE(attributes, '{}'::jsonb)
    || '{"entity_kind":"ability","presentation_domains":["help","npc"],"access_locks":{"view":"all()","invoke":"all()"}}'::jsonb
WHERE type_code = 'system_command_ability'
  AND (
    attributes IS NULL
    OR NOT (attributes ? 'entity_kind')
    OR NOT (attributes ? 'presentation_domains')
    OR NOT (attributes ? 'access_locks')
  );
""".strip(),
        )
        _try_exec(
            conn,
            """
UPDATE nodes
SET attributes = COALESCE(attributes, '{}'::jsonb)
    || '{"entity_kind":"item","presentation_domains":["room"],"access_locks":{"view":"all()","interact":"all()"}}'::jsonb
WHERE type_code = 'system_bulletin_board'
  AND (
    attributes IS NULL
    OR NOT (attributes ? 'entity_kind')
    OR NOT (attributes ? 'presentation_domains')
    OR NOT (attributes ? 'access_locks')
  );
""".strip(),
        )
    finally:
        conn.close()


def ensure_graph_seed_ontology(engine) -> None:
    """
    Ensure minimal ontology rows required by graph seed pipeline.

    This keeps integration tests and runtime graph seeding stable on old databases
    where these rows may be missing.

    Loads optional JSON overlays from db/ontology/graph_seed_node_types.yaml
    (schema_definition, schema_default, inferred_rules, tags, ui_config) and
    applies them on INSERT and ON CONFLICT DO UPDATE.
    """
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        nt_overlays = load_graph_seed_node_type_overrides()

        for type_code, parent_code, type_name, typeclass, classname, module_path in GRAPH_SEED_ONTOLOGY_NODE_ROWS:
            overlay = nt_overlays.get(type_code, {})
            jb = node_type_jsonb_params(overlay if isinstance(overlay, dict) else None)
            desc_override = overlay.get("description") if isinstance(overlay, dict) else None
            description = desc_override if isinstance(desc_override, str) and desc_override.strip() else (
                f"graph seed ontology ensured: {type_code}"
            )
            params = {
                "type_code": type_code,
                "parent_type_code": parent_code,
                "type_name": type_name,
                "typeclass": typeclass,
                "classname": classname,
                "module_path": module_path,
                "description": description,
                **jb,
            }
            _try_exec_mapped(
                conn,
                """
                INSERT INTO node_types (
                    type_code, parent_type_code, type_name, typeclass, status, classname, module_path, description,
                    schema_definition, schema_default, inferred_rules, tags, ui_config, trait_class, trait_mask
                )
                VALUES (
                    :type_code, :parent_type_code, :type_name, :typeclass, 0, :classname, :module_path, :description,
                    CAST(:schema_definition AS jsonb), CAST(:schema_default AS jsonb), CAST(:inferred_rules AS jsonb),
                    CAST(:tags AS jsonb), CAST(:ui_config AS jsonb), :trait_class, :trait_mask
                )
                ON CONFLICT (type_code) DO UPDATE SET
                    parent_type_code = EXCLUDED.parent_type_code,
                    type_name = EXCLUDED.type_name,
                    typeclass = EXCLUDED.typeclass,
                    classname = EXCLUDED.classname,
                    module_path = EXCLUDED.module_path,
                    description = EXCLUDED.description,
                    schema_definition = EXCLUDED.schema_definition,
                    schema_default = EXCLUDED.schema_default,
                    inferred_rules = EXCLUDED.inferred_rules,
                    tags = EXCLUDED.tags,
                    ui_config = EXCLUDED.ui_config,
                    trait_class = EXCLUDED.trait_class,
                    trait_mask = EXCLUDED.trait_mask;
                """,
                params,
            )

        # trait_mask: Conceptual + Spatial; see F01 + app.constants.trait_mask.LOCATION_RELATIONSHIP_EDGE
        rel_rows = [
            ("connects_to", "连接到", "app.models.relationships.LocationRelationship", "SPACE", LOCATION_RELATIONSHIP_EDGE),
            ("contains", "包含", "app.models.relationships.LocationRelationship", "SPACE", LOCATION_RELATIONSHIP_EDGE),
            ("located_in", "位于", "app.models.relationships.LocationRelationship", "SPACE", LOCATION_RELATIONSHIP_EDGE),
        ]
        for type_code, type_name, typeclass, trait_class, trait_mask in rel_rows:
            _try_exec_mapped(
                conn,
                """
                INSERT INTO relationship_types (
                    type_code, type_name, typeclass, status, description,
                    constraints, schema_definition, inferred_rules, tags, ui_config,
                    is_directed, is_symmetric, is_transitive, trait_class, trait_mask
                )
                VALUES (
                    :type_code, :type_name, :typeclass, 0, :description,
                    '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, '[]'::jsonb, '{}'::jsonb,
                    TRUE, FALSE, FALSE, :trait_class, :trait_mask
                )
                ON CONFLICT (type_code) DO UPDATE SET
                    type_name = EXCLUDED.type_name,
                    typeclass = EXCLUDED.typeclass,
                    trait_class = EXCLUDED.trait_class,
                    trait_mask = EXCLUDED.trait_mask;
                """,
                {
                    "type_code": type_code,
                    "type_name": type_name,
                    "typeclass": typeclass,
                    "description": f"graph seed ontology ensured: {type_code}",
                    "trait_class": trait_class,
                    "trait_mask": trait_mask,
                },
            )
    finally:
        conn.close()


def ensure_builtin_node_type_schema_envelopes(engine) -> None:
    """
    T5: Normalize legacy flat/fragment node_types.schema_definition for builtin types
    to JSON Schema object envelope (type + properties). Idempotent: skips rows that
    already use the envelope shape.
    """
    import json

    from db.ontology.schema_envelope import (
        account_node_type_schema_definition,
        is_json_schema_object_envelope,
        system_command_ability_node_type_schema_definition,
        system_notice_node_type_schema_definition,
    )

    targets = (
        ("account", account_node_type_schema_definition()),
        ("system_command_ability", system_command_ability_node_type_schema_definition()),
        ("system_notice", system_notice_node_type_schema_definition()),
    )
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        for type_code, sd in targets:
            row = conn.execute(
                text("SELECT schema_definition FROM node_types WHERE type_code = :tc"),
                {"tc": type_code},
            ).fetchone()
            if row is None:
                continue
            existing = row[0]
            if is_json_schema_object_envelope(existing):
                continue
            conn.execute(
                text("UPDATE node_types SET schema_definition = CAST(:js AS jsonb) WHERE type_code = :tc"),
                {"js": json.dumps(sd, ensure_ascii=False), "tc": type_code},
            )
    finally:
        conn.close()


def ensure_nodes_world_id_index(engine) -> None:
    """
    F11: partial B-tree on (attributes->>'world_id') for world-scoped graph policy filters.
    Idempotent: CREATE INDEX IF NOT EXISTS.
    """
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        _try_exec(
            conn,
            """
            CREATE INDEX IF NOT EXISTS idx_nodes_attributes_world_id_text
                ON nodes ((attributes->>'world_id'))
                WHERE attributes ? 'world_id'
            """,
        )
    finally:
        conn.close()


def ensure_account_data_access_defaults(engine) -> None:
    """
    F11: merge default `data_access` into seeded account nodes when missing.
    Idempotent: does not overwrite existing data_access.
    """
    import json

    from app.constants.data_access_defaults import (
        ADMIN_DATA_ACCESS,
        DEV_DATA_ACCESS,
        USER_LIKE_DATA_ACCESS,
    )

    mapping = (
        ("admin", ADMIN_DATA_ACCESS),
        ("dev", DEV_DATA_ACCESS),
        ("campus", USER_LIKE_DATA_ACCESS),
    )
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        for name, policy in mapping:
            merge = json.dumps({"data_access": policy}, ensure_ascii=False)
            conn.execute(
                text(
                    """
                    UPDATE nodes
                    SET attributes = attributes || CAST(:merge AS jsonb)
                    WHERE type_code = 'account'
                      AND name = :name
                      AND (
                        attributes->'data_access' IS NULL
                        OR attributes->'data_access' = 'null'::jsonb
                      )
                    """
                ),
                {"name": name, "merge": merge},
            )
    finally:
        conn.close()
