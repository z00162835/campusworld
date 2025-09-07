-- ==================================================
-- CampusWorld 纯图数据设计 - 修复版数据库建表语句
-- ==================================================
-- 
-- 修复问题：
-- 1. 正确的SQL执行顺序
-- 2. 完整的函数定义
-- 3. 事务安全处理
-- 4. 依赖关系管理
--
-- 作者：AI Assistant
-- 修复时间：2025-08-24
-- ==================================================

-- 启用必要的扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- 支持模糊搜索

-- ==================================================
-- 第一阶段：创建基础表结构
-- ==================================================

-- 1. 节点类型定义表
CREATE TABLE IF NOT EXISTS node_types (
    id SERIAL PRIMARY KEY,
    type_code VARCHAR(100) UNIQUE NOT NULL,
    type_name VARCHAR(255) NOT NULL,
    typeclass VARCHAR(500) NOT NULL,
    classname VARCHAR(100) NOT NULL,
    module_path VARCHAR(300) NOT NULL,
    description TEXT,
    schema_definition JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. 关系类型定义表
CREATE TABLE IF NOT EXISTS relationship_types (
    id SERIAL PRIMARY KEY,
    type_code VARCHAR(100) UNIQUE NOT NULL,
    type_name VARCHAR(255) NOT NULL,
    typeclass VARCHAR(500) NOT NULL,
    description TEXT,
    schema_definition JSONB DEFAULT '{}',
    is_directed BOOLEAN DEFAULT TRUE,
    is_symmetric BOOLEAN DEFAULT FALSE,
    is_transitive BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. 节点实例表（核心表）
CREATE TABLE IF NOT EXISTS nodes (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
    type_id INTEGER NOT NULL,
    type_code VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_public BOOLEAN DEFAULT TRUE,
    access_level VARCHAR(50) DEFAULT 'normal',
    location_id INTEGER,
    home_id INTEGER,
    attributes JSONB DEFAULT '{}',
    tags JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. 关系实例表
CREATE TABLE IF NOT EXISTS relationships (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
    type_id INTEGER NOT NULL,
    type_code VARCHAR(100) NOT NULL,
    source_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    weight INTEGER DEFAULT 1,
    attributes JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. 节点属性索引表
CREATE TABLE IF NOT EXISTS node_attribute_indexes (
    id SERIAL PRIMARY KEY,
    node_id INTEGER NOT NULL,
    attribute_key VARCHAR(255) NOT NULL,
    attribute_value TEXT,
    attribute_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. 节点标签索引表
CREATE TABLE IF NOT EXISTS node_tag_indexes (
    id SERIAL PRIMARY KEY,
    node_id INTEGER NOT NULL,
    tag VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==================================================
-- 第二阶段：添加外键约束
-- ==================================================

-- 添加外键约束
ALTER TABLE nodes 
ADD CONSTRAINT fk_nodes_type_id 
FOREIGN KEY (type_id) REFERENCES node_types(id);

ALTER TABLE nodes 
ADD CONSTRAINT fk_nodes_location_id 
FOREIGN KEY (location_id) REFERENCES nodes(id);

ALTER TABLE nodes 
ADD CONSTRAINT fk_nodes_home_id 
FOREIGN KEY (home_id) REFERENCES nodes(id);

ALTER TABLE relationships 
ADD CONSTRAINT fk_relationships_type_id 
FOREIGN KEY (type_id) REFERENCES relationship_types(id);

ALTER TABLE relationships 
ADD CONSTRAINT fk_relationships_source_id 
FOREIGN KEY (source_id) REFERENCES nodes(id);

ALTER TABLE relationships 
ADD CONSTRAINT fk_relationships_target_id 
FOREIGN KEY (target_id) REFERENCES nodes(id);

ALTER TABLE node_attribute_indexes 
ADD CONSTRAINT fk_node_attribute_indexes_node_id 
FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE;

ALTER TABLE node_tag_indexes 
ADD CONSTRAINT fk_node_tag_indexes_node_id 
FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE;

-- ==================================================
-- 第三阶段：创建索引
-- ==================================================

-- 节点类型索引
CREATE INDEX IF NOT EXISTS idx_node_types_code ON node_types(type_code);
CREATE INDEX IF NOT EXISTS idx_node_types_classname ON node_types(classname);
CREATE INDEX IF NOT EXISTS idx_node_types_active ON node_types(is_active);

-- 关系类型索引
CREATE INDEX IF NOT EXISTS idx_relationship_types_code ON relationship_types(type_code);
CREATE INDEX IF NOT EXISTS idx_relationship_types_active ON relationship_types(is_active);

-- 节点表索引
CREATE INDEX IF NOT EXISTS idx_nodes_uuid ON nodes(uuid);
CREATE INDEX IF NOT EXISTS idx_nodes_type_id ON nodes(type_id);
CREATE INDEX IF NOT EXISTS idx_nodes_type_code ON nodes(type_code);
CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
CREATE INDEX IF NOT EXISTS idx_nodes_active ON nodes(is_active);
CREATE INDEX IF NOT EXISTS idx_nodes_public ON nodes(is_public);
CREATE INDEX IF NOT EXISTS idx_nodes_access_level ON nodes(access_level);
CREATE INDEX IF NOT EXISTS idx_nodes_location_id ON nodes(location_id);
CREATE INDEX IF NOT EXISTS idx_nodes_home_id ON nodes(home_id);
CREATE INDEX IF NOT EXISTS idx_nodes_created_at ON nodes(created_at);
CREATE INDEX IF NOT EXISTS idx_nodes_updated_at ON nodes(updated_at);

-- JSONB字段GIN索引
CREATE INDEX IF NOT EXISTS idx_nodes_attributes_gin ON nodes USING GIN (attributes);
CREATE INDEX IF NOT EXISTS idx_nodes_tags_gin ON nodes USING GIN (tags);

-- 复合索引
CREATE INDEX IF NOT EXISTS idx_nodes_type_active ON nodes(type_code, is_active);
CREATE INDEX IF NOT EXISTS idx_nodes_type_public ON nodes(type_code, is_public);
CREATE INDEX IF NOT EXISTS idx_nodes_location_active ON nodes(location_id, is_active);

-- 全文搜索索引
CREATE INDEX IF NOT EXISTS idx_nodes_name_trgm ON nodes USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_nodes_description_trgm ON nodes USING GIN (description gin_trgm_ops);

-- 关系表索引
CREATE INDEX IF NOT EXISTS idx_relationships_uuid ON relationships(uuid);
CREATE INDEX IF NOT EXISTS idx_relationships_type_id ON relationships(type_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type_code ON relationships(type_code);
CREATE INDEX IF NOT EXISTS idx_relationships_source_id ON relationships(source_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target_id ON relationships(target_id);
CREATE INDEX IF NOT EXISTS idx_relationships_active ON relationships(is_active);
CREATE INDEX IF NOT EXISTS idx_relationships_weight ON relationships(weight);
CREATE INDEX IF NOT EXISTS idx_relationships_created_at ON relationships(created_at);

-- JSONB字段GIN索引
CREATE INDEX IF NOT EXISTS idx_relationships_attributes_gin ON relationships USING GIN (attributes);

-- 复合索引
CREATE INDEX IF NOT EXISTS idx_relationships_source_type ON relationships(source_id, type_code);
CREATE INDEX IF NOT EXISTS idx_relationships_target_type ON relationships(target_id, type_code);
CREATE INDEX IF NOT EXISTS idx_relationships_source_target ON relationships(source_id, target_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type_active ON relationships(type_code, is_active);

-- 唯一约束
CREATE UNIQUE INDEX IF NOT EXISTS idx_relationships_unique 
ON relationships(source_id, target_id, type_code) 
WHERE is_active = TRUE;

-- 根节点唯一约束 - 确保只有一个根节点
CREATE UNIQUE INDEX IF NOT EXISTS idx_nodes_single_root 
ON nodes(id) 
WHERE attributes->>'is_root' = 'true' AND is_active = TRUE;

-- 属性索引表索引
CREATE INDEX IF NOT EXISTS idx_node_attribute_indexes_node_id ON node_attribute_indexes(node_id);
CREATE INDEX IF NOT EXISTS idx_node_attribute_indexes_key ON node_attribute_indexes(attribute_key);
CREATE INDEX IF NOT EXISTS idx_node_attribute_indexes_value ON node_attribute_indexes(attribute_value);
CREATE INDEX IF NOT EXISTS idx_node_attribute_indexes_key_value ON node_attribute_indexes(attribute_key, attribute_value);
CREATE INDEX IF NOT EXISTS idx_node_attribute_indexes_type ON node_attribute_indexes(attribute_type);

-- 标签索引表索引
CREATE INDEX IF NOT EXISTS idx_node_tag_indexes_node_id ON node_tag_indexes(node_id);
CREATE INDEX IF NOT EXISTS idx_node_tag_indexes_tag ON node_tag_indexes(tag);
CREATE UNIQUE INDEX IF NOT EXISTS idx_node_tag_indexes_unique ON node_tag_indexes(node_id, tag);

-- ==================================================
-- 第四阶段：创建函数
-- ==================================================

-- 自动更新属性索引的函数
CREATE OR REPLACE FUNCTION update_node_attribute_indexes()
RETURNS TRIGGER AS $$
BEGIN
    -- 删除旧的属性索引
    DELETE FROM node_attribute_indexes WHERE node_id = NEW.id;
    
    -- 插入新的属性索引
    IF NEW.attributes IS NOT NULL THEN
        INSERT INTO node_attribute_indexes (node_id, attribute_key, attribute_value, attribute_type)
        SELECT 
            NEW.id,
            key,
            CASE 
                WHEN jsonb_typeof(value) = 'string' THEN value::text
                WHEN jsonb_typeof(value) = 'number' THEN value::text
                WHEN jsonb_typeof(value) = 'boolean' THEN value::text
                ELSE value::text
            END,
            jsonb_typeof(value)
        FROM jsonb_each(NEW.attributes);
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 自动更新标签索引的函数
CREATE OR REPLACE FUNCTION update_node_tag_indexes()
RETURNS TRIGGER AS $$
BEGIN
    -- 删除旧的标签索引
    DELETE FROM node_tag_indexes WHERE node_id = NEW.id;
    
    -- 插入新的标签索引
    IF NEW.tags IS NOT NULL AND jsonb_array_length(NEW.tags) > 0 THEN
        INSERT INTO node_tag_indexes (node_id, tag)
        SELECT NEW.id, jsonb_array_elements_text(NEW.tags);
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ==================================================
-- 第五阶段：创建触发器
-- ==================================================

-- 节点属性变化时自动更新索引
DROP TRIGGER IF EXISTS trigger_update_node_attribute_indexes ON nodes;
CREATE TRIGGER trigger_update_node_attribute_indexes
    AFTER INSERT OR UPDATE ON nodes
    FOR EACH ROW
    EXECUTE FUNCTION update_node_attribute_indexes();

-- 节点标签变化时自动更新索引
DROP TRIGGER IF EXISTS trigger_update_node_tag_indexes ON nodes;
CREATE TRIGGER trigger_update_node_tag_indexes
    AFTER INSERT OR UPDATE ON nodes
    FOR EACH ROW
    EXECUTE FUNCTION update_node_tag_indexes();

-- ==================================================
-- 第六阶段：创建视图
-- ==================================================

-- 活跃节点视图
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
    nt.type_code,
    nt.type_name,
    nt.classname,
    n.attributes,
    n.tags,
    n.created_at,
    n.updated_at
FROM nodes n
JOIN node_types nt ON n.type_id = nt.id
WHERE n.is_active = TRUE;

-- 活跃关系视图
DROP VIEW IF EXISTS active_relationships;
CREATE VIEW active_relationships AS
SELECT 
    r.id,
    r.uuid,
    r.source_id,
    r.target_id,
    r.weight,
    rt.type_code,
    rt.type_name,
    rt.is_directed,
    rt.is_symmetric,
    r.attributes,
    r.created_at,
    r.updated_at
FROM relationships r
JOIN relationship_types rt ON r.type_id = rt.id
WHERE r.is_active = TRUE;

-- ==================================================
-- 第七阶段：插入初始数据
-- ==================================================

-- 插入节点类型
INSERT INTO node_types (type_code, type_name, typeclass, classname, module_path, description) VALUES
('user', '用户', 'app.models.user.User', 'User', 'app.models.user', '系统用户'),
('campus', '校园', 'app.models.campus.Campus', 'Campus', 'app.models.campus', '校园实体'),
('world', '世界', 'app.models.world.World', 'World', 'app.models.world', '游戏世界'),
('world_object', '世界对象', 'app.models.world.WorldObject', 'WorldObject', 'app.models.world', '世界中的对象')
ON CONFLICT (type_code) DO NOTHING;

-- 插入关系类型
INSERT INTO relationship_types (type_code, type_name, typeclass, description, is_directed, is_symmetric) VALUES
('member', '成员关系', 'app.models.relationships.MemberRelationship', '用户与校园/世界的成员关系', TRUE, FALSE),
('friend', '朋友关系', 'app.models.relationships.FriendRelationship', '用户间的朋友关系', FALSE, TRUE),
('owns', '拥有关系', 'app.models.relationships.OwnershipRelationship', '所有权关系', TRUE, FALSE),
('location', '位置关系', 'app.models.relationships.LocationRelationship', '位置关系', TRUE, FALSE)
ON CONFLICT (type_code) DO NOTHING;

-- ==================================================
-- 第八阶段：添加表注释
-- ==================================================

COMMENT ON TABLE nodes IS '图节点实例表 - 存储所有对象实例';
COMMENT ON TABLE relationships IS '图关系实例表 - 存储节点间关系';
COMMENT ON TABLE node_types IS '节点类型定义表 - 定义可用的节点类型';
COMMENT ON TABLE relationship_types IS '关系类型定义表 - 定义可用的关系类型';
COMMENT ON TABLE node_attribute_indexes IS '节点属性索引表 - 优化属性查询性能';
COMMENT ON TABLE node_tag_indexes IS '节点标签索引表 - 优化标签查询性能';

-- ==================================================
-- 建表完成！
-- ==================================================

-- 验证表创建
SELECT 'Tables created successfully' as status;
