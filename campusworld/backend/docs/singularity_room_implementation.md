# Singularity Room 实现方案

## 概述

本文档详细描述了在CampusWorld项目中实现Singularity Room作为默认home地点的完整方案。该方案参考Evennia框架的DefaultHome设计模式，采用纯图数据模型，确保所有用户登录后默认出现在Singularity Room。

## 需求分析

1. **构建默认home地点**：所有用户登录默认出现在此
2. **地点名称**：Singularity Room
3. **图数据模型**：作为特殊的Node存在，可视为root node

## 架构设计

### 1. 核心组件

#### 1.1 Room模型 (`app/models/room.py`)
- **Room类**：基础房间模型，继承自DefaultObject
- **SingularityRoom类**：奇点房间专用类，继承自Room
- **特性**：
  - 支持房间容量管理
  - 支持出口管理
  - 支持访问控制
  - 支持房间效果
  - 标记为root node和默认home

#### 1.2 RootNodeManager (`app/models/root_manager.py`)
- **功能**：管理系统的根节点（Singularity Room）
- **特性**：
  - 自动创建和初始化根节点
  - 确保根节点唯一性
  - 提供根节点查询和统计功能
  - 支持用户迁移

#### 1.3 用户Spawn逻辑 (`app/models/user.py`)
- **新增方法**：
  - `spawn_to_singularity_room()`：spawn到奇点房间
  - `spawn_to_home()`：spawn到home位置
  - `set_home_to_singularity_room()`：设置home为奇点房间
  - `get_current_location_info()`：获取当前位置信息

### 2. 数据库设计

#### 2.1 节点表增强
- 在`nodes`表的`attributes`字段中存储房间特定属性
- 添加`is_root`和`is_home`标识
- 添加根节点唯一性约束

#### 2.2 约束和索引
```sql
-- 根节点唯一约束
CREATE UNIQUE INDEX IF NOT EXISTS idx_nodes_single_root 
ON nodes(id) 
WHERE attributes->>'is_root' = 'true' AND is_active = TRUE;
```

### 3. 登录流程集成

#### 3.1 SSH服务器修改 (`app/ssh/server.py`)
- 在用户认证成功后自动调用spawn逻辑
- 确保用户登录后出现在Singularity Room
- 记录spawn操作日志

## 实现细节

### 1. SingularityRoom特性

```python
class SingularityRoom(Room):
    def __init__(self, **kwargs):
        singularity_attrs = {
            'room_type': 'singularity',
            'room_description': self._get_default_description(),
            'is_root': True,
            'is_home': True,
            'is_special': True,
            'room_capacity': 0,  # 无限制
            'allow_pvp': False,
            'allow_combat': False,
            'allow_magic': True,
            'allow_teleport': True,
        }
```

### 2. 用户Spawn流程

1. **用户登录** → SSH认证成功
2. **自动Spawn** → 调用`_spawn_user_to_singularity_room()`
3. **确保根节点存在** → `root_manager.ensure_root_node_exists()`
4. **设置用户位置** → `location_id = root_node.id`
5. **设置用户home** → `home_id = root_node.id`

### 3. 根节点管理

```python
class RootNodeManager:
    def ensure_root_node_exists(self) -> bool:
        """确保根节点存在，如果不存在则创建"""
        
    def get_root_node(self) -> Optional[Node]:
        """获取根节点"""
        
    def is_root_node(self, node_id: int) -> bool:
        """检查指定节点是否为根节点"""
```

## 部署和使用

### 1. 初始化脚本

```bash
# 初始化奇点房间
python scripts/init_singularity_room.py

# 强制重新创建
python scripts/init_singularity_room.py --force

# 仅验证设置
python scripts/init_singularity_room.py --verify

# 迁移现有用户
python scripts/init_singularity_room.py --migrate
```

### 2. 测试脚本

```bash
# 运行完整测试套件
python scripts/test_singularity_room.py
```

### 3. 验证步骤

1. **检查根节点创建**：确认Singularity Room已创建
2. **验证用户spawn**：测试用户登录后是否出现在奇点房间
3. **检查数据库约束**：确认只有一个根节点
4. **测试房间功能**：验证房间描述、容量等功能

## 设计理由

### 1. 参考Evennia设计模式

- **DefaultHome模式**：Evennia中所有用户的默认起始位置
- **DefaultRoom模式**：房间的基础功能和属性管理
- **Spawn机制**：用户登录后的自动位置设置

### 2. 图数据模型优势

- **统一存储**：所有对象都存储在Node表中
- **关系管理**：通过location_id和home_id建立位置关系
- **属性扩展**：通过JSONB字段存储房间特定属性
- **查询效率**：通过索引优化位置相关查询

### 3. 系统一致性

- **唯一根节点**：确保系统只有一个起始点
- **自动spawn**：用户登录后自动出现在正确位置
- **状态同步**：用户位置状态与数据库保持同步

## 扩展性考虑

### 1. 多房间支持
- 可以创建其他房间，通过出口连接
- 支持房间间的移动和导航
- 支持房间特定的规则和效果

### 2. 权限系统
- 房间可以设置访问权限要求
- 支持角色和权限检查
- 支持动态权限管理

### 3. 房间效果
- 支持房间特定的环境效果
- 支持房间脚本和自动化
- 支持房间状态变化

## 监控和维护

### 1. 日志记录
- 用户spawn操作记录
- 根节点创建和管理日志
- 房间访问和移动日志

### 2. 统计信息
- 根节点用户数量统计
- 房间容量使用情况
- 用户活动模式分析

### 3. 健康检查
- 根节点存在性检查
- 用户位置一致性验证
- 数据库约束完整性检查

## 总结

本实现方案成功地将Evennia的DefaultHome设计模式应用到CampusWorld项目中，通过纯图数据模型实现了Singularity Room作为系统根节点和默认home的功能。该方案具有以下优势：

1. **架构清晰**：参考成熟框架的设计模式
2. **实现完整**：包含创建、管理、spawn等完整流程
3. **扩展性强**：支持未来功能扩展
4. **维护性好**：提供完整的测试和监控工具
5. **数据一致**：确保系统状态的一致性

通过这个实现，CampusWorld项目现在拥有了一个稳定、可扩展的默认home系统，为后续的游戏世界开发奠定了坚实的基础。
