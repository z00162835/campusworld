# CampusWorld 图数据结构系统

## 概述

CampusWorld 图数据结构系统是一个基于 PostgreSQL 的图数据库实现，参考 Evennia 系统的存储设计，为项目对象提供持久化存储和图结构操作能力。

## 核心特性

### 1. 图节点系统
- **Node**: 所有持久化对象的基础类型
- **GraphNode**: 实现图结构功能的节点类型
- **自动同步**: DefaultObject 与图节点系统的自动同步

### 2. 关系系统
- **Relationship**: 节点间关系的基础类型
- **属性存储**: 使用 JSONB 字段存储关系属性
- **类型安全**: 支持关系类型和属性验证

### 3. 元数据管理
- **classpath**: 存储类的完整路径作为元数据
- **类型信息**: 自动记录类名和模块路径
- **版本控制**: 支持对象版本和变更追踪

## 架构设计

### 核心类层次

```
Node (抽象基类)
├── GraphNode (图节点实现)
├── GraphDefaultObject (图节点版本的DefaultObject)
└── GraphDefaultAccount (图节点版本的DefaultAccount)

Relationship (关系类型)
├── 基础关系属性
├── 关系类型分类
└── 关系权重和状态
```

### 数据存储结构

#### 节点表 (nodes)
```sql
CREATE TABLE nodes (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) UNIQUE NOT NULL,
    classpath VARCHAR(500) NOT NULL,
    classname VARCHAR(100) NOT NULL,
    module_path VARCHAR(300) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    attributes JSONB DEFAULT '{}',
    tags JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    is_public BOOLEAN DEFAULT TRUE,
    access_level VARCHAR(50) DEFAULT 'normal',
    location_id INTEGER REFERENCES nodes(id),
    home_id INTEGER REFERENCES nodes(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 关系表 (relationships)
```sql
CREATE TABLE relationships (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) UNIQUE NOT NULL,
    type VARCHAR(100) NOT NULL,
    classpath VARCHAR(500) NOT NULL,
    source_id INTEGER NOT NULL REFERENCES nodes(id),
    target_id INTEGER NOT NULL REFERENCES nodes(id),
    attributes JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    weight INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(source_id, target_id, type)
);
```

## 使用方法

### 1. 创建图节点对象

```python
from app.models.graph import GraphDefaultObject

class PlayerObject(GraphDefaultObject):
    __tablename__ = "player_objects"
    
    def __init__(self, name: str, level: int = 1, **kwargs):
        super().__init__(name=name, **kwargs)
        self.level = level
        self.set_attribute("level", level)

# 自动同步到图节点系统
player = PlayerObject("英雄", level=5)
```

### 2. 创建和管理关系

```python
from app.models.graph_manager import get_graph_manager

graph_manager = get_graph_manager()

# 创建关系
relationship = graph_manager.create_relationship(
    source=player1,
    target=player2,
    rel_type="friend",
    friendship_level="close",
    met_at=time.time()
)

# 查询关系
friends = graph_manager.get_neighbors(player1, rel_type="friend")
```

### 3. 图遍历和查询

```python
# 获取路径
path = graph_manager.get_path(source_node, target_node, max_depth=5)

# 获取子图
subgraph = graph_manager.get_subgraph(center_node, depth=2)

# 按属性查询
high_level_players = graph_manager.get_nodes_by_attribute("level", 10)

# 按标签查询
fantasy_worlds = graph_manager.get_nodes_by_tag("fantasy")
```

### 4. 性能优化

```python
# 批量创建
nodes_data = [{"name": f"Node{i}", ...} for i in range(100)]
created_nodes = graph_manager.bulk_create_nodes(nodes_data)

# 预加载关系
nodes_with_rels = graph_manager.get_nodes_with_relationships([1, 2, 3])
```

## 高级功能

### 1. 自动同步机制

系统使用装饰器 `@graph_node_sync` 自动同步对象到图节点：

```python
@graph_node_sync
class MyObject(GraphDefaultObject):
    def __init__(self, name):
        super().__init__(name=name)
        # 自动同步到图节点系统
```

### 2. 属性系统

使用 JSONB 字段存储动态属性，支持复杂数据结构：

```python
# 设置属性
obj.set_attribute("inventory", ["sword", "shield"])
obj.set_attribute("stats", {"hp": 100, "mp": 50})

# 获取属性
inventory = obj.get_attribute("inventory", [])
hp = obj.get_attribute("stats.hp", 0)  # 支持嵌套属性
```

### 3. 标签系统

支持灵活的标签分类和查询：

```python
# 添加标签
obj.add_tag("hero")
obj.add_tag("warrior")

# 查询标签
heroes = graph_manager.get_nodes_by_tag("hero")
```

### 4. 图算法

内置多种图算法：

- **最短路径**: BFS 算法实现
- **邻居查询**: 支持方向性查询
- **子图提取**: 按深度提取子图
- **连通性分析**: 检查节点连通性

## 性能考虑

### 1. 索引优化

```sql
-- 节点表索引
CREATE INDEX idx_node_classpath ON nodes(classpath);
CREATE INDEX idx_node_attributes ON nodes USING GIN(attributes);
CREATE INDEX idx_node_uuid ON nodes(uuid);

-- 关系表索引
CREATE INDEX idx_relationship_type ON relationships(type);
CREATE INDEX idx_relationship_source ON relationships(source_id);
CREATE INDEX idx_relationship_target ON relationships(target_id);
CREATE INDEX idx_relationship_attributes ON relationships USING GIN(attributes);
```

### 2. 查询优化

- 使用 `joinedload` 预加载关系
- 批量操作减少数据库往返
- JSONB 字段的 GIN 索引支持复杂查询

### 3. 缓存策略

- 节点和关系的本地缓存
- 查询结果缓存
- 批量操作的事务优化

## 监控和统计

### 1. 图统计信息

```python
stats = graph_manager.get_graph_stats()
print(f"总节点数: {stats['total_nodes']}")
print(f"总关系数: {stats['total_relationships']}")
print(f"图密度: {stats['density']:.4f}")
```

### 2. 类型分布

```python
node_dist = graph_manager.get_node_type_distribution()
rel_dist = graph_manager.get_relationship_type_distribution()
```

### 3. 性能监控

```python
# 批量操作性能
start_time = time.time()
created_nodes = graph_manager.bulk_create_nodes(nodes_data)
end_time = time.time()
print(f"批量创建耗时: {end_time - start_time:.4f}秒")
```

## 最佳实践

### 1. 模型设计

- 继承 `GraphDefaultObject` 或 `GraphDefaultAccount`
- 使用 `@graph_node_sync` 装饰器
- 合理设计属性和标签结构

### 2. 关系设计

- 明确定义关系类型
- 使用关系属性存储额外信息
- 避免创建过多无意义的关系

### 3. 查询优化

- 合理使用索引
- 避免深度过大的图遍历
- 使用批量操作处理大量数据

### 4. 数据一致性

- 使用事务确保操作原子性
- 定期清理无效节点和关系
- 监控图结构的完整性

## 扩展和定制

### 1. 自定义节点类型

```python
class CustomNode(GraphDefaultObject):
    __tablename__ = "custom_nodes"
    
    # 添加自定义字段
    custom_field = Column(String(100))
    
    def custom_method(self):
        # 自定义方法
        pass
```

### 2. 自定义关系类型

```python
class CustomRelationship(Relationship):
    __tablename__ = "custom_relationships"
    
    # 添加自定义字段
    custom_field = Column(String(100))
```

### 3. 插件系统

系统支持插件扩展：

```python
# 注册自定义组件
model_factory.register_component("custom_component", CustomComponent)

# 创建带组件的模型
CustomModel = model_factory.create_model_with_components(
    "CustomModel", 
    ["custom_component"]
)
```

## 故障排除

### 常见问题

1. **导入错误**: 确保所有依赖模块正确安装
2. **数据库连接**: 检查 PostgreSQL 连接和权限
3. **性能问题**: 检查索引和查询优化
4. **同步失败**: 检查装饰器和继承关系

### 调试技巧

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 检查节点状态
node = graph_manager.get_node_by_id(1)
print(f"节点状态: {node.is_active}")
print(f"节点属性: {node.get_all_attributes()}")

# 检查关系
relationships = graph_manager.get_relationships_by_node(node)
print(f"关系数量: {len(relationships)}")
```

## 总结

CampusWorld 图数据结构系统提供了一个强大、灵活且高性能的对象持久化解决方案。通过继承 Evennia 的设计理念，结合现代数据库技术，系统能够支持复杂的业务逻辑和未来的功能扩展。

该系统特别适合：
- 需要复杂对象关系的应用
- 要求高性能查询的场景
- 需要灵活属性存储的系统
- 基于图算法的业务逻辑

通过合理使用系统提供的功能，开发者可以构建出强大而灵活的应用程序。
