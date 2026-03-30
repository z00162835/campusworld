# TODO - 数据库开发任务

## Schema 扩展

### 高优先级

- [ ] **索引优化**
  - graph_nodes(type_code) 索引
  - graph_edges(source_id, target_id) 复合索引
  - node_types(type_code) 唯一索引

- [ ] **种子数据完善**
  - 预定义空间（library/campus/canteen/dormitory）
  - 默认角色定义
  - 初始管理员账户

- [ ] **Schema 迁移**
  - Alembic 集成
  - 迁移版本管理
  - 回滚支持

### 中优先级

- [ ] **数据库健康检查**
  - 连接测试
  - 表存在检查
  - 索引检查

- [ ] **备份恢复**
  - 数据库备份脚本
  - 数据恢复脚本

### 低优先级

- [ ] **数据库集群支持**: 主从复制
- [ ] **向量搜索支持**: pgvector 扩展（用于语义搜索）

## 验收检查清单

- [ ] `init_database.py` 成功创建所有表
- [ ] `seed_data.py` 填充初始数据
- [ ] `verify_schema.py` 验证通过
- [ ] GraphNode/GraphEdge 表正常工作