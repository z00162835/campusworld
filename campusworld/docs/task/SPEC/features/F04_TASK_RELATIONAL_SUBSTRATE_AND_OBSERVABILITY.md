# F04 — 关系子底座与观测

> **Architecture Role：** 承载任务系统的"独立关系表厚"层（D2）：详情、协作分派、状态历史、运行轨迹、事件流、出站通知与 workflow 定义全部走专用表，与图节点 SSOT（[F01](F01_TASK_ONTOLOGY_AND_NODE_TYPES.md)）通过单事务（[F03](F03_TASK_COLLABORATION_WORKFLOW.md) §3）保持一致。本文件给出 7 张表的 DDL 草案、索引、CHECK 约束、巡检 worker 与事件回放契约。
>
> **依赖：** [`SPEC.md`](../SPEC.md) §1.2 SSOT 表、§1.3 I1–I6、§1.6 schema 版本、§1.7 软删、[`F03`](F03_TASK_COLLABORATION_WORKFLOW.md) 状态机入口。

**文档状态：Draft（v1）**

---

## 1. Goal

- 8 张关系表的 DDL 与字段命名稿（与本仓库 `agent_run_records / agent_memory_entries` 模式同形）。
- 索引、唯一约束（`event_seq` / `idempotency_key`）、CHECK 约束（group 标签互斥、池归属互斥）。
- 一致性巡检 worker 设计（v1 仅检测）。
- 事件回放契约（事件溯源式恢复，运维路径）。
- 出站事件 Outbox（v1 写无消费者；负载含 `pool_key` 为 v2 MQ 接入预留路由键）。

## 2. 表清单

| 表 | 角色 | 行级别 |
|---|---|---|
| `task_workflow_definitions` | 状态机定义（独立表，决策 11） | per (key, version) |
| `task_pools` | **池一等注册与治理**（[F05](F05_TASK_POOL_FIRST_CLASS_REGISTRY.md)） | per pool |
| `task_details` | 任务厚详情（1:1） | per task |
| `task_assignments` | 多人协作分派（M:N，对齐 Camunda IdentityLink） | per assignment row |
| `task_state_transitions` | 状态变迁审计（append-only） | per event |
| `task_runs` | PDCA 阶段轨迹（对齐 `agent_run_records`） | per run |
| `task_events` | 观测事件流 | per event |
| `task_outbox` | 出站通知（决策 16，v1 写无消费者） | per outgoing event |

## 3. DDL 草案

> Phase B 落地为 alembic 迁移；字段类型与命名应在迁移评审中最终确定。所有 `*_jsonb` 列要求顶层 `_schema_version: int`（[SPEC §1.6](../SPEC.md#16-jsonb-载荷-schema-版本约定)）。所有 FK 默认 **`ON DELETE RESTRICT`**（[SPEC §1.7](../SPEC.md#17-软删除与级联策略)）。

### 3.1 `task_workflow_definitions`

```sql
CREATE TABLE task_workflow_definitions (
  id          BIGSERIAL PRIMARY KEY,
  key         VARCHAR(64) NOT NULL,
  version     INT NOT NULL,
  spec        JSONB NOT NULL,                         -- _schema_version + states/events/...
  is_active   BOOLEAN NOT NULL DEFAULT true,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  description TEXT,
  UNIQUE (key, version)
);

CREATE INDEX idx_task_workflow_def_active
  ON task_workflow_definitions (key) WHERE is_active;
```

`spec` 形态见 [F03 §2.3](F03_TASK_COLLABORATION_WORKFLOW.md#23-workflow_definition-行seed-写入-f04-3-task_workflow_definitions)。

### 3.2 `task_details`

```sql
CREATE TABLE task_details (
  task_node_id   BIGINT PRIMARY KEY REFERENCES nodes(id) ON DELETE RESTRICT,
  description_md TEXT,
  checklist      JSONB,           -- _schema_version + items[]
  sla            JSONB,           -- _schema_version + due_at/escalations（v1 仅记录）
  tags           TEXT[],
  extra          JSONB,           -- _schema_version 自定义扩展
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

> 任务节点的 `nodes.attributes.tags` 与 `task_details.tags` 重复字段说明：
> - `nodes.attributes.tags` 用于**池家族过滤、可见性、selector**（瘦摘要）。
> - `task_details.tags` 用于**用户级业务标签**（自由命名、可富文本）。
> - v1 由命令层显式分别维护；不引入派生同步。

### 3.3 `task_assignments`

```sql
CREATE TABLE task_assignments (
  id                BIGSERIAL PRIMARY KEY,
  task_node_id      BIGINT NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
  principal_id      BIGINT NULL,                 -- account/npc_agent node id；group 时 NULL
  principal_kind    VARCHAR(16) NOT NULL,        -- user|agent|group|system
  principal_tag     TEXT NULL,                   -- 决策 12：principal_kind='group' 时必填
  role              VARCHAR(32) NOT NULL,        -- owner|assignee|approver|reviewer|observer|executor
  stage             VARCHAR(32) NOT NULL,        -- <derived from current_state>
  is_active         BOOLEAN NOT NULL DEFAULT true,
  assigned_by       BIGINT NULL,
  assigned_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  released_at       TIMESTAMPTZ NULL,
  lease_expires_at  TIMESTAMPTZ NULL,            -- OQ-19 B：v1 预留不使能；Phase C claim 时写入
  last_heartbeat_at TIMESTAMPTZ NULL,            -- OQ-19 B：v1 预留不使能
  CONSTRAINT chk_task_assignments_principal_shape CHECK (
    (principal_kind = 'group' AND principal_tag IS NOT NULL AND principal_id IS NULL)
    OR
    (principal_kind <> 'group' AND principal_tag IS NULL AND principal_id IS NOT NULL)
  )
);

CREATE INDEX idx_task_assignments_principal_active
  ON task_assignments (principal_id, is_active)
  WHERE principal_id IS NOT NULL;

CREATE INDEX idx_task_assignments_principal_tag_active
  ON task_assignments (principal_tag, is_active)
  WHERE principal_tag IS NOT NULL;

CREATE INDEX idx_task_assignments_task_role_stage
  ON task_assignments (task_node_id, role, stage);

CREATE INDEX idx_task_assignments_stage_active
  ON task_assignments (stage, is_active);

-- OQ-19 B 预留：Phase C 启用 lease 检测
CREATE INDEX idx_task_assignments_lease_expiring
  ON task_assignments (lease_expires_at)
  WHERE is_active AND role = 'executor' AND lease_expires_at IS NOT NULL;
```

> `stage` 派生自 `nodes.attributes.current_state`，由状态机服务在迁移时统一更新；外部禁直写。
>
> **`lease_expires_at` / `last_heartbeat_at`（OQ-19 方案 B）**：v1 这两列**一律写入 NULL**；命令层 `task claim` 不设置 lease；audit worker 不做过期检测。Phase C 启用时：`claim` 事件将同事务写入 `now() + workflow_definition.claim_ttl`（默认 15min），audit worker 增 `lease_expired` 检测项，发现 `lease_expires_at < now() AND is_active` 时驱动 `claimed → open` 的 `lease_expired` 事件、`is_active=false`。v1 预留字段的目的：避免 Phase C 再次 ALTER TABLE 加列造成线上迁移停机。

### 3.4 `task_state_transitions`

```sql
CREATE TABLE task_state_transitions (
  id                       BIGSERIAL PRIMARY KEY,
  task_node_id             BIGINT NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
  event_seq                INT NOT NULL,                       -- per-task 单调（I4）
  idempotency_key          TEXT NULL,                          -- I6；过期后由 audit worker 置 NULL
  idempotency_expires_at   TIMESTAMPTZ NULL,                   -- OQ-26：idempotency_key 非 NULL 时必填，默认 now()+7d
  from_state               VARCHAR(32) NOT NULL,
  to_state                 VARCHAR(32) NOT NULL,
  event                    VARCHAR(32) NOT NULL,
  actor_principal_id       BIGINT NULL,
  actor_principal_kind     VARCHAR(16) NOT NULL,               -- user|agent|system|api_key
  stage                    VARCHAR(32) NOT NULL,
  reason                   TEXT,
  correlation_id           TEXT NULL,
  trace_id                 TEXT NULL,
  metadata                 JSONB,                              -- _schema_version + side_effects 摘要
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_task_transitions_event_seq
    UNIQUE (task_node_id, event_seq),
  CONSTRAINT chk_task_transitions_idem_shape CHECK (
    (idempotency_key IS NULL AND idempotency_expires_at IS NULL)
    OR
    (idempotency_key IS NOT NULL AND idempotency_expires_at IS NOT NULL)
  )
);

CREATE UNIQUE INDEX uq_task_transitions_idempotency
  ON task_state_transitions (task_node_id, idempotency_key)
  WHERE idempotency_key IS NOT NULL;

CREATE INDEX idx_task_transitions_task_seq_desc
  ON task_state_transitions (task_node_id, event_seq DESC);

CREATE INDEX idx_task_transitions_correlation
  ON task_state_transitions (correlation_id) WHERE correlation_id IS NOT NULL;

-- OQ-26：idempotency TTL 清理用
CREATE INDEX idx_task_transitions_idem_expiring
  ON task_state_transitions (idempotency_expires_at)
  WHERE idempotency_key IS NOT NULL;
```

#### 3.4.1 Idempotency TTL（OQ-26）

- `task_state_machine.transition` 写入时，若调用者提供 `idempotency_key` 非 NULL：
  - `idempotency_expires_at = now() + INTERVAL ':idempotency_ttl'`（默认 **7d**，可配置）。
- `IdempotentReplay` 命中判定仅看"行存在 + `idempotency_key` 非 NULL"；过期行 `idempotency_key = NULL` 后**不再命中**（相当于 key 已失效，调用方必须用新 key）。
- **清理路径**（audit worker 每轮执行）：
  ```sql
  UPDATE task_state_transitions
     SET idempotency_key = NULL, idempotency_expires_at = NULL
   WHERE idempotency_key IS NOT NULL
     AND idempotency_expires_at < now()
   RETURNING id;
  ```
  批量清理后写 1 行 `task_events(kind='task.idempotency_expired', payload={count, window_end})`。
- **对业界的对齐**：Stripe 24h、AWS SDK 24h、主流 SaaS API 72h–7d；7d 覆盖绝大多数重试窗口且避免表膨胀。
- **调用方语义**：重试必须在 TTL 内完成，超过 TTL 再提交旧 key 视为新请求（与 Stripe `idempotency_key_expiration` 行为一致）。

### 3.5 `task_runs`

```sql
CREATE TABLE task_runs (
  id                    BIGSERIAL PRIMARY KEY,
  task_node_id          BIGINT NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
  actor_principal_id    BIGINT NULL,
  actor_principal_kind  VARCHAR(16) NOT NULL,
  phase                 VARCHAR(32) NOT NULL,             -- plan|do|check|act|expansion
  status                VARCHAR(32) NOT NULL,             -- running|success|failed|cancelled
  command_trace         JSONB,                            -- _schema_version + [{command, args}]
  result_summary        JSONB,                            -- _schema_version
  graph_ops_summary     JSONB,                            -- _schema_version + resolved_targets[] (selector freeze)
  extra                 JSONB,                            -- _schema_version 扩展：expansion_state 等
  correlation_id        TEXT NULL,
  trace_id              TEXT NULL,
  started_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at              TIMESTAMPTZ NULL
);

CREATE INDEX idx_task_runs_task_started
  ON task_runs (task_node_id, started_at DESC);

CREATE INDEX idx_task_runs_phase_status
  ON task_runs (phase, status) WHERE status = 'running';

CREATE INDEX idx_task_runs_correlation
  ON task_runs (correlation_id) WHERE correlation_id IS NOT NULL;
```

`phase` 合法值：

| phase | 含义 |
|---|---|
| `plan` / `do` / `check` / `act` | PDCA 执行轨迹（对齐 `agent_run_records.phase`） |
| `expansion` | 异步子任务物化（OQ-21，由 `task expand` 在 > 50 子任务时切换；详见 [F01 §5.2](F01_TASK_ONTOLOGY_AND_NODE_TYPES.md#52-大范围-expand-的异步协议)） |

`graph_ops_summary` 推荐结构：

```json
{
  "_schema_version": 1,
  "affected_node_ids": [4711, 4712],
  "affected_relationship_ids": [],
  "resolved_targets": [
    {"node_id": 4711, "type_code": "lighting_fixture", "resolved_at": "2026-04-28T01:23:45Z"}
  ],
  "notes": "selector freeze at run start"
}
```

`extra` 推荐结构（`phase='expansion'` 专用）：

```json
{
  "_schema_version": 1,
  "expansion_state": {
    "total_planned": 4000,
    "created": 1200,
    "failed": 3,
    "cursor": "room:4711|device:17",
    "batch_size": 100,
    "last_batch_at": "2026-04-28T01:25:12Z",
    "error_samples": [{"target": "device:99", "error": "NodeNotFound"}]
  }
}
```

> 复用约定（OQ-21）：异步 expand 不新建表，以单行 `task_runs(phase='expansion')` + 应用层 `UPDATE ... WHERE id=:run_id` 推进 `extra.expansion_state.cursor`；每批次独立事务；完成后 `status='success'` 或 `status='failed'`（`extra.expansion_state.error_samples` 保留最多 16 条）。

### 3.6 `task_events`

```sql
CREATE TABLE task_events (
  id                    BIGSERIAL PRIMARY KEY,
  task_node_id          BIGINT NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
  kind                  VARCHAR(64) NOT NULL,             -- task.created/claimed/.../consistency_drift
  actor_principal_id    BIGINT NULL,
  actor_principal_kind  VARCHAR(16) NULL,
  payload               JSONB,                            -- _schema_version + touched_nodes[] 等
  correlation_id        TEXT NULL,
  trace_id              TEXT NULL,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_task_events_task_created
  ON task_events (task_node_id, created_at DESC);

CREATE INDEX idx_task_events_kind_created
  ON task_events (kind, created_at DESC);
```

事件名清单（与 structlog / 未来指标对齐）：

```
task.created              — 创建（state=draft 或直接 open）
task.opened               — draft → open
task.published            — 发布到池（pool_id 变更）
task.claimed              — 认领成功
task.assigned             — 指派成功
task.started              — 开工
task.review_submitted     — 提交审批
task.approved             — 审批通过
task.rejected             — 审批驳回（approver 语义）
task.failed               — 执行失败（OQ-20 新增事件）
task.handoff              — 交接执行人
task.completed            — 完成
task.cancelled            — 取消
task.state_changed        — 通用兜底（payload 含 from/to/event）
task.expansion_started    — 异步 expand 开始（OQ-21，> 50 子任务场景）
task.expansion_progressed — 异步 expand 批次进度（cursor 推进）
task.expansion_completed  — 异步 expand 全部完成
task.expansion_failed     — 异步 expand 失败（含 partial）
task.children_rolled_up   — 父任务 children_summary 更新（I8）
task.consistency_drift    — 巡检发现不一致
task.outbox_gc            — Outbox GC 完成（I7 维护）
task.outbox_pending       — Outbox 长时间未消费（v2 dispatcher 报告）
task.idempotency_expired  — idempotency_key 过期批次清理（B2-4）
```

### 3.7 `task_outbox`

```sql
CREATE TABLE task_outbox (
  id              BIGSERIAL PRIMARY KEY,
  task_node_id    BIGINT NOT NULL REFERENCES nodes(id) ON DELETE RESTRICT,
  pool_key        VARCHAR(64) NULL,                      -- v2 MQ 路由键预留；非池任务可为 'task.system'
  event_kind      VARCHAR(64) NOT NULL,                  -- 与 task_events.kind 一致集合
  payload         JSONB NOT NULL,                        -- _schema_version + 完整事件载荷（payload.pool_key 与冗余列一致）
  correlation_id  TEXT NULL,
  trace_id        TEXT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  dispatched_at   TIMESTAMPTZ NULL,                      -- v1 始终 NULL
  retry_count     INT NOT NULL DEFAULT 0,
  last_error      TEXT NULL
);

CREATE INDEX idx_task_outbox_pending
  ON task_outbox (created_at) WHERE dispatched_at IS NULL;

CREATE INDEX idx_task_outbox_pool_pending
  ON task_outbox (pool_key, created_at) WHERE dispatched_at IS NULL;
```

> v1 仅由 `task_state_machine.transition` 同事务写入；无 dispatcher。  
> v2 接入 MQ（Debezium / 内部 worker）时，dispatcher 按 `dispatched_at IS NULL` 拉取、按 `pool_key` 路由到对应主题、回写 `dispatched_at`；失败递增 `retry_count` + 写 `last_error`。  
> Outbox 与状态机同事务保证 **exactly-once** 业务事件外发语义。  
> `pool_key` 冗余列与 `payload.pool_key` 一致，便于 dispatcher 不解析 jsonb 即可路由（详见 [F05 §10](F05_TASK_POOL_FIRST_CLASS_REGISTRY.md#10-mq-接入预留v2)）。

#### 3.7.1 Retention 与 GC（v1 硬要求）

- **保留期默认 `outbox_retention_days = 90`**（配置项，可运维调整；不可设置小于 7d 以防止 v2 dispatcher 未就位时过早丢事件）。
- **GC 责任方**：由 [`task.consistency_audit`](#5-一致性巡检-worker) 兼职执行，不单独起 worker。
- **清理语义**：
  - v1（无 dispatcher）：`DELETE FROM task_outbox WHERE created_at < now() - INTERVAL ':retention' * ' day'`；删除前按 `pool_key` 分组聚合写 1 行 `task_events(kind='task.outbox_gc', payload={count_by_pool, window_start, window_end})`。
  - v2（有 dispatcher）：仅清理 `dispatched_at IS NOT NULL AND dispatched_at < now() - INTERVAL ':retention' * ' day'`；未投递的长留以待人工介入。
- **不变式 I7（登记）**：`MIN(task_outbox.created_at) ≥ now() - INTERVAL ':retention'`（audit worker 周期内维护，允许 ±1 个巡检周期漂移）。
- **观测**：每次 GC 写 `structlog.info("task.outbox_gc", deleted=..., oldest=..., newest=...)`；异常（删除行 > `gc_alert_threshold` 默认 10_000）降级为 `WARN` 并额外写 `task_events(kind='task.consistency_drift', payload={reason: 'outbox_gc_burst'})`。

### 3.8 `task_pools`

```sql
CREATE TABLE task_pools (
  id                     BIGSERIAL PRIMARY KEY,
  key                    VARCHAR(64) NOT NULL UNIQUE,
  display_name           TEXT NOT NULL,
  description            TEXT,
  owner_principal_id     BIGINT NULL,
  owner_principal_kind   VARCHAR(16) NULL,                -- user|agent|system
  default_workflow_ref   JSONB NOT NULL,                  -- {key, version, _schema_version}
  default_visibility     VARCHAR(32) NOT NULL,            -- 5 枚举之一
  default_priority       VARCHAR(16) NOT NULL DEFAULT 'normal',
  publish_acl            JSONB NOT NULL,                  -- _schema_version + 见 F05 §4
  consume_acl            JSONB NOT NULL,                  -- 同上
  quota                  JSONB NULL,                      -- v2 启用：{max_inflight, max_pending, max_publish_rate}
  attributes             JSONB,                           -- _schema_version 扩展元数据
  is_active              BOOLEAN NOT NULL DEFAULT true,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT chk_task_pools_key_format CHECK (
    key ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,3}$'
  )
);

CREATE INDEX idx_task_pools_active ON task_pools (key) WHERE is_active;
CREATE INDEX idx_task_pools_owner  ON task_pools (owner_principal_id) WHERE owner_principal_id IS NOT NULL;
```

- **键命名约束**：`<scope>.<domain>` 至 `<scope>.<domain>.<sub1>.<sub2>`（最多 4 段），与 [F05 §3.2](F05_TASK_POOL_FIRST_CLASS_REGISTRY.md#32-命名规范) 一致。
- **任务侧引用**：通过 `nodes.attributes.pool_id::bigint` 引用本表 `id`。**不**为图节点 jsonb 字段建数据库外键约束（Postgres 限制），由命令层在 `task create / publish` 时校验存在性 + `is_active`。
- **更新时戳**：`updated_at` 由应用层维护或通过 `BEFORE UPDATE` 触发器（v1 由应用层维护，避免触发器副作用）。
- 查询样例与 ACL 评估见 [F05 §4 / §6.1](F05_TASK_POOL_FIRST_CLASS_REGISTRY.md)。

### 3.9 任务节点 JSONB expression index（B3-1 / OQ-30 支撑）

为保证 §1.8 / ACCEPTANCE 性能基线（`transition` P99 ≤ 50ms、并发 32 claim ≥ 200 req/s）能达到，Phase B 迁移须建立以下 `nodes` 表上的部分表达式索引（partial + expression）：

```sql
-- 任务状态
CREATE INDEX idx_nodes_task_current_state
  ON nodes ((attributes->>'current_state'))
 WHERE type_code = 'task';

-- 池归属
CREATE INDEX idx_nodes_task_pool_id
  ON nodes (((attributes->>'pool_id')::bigint))
 WHERE type_code = 'task' AND attributes->>'pool_id' IS NOT NULL;

-- 认领路由
CREATE INDEX idx_nodes_task_assignee_kind
  ON nodes ((attributes->>'assignee_kind'))
 WHERE type_code = 'task';

-- 可见性
CREATE INDEX idx_nodes_task_visibility
  ON nodes ((attributes->>'visibility'))
 WHERE type_code = 'task';

-- 优先级（池查询排序）
CREATE INDEX idx_nodes_task_priority_created
  ON nodes ((attributes->>'priority'), created_at)
 WHERE type_code = 'task';

-- workflow key（跨版本统计）
CREATE INDEX idx_nodes_task_workflow_key
  ON nodes ((attributes->'workflow_ref'->>'key'))
 WHERE type_code = 'task';

-- due_at（SLA 查询，v2 扩展）
CREATE INDEX idx_nodes_task_due_at
  ON nodes (((attributes->>'due_at')::timestamptz))
 WHERE type_code = 'task' AND attributes->>'due_at' IS NOT NULL;

-- tags（可选 GIN，评估查询频率后决定）
-- CREATE INDEX idx_nodes_task_tags_gin
--   ON nodes USING GIN ((attributes->'tags' jsonb_path_ops))
--  WHERE type_code = 'task';
```

- **全部 partial `WHERE type_code='task'`**，避免影响其他节点类型写入。
- `pool_id` 索引以 `::bigint` 强制类型转换，与 [`F02 §3`](F02_TASK_POOL_AND_CLAIM_PROTOCOL.md#3-池可见性查询参考-sql) JOIN 的 `(n.attributes->>'pool_id')::bigint` 表达式完全一致，保证查询走索引。
- Phase B 上线前对每个索引执行 `EXPLAIN ANALYZE` 验证真实走索引（池查询 / list / show / claim 等典型 SQL）。

## 4. 派生字段约定

| 派生字段 | 来源 SSOT | 维护责任 |
|---|---|---|
| `task_assignments.stage` | `nodes.attributes.current_state` | `task_state_machine.transition` 在状态变迁时统一更新；外部禁直写 |
| `task_state_transitions` 末条 `to_state` | `nodes.attributes.current_state` | I1 不变式约束 |
| `task_runs.graph_ops_summary.resolved_targets[]` | `nodes.attributes.scope_selector` 在 `started_at` 解析快照 | 执行实例 freeze；外部不可变 |

## 5. 一致性巡检 worker

### 5.1 `task.consistency_audit`

- **角色**：`npc_agent.agent_role=sys_worker`，单实例（leader-elect 留 v2）。
- **频率**：默认 60s（可配置；评审项见 [SPEC §10.3](../SPEC.md#103-v1-仍待评审的细节项)）。
- **检测项**：
  1. **I1 检查**：`task_state_transitions` 按 `(task_node_id, event_seq DESC)` 取末条 `to_state` ≠ `nodes.attributes.current_state`。
  2. **I2 检查**：`task_assignments WHERE is_active` 的 `role` 集合 ⊄ `workflow_definition[current_state].expected_roles`。
  3. **`event_seq` 单调**：发现任意 `task_node_id` 的 `event_seq` 序列存在缺口或重复。
  4. **I7 Outbox 保留期**：`MIN(task_outbox.created_at) < now() - INTERVAL ':retention'` → 触发 §3.7.1 GC 步骤（v1 直接删除；v2 仅删除 `dispatched_at IS NOT NULL`）。
  5. **I8 父子 rollup 一致性**：`nodes.attributes.children_summary.total` ≠ 实际 `PARENT_OF` 出边数（详见 [F01 §5.1](F01_TASK_ONTOLOGY_AND_NODE_TYPES.md#51-按需物化)）。
  6. **`task_outbox` 长时间未投递**：`dispatched_at IS NULL AND created_at < now() - INTERVAL '<N hours>'`（仅在 v2 接入消费者后开启）。
  7. **`idempotency_key` 过期清理**：将 `task_state_transitions.idempotency_expires_at < now()` 行的 `idempotency_key` 置 `NULL`，保留审计内容；配套处理见 §3.4.1。
- **行为**：
  - 写 `task_events.kind ∈ {task.consistency_drift, task.outbox_gc, task.idempotency_expired}`，`payload` 含发现详情。
  - structlog 输出 `WARN / INFO` 级别日志（漂移 WARN，常规 GC INFO），便于聚合告警。
  - **v1 不自愈**（状态/分派漂移）；仅 outbox GC 与 idempotency TTL 为常态清理操作。
  - 运维通过事件回放或人工介入修复状态漂移。

### 5.2 检测 SQL 草案

```sql
-- I1 漂移
WITH latest AS (
  SELECT DISTINCT ON (task_node_id)
         task_node_id, to_state, event_seq
    FROM task_state_transitions
   ORDER BY task_node_id, event_seq DESC
)
SELECT n.id AS task_node_id,
       n.attributes->>'current_state' AS ssot_state,
       l.to_state AS last_transition_to_state,
       l.event_seq
  FROM nodes n
  JOIN latest l ON l.task_node_id = n.id
 WHERE n.type_code = 'task'
   AND n.attributes->>'current_state' <> l.to_state;
```

## 6. 事件回放（运维路径）

- 当怀疑某 `task` 的 `nodes.attributes.current_state` 损坏时，可由 `task_state_transitions` 重建：
  ```python
  def replay_state(task_id: int) -> str:
      rows = SELECT to_state FROM task_state_transitions
              WHERE task_node_id = :task_id ORDER BY event_seq ASC
      return rows[-1].to_state if rows else 'draft'
  ```
- v1 提供 admin CLI 工具（建议 `python -m app.tools.task_replay <task_id> [--apply]`）；默认 dry-run，`--apply` 后**仅**覆盖图节点 `current_state`，不重放 assignments / outbox。
- 不进入业务路径，不在状态机服务内自动调用。

## 7. 与 Agent 记忆的边界

- Agent 在执行任务过程中的细粒度观测、LLM 对话、工具调用日志写入 `agent_memory_entries(kind=raw)`（参见 [F02 §9](../../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)）。
- **任务侧只记审计级事件**；`task_runs.command_trace` 仅含命令名 + 关键参数摘要，不含 LLM 完整 token 流。
- 关联：`task_runs.correlation_id ↔ agent_memory_entries.session_id`（可选，由调用方约定）。

## 8. 字段命名与存量约定对齐

| 本 SPEC | 对齐参考 |
|---|---|
| `task_runs.command_trace` | `agent_run_records.command_trace`（[F02 §9.2](../../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md#92-agent_run_records)） |
| `task_runs.graph_ops_summary` | `agent_run_records.graph_ops_summary` |
| `task_events.payload` | `agent_memory_entries.payload` |
| `task_outbox.payload` | 与 `task_events.payload` 同 schema（v1 简化） |
| `actor_principal_id / actor_principal_kind` | 与 RBAC `Principal`（id + kind）一致；非 `account_id` |
| `correlation_id / trace_id` | 与 [`app/core/log/`](../../../../backend/app/core/log/) 上下文字段名待评审对齐（[SPEC §10.3](../SPEC.md#103-v1-仍待评审的细节项)） |

## 9. ACCEPTANCE

- [ ] 8 张表迁移落地，字段、索引、唯一约束、CHECK 全部就位。
- [ ] `task_assignments` 的 group CHECK 约束生效（向 `principal_kind='group'` 行写入 `principal_id` 时数据库拒绝）。
- [ ] `task_pools.key` 命名 CHECK 约束生效（不符 `<scope>.<domain>` 模式被拒绝）。
- [ ] `task_state_transitions(task_node_id, event_seq)` 唯一约束生效（重复插入失败）。
- [ ] `task_state_transitions(task_node_id, idempotency_key)` 部分唯一索引生效（同 `(task, idem)` 重复 INSERT 失败）。
- [ ] `task_outbox` 在状态机事务内写入；`dispatched_at` 始终 `NULL`（v1）；`pool_key` 列与 `payload.pool_key` 一致；非池任务 `pool_key='task.system'`。
- [ ] `task.consistency_audit` 巡检 worker 周期运行；构造 I1 漂移用例时正确写出 `consistency_drift` 事件。
- [ ] `replay_state` 工具能从空 `current_state` 推回正确终态（运维测试）。

## 10. 升规模分区迁移指南（OQ-29）

**v1 立场**：小规模部署**不分区**；所有 `task_*` 表为普通堆表 + 索引；保持 DDL 与运维门槛最低。

**触发迁移的阈值**（任一命中即启动评估）：

| 指标 | 阈值 |
|---|---|
| `task_state_transitions` 日增行数 | > 10_000 行/天 |
| 任一 append-only 表总行数 | > 1e8 行（约 1 亿） |
| `task_outbox` 活跃行数（未 GC） | > 5e6 行 |
| `transition` P99（在不减索引的前提下） | > 80ms 持续 24h |

**推荐分区策略**（达阈值后的 Phase-D 迁移）：

```sql
-- 示例：task_state_transitions 月分区
CREATE TABLE task_state_transitions_v2 (
  LIKE task_state_transitions INCLUDING ALL
) PARTITION BY RANGE (created_at);

CREATE TABLE task_state_transitions_2027_01
  PARTITION OF task_state_transitions_v2
  FOR VALUES FROM ('2027-01-01') TO ('2027-02-01');
-- ... 逐月
```

**迁移步骤（在线迁移，零停机）**：

1. 建并行表 `*_v2` + 月分区子表；与主表 schema 完全相同。
2. 触发器 / logical replication 把主表写流量同步复制到 `_v2`（`pgroll` / `pg_logical` 方案）。
3. 历史回填：`INSERT INTO *_v2 SELECT * FROM *`（按月批处理）。
4. 验证一致性（`COUNT(*)` + 热点行 hash）。
5. 切换：事务内 `ALTER TABLE ... RENAME`；双写关闭。
6. 保留旧表 7d 冷观察；通过后 `DROP`。

**分区候选表清单**（按优先级）：

| 表 | 分区键 | 周期 | 冷归档策略 |
|---|---|---|---|
| `task_state_transitions` | `created_at` | 月 | `DETACH` 老分区后冷盘归档；保留 24 个月 |
| `task_events` | `created_at` | 月 | 同上，保留 12 个月 |
| `task_outbox` | `created_at` | 月 | 配合 §3.7.1 GC，保留 3 个月 |
| `task_runs` | `started_at` | 月 | 保留 12 个月；PDCA 轨迹分析常用 |
| `task_assignments / task_details / task_pools / task_workflow_definitions` | — | 不分区 | 主键量级可控（~100k 级） |

> v1 SPEC 不引入分区 DDL；Phase B 迁移 **不**为分区预留表结构差异。上述迁移遵循 PostgreSQL 官方文档 *Partitioning* 与 `pgroll` / `pg_partman` 社区最佳实践。

## 11. 相关

- 主 SPEC：[`../SPEC.md`](../SPEC.md)
- 任务本体：[`F01_TASK_ONTOLOGY_AND_NODE_TYPES.md`](F01_TASK_ONTOLOGY_AND_NODE_TYPES.md)
- 任务池：[`F02_TASK_POOL_AND_CLAIM_PROTOCOL.md`](F02_TASK_POOL_AND_CLAIM_PROTOCOL.md)
- 状态机：[`F03_TASK_COLLABORATION_WORKFLOW.md`](F03_TASK_COLLABORATION_WORKFLOW.md)
- 命令族：[`../../../command/SPEC/features/CMD_task.md`](../../../command/SPEC/features/CMD_task.md)
- npc_agent 记忆/运行表先例：[`../../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md`](../../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)
