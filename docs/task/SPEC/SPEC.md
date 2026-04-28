# Task System SPEC（任务系统）

> **Architecture Role**：在 CampusWorld 中新增一条**任务语义**横切线，与 `npc_agent` 并列贯穿 L1 数据（图节点 `task`）、L2 命令（`task ...` 子命令族）、L3 思考（Agent 从任务池提取意图）、L4 经验（任务模板/剧本预留）。**默认写入路径走命令层**（与 [`docs/models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md`](../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md) §6.1 一致）；**不**改 [`backend/app/models/graph.py`](../../../backend/app/models/graph.py)。

**文档状态：Draft（v1）**

**交叉引用：**
- 命令层：[`docs/command/SPEC/features/CMD_task.md`](../../command/SPEC/features/CMD_task.md)
- 数据模型层：[`docs/models/SPEC/SPEC.md`](../../models/SPEC/SPEC.md)、[`docs/models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md`](../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)
- 数据库层：[`docs/database/SPEC/features/F01_TRAIT_CLASS_MASK_FOR_AGENT.md`](../../database/SPEC/features/F01_TRAIT_CLASS_MASK_FOR_AGENT.md)
- 授权策略：[`docs/api/SPEC/features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md`](../../api/SPEC/features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md)
- Ontology：[`docs/ontology/NODE_TYPES_SCHEMA.md`](../../ontology/NODE_TYPES_SCHEMA.md)、[`backend/db/ontology/graph_seed_node_types.yaml`](../../../backend/db/ontology/graph_seed_node_types.yaml)
- 测试守则：[`docs/testing/SPEC/SPEC.md`](../../testing/SPEC/SPEC.md)

---

## 0. 范围与产品目标

`Task System` 提供**以用户/Agent 为中心的任务语义**：

1. 每个 **User 或 NpcAgent** 拥有/被指派/可认领自己的专有任务集。
2. 任务**作用范围覆盖整个语义世界**：单房间清洁、整楼安防巡检（多区/多房/多系统/多设备）等均以同一本体表达。
3. 支持**多人/多 Agent 协作**：典型链路 *agent1 检查 → admin 审批 → agent2 执行*。
4. 支持**任务池**：Agent 可自主从池中认领任务。

v1 仅覆盖 **后端本体 + 关系表 + 命令族（SSH/REST 同源）**；前端工作台、SLA 自动驱动、跨世界联邦等留 v2（见 §10 备忘录）。

---

## 1. 设计律与契约

### 1.1 三大设计律 D1–D3

| 设计律 | 关键约束 | 业界对照 |
|---|---|---|
| **D1 边稀疏** | `task` 节点的**永久出边度恒为 O(1)**：`SCOPED_AT≤1` + `OWNED_BY≤1` + `PARENT_OF`（仅父任务持出边）+ `BLOCKED_BY` 小基数；范围内的多目标用 `scope_selector` DSL 表达，**不**为每个被作用对象建边；DSL 支持 [`trait_class` / `trait_mask`](../../database/SPEC/features/F01_TRAIT_CLASS_MASK_FOR_AGENT.md) 过滤，走位运算索引而非全表扫描 | Neo4j supernode 规避；K8s `labelSelector`；Temporal business key；ServiceNow CMDB 引用 + CI 既有关系；本仓库 [`location_id`](../../../backend/app/models/graph.py) 单父链先例与 trait_mask 位运算检索范式 |
| **D2 属性瘦 / 独立表厚** | 图节点 `nodes.attributes` 仅放 SSOT 字段与瘦摘要；详情、协作分派、状态历史、运行轨迹、事件、出站通知全部走独立关系表 | Camunda `ACT_RU_TASK` + `ACT_RU_IDENTITYLINK` + `ACT_HI_*`；JIRA / Linear / GitHub Issues；DDD 聚合根；本仓库 [`F02 §9`](../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md) `agent_memory_entries / agent_run_records / agent_long_term_memory` |
| **D3 SSOT + 单一写入路径 + 单事务原子 + 幂等** | 主状态在图节点；所有迁移经唯一服务 `task_state_machine.transition`；版本号乐观锁 + 客户端幂等键；图节点 + 关系表写入在同一 PostgreSQL 事务；事件 `event_seq` 单调 | DDD Aggregate Root；GitHub `issues.state` + `issue_events`；Camunda PVM 单入口；Stripe / AWS `Idempotency-Key`；EventStore `version` |

### 1.2 SSOT 与字段权威边界

| 字段 | 位置 | 角色 |
|---|---|---|
| `current_state` | `nodes.attributes.current_state` | **主状态 SSOT**；所有读以此为准 |
| `state_version` | `nodes.attributes.state_version`（int 单调） | 乐观并发控制版本号 |
| `workflow_ref` | `nodes.attributes.workflow_ref` (`{key, version}`) | 指向独立表 `task_workflow_definitions` 的复合引用；**创建时 pin 版本**（OQ-23），in-flight 任务不跨版本迁移；`task migrate` 留 v2 |
| `pool_id` | `nodes.attributes.pool_id`（int FK） | 单池归属，引用 [`task_pools.id`](features/F05_TASK_POOL_FIRST_CLASS_REGISTRY.md)；`assignee_kind=pool` 时必填，否则 NULL |
| `scope_selector` | `nodes.attributes.scope_selector`（jsonb DSL） | 范围声明，**late-binding**，不落边 |
| `task_state_transitions` 末条 (按 `event_seq` DESC) | 关系表 | **派生**：约束 = `current_state`（不变式 I1） |
| `task_assignments.is_active` 集合 | 关系表 | **派生**：约束 = `workflow_definition[current_state].expected_roles`（I2） |
| `task_details.*` | 关系表 1:1 | 扩展数据（无状态语义） |

### 1.3 不变式 I1–I8（契约级）

- **I1（终态对齐）** 对任意任务 T，按 `(task_node_id, event_seq DESC)` 取得的最新一条 `task_state_transitions.to_state` 必须等于 `nodes.attributes.current_state`。
- **I2（活跃分派对齐）** `task_assignments WHERE task_node_id=T AND is_active` 的角色集合 ⊆ `workflow_definition[current_state].expected_roles`。
- **I3（单一写入路径）** 所有 `current_state` 与相关派生表写入必须经 `app/services/task/task_state_machine.transition`；其他路径写视为契约违规（CI 静态检查 + 运行时日志告警）。
- **I4（版本单调）** `state_version` 与 `event_seq`（per task）严格单调递增；同 version 并发更新必失败一方。
- **I5（事务原子）** 单次状态迁移的图节点 + 关系表写入必在同一 PostgreSQL 事务；跨事务"补写"被禁止。
- **I6（幂等性）** `task_state_machine.transition(idempotency_key=K)` 在同一 `(task_node_id, K)` 上必须返回**原结果**而非重做；`task_state_transitions(idempotency_key)` 唯一约束保证；过期（> 7d）行的 `idempotency_key` 被 audit worker 置 NULL 后**不再命中**，等同于 key 已失效。
- **I7（Outbox 保留上限）** `MIN(task_outbox.created_at) ≥ now() - INTERVAL ':outbox_retention_days'`（默认 90d）；由 [`task.consistency_audit`](features/F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md#5-一致性巡检-worker) 每轮维护；允许 ±1 个巡检周期漂移。
- **I8（父子 rollup 一致性）** 对任意父任务 P，`nodes.attributes.children_summary.total = COUNT(*) FROM edges WHERE kind='PARENT_OF' AND from_node_id=P.id` 且 `SUM(children_summary.by_state.values()) = total`；由状态机服务在子任务状态事件的同事务内维护（见 [F03 §3](features/F03_TASK_COLLABORATION_WORKFLOW.md#3-单事务原子写入模板) step 6'）。

### 1.4 RBAC 权限码

注册到 [`backend/app/core/permissions.py`](../../../backend/app/core/permissions.py)，Phase B 落代码：

| 权限码 | 适用 |
|---|---|
| `task.create` | 创建任务（含设定 selector / scope） |
| `task.read` | 读取自己可见的任务（受可见性矩阵 §1.5 约束） |
| `task.update` | 修改自己 owner 的任务非状态字段 |
| `task.publish` | 发布任务到任意池（与池 `publish_acl` AND；详见 [F05](features/F05_TASK_POOL_FIRST_CLASS_REGISTRY.md)） |
| `task.claim` | 从池中认领任务（与池 `consume_acl` AND） |
| `task.assign` | 指派任务给他人（owner 或具备此权限） |
| `task.approve` | 在审批阶段批准/拒绝 |
| `task.cancel` | 取消（owner 或 admin） |
| `task.pool.admin` | 创建 / 修改 / 停用 `task_pools` 注册项；查看任意池 stats |
| `task.admin` | 跨 owner 操作、强制状态迁移、巡检读 |

**`system` 虚拟主体（OQ-28）**：

- `principal_id = 0, principal_kind = 'system'`；**非图节点**，RBAC 内预置。
- 用途：系统自动化源（传感器告警、cron 定时任务、`task.consistency_audit` worker、`task.expand_worker`）触发任务创建 / 发布 / 状态变更时使用的 actor principal。
- 默认权限：`task.create / task.publish / task.claim / task.read`；**不默认持** `task.approve / task.pool.admin / task.admin`。
- 在 `task_assignments / task_state_transitions / task_events / task_outbox` 的 `actor_principal_*` 字段中按 `(0, 'system')` 写入；审计可查询 `WHERE actor_principal_kind = 'system'` 区分人/机/系统来源。
- 不可作为 `assignee`（`task_assignments.role='executor'`），仅出现在 `actor` 列；池 ACL 评估视 `system` 为特殊白名单（`publish_acl.principal_kinds` 含 `system` 时允许）。

### 1.5 可见性谓词矩阵

`nodes.attributes.visibility` 的五个枚举与对应"列表/读取"和"池可见性"谓词：

> Phase B 说明：当前实现仅启用 `private / explicit / pool_open`。`role_scope / world_scope`
> 作为保留枚举，待后续版本启用。

| `visibility` | 列表 / 读取谓词 | 池可见性 | 典型场景 |
|---|---|---|---|
| `private` | `principal_id ∈ owner ∪ active_assignments(*)` | 不可见 | 个人备忘任务 |
| `explicit` | `principal_id ∈ owner ∪ all_assignments(history)` | 不可见 | 明确指派 |
| `role_scope` | `principal.role ∈ workflow_definition[current_state].expected_roles ∪ owner` | `role` 命中即可见 | 审批工作流 |
| `world_scope` | `principal 满足 F11 data_access(scope_anchor)` | 满足即可见 | 园区公开池 |
| `pool_open` | `world_scope` 谓词 + `assignee_kind='pool'` + `task_pools[pool_id].is_active` + `consume_acl(actor)=allow` | 通过池 `consume_acl` 即可见 | 公共认领池 |

> 谓词以伪 SQL 表达；实际由命令层装饰器与 [F11 `data_access`](../../api/SPEC/features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md) 评估；`scope_anchor` = `SCOPED_AT` 边目标节点。

### 1.6 jsonb 载荷 schema 版本约定

- 所有 jsonb 字段（`scope_selector / metadata / payload / command_trace / result_summary / graph_ops_summary / extra / checklist / sla / spec`）顶层强制 `_schema_version: int`；v1 = `1`。
- 演进规则：
  - **增字段**不升版（向前兼容）。
  - **删 / 改字段语义**须升版并提供 reader 兼容矩阵。
  - 状态机服务在写入前补默认 `_schema_version`；读取侧按版本分支解析。

### 1.7 软删除与级联策略

- v1 **禁止物理删除任务节点与关系表行**；`cancelled` / `archived` 仅状态变更；归档保留全部审计与运行记录。
- 8 张关系表外键统一 **`ON DELETE RESTRICT`**；如确需 GC，走专门 ADR + admin 命令（v2，见 §10）。

### 1.8 测试约束与性能基线

#### 1.8.1 测试覆盖

- **单元**：`task_state_machine` 全状态/事件组合矩阵（含 `publish / fail / lease_expired(v2)`）；`scope_selector` 解析器（含 `bounds`、`trait_*` 过滤、`exclude`）；`workflow_definition` 校验；`evaluate_acl` 全分支；`BLOCKED_BY` 环检测（含深度 64 兜底）。
- **集成**（PostgreSQL 真库）：I1–I8 全部不变式；乐观锁冲突；幂等键命中与 7d 过期；并发认领；同事务死锁守则（对齐 [docs/testing/SPEC/SPEC.md](../../testing/SPEC/SPEC.md)）；父子 rollup 并发；async expand worker 崩溃恢复；池 ACL 拒绝路径；池 `is_active=false` 拒绝路径；`workflow_ref` 热更新 in-flight 稳定性。
- **属性测试**（`hypothesis`）：随机事件序列对 I1–I8 的保持；selector DSL 解析等价性；`event_seq` 单调。
- **契约测试**：`POST /api/v1/command/execute` 与 SSH 双协议同源结果一致。
- **Chaos 测试**（B3-3 / OQ-30 支撑）：Jepsen-lite 注入（连接抖动、PostgreSQL 主备切换、时钟漂移 ±30s、I/O 高延迟）场景下 I1–I8 保持；`task.consistency_audit` 能够在注入恢复后发现并告警 outbox / state 漂移；async expand worker 在主备切换后 `cursor` 无重复与丢失。

#### 1.8.2 性能基线（OQ-30）

基准环境：PostgreSQL 14 + 单机 16 vCPU / 32 GB / NVMe；应用侧连接池 ≥ 32；网络 ≤ 1ms RTT。

| 场景 | 指标 | 目标 |
|---|---|---|
| `task_state_machine.transition`（热路径，单任务） | P99 | **≤ 50ms** |
| 并发 32 agent `task claim` 同任务 | 吞吐 | ≥ 200 req/s；乐观锁失败率 ≤ 3% |
| 池视图查询（§3 SQL，1M tasks + 10 pools + 订阅 3 pool_key） | P99 | ≤ 30ms |
| `scope_selector` 解析 10k 目标（typical trait_class + mask 过滤） | 端到端 | ≤ 200ms |
| 异步 expand（N=4000 子任务，batch_size=100） | 全量完成 | ≤ 120s；worker 崩溃恢复 RTO ≤ 10s |
| `task_outbox` GC（删除 100k 行） | 耗时 | ≤ 5s（audit 周期内完成） |

**上线门槛**：Phase B 发布前跑一次完整基准；任一目标劣化 > 30%（相对前一次基准）阻塞上线，需附 ADR 说明。基准脚本：`backend/tests/bench/task_bench.py`（Phase B 新建）。

---

## 2. 术语

| 术语 | 含义 |
|------|------|
| **`task`** | 图 `type_code`；任务节点本体，瘦属性 + SSOT。 |
| **`scope_anchor`** | `SCOPED_AT` 边唯一目标，定义任务作用范围的根节点（`room` / `building_floor` / `building` / `logical_zone` / `world` / 设备）。 |
| **`scope_selector`** | jsonb DSL，late-binding 解析任务作用对象集合，不落边。 |
| **`workflow_definition`** | 独立表中的状态机定义；按 `(key, version)` 复合引用。 |
| **`current_state`** | 任务主状态，SSOT 落在图节点 attributes。 |
| **`event_seq`** | per-task 单调事件序号，用于 `task_state_transitions` 排序与重放。 |
| **`idempotency_key`** | 客户端供给的幂等键；`(task_node_id, idempotency_key)` 唯一。 |
| **`assignment role`** | `owner / assignee / approver / reviewer / observer / executor`，多人协作识别角色。 |
| **`pool`** | `task_pools` 一等注册项（`key / display_name / acl / 默认值`，详见 [F05](features/F05_TASK_POOL_FIRST_CLASS_REGISTRY.md)）；池可见性 = `assignee_kind=pool ∧ pool_id 命中 ∧ is_active ∧ 无 active executor ∧ consume_acl 通过`。 |
| **`pool_key`** | `task_pools.key`，遵循 `<scope>.<domain>[.<sub>]` 命名；同时是未来 MQ 路由键。 |
| **`Outbox`** | `task_outbox` 表，与状态机同事务写入的出站事件，留 MQ 接入扩展点。 |

---

## 3. Feature 索引

- **F01** 任务本体与节点类型 — [`features/F01_TASK_ONTOLOGY_AND_NODE_TYPES.md`](features/F01_TASK_ONTOLOGY_AND_NODE_TYPES.md)
- **F02** 任务池查询与认领协议 — [`features/F02_TASK_POOL_AND_CLAIM_PROTOCOL.md`](features/F02_TASK_POOL_AND_CLAIM_PROTOCOL.md)
- **F03** 协作状态机与审批 — [`features/F03_TASK_COLLABORATION_WORKFLOW.md`](features/F03_TASK_COLLABORATION_WORKFLOW.md)
- **F04** 关系子底座与观测 — [`features/F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md`](features/F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md)
- **F05** 任务池一等注册与治理（v1 起一等实体；MQ-ready） — [`features/F05_TASK_POOL_FIRST_CLASS_REGISTRY.md`](features/F05_TASK_POOL_FIRST_CLASS_REGISTRY.md)

---

## 4. 范围 / Non-Goals（v1）

### 4.1 In-Scope

- 后端本体（瘦节点 + selector DSL + late-binding）
- 8 张关系表（含独立 workflow 定义表 + **`task_pools` 一等池注册表** + Outbox）
- 统一状态机服务（含 `idempotency_key` + `correlation_id/trace_id` 注入 + Outbox 同事务）
- 命令族（含 bulk 逐个 transition 子命令；`task pool *` 治理子命令；`task publish`）
- `POST /api/v1/command/execute` 与 SSH 双协议路径
- Agent 接单契约（`subscription_bindings.kind=pool, pool_key=<task_pools.key>`，支持 `*` 通配）
- 池治理：`publish_acl` / `consume_acl` / 默认值合并 / `is_active` 软停用
- 审批接力链路（agent1 → admin → agent2）
- 单事务一致性、I1–I8 不变式（含 Outbox 保留与父子 rollup）
- `fail / failed` 执行失败终态（OQ-20），与审批 `reject / rejected` 语义分离
- `workflow_ref` 版本 pin（OQ-23），in-flight 任务不漂移
- `task_outbox` 90d retention + audit GC（OQ-22）
- `idempotency_key` 7d TTL 与过期回收（OQ-26）
- `scope_selector.bounds` 解析结果数量护栏
- `BLOCKED_BY` 环检测
- `children_summary` 父任务瘦摘要（I8）
- 异步 expand（> 50 子任务）复用 `task_runs(phase='expansion')`
- `system` 虚拟主体（OQ-28）与 RBAC 默认权限
- 巡检 worker（**仅检测，不自愈**）
- 运行记录与审计
- 可见性矩阵、权限码、jsonb schema 版本、软删策略

### 4.2 Out-of-Scope

- 前端工作台视图、图形化 workflow 编辑器
- SLA 自动驱动（`due_at` 仅记录，不触发状态机）
- 跨世界任务联邦
- 独立 REST 资源路由（`/tasks/*`，v2）
- 自动自愈一致性
- Outbox 消费者 / MQ 接入（`task_pools.key` 已为路由键预留）
- 池配额 `quota` 运行时执行（v1 仅字段保留）
- 向量化任务检索 / GraphRAG 整合
- 审批委托（仅文档化钩子点，无表无字段）
- token-bucket 抢单公平性
- CQRS 读侧投影
- `task_template` 节点类型
- `task_comments` 评论流

### 4.3 Non-Goals

- 不引入新队列中间件
- 不新增通用 BPMN 引擎；状态机以 workflow_definition + 命令分支表达
- 不引入触发器 / 物化视图维护派生字段；应用层维护
- 不引入物理删除路径

---

## 5. 默认写入路径

```
用户/Agent
  → 命令层（SSH / POST /command/execute）
  → CommandContext（principal + correlation/trace 注入）
  → app/services/task/task_state_machine.transition(...)
  → 单事务：
      1) 幂等键命中检查
      2) FOR UPDATE 锁 nodes
      3) 校验 (current_state, event) ∈ workflow_definition；校验 expected_version
      4) 取 per-task event_seq = MAX+1
      5) UPDATE nodes.attributes (current_state, state_version)
      6) UPDATE/INSERT task_assignments
      7) INSERT task_state_transitions（含 event_seq, idempotency_key, correlation/trace）
      8) INSERT task_outbox（同事务出站事件）
  → 命令层返回 TransitionResult
```

加锁顺序固定：**`nodes` → `task_assignments` → `task_state_transitions`**，对齐 [`docs/testing/SPEC/SPEC.md`](../../testing/SPEC/SPEC.md) 死锁守则。

---

## 6. 分期实现

| 阶段 | 内容 |
|------|------|
| **Phase A** | 本 SPEC 评审定稿（含 5 份 feature + ACCEPTANCE + TODO + CMD_task + 交叉引用补段）。 |
| **Phase B** | `graph_seed_node_types.yaml` 注册 `task`；迁移新建 8 张关系表（含 `task_pools`）；seed `hicampus.cleaning / hicampus.security / hicampus.maintenance` 三池；注册 RBAC 权限码（含 `task.publish` / `task.pool.admin`）；实现 `task_state_machine.transition`（最小事件集 `create/publish/claim/assign/complete` + ACL 校验）；实现命令 `task create / list / show / claim / assign / complete / publish / pool list/show/create` + 单元测试 + 覆盖 I1/I2/I4/I6 + 乐观锁冲突 + ACL 拒绝路径的集成测试。 |
| **Phase C** | 状态机扩展事件 `submit-review / approve / reject / handoff / cancel / expand`；`npc_agent` 订阅 `kind=pool, pool_key=<task_pools.key>` 含 `*` 通配；selector 解析器 + late-binding freeze；`task.consistency_audit` 巡检 worker；structlog 事件 + 集成测试覆盖 `agent1 → admin → agent2` + 池切换；属性测试；Bulk 命令 `task bulk-approve / bulk-claim`；`task pool stats` 聚合实现。 |

---

## 7. 文档级 ACCEPTANCE（详见 [`ACCEPTANCE.md`](ACCEPTANCE.md)）

- [ ] 设计律 D1–D3、SSOT 字段表、I1–I6 不变式经评审无异议。
- [ ] 8 张表 DDL（F04，含 `task_pools`）评审通过；字段命名与本仓库约定（`agent_run_records / agent_memory_entries`）一致。
- [ ] F05 池一等模型（注册、ACL、默认值、`is_active`、`pool_key` MQ 路由键预留）评审通过；`task` 节点 `pool_id` 替换历史 `pool_tags` 草案。
- [ ] 可见性矩阵 §1.5 与 [F11 `data_access`](../../api/SPEC/features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md) 表达式无冲突。
- [ ] 审批接力链路示例（F03）与 `task_assignments + task_state_transitions` 写入顺序自洽。
- [ ] 命令族（CMD_task）与统一状态机入口约束一致；只读命令不经状态机。
- [ ] 与 [F02 npc_agent](../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md) `triggers / subscription_bindings` 接单契约自洽。

---

## 8. 设计决策（Why）

1. **为何不用 `TARGETS` 多边边表达任务作用对象？** 单"楼宇巡检"任务可达 O(10²–10³) 个对象，多任务后产生 supernode/edge-explosion；改用 `SCOPED_AT` 单锚 + `scope_selector` DSL 后，任务节点边度恒 O(1)，作用对象在查询时由 `location_id` 单父链 + `type_code` / `trait_class` / `trait_mask`（[F01 trait](../../database/SPEC/features/F01_TRAIT_CLASS_MASK_FOR_AGENT.md) 位运算）联合索引推导（参考 K8s labelSelector、Neo4j supernode 规避）。selector 的 `trait_mask_all_of / trait_mask_any_of` 子句让"楼宇内全部可控设备"等典型查询从枚举 N 个 `type_code` 退化为单次 `(trait_mask & :m)` 位运算扫描。
2. **为何主状态 SSOT 在图节点而非 `task_state_transitions`？** 图节点是聚合根，所有读以"当前态"为主语；事件流是审计与回放底座。等同于 GitHub Issues `issues.state` + `issue_events` 模式（事件可重建主状态，但主状态是 SSOT）。
3. **为何引入幂等键 + per-task `event_seq`？** 命令层与 Agent 自动重试不可避免；幂等键与单调序号是 Stripe/AWS/EventStore 的工业级一致性标配。
4. **为何 workflow 定义在独立表而非节点 attributes？** 工作流热更新与版本治理是高频运维需求；独立表带 `(key, version, is_active)` 提供版本演进；与 Camunda / Temporal / Argo 实践一致。
5. **为何 group 委派走纯标签？** v1 不引入 `account_group` 节点类型，避免新增本体复杂度；标签可与未来 RBAC 角色直接对齐。
6. **为何 v1 不实现 Outbox 消费者？** Schema 先行（同事务写入）即提供 exactly-once 接入点；消费者随 MQ 选型（Debezium / 内建 worker）一并 v2 决定，避免锁定。
7. **为何父子任务 rollup 默认手动？** 自动 rollup 在事务边界、并发、异常补偿上引入大量复杂性（参考 JIRA epic / Linear 子 issue 的多年迭代）；v1 显式手动，可选自动 rollup 留作 workflow_definition opt-in 扩展。
8. **为何 v1 即把池升格为一等实体（F05）而不沿用 jsonb tag？** 新构建无需考虑兼容性；池本身需要承载 ACL（发布/认领分别治理）、默认值（workflow / visibility / priority）、生命周期（`is_active` 软停用）与未来 MQ 路由键。jsonb tag 模型让以上能力散落到查询拼装与命令分支，治理面无法收拢；一等表是 Camunda topic / Kafka topic / SQS queue / Pub/Sub topic 的工业惯例，dispatcher 接入零迁移成本。任务与池采取**1:N 单池归属**（与 Camunda External Task topic、Kafka topic 一致）；多业务域语义经"父任务多池子任务"组合表达，避免 ACL/默认值合并复杂性。

---

## 9. 业界类比

- **Camunda BPMN**：`ACT_RU_TASK` SSOT + `ACT_RU_IDENTITYLINK` 多人协作 + `ACT_HI_*` 审计 + PVM 单入口 ≈ 本 SPEC 的 `nodes(task)` + `task_assignments` + `task_state_transitions` + `task_state_machine`。
- **Temporal.io**：Workflow Execution state 在持久层 + Activity 引用业务实体 + 幂等性与事件溯源 ≈ 本 SPEC 的状态机 + `idempotency_key` + `event_seq` 重放。
- **GitHub Issues / Linear / JIRA**：`issues.state` SSOT + `issue_events` append-only + 单事务多表写 ≈ 本 SPEC 的图节点 + 关系表 + 单事务模板。
- **ServiceNow**：`task` 父表继承 + `assignment_group` + CMDB CI 引用 ≈ 本 SPEC 的 `task` 节点 + `principal_kind=group` 标签 + `SCOPED_AT` 锚点。
- **Kubernetes**：`labelSelector` 的 late-binding 解析 ≈ 本 SPEC 的 `scope_selector`。
- **Stripe / AWS API**：`Idempotency-Key` 头 ≈ 本 SPEC 的 `idempotency_key` 列与 I6。
- **Outbox Pattern**（Debezium / EventStore）：与业务事务同表 + `dispatched_at` 标记 ≈ 本 SPEC 的 `task_outbox`。

---

## 10. Open Questions / 备忘录

### 10.1 已答复决策（已并入设计，留索引）

- **OQ-11 → 决策**：workflow 定义采用独立表 `task_workflow_definitions`（已并入 F04）。
- **OQ-23 → 决策**：`workflow_ref` 在 `task create` 时 pin 到当时 `is_active` 的最大版本；in-flight 任务不随热更新迁移（已并入 F01 属性表 + F03 §2.4）。
- **OQ-12 → 决策**：`principal_kind=group` 采用纯标签 `principal_tag`（已并入 F04 DDL 与 CHECK 约束）。
- **OQ-13 → 决策**：审批委托 v1 仅文档化钩子点；未来表与服务方法见 §10.2。
- **OQ-14 → 决策**：Bulk 操作采用逐个 transition + 错误聚合返回（已并入 F02 / CMD_task）。
- **OQ-15 → 决策**：SLA v1 仅 `due_at` 记录，不驱动状态机（已并入 F01 属性辞典）。
- **OQ-16 → 决策**：状态变更通过 `task_outbox` 同事务记录（已并入 F03 模板与 F04 DDL）；MQ 接入留 v2。
- **OQ-17 → 决策**：可见性枚举与谓词矩阵已写入 §1.5。
- **OQ-18 → 决策**：池升格为一等实体 `task_pools`（v1 起，不考虑兼容性，详见 [F05](features/F05_TASK_POOL_FIRST_CLASS_REGISTRY.md)）；任务与池为 1:N 单池归属；`pool_key` 同时是未来 MQ 路由键。
- **OQ-20 → 决策**：新增 `fail` 事件与 `failed` 终态，与 `reject`（审批驳回）语义分离（已并入 F03 §2.1–2.3、CMD_task、F04 事件名清单）。
- **OQ-21 → 决策**：`expand` 阈值 50 同步，> 50 走异步协议；复用 `task_runs(phase='expansion')` 不新增表（已并入 F01 §5.1/§5.2、F04 §3.5）。
- **OQ-22 → 决策**：`task_outbox` 默认 90d retention，由 `task.consistency_audit` 兼职 GC（已并入 F04 §3.7.1 与 §5）。
- **OQ-24 → 决策**：保留 `task_state_transitions` 与 `task_events` 双表（写侧审计 vs 读侧可观测）。
- **OQ-25 → 决策**：不引入 DB 触发器防御 I1，靠 CI 静态检查 + 运行时 audit worker + 日志告警。
- **OQ-26 → 决策**：`idempotency_key` 默认 7d TTL，过期由 audit worker 置 NULL 保留审计行（已并入 F04 §3.4.1）。
- **OQ-27 → 决策**：池 ACL 沿用 hardcoded schema；policy engine 升级留 v2。
- **OQ-28 → 决策**：`principal_id=0, principal_kind='system'` 虚拟主体，非图节点；RBAC 内默认持 `task.publish / task.create / task.claim` 为系统自动化源（已并入 §1.4 与 F05 §4）。
- **OQ-29 → 决策**：小规模部署 v1 不分区；v1 仅文档化升规模迁移指南（F04 §10）。
- **OQ-30 → 决策**：性能基线 `task_state_machine.transition` P99 ≤ 50ms（PG 14 单机 16 vCPU）；并发 32 claim 同任务 ≥ 200 req/s；selector 10k 目标 ≤ 200ms（已并入 §1.8 与 ACCEPTANCE Phase B）。

### 10.2 未来扩展（v2+ 候选）

- **Lease / Heartbeat 启用**（OQ-19 方案 B 字段已预留于 `task_assignments`）：Phase C 实现 `heartbeat / lease_expired` 事件与 audit 自动释放。
- **`task migrate`** 跨 workflow 版本迁移（OQ-23 占位）：校验新版本状态/事件超集兼容；写 `task_state_transitions(event='migrate')`。
- **`retry` 一等事件** `failed → open` 带 `retry_attempt` 与 `max_retries`。
- **`suspended / paused` 状态** 运维暂停单任务。
- **DB 级 I1 / I8 触发器防御**（OQ-25 v1 暂不引入）：若一致性事故频发再评估。
- **池配额执行** `task_pools.quota`（v1 字段保留，运行时不生效）。
- **池 consumer group / 分片键** 解决多 agent 订阅同 pool_key 的热点竞争。
- **池 ACL policy engine 升级**（OQ-27 v1 沿用 hardcoded schema）：整合 OPA / Casbin 表达式。
- **`task_snapshots` 快照回放加速** 每 K 事件一次 snapshot，长任务重放 O(1)。
- **Audit tamper-proof hash chain** `task_state_transitions.prev_hash` 链式校验。
- **表分区迁移**（OQ-29 触发阈值见 [F04 §10](features/F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md#10-升规模分区迁移指南oq-29)）。
- **审批委托** `task_approval_delegations(delegator_id, delegatee_id, scope, valid_from, valid_to)`；钩子点：`task_state_machine._resolve_effective_principal_for_event(event='approve', actor=...)`。
- **Outbox 消费者** / Debezium / 内部 dispatcher worker，按 `dispatched_at IS NULL` 拉取，按 `task_outbox.pool_key` 路由到 MQ 主题（无池任务走默认 `task.system`）。
- **池配额执行**：`task_pools.quota`（`max_inflight / max_pending / max_publish_rate`）的运行时检查（v1 仅字段）。
- **池间合并 / 拆分迁移工具**：admin CLI 自动调整 `pool_id`，附迁移审计。
- **SLA 引擎** cron worker + 状态机事件 `time.elapsed`；驱动 `escalate / overdue` 状态。
- **Token-bucket 公平性**：池抢占节流，防单 agent 抢占。
- **`task_template` 节点类型**：可复用任务剧本，与 `node_types` 类型系统集成。
- **`task_comments` 评论流**：Markdown 渲染、@mention、附件。
- **多语言任务内容**：`task_details_i18n(task_node_id, locale, title, description_md)`。
- **任务依赖 DAG**：`BLOCKED_BY` 之外的并发分支与汇合节点。
- **跨世界任务联邦**：跨 hicampus / campus_life 任务接力。
- **向量化任务检索 / GraphRAG 整合**：与 [F06 CampusLibrary](../../models/SPEC/features/F06_CAMPUSLIBRARY_KNOWLEDGE_WORLD.md) 的语义搜索拼接。
- **自愈式一致性修复**：巡检从"检测"升级为"补偿事务"。
- **CQRS 读侧投影**：`user_task_inbox` 等预聚合表，加速大用户待办列表。
- **bulk 事务化变体**：少数场景需强一致；需新设计避免锁爆炸。
- **Notification fan-out 适配器**：Slack / 邮件 / WebSocket 推送。
- **`PARENT_OF` 自动 rollup**：作为 workflow_definition opt-in 行为。
- **审计长保留与冷归档**：`task_state_transitions` 分区表 + 冷数据归档策略。
- **图节点物理删除路径**：admin GC 命令 + 关系表 ON DELETE CASCADE 变体（需专门 ADR）。

### 10.3 v1 仍待评审的细节项

- `trait_class=TASK` 位图编号需与 [`backend/app/constants/trait_mask.py`](../../../backend/app/constants/trait_mask.py) 评审确定。
- `state_version` 字段名 vs 统一 `_revision` 命名习惯。
- `TARGETS_PINNED` 上限 8 是否合理（F01）。
- 巡检 worker 默认频率（建议 60s）与对大规模任务表的扫描成本。
- `correlation_id` / `trace_id` 与 [`app/core/log/`](../../../backend/app/core/log/) 已有上下文字段名对齐评审。
- jsonb `_schema_version` 是统一字段名还是允许各 schema 自定义（建议统一）。

---

## 11. 相关文档

- 详细本体与节点类型：[`features/F01_TASK_ONTOLOGY_AND_NODE_TYPES.md`](features/F01_TASK_ONTOLOGY_AND_NODE_TYPES.md)
- 任务池查询与认领协议：[`features/F02_TASK_POOL_AND_CLAIM_PROTOCOL.md`](features/F02_TASK_POOL_AND_CLAIM_PROTOCOL.md)
- 协作状态机与审批：[`features/F03_TASK_COLLABORATION_WORKFLOW.md`](features/F03_TASK_COLLABORATION_WORKFLOW.md)
- 关系子底座与观测：[`features/F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md`](features/F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md)
- 任务池一等注册与治理：[`features/F05_TASK_POOL_FIRST_CLASS_REGISTRY.md`](features/F05_TASK_POOL_FIRST_CLASS_REGISTRY.md)
- 命令族：[`docs/command/SPEC/features/CMD_task.md`](../../command/SPEC/features/CMD_task.md)
- 接受度清单：[`ACCEPTANCE.md`](ACCEPTANCE.md)
- 实施 TODO：[`TODO.md`](TODO.md)
