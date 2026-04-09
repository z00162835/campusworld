# F01 - Trait Class & 64-bit Trait Mask for Agent-Friendly Graph

## Goal

在图数据库中引入统一的 `trait_class` 与 `trait_mask`（64-bit），让 Agent 能够：

- 用 `trait_class` 快速理解类型语义内涵与边界（回答“这是什么”）。
- 用 `trait_mask` 表示类型所具备的能力集（回答“这能怎么样”），做高性能候选集过滤（位运算），降低 join/全量扫描成本。（例如 `Spatial` 表示有体积并可参与空间拓扑，`Controllable` 表示可被控制运行；具体见下位表）
- 在节点与关系两条主线同时生效：`node_types/nodes` 与 `relationship_types/relationships`。

## Scope

- 为以下四张表增加 trait 能力字段：
  - `node_types`
  - `nodes`
  - `relationship_types`
  - `relationships`
- 建立“类型定义为内涵，实例继承且不可覆盖”的一致性契约。
- 增加面向位运算检索的索引与标准查询范式。
- 提供迁移、回填、校验、回归测试基线。

## Non-Goals

- 不引入独立的 `traits` 注册表。
- 不在本特性中设计超 64 位的 mask 容量扩展。
- 不改造业务层 Agent 策略逻辑，仅提供可被调用的数据契约。

## Architecture Decisions

### 1) 数据治理模型

- **类型层（source of truth）**：`node_types`、`relationship_types` 的 trait 字段为语义内涵。
- **实例层（performance copy）**：`nodes`、`relationships` 持有冗余 trait 字段，仅用于检索加速与运行期过滤。
- **继承规则**：实例 trait 必须等于其类型 trait，实例不可覆盖。
- **语义分工**：
  - `trait_class`：语义分类，回答“是什么”。
  - `trait_mask`：能力分类，回答“能怎么样”。
  - 两者禁止重复编码同一语义。

### 2) 位宽选择

- 采用 `BIGINT` 作为 `trait_mask`（64-bit）。
- 约定 bit 位语义由 **本文档 + 代码常量** 双轨维护，不使用数据库注册表。
- 正式常量与常用组合见 `backend/app/constants/trait_mask.py`（与 §2.1–2.3 数值一致；`ensure_graph_seed_ontology` 中空间关系边使用 `LOCATION_RELATIONSHIP_EDGE`）。
- bit 编号从低位开始（`bit0 = 1 << 0`），不保留系统位段。

### 2.0) 冷启动 Schema 与图种子覆盖

- `database_schema.sql` 中部分内置 `node_types`（如顶层 `world`）可能为 `trait_mask = 0`，表示「未打能力标签的默认值」。
- HiCampus / 图种子通过 `ensure_graph_seed_ontology` + `graph_seed_node_types.yaml` **幂等 upsert** 同一 `type_code` 时，会覆盖为 §2.2 中的 v1 数值。二者并非矛盾，而是 **bootstrap 默认 vs 本体覆盖层**；以运行期类型表为准。

### 2.1) Bit 语义 v1（人工定稿，与 graph seed 对齐）

> **治理约定**：下文为正式 bit 含义；`backend/db/ontology/graph_seed_node_types.yaml` 与 `ensure_graph_seed_ontology` 中关系类型的 `trait_mask` 必须与本表及「HiCampus 类型层映射」一致。调整语义时须同时改 YAML、关系类型种子、并安排实例回填（见「类型层 mask 变更后的数据调整计划」）。

| bit位 | 数值 | 能力名 | 含义 | HiCampus 示例组合 |
|---|---:|---|---|---|
| `bit0` | `1` | `Conceptual` | 概念/抽象语义（目标、规则、流程、逻辑区等） | 逻辑区、世界入口（流程语义） |
| `bit1` | `2` | `Factual` | 客观物理/可度量事实（非纯抽象） | 设备、NPC（具身） |
| `bit2` | `4` | `Spatial` | 具备空间属性（体积、拓扑、安装位置） | 空间类节点、空间关系、闸机终端 |
| `bit3` | `8` | `Perceptual` | 可被感知/被观测 | 设备遥测与可见物品 |
| `bit4` | `16` | `Temporal` | 时序变化（状态/度量随时间变） | 设备快照、NPC 行为 |
| `bit5` | `32` | `Controllable` | 可被控制、配置、驱动运行 | 照明/显示/网络、门禁终端、入口 |
| `bit6` | `64` | `Event-based` | 事件驱动或事件边界明显 | 门禁、入口、逻辑区策略、NPC |
| `bit7` | `128` | `Mobile` | 可移动（主动或被动） | NPC |
| `bit8` | `256` | `Auto` | 可自动/自主决策运行 | NPC |
| `bit9` | `512` | `Load-bearing` | 可承载/容纳（含容纳空间的物体） | 房间/楼/层/世界、家具类物品 |

**组合速记**：`Spatial|Load-bearing`（516）= 有体积且可作容器；`Factual|Perceptual|Temporal|Controllable`（58）= 典型物联末端；门禁类在 58 基础上加 `Spatial|Event-based`（126）。

### 2.2) HiCampus 图种子 `node_types` 映射（与 YAML 一致）

| `type_code` | `trait_class` | 置位（十进制合算） | `trait_mask` |
|---|---|---|---:|
| `room`, `building`, `building_floor`, `world` | SPACE | Spatial(4) + Load-bearing(512) | 516 |
| `network_access_point`, `lighting_fixture`, `av_display` | DEVICE | Factual(2) + Perceptual(8) + Temporal(16) + Controllable(32) | 58 |
| `access_terminal` | DEVICE | 上表 + Spatial(4) + Event-based(64) | 126 |
| `furniture`, `conference_seating`, `lounge_furniture` | ITEM | Spatial(4) + Load-bearing(512) | 516 |
| `world_object` | ITEM | Perceptual(8) + Load-bearing(512) | 520 |
| `npc_agent` | AGENT | Factual(2) + Temporal(16) + Controllable(32) + Event-based(64) + Mobile(128) + Auto(256) | 498 |
| `logical_zone` | ENV | Conceptual(1) + Event-based(64) | 65 |
| `world_entrance` | PROCESS | Conceptual(1) + Spatial(4) + Controllable(32) + Event-based(64) | 101 |

### 2.3) 图种子 `relationship_types`（`ensure_graph_seed_ontology`）

对 `connects_to` / `contains` / `located_in`：`trait_class = SPACE`，`trait_mask = 5`（`Conceptual`(1) + `Spatial`(4)，表示拓扑/包容类空间语义边，与纯几何容器节点区分）。

### 3) 约束实现策略

- 通过数据库触发器保证“实例写入时按类型强制回填”。
- 类型 trait 变更采用最终一致性：通过异步任务刷新实例副本，不在同一事务内批量更新。

### 4) `trait_class` 首批值（文档约定）

`GOAL`（目标）、`RULE`（规则）、`SKILL`（技能）、`EXP`（经验）、`PROCESS`（流程）、`EVENT`（事件）、`TASK`（任务）、`SPACE`（空间）、`DEVICE`（设备）、`ENV`（环境）、`AGENT`（智能体）、`PERSON`（人）、`ITEM`（物品）

> 当前不在数据库层做枚举 check 约束。

## Schema Changes (Draft)

> 具体 SQL 名称可按现有命名风格调整。

### `node_types`

- `trait_class VARCHAR(64) NOT NULL DEFAULT 'UNKNOWN'`
- `trait_mask BIGINT NOT NULL DEFAULT 0`
- `CHECK (trait_mask >= 0)`

### `nodes`

- `trait_class VARCHAR(64) NOT NULL DEFAULT 'UNKNOWN'`
- `trait_mask BIGINT NOT NULL DEFAULT 0`
- `CHECK (trait_mask >= 0)`

### `relationship_types`

- `trait_class VARCHAR(64) NOT NULL DEFAULT 'UNKNOWN'`
- `trait_mask BIGINT NOT NULL DEFAULT 0`
- `CHECK (trait_mask >= 0)`

### `relationships`

- `trait_class VARCHAR(64) NOT NULL DEFAULT 'UNKNOWN'`
- `trait_mask BIGINT NOT NULL DEFAULT 0`
- `CHECK (trait_mask >= 0)`

## Inheritance Contract (Critical)

### 写入契约

- 对 `nodes` 的 `INSERT/UPDATE`：
  - 忽略外部传入的 `trait_class`、`trait_mask`。
  - 按 `type_code` 读取 `node_types` 并覆盖写入实例字段。
- 对 `relationships` 同理，来源为 `relationship_types`。

### 变更传播契约

- 当 `node_types.trait_*` 变化时，异步更新所有同类型 `nodes.trait_*`。
- 当 `relationship_types.trait_*` 变化时，异步更新所有同类型 `relationships.trait_*`。
- 同步策略为最终一致性，要求有可观测的补偿任务与失败重试。

### 失败策略

- **实例写入（`nodes` / `relationships`）**：`type_code` 在对应类型表中不存在时，**触发器抛错，当前事务回滚**（fail fast）。
- **类型表更新（`node_types` / `relationship_types`）**：`trait_*` 变更 **正常提交**；实例副本通过 `trait_sync_jobs` + worker **最终一致**。若 worker 失败，会出现短暂「类型已变、实例仍旧」窗口，需重试任务或跑 `trait_migration_check` / 手动 backfill 对齐；**不因 worker 失败而回滚类型表事务**。
- 「映射冲突」等数据治理错误仍应在应用/迁移层 fail fast，避免 silently 写脏类型。

## Query Patterns (Agent-Oriented)

### 1) 按能力“任一命中”

```sql
SELECT id, uuid, type_code, name
FROM nodes
WHERE is_active = TRUE
  AND (trait_mask & :required_any_mask) <> 0;
```

### 2) 按能力“全部命中”

```sql
SELECT id, uuid, type_code, name
FROM nodes
WHERE is_active = TRUE
  AND (trait_mask & :required_all_mask) = :required_all_mask;
```

### 2.1) `mask = 0` 语义

- `trait_mask = 0` 定义为“无能力标签”，是合法状态，可被查询。
- 当查询参数 `:required_any_mask = 0` 或 `:required_all_mask = 0` 时，业务层应显式选择：
  - 作为“不过滤能力”的全量查询，或
  - 拒绝该参数（避免误用）。
- 本特性默认建议：API 层将 `0` 解释为“不过滤能力”。

### 3) 关系过滤

```sql
SELECT id, source_id, target_id, type_code
FROM relationships
WHERE is_active = TRUE
  AND (trait_mask & :edge_mask) <> 0;
```

### 4) class + mask 组合

```sql
SELECT id, uuid, type_code, name
FROM nodes
WHERE trait_class = 'PROCESS'
  AND (trait_mask & :mask) <> 0;
```

## Indexing Strategy

> PostgreSQL 对位运算谓词通常难以直接用普通 B-Tree 全覆盖，建议采用“组合索引 + 约束前置过滤”降低扫描范围。

最小索引集（本特性必选）：
- `nodes(is_active, trait_class)`
- `relationships(is_active, trait_class)`

可选增强（按观测补充）：
- 保留并复用现有 `type_code`、`type_id`、图遍历相关索引。
- 如果某些热点 mask 固定（例如 `SKILL` 安全检查位），可按后续观测补充局部索引（partial index）。

## Migration Plan

1. **DDL**：为四张表添加字段与 check 约束（默认值确保在线兼容）。
2. **Backfill**：
   - 先补齐 `node_types/relationship_types` 的 trait 默认值与业务映射值。
   - 回填 `nodes/relationships` 的 trait 字段（join type 表）。
3. **Trigger**：
   - 实例表 `BEFORE INSERT/UPDATE` 强制继承。
   - 类型表 `AFTER UPDATE OF trait_*` 写入异步同步任务（最终一致性）。
4. **Validation**：
   - 差异检查：实例 trait 与类型 trait 不一致计数必须为 0。
5. **Rollout**：
   - API/命令查询切换到 trait 过滤路径。
   - 观察慢查询与命中率，必要时补充 partial index。

## 类型层 mask 变更后的数据调整计划（bit 语义 v1）

适用于：**已上线**环境中仅类型层数值与 v1 位表不一致、或从旧「反向推断」数值迁移到本 SPEC 的情形。

1. **代码与本体**  
   - 合并与本节一致的 `graph_seed_node_types.yaml`（及各图种子 `relationship_types` 种子行）。  
   - 部署含 `ensure_graph_seed_ontology` 的后端，使 `node_types` / `relationship_types` 在启动或迁移流程中被 `ON CONFLICT DO UPDATE` 覆盖为 v1。

2. **实例层**  
   - 触发器保证新写入继承类型；已存实例依赖「类型 `trait_*` 变更 → 异步任务」路径刷副本，或执行一次性 SQL 将 `nodes`/`relationships` 按 `type_code` join 类型表对齐（与既有 backfill 脚本同一思路）。  
   - 消费/排空 `trait_sync_jobs`（若有），并对账 `trait_migration_report` / 巡检：实例与类型 trait 差异为 0。

3. **业务校验**  
   - `world validate hicampus`（及 CI 中 ontology/hicampus 相关单测）通过。  
   - 若有 Agent/API 按 mask 过滤的集成测试，更新期望 mask 常量。

4. **兼容说明**  
   - **破坏性**：与旧数值（如节点 `trait_mask` 1/3/5/7/8/9/24/33 对应旧位名）**不兼容**；迁移后须以 v1 解释为唯一真源。  
   - 文档与 YAML 任一方变更 bit 含义时，须重复本流程并记录审计日志字段（见 Observability）。

## Compatibility & Risk

### 风险点

- 类型 trait 变更可能导致大批量实例更新，产生写放大。
- 位定义由代码/文档维护，若缺少治理会出现 bit 语义冲突。
- 旧查询路径可能未接入 trait 条件，导致效果不一致。

### 缓解

- 类型变更操作增加审计与限流（管理命令层可做保护）。
- 在 `docs/ontology` 维护 bit 位分配表（版本化）。
- 引入一致性巡检任务（每日/每次迁移后）。

## Observability & Audit

- **已实现（worker）**：`trait_sync_job_done` / `trait_sync_job_failed` 结构化日志中带 `event=trait.update.type_trait_synced|trait.update.type_trait_sync_failed`，以及 payload 内 `before_/after_trait_class`、`before_/after_trait_mask`（若 job 含 payload）。与 `trait_sync_jobs.payload` 互补。
- **建议补全（类型编辑入口）**：管理侧直接改类型表时增加：
  - `trait.update.node_type` / `trait.update.relationship_type`（或等价事件名）
  - `operator`、`target_type_code`、`affected_instances`（预估或异步汇总）等字段。
- 记录方式：结构化日志（无需新增审计表）。

## Test Plan (Initial)

### Unit

- type → instance 继承：insert/update 均生效。
- 实例试图覆盖 trait 字段时被触发器改写回类型值。
- 类型 trait 变更后，实例批量同步正确。

### Integration

- 迁移后历史数据一致性检查为 0 差异。
- 迁移默认虚拟世界hicampus包并进行一致性检查为0差异
- API/命令检索按 mask 过滤结果正确。
- 关系查询在 `relationships.trait_mask` 过滤下结果稳定。

### Regression

- 现有图遍历、world seed、look/move 等路径不受 trait 字段引入破坏。

## Definition of Done

- [x] 四张表新增 `trait_class` + `trait_mask(BIGINT)`（迁移 + `database_schema.sql`）。
- [x] 实例层“继承且不可覆盖”由触发器保证；类型变更入队 + worker 最终一致。
- [x] 关键查询入口：`GET /api/v1/accounts`（`trait_class` / `required_*_mask`）、`Node.get_active_nodes`、`Relationship` 同类过滤、`NodeRepository.get_active_nodes` 透传；命令/SSH 链路按需接入。
- [x] 一致性巡检：`db/trait_migration_check.py`；图种子侧有 trait 完整性检查。
- [x] 测试：`test_trait_query_helpers`、`test_trait_migration_check`（unit）、`test_trait_inheritance`（integration，需 PostgreSQL）、位常量单测。

## Finalized Defaults

- 最终一致性同步任务执行载体：`app worker`（由应用层异步任务消费并重试）。
- 查询参数 `mask=0`：API 层统一解释为“不过滤能力”，不报错。

## Related HTTP API（初稿）

- 本体与图谱 **原子服务** REST 契约（查询/管理类型与实例时的 HTTP 语义、Problem Details、OpenAPI 约定）：[`docs/api/SPEC/features/F10_ONTOLOGY_AND_GRAPH_API.md`](../../../api/SPEC/features/F10_ONTOLOGY_AND_GRAPH_API.md)

## Suggested Next Files

- `backend/app/constants/trait_mask.py`
- `backend/db/schemas/database_schema.sql`
- `backend/db/schema_migrations.py`
- `backend/db/trait_migration_check.py`
- `backend/app/services/trait_sync_worker.py`
- `backend/tests/constants/test_trait_mask.py`
- `backend/tests/db/test_trait_inheritance.py`
