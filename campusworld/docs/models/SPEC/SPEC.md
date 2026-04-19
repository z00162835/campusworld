# Data Models SPEC

> **Architecture Role**: 本模块是 CampusWorld **知识本体**的核心实现，通过**全图数据结构**构筑世界语义。所有实体（User/Character/Room/World 等）以图节点形式存在，关系以语义边表达，构成知识本体的骨架。属于"知识与能力层"的底层数据支撑，上承命令系统（commands）和游戏引擎（game_engine），下接数据库持久化层（db）。

## Module Overview

数据模型（`backend/app/models/`）采用**纯图数据设计**，所有模型基于图数据结构。

> **注**：CampusWorld 是智慧园区 OS，不是游戏。系统的"图数据模型"是知识本体设计，不是游戏引擎的数据结构。

```
实体（Node） + 关系（Edge） = 知识本体
```

## Unified Terms (Cross-SPEC)

- **Agent 四层架构（L1–L4）**：类型与数据、命令工具、思考模型、经验 Skill 的全局分层语言；规范真源见 [`features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md`](features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)。
- **System Entry Space**: `SingularityRoom`，系统级统一入口空间。
- **World Default Spawn**: 某个世界内部默认出生点（例如 `campus_life/campus`）。
- **Last Location Resume**: 用户重连后的位置恢复策略。

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
| `SingularityRoom` | room.py | 系统入口空间（全局单例）|
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

### `NodeType` 与本体属性元数据

持久化表为 **`nodes`** / **`relationships`**（`Node` / `Relationship`，非历史文档中的 `graph_nodes` / `graph_edges` 命名）。**`node_types.schema_definition`** 按 **`type_code`** 描述该类型在 **`nodes.attributes`** 上的属性注册：以 JSON Schema 惯用 **`properties.<attr_name>`** 为键，与实例 JSON 同层键名对齐；**`value_kind`**、**`mutability`**、**`semantic_type`**、**`role`** 等与 **`type`** / **`enum`** / **`title`** **同级并列**（默认写法）。**`inferred_rules`** 承载跨属性约束；**`ui_config`** 承载表单布局并通过 `property_ref` 引用属性路径。图种子类型的扩展定义见 [`docs/ontology/NODE_TYPES_SCHEMA.md`](../ontology/NODE_TYPES_SCHEMA.md) 与 [`backend/db/ontology/graph_seed_node_types.yaml`](../../../backend/db/ontology/graph_seed_node_types.yaml)。字段与 DDL 见 [`backend/db/schemas/README.md`](../../../backend/db/schemas/README.md)。

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

## SingularityRoom as World Gateway

- `SingularityRoom` 的语义是**系统入口与世界连接枢纽**，而不是每用户独有空间。
- 用户登录后先进入系统入口，再由路由策略决定是否进入具体世界。
- 世界内 spawn（如 `campus_life/campus`）属于世界语义，不应覆盖系统入口语义。
- 奇点屋与世界的连接可通过图关系（如 `CONNECTED_TO` / `CONTAINS`）或策略映射表达，但必须保证可观测与可回退。

## Acceptance Criteria

- [ ] 所有实体继承 `DefaultObject` 或 `DefaultAccount`
- [ ] `model_factory.register_model("room", Room)` 后 `model_factory.get_model("room")` 能获取 Room 类
- [ ] `Character` 位于 `Room` 通过语义边（而非外键）表达
- [ ] 新用户创建后自动生成对应 Character 并 spawn 到 SingularityRoom
- [ ] `SingularityRoom` 被定义为全局系统入口（非每用户单例）

## Design Decisions

1. **为何用图结构而非关系型**: 知识本体中实体关系复杂（空间连接、角色归属、物品位置），图结构比外键更自然表达语义关系
2. **为何用 ModelFactory**: 支持动态模型发现，新增实体类型无需修改核心代码
3. **为何区分 DefaultObject 和 DefaultAccount**: 账户（User）和非账户实体（图节点）在身份认证上有本质区别

## Feature Specs

- `F02` Intelligent Agent Service（`npc_agent` 扩展、命令优先、记忆/运行独立表）  
  [`features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md`](features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)  
  实现锚点：`app/models/system/agent_memory_tables.py`（ORM）、`app/game_engine/agent_runtime/`（PDCA / MemoryPort / 注册表）、`app/commands/agent_commands.py`（`agent_capabilities` / `agent_tools` / `aico` / `agent` 等）。  
  扩展（向量检索、LTM 间关联）：[`features/F02_LTM_VECTORS_AND_MEMORY_LINKS.md`](features/F02_LTM_VECTORS_AND_MEMORY_LINKS.md) — 检索与扩展实现见 `app/services/ltm_semantic_retrieval.py`。

- `F03` 系统默认助手 AICO（`npc_agent` 单例、奇点屋锚点、trait 不可移动、初始配置与 schema；**含 AICO 优化可观测专用日志 §5.7**）  
  [`features/F03_AICO_DEFAULT_SYSTEM_ASSISTANT.md`](features/F03_AICO_DEFAULT_SYSTEM_ASSISTANT.md)

- `F04` `@` 与智能体交互命令特性（`@<handle>` 全局可用、handle 解析、与 `help` 同级可见性）  
  [`features/F04_AT_AGENT_INTERACTION_PROTOCOL.md`](features/F04_AT_AGENT_INTERACTION_PROTOCOL.md)

- `F05` `agent` 命令：`agent list` 列出可见 Agent、`agent status` 查询状态（不可用 / 空闲 / 工作中）；用户与 Agent 共用  
  [`features/F05_AGENT_COMMAND_LIST_AND_STATUS.md`](features/F05_AGENT_COMMAND_LIST_AND_STATUS.md)

- `F06` CampusLibrary 内置知识世界（OS 级全局知识库、`cl search|ingest|del`、GraphRAG 式语义、pgvector、奇点屋可见不可 enter、软删 `is_active`）  
  [`features/F06_CAMPUSLIBRARY_KNOWLEDGE_WORLD.md`](features/F06_CAMPUSLIBRARY_KNOWLEDGE_WORLD.md)

- `F07` 按用户区隔的 Agent 记忆与 LTM 异步晋升（后续迭代，Deferred）  
  [`features/F07_PER_USER_AGENT_MEMORY_AND_ASYNC_LTM_PROMOTION.md`](features/F07_PER_USER_AGENT_MEMORY_AND_ASYNC_LTM_PROMOTION.md)

- `F08` AICO 工具调用与命令上下文（Command-as-Tool：注册表命令输出作为 LLM 上下文；**扩展** [**F03**](features/F03_AICO_DEFAULT_SYSTEM_ASSISTANT.md)）  
  [`features/F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md`](features/F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md)

- `F09` CampusWorld Agent 四层架构（L1–L4 规范真源、与 F02–F08 及代码映射、F07/F06 边界）  
  [`features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md`](features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)

## Open Questions

- [ ] GraphNode/GraphEdge 表是否需要支持向量属性（用于语义搜索）？
- [ ] 模型是否需要版本控制（schema evolution）？
- [ ] 语义边是否需要属性（如 Exit 的 locked 状态）？