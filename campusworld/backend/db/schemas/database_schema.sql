-- ==================================================
-- CampusWorld 纯图数据设计 - 数据库建表语句
-- ==================================================
-- 设计要点（Evennia + Palantir 类实践）:
-- - Evennia: 统一 Node/Relationship + 属性/标签旁路索引；类型表驱动运行时行为
-- - Palantir 类: 类型层级(parent)、schema_default + inferred_rules(本体/约束)、
--   ui_config(管理端表单)、审计与可演进元数据；节点侧向量/空间/时序引用可选扩展
--
-- 依赖扩展（按环境安装）:
-- - pgvector: 语义/结构向量
-- - postgis:  WGS84 几何与空间索引
-- - pg_trgm:  模糊搜索
-- TimescaleDB 为可选：见文件末尾说明块，默认不启用以免破坏纯 PostgreSQL 环境
-- ==================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ==================================================
-- 第一阶段：创建基础表结构
-- ==================================================

-- 1. 节点类型定义表（支持类型层级 + 本体默认 + 推理约束 + 配置 UI）
CREATE TABLE IF NOT EXISTS node_types (
    id SERIAL PRIMARY KEY,
    type_code VARCHAR(128) UNIQUE NOT NULL,
    parent_type_code VARCHAR(128) REFERENCES node_types (type_code) ON DELETE RESTRICT,
    type_name VARCHAR(255) NOT NULL,
    typeclass VARCHAR(500) NOT NULL,
    status SMALLINT NOT NULL DEFAULT 0 CHECK (status IN (0, 1, 2)),
    classname VARCHAR(100) NOT NULL,
    module_path VARCHAR(300) NOT NULL,
    description TEXT,
    schema_definition JSONB NOT NULL DEFAULT '{}',
    schema_default JSONB NOT NULL DEFAULT '{}',
    inferred_rules JSONB NOT NULL DEFAULT '{}',
    tags JSONB NOT NULL DEFAULT '[]',
    ui_config JSONB NOT NULL DEFAULT '{}',
    trait_class VARCHAR(64) NOT NULL DEFAULT 'UNKNOWN',
    trait_mask BIGINT NOT NULL DEFAULT 0 CHECK (trait_mask >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_node_types_parent_type_code ON node_types (parent_type_code);
CREATE INDEX IF NOT EXISTS idx_node_types_tags_gin ON node_types USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_node_types_schema_definition_gin ON node_types USING GIN (schema_definition);
CREATE INDEX IF NOT EXISTS idx_node_types_schema_default_gin ON node_types USING GIN (schema_default);
CREATE INDEX IF NOT EXISTS idx_node_types_inferred_rules_gin ON node_types USING GIN (inferred_rules);
CREATE INDEX IF NOT EXISTS idx_node_types_ui_config_gin ON node_types USING GIN (ui_config);
CREATE INDEX IF NOT EXISTS idx_node_types_status ON node_types (status);
CREATE INDEX IF NOT EXISTS idx_node_types_code ON node_types (type_code);
CREATE INDEX IF NOT EXISTS idx_node_types_classname ON node_types (classname);

-- 2. 关系类型定义表
CREATE TABLE IF NOT EXISTS relationship_types (
    id SERIAL PRIMARY KEY,
    type_code VARCHAR(128) UNIQUE NOT NULL,
    type_name VARCHAR(255) NOT NULL,
    typeclass VARCHAR(500) NOT NULL,
    status SMALLINT NOT NULL DEFAULT 0 CHECK (status IN (0, 1, 2)),
    constraints JSONB NOT NULL DEFAULT '{}',
    schema_definition JSONB NOT NULL DEFAULT '{}',
    inferred_rules JSONB NOT NULL DEFAULT '{}',
    tags JSONB NOT NULL DEFAULT '[]',
    ui_config JSONB NOT NULL DEFAULT '{}',
    trait_class VARCHAR(64) NOT NULL DEFAULT 'UNKNOWN',
    trait_mask BIGINT NOT NULL DEFAULT 0 CHECK (trait_mask >= 0),
    description TEXT,
    is_directed BOOLEAN NOT NULL DEFAULT TRUE,
    is_symmetric BOOLEAN NOT NULL DEFAULT FALSE,
    is_transitive BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_relationship_types_tags_gin ON relationship_types USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_relationship_types_constraints_gin ON relationship_types USING GIN (constraints);
CREATE INDEX IF NOT EXISTS idx_relationship_types_ui_config_gin ON relationship_types USING GIN (ui_config);
CREATE INDEX IF NOT EXISTS idx_relationship_types_status ON relationship_types (status);
CREATE INDEX IF NOT EXISTS idx_relationship_types_code ON relationship_types (type_code);

-- 3. 节点实例表（向量 / PostGIS / GeoJSON / 可选时序引用）
CREATE TABLE IF NOT EXISTS nodes (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
    type_id INTEGER NOT NULL REFERENCES node_types (id) ON DELETE RESTRICT,
    type_code VARCHAR(128) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_public BOOLEAN NOT NULL DEFAULT TRUE,
    access_level VARCHAR(50) NOT NULL DEFAULT 'normal',
    trait_class VARCHAR(64) NOT NULL DEFAULT 'UNKNOWN',
    trait_mask BIGINT NOT NULL DEFAULT 0 CHECK (trait_mask >= 0),
    location_id INTEGER REFERENCES nodes (id),
    home_id INTEGER REFERENCES nodes (id),
    location_geom geometry(Geometry, 4326),
    home_geom geometry(Geometry, 4326),
    geom_geojson JSONB,
    -- attributes 内约定扩展：
    -- - entity_kind: item | ability | character | service | ui | hidden
    -- - presentation_domains: ["room" | "inventory" | "help" | "npc" | ...]
    -- - access_locks: {"view":"all()","interact":"perm(x)","invoke":"role(admin) OR perm(y)"}
    attributes JSONB NOT NULL DEFAULT '{}',
    tags JSONB NOT NULL DEFAULT '[]',
    semantic_embedding vector(1536),
    structure_embedding vector(256),
    ts_data_ref_id UUID UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. 关系实例表（与内部整数 id 一致，便于 ORM 与图遍历）
CREATE TABLE IF NOT EXISTS relationships (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
    type_id INTEGER NOT NULL REFERENCES relationship_types (id) ON DELETE RESTRICT,
    type_code VARCHAR(128) NOT NULL,
    source_id INTEGER NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
    target_id INTEGER NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    weight INTEGER NOT NULL DEFAULT 1,
    trait_class VARCHAR(64) NOT NULL DEFAULT 'UNKNOWN',
    trait_mask BIGINT NOT NULL DEFAULT 0 CHECK (trait_mask >= 0),
    source_role VARCHAR(128),
    target_role VARCHAR(128),
    attributes JSONB NOT NULL DEFAULT '{}',
    tags JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_relationships_type_code
        FOREIGN KEY (type_code) REFERENCES relationship_types (type_code) ON DELETE RESTRICT
);

-- 5. 节点属性索引表
CREATE TABLE IF NOT EXISTS node_attribute_indexes (
    id SERIAL PRIMARY KEY,
    node_id INTEGER NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
    attribute_key VARCHAR(255) NOT NULL,
    attribute_value TEXT,
    attribute_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 6. 节点标签索引表
CREATE TABLE IF NOT EXISTS node_tag_indexes (
    id SERIAL PRIMARY KEY,
    node_id INTEGER NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
    tag VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ==================================================
-- Control Plane: Command authorization policies
-- ==================================================
-- BEGIN command_policies
CREATE TABLE IF NOT EXISTS command_policies (
    id SERIAL PRIMARY KEY,
    command_name VARCHAR(128) NOT NULL,
    required_permissions_any JSONB NOT NULL DEFAULT '[]'::jsonb,
    required_permissions_all JSONB NOT NULL DEFAULT '[]'::jsonb,
    required_roles_any JSONB NOT NULL DEFAULT '[]'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    scope VARCHAR(64) NOT NULL DEFAULT 'global',
    version INTEGER NOT NULL DEFAULT 1,
    updated_by VARCHAR(128),
    policy_expr TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_command_policy_command_name
    ON command_policies (command_name);
CREATE INDEX IF NOT EXISTS ix_command_policies_enabled
    ON command_policies (enabled);
-- END command_policies

-- ==================================================
-- Control Plane: World runtime state & install jobs
-- ==================================================
-- BEGIN world_runtime
CREATE TABLE IF NOT EXISTS world_runtime_states (
    world_id VARCHAR(128) PRIMARY KEY,
    status VARCHAR(32) NOT NULL,
    version VARCHAR(64),
    last_error_code VARCHAR(128),
    last_error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_by VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_world_runtime_states_status
    ON world_runtime_states (status);
CREATE INDEX IF NOT EXISTS ix_world_runtime_states_updated_at
    ON world_runtime_states (updated_at);

CREATE TABLE IF NOT EXISTS world_install_jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    world_id VARCHAR(128) NOT NULL,
    action VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    requested_by VARCHAR(128),
    request_fingerprint VARCHAR(255),
    error_code VARCHAR(128),
    event_log JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

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
CREATE INDEX IF NOT EXISTS ix_trait_sync_jobs_status_created_at
    ON trait_sync_jobs (status, created_at);
CREATE INDEX IF NOT EXISTS ix_trait_sync_jobs_type_code
    ON trait_sync_jobs (domain, type_code);

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

CREATE INDEX IF NOT EXISTS ix_world_install_jobs_world_id
    ON world_install_jobs (world_id);
CREATE INDEX IF NOT EXISTS ix_world_install_jobs_status
    ON world_install_jobs (status);
CREATE INDEX IF NOT EXISTS ix_world_install_jobs_created_at
    ON world_install_jobs (created_at);
CREATE INDEX IF NOT EXISTS ix_world_install_jobs_fingerprint
    ON world_install_jobs (request_fingerprint);
CREATE UNIQUE INDEX IF NOT EXISTS uq_world_install_jobs_running_action
    ON world_install_jobs (world_id, action)
    WHERE status = 'running';
-- END world_runtime

-- ==================================================
-- 第三阶段：索引（几何 / 向量 / 查询）
-- ==================================================

CREATE INDEX IF NOT EXISTS idx_nodes_uuid ON nodes (uuid);
CREATE INDEX IF NOT EXISTS idx_nodes_type_id ON nodes (type_id);
CREATE INDEX IF NOT EXISTS idx_nodes_type_code ON nodes (type_code);
CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes (name);
CREATE INDEX IF NOT EXISTS idx_nodes_active ON nodes (is_active);
CREATE INDEX IF NOT EXISTS idx_nodes_public ON nodes (is_public);
CREATE INDEX IF NOT EXISTS idx_nodes_access_level ON nodes (access_level);
CREATE INDEX IF NOT EXISTS idx_nodes_location_id ON nodes (location_id);
CREATE INDEX IF NOT EXISTS idx_nodes_home_id ON nodes (home_id);
CREATE INDEX IF NOT EXISTS idx_nodes_created_at ON nodes (created_at);
CREATE INDEX IF NOT EXISTS idx_nodes_updated_at ON nodes (updated_at);
CREATE INDEX IF NOT EXISTS idx_nodes_ts_data_ref_id ON nodes (ts_data_ref_id) WHERE ts_data_ref_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_nodes_attributes_gin ON nodes USING GIN (attributes);
CREATE INDEX IF NOT EXISTS idx_nodes_tags_gin ON nodes USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_nodes_geom_geojson_gin ON nodes USING GIN (geom_geojson);

CREATE INDEX IF NOT EXISTS idx_nodes_type_active ON nodes (type_code, is_active);
CREATE INDEX IF NOT EXISTS idx_nodes_type_public ON nodes (type_code, is_public);
CREATE INDEX IF NOT EXISTS idx_nodes_location_active ON nodes (location_id, is_active);
CREATE INDEX IF NOT EXISTS idx_nodes_active_trait_class ON nodes (is_active, trait_class);

-- F11: 按 attributes.world_id 过滤（表达式 B-tree）；部分索引缩小体积（仅含存在 world_id 键的行）
CREATE INDEX IF NOT EXISTS idx_nodes_attributes_world_id_text
    ON nodes ((attributes->>'world_id'))
    WHERE attributes ? 'world_id';

CREATE INDEX IF NOT EXISTS idx_nodes_name_trgm ON nodes USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_nodes_description_trgm ON nodes USING GIN (description gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_nodes_location_geom_gist ON nodes USING GIST (location_geom) WHERE location_geom IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_nodes_home_geom_gist ON nodes USING GIST (home_geom) WHERE home_geom IS NOT NULL;

-- 向量 ANN 索引：建议在有一定数据量后创建（空表/极少行时 ivfflat/hnsw 可能报错或无效）
-- CREATE INDEX idx_nodes_semantic_embedding_ivfflat ON nodes USING ivfflat (semantic_embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX idx_nodes_structure_embedding_ivfflat ON nodes USING ivfflat (structure_embedding vector_cosine_ops) WITH (lists = 50);

CREATE INDEX IF NOT EXISTS idx_relationships_uuid ON relationships (uuid);
CREATE INDEX IF NOT EXISTS idx_relationships_type_id ON relationships (type_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type_code ON relationships (type_code);
CREATE INDEX IF NOT EXISTS idx_relationships_source_id ON relationships (source_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target_id ON relationships (target_id);
CREATE INDEX IF NOT EXISTS idx_relationships_active ON relationships (is_active);
CREATE INDEX IF NOT EXISTS idx_relationships_weight ON relationships (weight);
CREATE INDEX IF NOT EXISTS idx_relationships_created_at ON relationships (created_at);
CREATE INDEX IF NOT EXISTS idx_relationships_attributes_gin ON relationships USING GIN (attributes);
CREATE INDEX IF NOT EXISTS idx_relationships_tags_gin ON relationships USING GIN (tags);

CREATE INDEX IF NOT EXISTS idx_relationships_source_type ON relationships (source_id, type_code);
CREATE INDEX IF NOT EXISTS idx_relationships_target_type ON relationships (target_id, type_code);
CREATE INDEX IF NOT EXISTS idx_relationships_source_target ON relationships (source_id, target_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type_active ON relationships (type_code, is_active);
CREATE INDEX IF NOT EXISTS idx_relationships_active_trait_class ON relationships (is_active, trait_class);

CREATE UNIQUE INDEX IF NOT EXISTS idx_relationships_unique_active
    ON relationships (source_id, target_id, type_code)
    WHERE is_active = TRUE;

CREATE UNIQUE INDEX IF NOT EXISTS idx_nodes_single_root
    ON nodes (id)
    WHERE (attributes->>'is_root') = 'true' AND is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_node_attribute_indexes_node_id ON node_attribute_indexes (node_id);
CREATE INDEX IF NOT EXISTS idx_node_attribute_indexes_key ON node_attribute_indexes (attribute_key);
CREATE INDEX IF NOT EXISTS idx_node_attribute_indexes_value ON node_attribute_indexes (attribute_value);
CREATE INDEX IF NOT EXISTS idx_node_attribute_indexes_key_value ON node_attribute_indexes (attribute_key, attribute_value);
CREATE INDEX IF NOT EXISTS idx_node_attribute_indexes_type ON node_attribute_indexes (attribute_type);

CREATE INDEX IF NOT EXISTS idx_node_tag_indexes_node_id ON node_tag_indexes (node_id);
CREATE INDEX IF NOT EXISTS idx_node_tag_indexes_tag ON node_tag_indexes (tag);
CREATE UNIQUE INDEX IF NOT EXISTS idx_node_tag_indexes_unique ON node_tag_indexes (node_id, tag);

-- ==================================================
-- 第四阶段：触发器函数（属性/标签索引维护）
-- ==================================================

CREATE OR REPLACE FUNCTION update_node_attribute_indexes()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM node_attribute_indexes WHERE node_id = NEW.id;
    IF NEW.attributes IS NOT NULL AND NEW.attributes <> '{}'::jsonb THEN
        INSERT INTO node_attribute_indexes (node_id, attribute_key, attribute_value, attribute_type)
        SELECT
            NEW.id,
            key,
            CASE
                WHEN jsonb_typeof(value) = 'string' THEN trim(both '"' from value::text)
                WHEN jsonb_typeof(value) IN ('number', 'boolean') THEN value::text
                ELSE value::text
            END,
            jsonb_typeof(value)
        FROM jsonb_each(NEW.attributes);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_node_tag_indexes()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM node_tag_indexes WHERE node_id = NEW.id;
    IF NEW.tags IS NOT NULL AND jsonb_array_length(NEW.tags) > 0 THEN
        INSERT INTO node_tag_indexes (node_id, tag)
        SELECT NEW.id, jsonb_array_elements_text(NEW.tags);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sync_node_traits_from_type()
RETURNS TRIGGER AS $$
DECLARE
    nt_trait_class VARCHAR(64);
    nt_trait_mask BIGINT;
BEGIN
    SELECT trait_class, trait_mask
      INTO nt_trait_class, nt_trait_mask
      FROM node_types
     WHERE type_code = NEW.type_code
     LIMIT 1;

    IF nt_trait_class IS NULL THEN
        RAISE EXCEPTION 'node_types.type_code % not found for node trait sync', NEW.type_code;
    END IF;

    NEW.trait_class := nt_trait_class;
    NEW.trait_mask := nt_trait_mask;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sync_relationship_traits_from_type()
RETURNS TRIGGER AS $$
DECLARE
    rt_trait_class VARCHAR(64);
    rt_trait_mask BIGINT;
BEGIN
    SELECT trait_class, trait_mask
      INTO rt_trait_class, rt_trait_mask
      FROM relationship_types
     WHERE type_code = NEW.type_code
     LIMIT 1;

    IF rt_trait_class IS NULL THEN
        RAISE EXCEPTION 'relationship_types.type_code % not found for relationship trait sync', NEW.type_code;
    END IF;

    NEW.trait_class := rt_trait_class;
    NEW.trait_mask := rt_trait_mask;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION enqueue_node_trait_sync_job()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.trait_class IS DISTINCT FROM NEW.trait_class)
       OR (OLD.trait_mask IS DISTINCT FROM NEW.trait_mask) THEN
        INSERT INTO trait_sync_jobs(domain, type_code, reason, payload)
        VALUES (
            'node',
            NEW.type_code,
            'type_trait_changed',
            jsonb_build_object(
                'before_trait_class', OLD.trait_class,
                'after_trait_class', NEW.trait_class,
                'before_trait_mask', OLD.trait_mask,
                'after_trait_mask', NEW.trait_mask
            )
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION enqueue_relationship_trait_sync_job()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.trait_class IS DISTINCT FROM NEW.trait_class)
       OR (OLD.trait_mask IS DISTINCT FROM NEW.trait_mask) THEN
        INSERT INTO trait_sync_jobs(domain, type_code, reason, payload)
        VALUES (
            'relationship',
            NEW.type_code,
            'type_trait_changed',
            jsonb_build_object(
                'before_trait_class', OLD.trait_class,
                'after_trait_class', NEW.trait_class,
                'before_trait_mask', OLD.trait_mask,
                'after_trait_mask', NEW.trait_mask
            )
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_node_attribute_indexes ON nodes;
CREATE TRIGGER trigger_update_node_attribute_indexes
    AFTER INSERT OR UPDATE OF attributes ON nodes
    FOR EACH ROW
    EXECUTE PROCEDURE update_node_attribute_indexes();

DROP TRIGGER IF EXISTS trigger_update_node_tag_indexes ON nodes;
CREATE TRIGGER trigger_update_node_tag_indexes
    AFTER INSERT OR UPDATE OF tags ON nodes
    FOR EACH ROW
    EXECUTE PROCEDURE update_node_tag_indexes();

DROP TRIGGER IF EXISTS trigger_sync_node_traits_from_type ON nodes;
CREATE TRIGGER trigger_sync_node_traits_from_type
    BEFORE INSERT OR UPDATE OF type_code, trait_class, trait_mask ON nodes
    FOR EACH ROW
    EXECUTE PROCEDURE sync_node_traits_from_type();

DROP TRIGGER IF EXISTS trigger_sync_relationship_traits_from_type ON relationships;
CREATE TRIGGER trigger_sync_relationship_traits_from_type
    BEFORE INSERT OR UPDATE OF type_code, trait_class, trait_mask ON relationships
    FOR EACH ROW
    EXECUTE PROCEDURE sync_relationship_traits_from_type();

DROP TRIGGER IF EXISTS trigger_enqueue_node_trait_sync_job ON node_types;
CREATE TRIGGER trigger_enqueue_node_trait_sync_job
    AFTER UPDATE OF trait_class, trait_mask ON node_types
    FOR EACH ROW
    EXECUTE PROCEDURE enqueue_node_trait_sync_job();

DROP TRIGGER IF EXISTS trigger_enqueue_relationship_trait_sync_job ON relationship_types;
CREATE TRIGGER trigger_enqueue_relationship_trait_sync_job
    AFTER UPDATE OF trait_class, trait_mask ON relationship_types
    FOR EACH ROW
    EXECUTE PROCEDURE enqueue_relationship_trait_sync_job();

-- ==================================================
-- 第五阶段：视图
-- ==================================================

DROP VIEW IF EXISTS active_nodes;
CREATE VIEW active_nodes AS
SELECT
    n.id,
    n.uuid,
    n.name,
    n.description,
    n.is_public,
    n.access_level,
    n.location_id,
    n.home_id,
    n.location_geom,
    n.home_geom,
    n.geom_geojson,
    n.ts_data_ref_id,
    nt.type_code,
    nt.type_name,
    nt.classname,
    nt.parent_type_code,
    n.attributes,
    n.tags,
    n.created_at,
    n.updated_at
FROM nodes n
JOIN node_types nt ON n.type_id = nt.id
WHERE n.is_active = TRUE AND nt.status = 0;

DROP VIEW IF EXISTS active_relationships;
CREATE VIEW active_relationships AS
SELECT
    r.id,
    r.uuid,
    r.source_id,
    r.target_id,
    r.weight,
    r.source_role,
    r.target_role,
    rt.type_code,
    rt.type_name,
    rt.is_directed,
    rt.is_symmetric,
    r.attributes,
    r.tags,
    r.created_at,
    r.updated_at
FROM relationships r
JOIN relationship_types rt ON r.type_id = rt.id
WHERE r.is_active = TRUE AND rt.status = 0;

-- ==================================================
-- 第六阶段：初始数据（无父类型先行插入）
-- ==================================================

INSERT INTO node_types (
    type_code, parent_type_code, type_name, typeclass, status, classname, module_path, description,
    schema_definition, schema_default, inferred_rules, tags, ui_config, trait_class, trait_mask
) VALUES
('user', NULL, '用户', 'app.models.user.User', 0, 'User', 'app.models.user', '系统用户',
 '{}', '{}', '{}', '[]', '{}', 'PERSON', 0),
('campus', NULL, '园区', 'app.models.campus.Campus', 0, 'Campus', 'app.models.campus', '校园实体',
 '{}', '{}', '{}', '[]', '{}', 'SPACE', 0),
('world', NULL, '世界', 'app.models.world.World', 0, 'World', 'app.models.world', '场景世界',
 '{}', '{}', '{}', '[]', '{}', 'SPACE', 0),
('world_object', NULL, '世界对象', 'app.models.world.WorldObject', 0, 'WorldObject', 'app.models.world', '世界中的对象',
 '{}', '{}', '{}', '[]', '{}', 'ITEM', 0)
ON CONFLICT (type_code) DO NOTHING;

INSERT INTO relationship_types (
    type_code, type_name, typeclass, status, description,
    constraints, schema_definition, inferred_rules, tags, ui_config,
    is_directed, is_symmetric, is_transitive, trait_class, trait_mask
) VALUES
('member', '成员关系', 'app.models.relationships.MemberRelationship', 0, '用户与校园/世界的成员关系',
 '{}', '{}', '{}', '[]', '{}', TRUE, FALSE, FALSE, 'PROCESS', 0),
('friend', '朋友关系', 'app.models.relationships.FriendRelationship', 0, '用户间的朋友关系',
 '{}', '{}', '{}', '[]', '{}', FALSE, TRUE, FALSE, 'EVENT', 0),
('owns', '拥有关系', 'app.models.relationships.OwnershipRelationship', 0, '所有权关系',
 '{}', '{}', '{}', '[]', '{}', TRUE, FALSE, FALSE, 'RULE', 0),
('location', '位置关系', 'app.models.relationships.LocationRelationship', 0, '位置关系',
 '{}', '{}', '{}', '[]', '{}', TRUE, FALSE, FALSE, 'SPACE', 0)
ON CONFLICT (type_code) DO NOTHING;

-- ==================================================
-- 注释（供 DBA / 配置 UI 生成器阅读）
-- ==================================================

COMMENT ON TABLE node_types IS '节点类型本体：层级(parent_type_code)、默认结构(schema_default)、推理约束(inferred_rules)、管理端 ui_config(JSON)';
COMMENT ON COLUMN node_types.schema_default IS '新建该类型节点时合并到 attributes 的默认键值（Evennia 类默认属性）';
COMMENT ON COLUMN node_types.inferred_rules IS '可选：JSON 规则，如下游校验、必填字段、关系基数（Palantir 类 ontology constraints 的轻量版）';
COMMENT ON COLUMN node_types.ui_config IS '管理端表单：如 {"fields":[{"key":"name","widget":"text"}],"layout":"tabs"}';

COMMENT ON COLUMN nodes.location_geom IS 'PostGIS geometry, SRID 4326；点/线/面均可';
COMMENT ON COLUMN nodes.geom_geojson IS 'RFC 7946 GeoJSON 缓存；与 location_geom 应在应用层保持一致';
COMMENT ON COLUMN nodes.semantic_embedding IS '文本/多模态语义向量（pgvector）';
COMMENT ON COLUMN nodes.structure_embedding IS '图结构/拓扑 embedding（维度可随模型调整）';
COMMENT ON COLUMN nodes.ts_data_ref_id IS '可选：关联时序数据（TimescaleDB hypertable 或外部 series UUID）';

COMMENT ON TABLE relationships IS '图边；source_role/target_role 可用于本体角色（Palantir link roles）';

-- ==================================================
-- 可选：TimescaleDB（需单独安装 TimescaleDB 扩展）
-- ==================================================
-- CREATE EXTENSION IF NOT EXISTS timescaledb;
-- CREATE TABLE IF NOT EXISTS node_time_series (
--     time TIMESTAMPTZ NOT NULL,
--     series_id UUID NOT NULL,
--     node_id INTEGER REFERENCES nodes(id) ON DELETE CASCADE,
--     metric TEXT NOT NULL,
--     value DOUBLE PRECISION,
--     labels JSONB NOT NULL DEFAULT '{}'
-- );
-- SELECT create_hypertable('node_time_series', 'time', if_not_exists => TRUE);
-- 然后在 nodes.ts_data_ref_id 中存 series_id 或与 hypertable 主键对齐。

SELECT 'Tables created successfully' AS status;
