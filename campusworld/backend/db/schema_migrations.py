"""
轻量 schema 兼容迁移（非 Alembic）

目的：在已有老库（仅包含最初字段）的情况下，让 ORM 新增字段可用，
避免 `create_all()` 不会 alter table 导致的运行时报错。
"""

from __future__ import annotations

from pathlib import Path
from sqlalchemy import text


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
        # 扩展尽力启用（失败不阻断）
        _try_exec(conn, 'CREATE EXTENSION IF NOT EXISTS "vector";')
        _try_exec(conn, 'CREATE EXTENSION IF NOT EXISTS "postgis";')
        _try_exec(conn, 'CREATE EXTENSION IF NOT EXISTS "pg_trgm";')

        # 若关键扩展缺失，则不继续添加依赖这些扩展的列类型
        ext_rows = conn.execute(
            text("select extname from pg_extension where extname in ('postgis','vector')")
        ).fetchall()
        installed = {r[0] for r in ext_rows}
        if "postgis" not in installed or "vector" not in installed:
            raise SchemaMigrationError(
                f"missing required extensions: {sorted({'postgis','vector'} - installed)}"
            )

        # node_types（关键列：ORM 依赖）
        _must_exec(conn, "ALTER TABLE node_types ADD COLUMN IF NOT EXISTS parent_type_code VARCHAR(128);", "add node_types.parent_type_code failed")
        _must_exec(conn, "ALTER TABLE node_types ADD COLUMN IF NOT EXISTS status SMALLINT NOT NULL DEFAULT 0;", "add node_types.status failed")
        _try_exec(conn, "ALTER TABLE node_types ADD COLUMN IF NOT EXISTS schema_default JSONB NOT NULL DEFAULT '{}'::jsonb;")
        _try_exec(conn, "ALTER TABLE node_types ADD COLUMN IF NOT EXISTS inferred_rules JSONB NOT NULL DEFAULT '{}'::jsonb;")
        _try_exec(conn, "ALTER TABLE node_types ADD COLUMN IF NOT EXISTS tags JSONB NOT NULL DEFAULT '[]'::jsonb;")
        _try_exec(conn, "ALTER TABLE node_types ADD COLUMN IF NOT EXISTS ui_config JSONB NOT NULL DEFAULT '{}'::jsonb;")
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
        _try_exec(conn, "ALTER TABLE relationship_types ALTER COLUMN type_code TYPE VARCHAR(128);")

        # nodes
        _try_exec(conn, "ALTER TABLE nodes ALTER COLUMN type_code TYPE VARCHAR(128);")
        _try_exec(conn, "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS location_geom geometry(Geometry, 4326);")
        _try_exec(conn, "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS home_geom geometry(Geometry, 4326);")
        _try_exec(conn, "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS geom_geojson JSONB;")
        _try_exec(conn, "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS semantic_embedding vector(1536);")
        _try_exec(conn, "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS structure_embedding vector(256);")
        _try_exec(conn, "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS ts_data_ref_id UUID UNIQUE;")

        # relationships
        _try_exec(conn, "ALTER TABLE relationships ALTER COLUMN type_code TYPE VARCHAR(128);")
        _try_exec(conn, "ALTER TABLE relationships ADD COLUMN IF NOT EXISTS source_role VARCHAR(128);")
        _try_exec(conn, "ALTER TABLE relationships ADD COLUMN IF NOT EXISTS target_role VARCHAR(128);")
        _try_exec(conn, "ALTER TABLE relationships ADD COLUMN IF NOT EXISTS tags JSONB NOT NULL DEFAULT '[]'::jsonb;")
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
    """
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        node_rows = [
            ("world", None, "世界", "app.models.world.World", "World", "app.models.world"),
            ("world_object", None, "世界对象", "app.models.world.WorldObject", "WorldObject", "app.models.world"),
            ("building", "world_object", "建筑", "app.models.building.Building", "Building", "app.models.building"),
            ("building_floor", "world_object", "楼层", "app.models.floor.BuildingFloor", "BuildingFloor", "app.models.floor"),
            ("room", "world_object", "房间", "app.models.room.Room", "Room", "app.models.room"),
            ("npc_agent", "world_object", "NPC代理", "app.models.things.agents.NpcAgent", "NpcAgent", "app.models.things.agents"),
            (
                "access_terminal",
                "world_object",
                "访问终端",
                "app.models.things.terminals.AccessTerminal",
                "AccessTerminal",
                "app.models.things.terminals",
            ),
            (
                "logical_zone",
                "world_object",
                "逻辑分区",
                "app.models.things.zones.LogicalZone",
                "LogicalZone",
                "app.models.things.zones",
            ),
            (
                "furniture",
                "world_object",
                "家具",
                "app.models.things.furniture.Furniture",
                "Furniture",
                "app.models.things.furniture",
            ),
            (
                "network_access_point",
                "world_object",
                "无线接入点",
                "app.models.things.devices.NetworkAccessPoint",
                "NetworkAccessPoint",
                "app.models.things.devices",
            ),
            (
                "av_display",
                "world_object",
                "音视频大屏",
                "app.models.things.devices.AvDisplay",
                "AvDisplay",
                "app.models.things.devices",
            ),
            (
                "lighting_fixture",
                "world_object",
                "照明灯具",
                "app.models.things.devices.LightingFixture",
                "LightingFixture",
                "app.models.things.devices",
            ),
            (
                "conference_seating",
                "world_object",
                "会议座椅",
                "app.models.things.seating.ConferenceSeating",
                "ConferenceSeating",
                "app.models.things.seating",
            ),
            (
                "lounge_furniture",
                "world_object",
                "休闲家具",
                "app.models.things.seating.LoungeFurniture",
                "LoungeFurniture",
                "app.models.things.seating",
            ),
        ]
        for type_code, parent_code, type_name, typeclass, classname, module_path in node_rows:
            _try_exec_mapped(
                conn,
                """
                INSERT INTO node_types (
                    type_code, parent_type_code, type_name, typeclass, status, classname, module_path, description,
                    schema_definition, schema_default, inferred_rules, tags, ui_config
                )
                VALUES (
                    :type_code, :parent_type_code, :type_name, :typeclass, 0, :classname, :module_path, :description,
                    '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, '[]'::jsonb, '{}'::jsonb
                )
                ON CONFLICT (type_code) DO UPDATE SET
                    parent_type_code = EXCLUDED.parent_type_code,
                    type_name = EXCLUDED.type_name,
                    typeclass = EXCLUDED.typeclass,
                    classname = EXCLUDED.classname,
                    module_path = EXCLUDED.module_path;
                """,
                {
                    "type_code": type_code,
                    "parent_type_code": parent_code,
                    "type_name": type_name,
                    "typeclass": typeclass,
                    "classname": classname,
                    "module_path": module_path,
                    "description": f"graph seed ontology ensured: {type_code}",
                },
            )

        rel_rows = [
            ("connects_to", "连接到", "app.models.relationships.LocationRelationship"),
            ("contains", "包含", "app.models.relationships.LocationRelationship"),
            ("located_in", "位于", "app.models.relationships.LocationRelationship"),
        ]
        for type_code, type_name, typeclass in rel_rows:
            _try_exec_mapped(
                conn,
                """
                INSERT INTO relationship_types (
                    type_code, type_name, typeclass, status, description,
                    constraints, schema_definition, inferred_rules, tags, ui_config,
                    is_directed, is_symmetric, is_transitive
                )
                VALUES (
                    :type_code, :type_name, :typeclass, 0, :description,
                    '{}'::jsonb, '{}'::jsonb, '{}'::jsonb, '[]'::jsonb, '{}'::jsonb,
                    TRUE, FALSE, FALSE
                )
                ON CONFLICT (type_code) DO UPDATE SET
                    type_name = EXCLUDED.type_name,
                    typeclass = EXCLUDED.typeclass;
                """,
                {
                    "type_code": type_code,
                    "type_name": type_name,
                    "typeclass": typeclass,
                    "description": f"graph seed ontology ensured: {type_code}",
                },
            )
    finally:
        conn.close()
