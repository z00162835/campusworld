# CampusWorld 数据库优化工具说明

## 📋 概述

本文档介绍了基于当前纯图数据设计的PostgreSQL数据库优化方案，包括优化的数据库结构、迁移工具和性能测试工具。

## 🏗️ 优化数据库结构设计

### 设计理念

1. **分层设计**: 类型定义表 + 实例表，提高查询效率
2. **查询优化**: 常用字段单独存储，JSONB属性建立GIN索引
3. **性能优化**: 合理的索引策略，支持高效图查询
4. **扩展性**: 支持动态属性和标签系统

### 核心表结构

#### 1. 节点类型定义表 (`node_types`)
- 定义可用的节点类型（user, campus, world, world_object）
- 存储类型元数据和模式定义
- 支持类型扩展和配置

#### 2. 关系类型定义表 (`relationship_types`)
- 定义可用的关系类型（member, friend, owns, location）
- 支持有向/无向、对称/非对称关系配置
- 存储关系模式定义

#### 3. 节点实例表 (`nodes`) - 核心表
- 存储所有对象实例
- 常用字段单独存储（name, description, is_active等）
- JSONB字段存储动态属性
- 支持位置关系和标签系统

#### 4. 关系实例表 (`relationships`)
- 存储节点间的关系
- 支持关系权重和动态属性
- 防止重复关系的唯一约束

#### 5. 索引优化表
- `node_attribute_indexes`: 优化特定属性查询
- `node_tag_indexes`: 优化标签查询

### 索引策略

#### 基础索引
- UUID、类型、名称等常用字段的B-tree索引
- 复合索引优化复杂查询条件

#### JSONB索引
- GIN索引支持高效属性查询
- 支持包含、路径等JSON操作

#### 全文搜索索引
- 支持名称和描述的模糊搜索
- 使用pg_trgm扩展

## 🚀 使用方法

### 1. 创建优化数据库结构

```bash
# 方法1: 直接执行SQL文件
psql -h localhost -p 5433 -U campusworld -d campusworld -f database_schema_optimized.sql

# 方法2: 使用Python迁移工具
python database_migration.py
```

### 2. 运行数据库迁移

```bash
# 设置环境变量（可选）
export DATABASE_URL="postgresql://campusworld:campusworld@localhost:5433/campusworld"

# 运行迁移
python database_migration.py
```

### 3. 性能测试

```bash
# 运行完整性能测试
python database_performance_test.py

# 自定义测试参数
python -c "
from database_performance_test import DatabasePerformanceTester
tester = DatabasePerformanceTester('postgresql://...')
tester.generate_test_data(5000, 25000)  # 5000节点，25000关系
tester.test_basic_queries()
"
```

## 📊 性能优化特性

### 1. 查询优化
- **类型查询**: 通过type_code字段快速过滤
- **属性查询**: JSONB GIN索引支持高效属性搜索
- **标签查询**: 专门的标签索引表
- **复合查询**: 多字段复合索引优化

### 2. 图查询优化
- **关系查询**: 优化的JOIN查询
- **路径查询**: 支持多跳路径查询
- **聚合查询**: 高效的GROUP BY操作

### 3. 并发性能
- **连接池**: 支持高并发访问
- **索引优化**: 减少锁竞争
- **批量操作**: 支持批量插入和更新

## 🔧 配置说明

### 数据库连接配置

```python
# 默认配置
DATABASE_URL = "postgresql://campusworld:campusworld@localhost:5433/campusworld"

# 环境变量覆盖
export DATABASE_URL="postgresql://user:password@host:port/database"
```

### 性能测试配置

```python
# 测试数据规模
node_count = 1000        # 节点数量
relationship_count = 5000 # 关系数量

# 并发测试参数
concurrent_users = 10    # 并发用户数
queries_per_user = 100   # 每个用户的查询数
```

## 📈 性能基准

### 查询性能目标
- **简单查询**: < 1ms
- **类型查询**: < 5ms
- **属性查询**: < 10ms
- **复合查询**: < 20ms
- **图查询**: < 50ms

### 并发性能目标
- **查询吞吐量**: > 1000 QPS
- **响应时间**: < 100ms (95%分位)
- **并发用户**: > 100

## 🛠️ 维护和监控

### 定期维护
```sql
-- 更新统计信息
ANALYZE nodes;
ANALYZE relationships;
ANALYZE node_attribute_indexes;
ANALYZE node_tag_indexes;

-- 清理无效数据
DELETE FROM nodes WHERE is_active = FALSE AND updated_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
DELETE FROM relationships WHERE is_active = FALSE AND updated_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
```

### 性能监控
```sql
-- 查看慢查询
SELECT query, mean_time, calls, total_time
FROM pg_stat_statements
WHERE mean_time > 100
ORDER BY mean_time DESC;

-- 查看索引使用情况
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

## 🔍 故障排除

### 常见问题

#### 1. 连接失败
```bash
# 检查PostgreSQL服务状态
docker ps | grep postgres

# 检查端口映射
docker port campusworld-postgres-1
```

#### 2. 权限问题
```sql
-- 创建用户并授权
CREATE USER campusworld_app WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE campusworld TO campusworld_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO campusworld_app;
```

#### 3. 性能问题
```sql
-- 检查查询计划
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM nodes WHERE type_code = 'user';

-- 检查索引使用
SELECT * FROM pg_stat_user_indexes WHERE tablename = 'nodes';
```

## 📚 相关文档

- `database_schema_optimized.sql` - 优化的数据库建表语句
- `database_migration.py` - 数据库迁移工具
- `database_performance_test.py` - 性能测试工具
- `PURE_GRAPH_REFACTORING_COMPLETED.md` - 纯图数据设计重构完成总结

## 🎯 下一步计划

1. **API接口开发**: 基于新数据库结构开发RESTful API
2. **前端界面**: 实现图数据可视化管理界面
3. **性能调优**: 根据实际使用情况优化数据库配置
4. **监控系统**: 建立完整的性能监控和告警系统

## 📞 技术支持

如果在使用过程中遇到问题，请：

1. 检查本文档的故障排除部分
2. 查看错误日志和性能测试结果
3. 参考PostgreSQL官方文档
4. 联系开发团队获取支持

---

**注意**: 在生产环境使用前，请务必在测试环境充分验证数据库结构的性能和稳定性。
