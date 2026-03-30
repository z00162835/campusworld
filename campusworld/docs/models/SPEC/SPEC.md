# Data Models SPEC

> **Architecture Role**: 本模块是 CampusWorld **知识本体**的核心实现，通过**全图数据结构**构筑世界语义。所有实体（User/Character/Room/World 等）以图节点形式存在，关系以语义边表达，构成知识本体的骨架。属于"知识与能力层"的底层数据支撑，上承命令系统（commands）和游戏引擎（game_engine），下接数据库持久化层（db）。

## Module Overview

数据模型（`backend/app/models/`）采用**纯图数据设计**，所有模型基于图数据结构。

> **注**：CampusWorld 是智慧园区 OS，不是游戏。系统的"图数据模型"是知识本体设计，不是游戏引擎的数据结构。

```
实体（Node） + 关系（Edge） = 知识本体
```

## Core Abstractions

### 基础模型

| 类 | 文件 | 说明 |
|---|---|---|
| `DefaultObject` | base.py | 所有对象的基类：id/name/description/created_at |
| `DefaultAccount` | base.py | 账户基类：继承 DefaultObject + username/email/hashed_password |
| `GraphNodeInterface` | base.py | 图节点接口 |
| `GraphRelationshipInterface` | base.py | 图关系接口 |

### 知识节点（实体）

| 模型 | 文件 | 说明 |
|------|------|------|
| `User` | user.py | 用户账户（继承 DefaultAccount）|
| `Character` | character.py | 角色（在知识本体中代表用户进入世界的化身）|
| `Room` | room.py | 空间位置（图书馆/食堂/宿舍等）|
| `SingularityRoom` | room.py | 单例空间（用户默认 spawn 位置）|
| `World` | world.py | 世界 |
| `WorldObject` | world.py | 世界对象 |
| `Building` | building.py | 建筑 |
| `Campus` | campus.py | 园区 |
| `Exit` | exit.py | 出口（连接两个空间）|

### 图结构层

| 类 | 文件 | 说明 |
|---|---|---|
| `Node` | graph.py | 知识节点（所有实体的底层存储）|
| `Relationship` | graph.py | 语义边（实体间的关系）|
| `GraphNode` | graph.py | GraphNode 表的 ORM 模型 |
| `GraphEdge` | graph.py | GraphEdge 表的 ORM 模型 |
| `NodeType` | graph.py | 节点类型注册表 |

### 组件系统

| 类 | 文件 | 说明 |
|---|---|---|
| `ModelFactory` | factory.py | 模型工厂（动态发现/注册/获取）|
| `ComponentMixin` | factory.py | 组件混入基类 |
| `InventoryMixin` | factory.py | 背包组件 |
| `StatsMixin` | factory.py | 属性组件（精力/饱食度等）|
| `CombatMixin` | factory.py | 战斗组件（预留）|

### 模型管理器

| 类 | 文件 | 说明 |
|---|---|---|
| `ModelManager` | model_manager.py | 模型管理器 |
| `RootManager` | root_manager.py | 根节点管理器 |

## 知识本体结构

```
知识本体（Knowledge Ontology）

节点类型：
  account  — 用户账户
  character — 世界角色
  room     — 空间位置
  world    — 世界
  building — 建筑
  exit     — 出口连接
  campus   — 园区

语义边类型：
  LOCATED_IN  — 角色位于空间
  CONNECTED   — 空间通过出口连接
  OWNS        — 账户拥有角色
  CONTAINS    — 世界包含空间/建筑
```

## User Stories

1. **实体创建**: 创建 User 时自动创建对应的 Character，Character 默认 spawn 到 SingularityRoom
2. **空间连接**: Room 通过 Exit 连接到其他 Room，Exit 的 `source` 和 `destination` 代表空间的连通性
3. **动态发现**: 新模型类通过 `model_factory` 自动注册，无需修改工厂代码

## Acceptance Criteria

- [ ] 所有实体继承 `DefaultObject` 或 `DefaultAccount`
- [ ] `model_factory.register_model("room", Room)` 后 `model_factory.get_model("room")` 能获取 Room 类
- [ ] `Character` 位于 `Room` 通过语义边（而非外键）表达
- [ ] 新用户创建后自动生成对应 Character 并 spawn 到 SingularityRoom

## Design Decisions

1. **为何用图结构而非关系型**: 知识本体中实体关系复杂（空间连接、角色归属、物品位置），图结构比外键更自然表达语义关系
2. **为何用 ModelFactory**: 支持动态模型发现，新增实体类型无需修改核心代码
3. **为何区分 DefaultObject 和 DefaultAccount**: 账户（User）和非账户实体（图节点）在身份认证上有本质区别

## Open Questions

- [ ] GraphNode/GraphEdge 表是否需要支持向量属性（用于语义搜索）？
- [ ] 模型是否需要版本控制（schema evolution）？
- [ ] 语义边是否需要属性（如 Exit 的 locked 状态）？