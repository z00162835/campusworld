# Data Models - 数据模型

> **Architecture Role**: 本模块是 CampusWorld **知识本体**的核心实现，通过**全图数据结构**构筑世界语义。所有实体（User、Character、Room、World 等）以图节点形式存在，关系以语义边表达，构成知识本体的骨架。属于"知识与能力层"的底层数据支撑，上承命令系统（commands）和引擎（game_engine），下接数据库持久化层（db）。

CampusWorld 采用**纯图数据设计**，所有模型基于图数据结构，存储在统一的 Node 表中，通过 type 和 typeclass 区分不同的对象类型。

### Node 行 → 内存对象（hydrate）

- 持久化以 `nodes` 表为准；从已有 `Node` 构造 `DefaultObject` 子类时，须 **`disable_auto_sync=True`** 或统一走 **`GraphSynchronizer.sync_node_to_object`**（含 `ModelManager._node_to_object` 委托路径），避免 `DefaultObject.__init__` 末尾按新 uuid **隐式 INSERT** 重复行。
- 新建节点并要落库时，使用显式 **`sync_to_node` / `sync_object_to_node`** 或单次 ORM `Node` 写入，避免「内存构造已 sync + 手写 `Node`」双写。

## 模型列表

### 基础模型 (base.py)

```python
# 基础对象接口
class DefaultObject:
    """默认对象基类"""
    id: UUID
    name: str
    description: str
    created_at: datetime

class DefaultAccount:
    """账户基类，继承自DefaultObject"""
    username: str
    email: str
    hashed_password: str

class GraphNodeInterface:
    """图节点接口"""

class GraphRelationshipInterface:
    """图关系接口"""
```

### User - 用户

```python
class User(DefaultAccount):
    """用户账户模型"""
    is_active: bool
    is_superuser: bool
    last_login: datetime
```

### Campus - 园区

```python
class Campus(DefaultObject):
    """园区模型"""
    owner_id: UUID
    max_members: int
    is_public: bool
```

### World - 世界

```python
class World(DefaultObject):
    """虚拟世界"""
    owner_id: UUID
    is_public: bool

class WorldObject(DefaultObject):
    """世界对象"""
    world_id: UUID
    location_id: UUID
```

### Room - 房间

```python
class Room(DefaultObject):
    """房间模型"""
    world_id: UUID
    x: int  # 坐标
    y: int
    z: int
    exits: List[Exit]

class SingularityRoom:
    """奇点房间 - 特殊位置"""
```

### Exit - 出口

```python
class Exit(DefaultObject):
    """出口模型"""
    room_id: UUID
    destination_id: UUID
    locked: bool
```

### 图结构 (graph.py)

图结构是**知识本体**的底层支撑：

```python
class Node:
    """知识节点 - 世界中的实体"""
    id: UUID
    type: str  # node_type = 实体类型
    properties: JSON  # 节点属性 = 实体属性

class Relationship:
    """语义边 - 实体间的关系"""
    id: UUID
    source_id: UUID  # 源节点
    target_id: UUID  # 目标节点
    type: str  # edge_type = 语义关系类型
```

> 世界语义体现在：Room 通过 Exit 连接到其他 Room（空间关系），Character 位于 Room 中（位置关系），User 拥有 Character（归属关系）—— 一切皆为节点，一切皆为关系。

### 组件系统 (factory.py)

```python
class ModelFactory:
    """模型工厂"""
    def register_model(self, name: str, model_class): ...
    def get_model(self, name: str): ...

# 组件混入类
class ComponentMixin: ...
class InventoryMixin: ...
class StatsMixin: ...
class CombatMixin: ...

model_factory: ModelFactory  # 全局实例
```

## 关系图

```
User / DefaultAccount
    └─< Campus
         └─< World
              ├─< Room / SingularityRoom
              │    ├─< Exit
              │    └─< WorldObject
              └─< WorldObject

图结构:
    Node 1 --< Relationship >-- 1 Node
```

## 使用示例

```python
from app.models import User, World, Room, model_factory

# 使用模型工厂
UserModel = model_factory.get_model("user")
user = UserModel(name="player1", ...)

# 直接使用模型
from app.core.database import SessionLocal
from app.models import User, World, Room

db = SessionLocal()

# 创建用户
user = User(username="player1", email="p1@test.com", ...)
db.add(user)
db.commit()

# 查询世界
world = db.query(World).filter(World.name == "Main").first()
rooms = db.query(Room).filter(Room.world_id == world.id).all()
```

## 模型注册

模型通过 `model_factory` 自动注册:

```python
from app.models import model_factory

model_factory.register_model("user", User)
model_factory.register_model("room", Room)
model_factory.register_model("world", World)
model_factory.register_model("graph_node", Node)
model_factory.register_model("relationship", Relationship)
```
