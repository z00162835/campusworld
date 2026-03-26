# CampusWorld 数据库Schema工具

## 当前图模式设计（Evennia + Palantir 类实践）

`database_schema.sql` 实现以下能力，并与 `app.models.graph` 对齐：

| 能力 | 说明 |
|------|------|
| **类型层级** | `node_types.parent_type_code` 自引用，插入子类型前须先有父类型 `type_code`。 |
| **本体默认 / 推理** | `schema_default`（新建节点默认属性）、`inferred_rules`（轻量规则 JSON）、`relationship_types.constraints`（端点类型等）。 |
| **配置 UI** | `ui_config`：管理端表单布局/控件描述（JSON），由前端按约定渲染。 |
| **向量** | `nodes.semantic_embedding` / `structure_embedding`（pgvector `vector`）；ANN 索引请在有数据后按需 `CREATE INDEX`（文件内已注释示例）。 |
| **GIS + GeoJSON** | `location_geom` / `home_geom`（PostGIS，SRID 4326）+ `geom_geojson`（API 互换；应用层负责与 geometry 一致）。 |
| **时序** | `ts_data_ref_id` 可选 UUID；TimescaleDB hypertable 示例见 SQL 文件末尾注释块。 |

**数据库依赖**：PostgreSQL 需安装扩展 `uuid-ossp`、`vector`、`postgis`、`pg_trgm`。Docker 镜像需基于带 PostGIS/pgvector 的发行版（或自行安装）。**TimescaleDB 为可选**，未安装时不要执行文件末尾注释中的 `timescaledb` 语句。

**触发器语法**：若 `EXECUTE PROCEDURE` 报错，可改为 PostgreSQL 14+ 的 `EXECUTE FUNCTION`（视实例版本而定）。

## 📋 问题分析

原始数据库schema执行失败的主要原因：

### 1. **SQL语句分割问题**
- 使用简单的`;`分割SQL语句
- PostgreSQL函数定义包含多个分号，被错误分割
- 导致语法错误和函数定义不完整

### 2. **执行顺序错误**
- 在创建表之前就尝试添加外键约束
- 在创建表之前就尝试创建索引
- 在创建表之前就尝试创建视图

### 3. **事务处理问题**
- 第一个错误导致事务失败
- 后续所有操作都被忽略
- 缺乏错误恢复机制

### 4. **文件路径问题**
- 迁移脚本在`db/schemas/`目录下
- SQL文件路径不正确
- 相对路径引用问题

## 🚀 修复方案

### 1. **修复后的SQL文件** (`database_schema_fixed.sql`)
- **正确的执行顺序**：表 → 约束 → 索引 → 函数 → 触发器 → 视图 → 数据
- **事务安全处理**：使用`IF NOT EXISTS`避免重复创建
- **依赖关系管理**：确保所有依赖项按正确顺序创建
- **完整的函数定义**：避免函数定义被错误分割

### 2. **修复后的迁移脚本** (`database_migration_fixed.py`)
- **智能SQL分割**：识别函数、触发器、视图定义
- **错误恢复机制**：检测关键错误时回滚事务
- **详细的执行日志**：显示每个SQL语句的执行状态
- **完整的验证流程**：验证表、视图、函数是否创建成功

### 3. **直接执行脚本** (`run_schema_direct.py`)
- **简化执行流程**：直接执行SQL文件，避免复杂迁移逻辑
- **智能语句分割**：正确处理PostgreSQL语法结构
- **实时执行反馈**：显示每个语句的执行结果
- **自动验证结果**：执行完成后自动验证数据库结构

## 🛠️ 使用方法

### 方法1：使用直接执行脚本（推荐）

```bash
# 进入schemas目录
cd campusworld/backend/db/schemas

# 执行修复后的SQL文件
python run_schema_direct.py
```

### 方法2：使用修复后的迁移脚本

```bash
# 进入schemas目录
cd campusworld/backend/db/schemas

# 执行修复后的迁移脚本
python database_migration_fixed.py
```

### 方法3：直接执行SQL文件

```bash
# 使用psql直接执行
psql -h localhost -p 5433 -U campusworld_dev_user -d campusworld_dev -f database_schema_fixed.sql
```

## 📊 执行流程

### 第一阶段：创建基础表结构
1. `node_types` - 节点类型定义表
2. `relationship_types` - 关系类型定义表
3. `nodes` - 节点实例表（核心表）
4. `relationships` - 关系实例表
5. `node_attribute_indexes` - 节点属性索引表
6. `node_tag_indexes` - 节点标签索引表

### 第二阶段：添加外键约束
- 确保表间关系的完整性
- 支持级联删除操作

### 第三阶段：创建索引
- B-tree索引：主键、外键、常用查询字段
- GIN索引：JSONB字段、数组字段
- 复合索引：多字段组合查询优化
- 全文搜索索引：支持模糊查询

### 第四阶段：创建函数
- `update_node_attribute_indexes()` - 自动维护属性索引
- `update_node_tag_indexes()` - 自动维护标签索引

### 第五阶段：创建触发器
- 节点属性变化时自动更新索引
- 节点标签变化时自动更新索引

### 第六阶段：创建视图
- `active_nodes` - 活跃节点视图
- `active_relationships` - 活跃关系视图

### 第七阶段：插入初始数据
- 预定义节点类型（user, campus, world, world_object）
- 预定义关系类型（member, friend, owns, location）

### 第八阶段：添加表注释
- 为所有表添加中文注释
- 便于理解和维护

## 🔍 验证步骤

执行完成后，脚本会自动验证：

### 1. **表结构验证**
```sql
-- 检查表是否存在
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('node_types', 'relationship_types', 'nodes', 'relationships', 'node_attribute_indexes', 'node_tag_indexes');
```

### 2. **视图验证**
```sql
-- 检查视图是否存在
SELECT viewname FROM pg_views 
WHERE viewname IN ('active_nodes', 'active_relationships');
```

### 3. **函数验证**
```sql
-- 检查函数是否存在
SELECT routine_name FROM information_schema.routines 
WHERE routine_name IN ('update_node_attribute_indexes', 'update_node_tag_indexes');
```

### 4. **索引验证**
```sql
-- 检查索引是否创建
SELECT indexname FROM pg_indexes 
WHERE tablename IN ('nodes', 'relationships');
```

## ⚠️ 注意事项

### 1. **数据库连接**
- 确保PostgreSQL服务正在运行
- 检查连接参数（主机、端口、用户名、密码、数据库名）
- 确保用户有足够的权限创建表、函数、触发器

### 2. **扩展支持**
- 确保`uuid-ossp`扩展可用
- 确保`pg_trgm`扩展可用（用于全文搜索）

### 3. **事务处理**
- 脚本使用自动提交模式
- 每个SQL语句独立执行
- 失败时不会影响已成功的操作

### 4. **错误处理**
- 忽略"已存在"的错误
- 记录其他错误的详细信息
- 提供执行统计信息

## 🐛 故障排除

### 1. **连接失败**
```bash
# 检查PostgreSQL服务状态
docker ps | grep postgres

# 检查端口是否开放
netstat -an | grep 5433
```

### 2. **权限不足**
```sql
-- 检查用户权限
SELECT usename, usesuper, usecreatedb FROM pg_user WHERE usename = 'campusworld_dev_user';

-- 授予必要权限
GRANT ALL PRIVILEGES ON DATABASE campusworld_dev TO campusworld_dev_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO campusworld_dev_user;
```

### 3. **扩展不可用**
```sql
-- 检查扩展状态
SELECT * FROM pg_extension WHERE extname IN ('uuid-ossp', 'pg_trgm');

-- 安装扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
```

### 4. **表已存在**
- 脚本会自动跳过已存在的对象
- 如需重新创建，先删除现有对象：
```sql
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
```

## 📈 性能优化

### 1. **索引策略**
- 为常用查询字段创建B-tree索引
- 为JSONB字段创建GIN索引
- 为全文搜索创建trigram索引

### 2. **分区策略**
- 考虑按时间或类型对大型表进行分区
- 提高查询和维护性能

### 3. **统计信息**
- 定期更新表统计信息
- 优化查询计划

## 🔄 后续维护

### 1. **定期备份**
```bash
pg_dump -h localhost -p 5433 -U campusworld_dev_user -d campusworld_dev > backup_$(date +%Y%m%d).sql
```

### 2. **性能监控**
```sql
-- 检查慢查询
SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;

-- 检查索引使用情况
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch 
FROM pg_stat_user_indexes ORDER BY idx_scan DESC;
```

### 3. **数据清理**
```sql
-- 清理无效数据
DELETE FROM nodes WHERE is_active = FALSE AND updated_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
DELETE FROM relationships WHERE is_active = FALSE AND updated_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
```

## 📞 技术支持

如果遇到问题，请：

1. 检查错误日志和输出信息
2. 验证数据库连接和权限
3. 确认PostgreSQL版本和扩展支持
4. 查看本文档的故障排除部分

---

**作者**: AI Assistant  
**创建时间**: 2025-08-24  
**版本**: 修复版 v1.0
