# F02 — 任务池与认领协议

> **Architecture Role：** 定义"任务池查询视图"与**原子认领契约**：池本体（注册、ACL、默认值、MQ 路由键）由 [`F05`](F05_TASK_POOL_FIRST_CLASS_REGISTRY.md) 一等表 `task_pools` 承载；本文件聚焦 **运行时的池可见性查询、认领状态机、Agent 订阅消费、Bulk 接力**。
>
> **依赖：** [`SPEC.md`](../SPEC.md) §1.5 可见性矩阵、[`F01`](F01_TASK_ONTOLOGY_AND_NODE_TYPES.md) `pool_id` / `assignee_kind`、[`F03`](F03_TASK_COLLABORATION_WORKFLOW.md) 状态机入口、[`F04`](F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md) `task_assignments / task_pools`、[`F05`](F05_TASK_POOL_FIRST_CLASS_REGISTRY.md) 池注册与治理。

**文档状态：Draft（v1）**

---

## 1. Goal

- 把"任务池可见性"建模为**JOIN 查询视图**：基于 `task_pools` 一等表 + `task_assignments` 的"无 active executor"判据，不引入新队列表。
- 提供 **原子、可重试、幂等** 的认领命令 `task claim <id>`，以乐观锁 + 状态机服务保证多 Agent 并发时仅一方成功；额外校验池 `consume_acl`（[F05 §6](F05_TASK_POOL_FIRST_CLASS_REGISTRY.md#6-认领路径consume)）。
- 与 [F02 npc_agent](../../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md) 的 `subscription_bindings` 契约对接：订阅项 `kind=pool, pool_key=<task_pools.key>`，支持 `*` 通配。
- 提供 **bulk 操作**（决策 14）：命令层循环 + 错误聚合，不在状态机服务实现批事务。

## 2. 池语义

- 一个任务出现在某池可领队列的充分条件：
  1. `nodes.attributes.assignee_kind = 'pool'` 且 `nodes.attributes.pool_id = <pool_id>`
  2. `task_pools[<pool_id>].is_active = true`
  3. `nodes.attributes.visibility ∈ {pool_open, role_scope, world_scope}`
  4. `task_assignments` 中**不存在** `is_active=true AND role='executor'` 的行
  5. actor principal 通过 `task_pools[<pool_id>].consume_acl` 评估（[F05 §4](F05_TASK_POOL_FIRST_CLASS_REGISTRY.md#4-acl-模型)）
- "池视图"是上述谓词的并集，对每个 `task_pools.key` 独立。Agent 订阅家族（pool_key 列表，含通配）决定其可见的池集合。

## 3. 池可见性查询（参考 SQL）

```sql
SELECT n.id, n.attributes, p.key AS pool_key
  FROM nodes n
  JOIN task_pools p
    ON p.id = (n.attributes->>'pool_id')::bigint
   AND p.is_active
 WHERE n.type_code = 'task'
   AND n.attributes->>'assignee_kind' = 'pool'
   AND n.attributes->>'current_state' IN ('open', 'rejected')
   AND NOT EXISTS (
     SELECT 1
       FROM task_assignments a
      WHERE a.task_node_id = n.id
        AND a.is_active
        AND a.role = 'executor')
   AND p.key = ANY(:expanded_pool_keys)              -- 通配展开后的 agent 订阅家族
   AND <F11 data_access predicate on SCOPED_AT 锚点>
   AND <evaluate_consume_acl(:actor, p.consume_acl)> -- 应用层补谓词或预过滤
 ORDER BY
   CASE n.attributes->>'priority'
     WHEN 'urgent' THEN 0 WHEN 'high' THEN 1
     WHEN 'normal' THEN 2 WHEN 'low' THEN 3
   END,
   n.created_at ASC;
```

> 谓词形态与 [SPEC §1.5 可见性矩阵](../SPEC.md#15-可见性谓词矩阵) 一致；`<F11 data_access predicate>` 由 [F11](../../../api/SPEC/features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md) 装饰器在命令层注入；`evaluate_consume_acl` 见 [F05 §4.1](F05_TASK_POOL_FIRST_CLASS_REGISTRY.md#41-评估顺序)。

### 3.1 通配订阅展开

Agent 订阅项 `pool_key` 支持单层 `*`（如 `hicampus.security.*`），命令层在查询前展开：

```sql
WITH expanded AS (
  SELECT key FROM task_pools
   WHERE is_active
     AND (key = :literal_key OR key LIKE :glob_pattern)
)
SELECT array_agg(key) FROM expanded;
```

通配展开缓存可由 agent runtime 持有 N 秒（默认 30s），减少高频 tick 重复查询。

### 3.2 与 `scope_selector` 的 trait 过滤联用

当 Agent 订阅家族（pool_key）以外还希望按"我的能力相称的设备类"二次收窄（如只接 `trait_mask_all_of=[CONTROLLABLE, AUTO]` 的清洁类），命令层可在池查询基础上拼接 selector 的 trait 子句，所有过滤都落在 `nodes` 已有 B-tree / 位运算索引上，无需扩表（详见 [F01 §4.4](F01_TASK_ONTOLOGY_AND_NODE_TYPES.md#44-trait_class--trait_mask-过滤性能优先路径)）。

## 4. 原子认领契约

### 4.1 命令路径

```
用户/Agent: task claim <id> [--idempotency-key K]
  → CommandContext (principal, correlation_id, trace_id)
  → 校验 RBAC: task.claim
  → task_state_machine.transition(
       task_id=id, event='claim', actor_principal=principal,
       expected_version=<from latest read>, idempotency_key=K)
  → TransitionResult
```

### 4.2 状态机内事务（节选，详见 [F03 §3](F03_TASK_COLLABORATION_WORKFLOW.md#3-单事务原子写入模板)）

```sql
BEGIN;
-- I6 幂等键命中检查
SELECT id, to_state FROM task_state_transitions
 WHERE task_node_id = :task_id AND idempotency_key = :idem;
-- 命中 → 返回原结果

-- 加锁顺序：nodes → task_pools(只读) → task_assignments → task_state_transitions → task_outbox
SELECT id, attributes FROM nodes
 WHERE id = :task_id AND type_code = 'task'
 FOR UPDATE;

-- 校验池治理（pool_id 解析 + is_active + consume_acl）
SELECT id, key, is_active, consume_acl FROM task_pools
 WHERE id = (n.attributes->>'pool_id')::bigint;
-- 不存在 → PoolNotFound；is_active=false → PoolInactive
-- evaluate_consume_acl(actor, consume_acl) = false → ConsumeAclDenied

-- 校验：current_state ∈ {open, rejected}；event='claim' 合法
-- 校验：expected_version = (attributes->>'state_version')::int

-- 双重校验：再读一次 task_assignments，确保没有其他 active executor
SELECT 1 FROM task_assignments
 WHERE task_node_id = :task_id AND is_active AND role = 'executor';
-- 命中 → AlreadyClaimedError

UPDATE nodes
   SET attributes = jsonb_set(
         jsonb_set(attributes, '{current_state}', '"claimed"'),
         '{state_version}', to_jsonb((attributes->>'state_version')::int + 1))
 WHERE id = :task_id
   AND (attributes->>'state_version')::int = :expected_version;
-- 受影响行 = 0 → OptimisticLockError

INSERT INTO task_assignments
  (task_node_id, principal_id, principal_kind, role, stage,
   is_active, assigned_by, assigned_at)
 VALUES (:task_id, :principal_id, :principal_kind,
         'executor', 'claim', true, :principal_id, now());

INSERT INTO task_state_transitions
  (task_node_id, event_seq, idempotency_key, from_state, to_state, event,
   actor_principal_id, actor_principal_kind, stage, correlation_id, trace_id, metadata)
 VALUES (...);

INSERT INTO task_outbox
  (task_node_id, pool_key, event_kind, payload, correlation_id, trace_id)
 VALUES (:task_id, :pool_key, 'task.claimed', ...);
COMMIT;
```

### 4.3 错误形态

| 错误 | 触发 | 命令层文案（i18n key） |
|---|---|---|
| `AlreadyClaimedError` | 任务已被他人认领 | `commands.task.claim.already_claimed` |
| `OptimisticLockError` | `expected_version` 不匹配 | `commands.task.claim.version_stale` |
| `WorkflowEventNotAllowed` | 当前状态不允许 `claim` | `commands.task.claim.invalid_state` |
| `PoolNotFound` | `pool_id` 解析失败 | `commands.task.claim.pool_not_found` |
| `PoolInactive` | 池 `is_active=false` | `commands.task.claim.pool_inactive` |
| `ConsumeAclDenied` | actor 未通过池 `consume_acl` | `commands.task.claim.consume_denied` |
| `PermissionDenied` | 缺 RBAC `task.claim` 或不满足 visibility | `commands.task.claim.forbidden` |
| `NotFound` | task 不存在 | `commands.task.claim.not_found` |

### 4.4 幂等

- 客户端可显式提供 `--idempotency-key`；建议 Agent 自动生成 `<service_id>:<correlation_id>`。
- 服务层在 `task_state_transitions(task_node_id, idempotency_key)` 唯一约束命中时**返回原结果**（含原 `to_state / event_seq / state_version`），不再写入。
- 幂等命中**不触发** `task_outbox` 二次写入。

## 5. Agent 自主接单

### 5.1 与 `npc_agent` 的契约接续

复用 [F02 npc_agent](../../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md) 已有字段；订阅项采用 `kind=pool, pool_key=<task_pools.key>` 直接对齐一等池：

```yaml
# npc_agent 实例 attributes 示例（节选）
agent_role: sys_worker
service_id: cleaning-bot-hicampus-01
decision_mode: rules
cognition_profile_ref: pdca_v1
trigger_overrides: {}
subscription_bindings:
  - kind: pool
    pool_key: hicampus.cleaning              # 直接对齐 task_pools.key
    message_format_version: "1"
  - kind: pool
    pool_key: hicampus.security.*            # 单层通配，匹配子族池
    message_format_version: "1"
tool_allowlist:
  - command.task.list
  - command.task.claim
  - command.task.show
  - command.task.complete
```

### 5.2 调度链路

```
agent runtime tick
  → 拉取 subscription_bindings 命中 pool_tag 的池视图（§3 SQL）
  → 选取一条候选（默认 priority + FIFO）
  → 在 CommandContext 下调 `task claim <id> --idempotency-key <service_id>:<run_id>`
  → 成功 → 写 agent_run_records.phase=plan，进入 PDCA do 阶段
  → 失败（AlreadyClaimedError / OptimisticLockError）→ 退避，下一条候选
```

### 5.3 公平性与节流（v1 文档化，Phase C 实现 token-bucket 留 v2）

- v1 仅保证**正确性**：先到先得 + 乐观锁拒绝失败者；Agent 退避策略由实现层定（建议指数退避 + 最大并发 `max_inflight_claims`）。
- token-bucket 公平性：见 [`SPEC.md`](../SPEC.md) §10.2 备忘录。

## 6. 指派路径

`task assign <id> <handle>`：

- 主体：owner 或 `task.assign` 权限。
- 等价于 `task_state_machine.transition(event='assign', payload={'principal_handle': '<handle>'})`。
- 状态机：`open → claimed`（`assignee_kind` 不必为 `pool`，可以是 `user/agent/group`）。
- 同事务插入 `task_assignments(role='executor', principal_kind, principal_id|principal_tag, is_active=true)`。
- handle 解析：参考 [F04 npc_agent handle 解析](../../../models/SPEC/features/F04_AT_AGENT_INTERACTION_PROTOCOL.md)；group 走纯标签（`principal_kind='group'`，`principal_tag=<group_label>`）。

## 7. Bulk 操作（决策 14：逐个 transition）

### 7.1 命令

- `task bulk-claim <id1,id2,...>`
- `task bulk-approve <id1,id2,...>`（详见 [F03](F03_TASK_COLLABORATION_WORKFLOW.md)）

### 7.2 实现策略

- **不在状态机服务实现批事务**；命令层循环逐个调用 `task_state_machine.transition`。
- 每个 task 独立事务、独立 `expected_version` 读取。
- 幂等键自动衍生：`<bulk_id>:<task_id>`，其中 `<bulk_id>` 为命令实例 UUID（或用户传入 `--bulk-id`）。
- **first-failure-continue**：单个失败不中断后续；最终聚合返回：

```json
{
  "succeeded": [{"id": 1, "to_state": "claimed", "event_seq": 4}, ...],
  "failed":    [{"id": 2, "reason": "AlreadyClaimedError"},
                {"id": 5, "reason": "OptimisticLockError"}]
}
```

### 7.3 Why 不批事务

- 单事务批量更新需对 N 个 `nodes` 行同时 `FOR UPDATE`，加锁顺序与超时不可控；与本 SPEC §1.7 死锁守则冲突。
- 单事务回滚一刀切违反"部分成功"产品语义；与 JIRA / GitHub bulk 操作行业惯例不符。
- 强一致 bulk 留 v2 评审（见 [SPEC §10.2](../SPEC.md#102-未来扩展v2-候选)）。

## 8. 列表与导航命令

| 命令 | 行为 |
|---|---|
| `task pool [--scope <tag>]` | 列出池中可领任务（`assignee_kind=pool` + 无 active executor + selector tag 过滤 + `task.claim` 可见） |
| `task list --mine` | 列出我作为 owner 或 active assignment 的任务 |
| `task list --assigned` | 列出我作为 active executor 的任务 |
| `task list --approver` | 列出当前 stage 期望我审批的任务 |
| `task show <id>` | 单任务详情（联表 `task_details / task_assignments` 当前状态切片） |

可见性谓词由 [SPEC §1.5](../SPEC.md#15-可见性谓词矩阵) 矩阵决定；命令实现统一在 `app/repositories/task_repo.py`（Phase B 落地）。

## 9. 样例：Agent 接单完整链路

1. **任务创建（发布）**：管理员 `task create --title "F1 卫生间清洁" --scoped-at room#4711 --to-pool hicampus.cleaning`：
   - 命令层解析 `pool_key='hicampus.cleaning'` → `pool_id=101`；evaluate `publish_acl`；`assignee_kind=pool`、`pool_id=101`、池默认 `workflow_ref / visibility / priority` 自动填充；初始事件 `open` 经状态机服务写入；`task_outbox(pool_key='hicampus.cleaning', event_kind='task.published')` 同事务写出。
2. **池可见**：cleaning-bot-hicampus-01 tick 时，订阅项 `kind=pool, pool_key=hicampus.cleaning` 命中；§3 池查询 JOIN `task_pools` 返回该任务。
3. **认领**：Agent 调 `task claim <id> --idempotency-key cleaning-bot-hicampus-01:run-uuid-...`：
   - 事务：评估 `consume_acl` 通过；`current_state open → claimed`、`state_version 1 → 2`、插入 `task_assignments(role=executor)`、追加 `task_state_transitions(event_seq=2)`、写 `task_outbox(pool_key='hicampus.cleaning', kind=task.claimed)`。
4. **执行**：Agent 进入 PDCA Plan→Do，`task_runs(phase=do, started_at)` 创建；selector freeze 至 `graph_ops_summary.resolved_targets[]`。
5. **完成**：`task complete <id>`：`claimed → done`（如 workflow 简单）或 `claimed → in_progress → pending_review`（如有审批）。

## 9.1 Lease / Heartbeat 预留（OQ-19 方案 B）

- v1 **不实现** claim 后的 lease 与 heartbeat；agent 崩溃任务会留在 `claimed` 态，需人工介入或 `task cancel`。
- `task_assignments.lease_expires_at` 与 `last_heartbeat_at` 两列 v1 预留（见 [F04 §3.3](F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md#33-task_assignments)），写入均为 NULL。
- **Phase C（v2）启用路径**：
  - `claim` 事件时同事务写入 `lease_expires_at = now() + workflow_definition.claim_ttl`（默认 15min）。
  - 新增命令 `task heartbeat <id>`（延长 lease），`task lease-expired <id>`（由 audit worker 内部事件驱动，不暴露到用户命令）。
  - audit worker 新增检测项 `lease_expired`：`SELECT id FROM task_assignments WHERE is_active AND role='executor' AND lease_expires_at < now()` → 驱动 `claimed → open`（event=`lease_expired`）+ `is_active=false` + 写 `task_events(kind='task.lease_expired')`。
  - 与 SQS visibility timeout / Camunda External Task lockExpirationTime 对齐。

## 10. ACCEPTANCE

- [ ] 池可见性 SQL JOIN `task_pools.is_active=true`；与 [SPEC §1.5](../SPEC.md#15-可见性谓词矩阵) 一致。
- [ ] 并发 N 个 Agent 同时 `task claim` 同一任务，仅 1 方成功；其余收 `AlreadyClaimedError` 或 `OptimisticLockError`。
- [ ] 同一 `(task_id, idempotency_key)` 重复调用 `task claim` 返回**等价** `TransitionResult`，不二次写入。
- [ ] `task claim` 在 `consume_acl` 拒绝时返回 `ConsumeAclDenied`；池停用时返回 `PoolInactive`。
- [ ] `task bulk-claim` 单个失败不中断；最终聚合返回 succeeded + failed 列表。
- [ ] Agent `subscription_bindings[kind=pool, pool_key=...]` 含通配（`hicampus.security.*`）时，命令层正确展开匹配活跃池 keys。
- [ ] `task_outbox.pool_key` 列在 claim/published 等事件写入时与 `task_pools.key` 一致；非池任务为 `task.system`。

## 11. 相关

- 主 SPEC：[`../SPEC.md`](../SPEC.md)
- 任务本体：[`F01_TASK_ONTOLOGY_AND_NODE_TYPES.md`](F01_TASK_ONTOLOGY_AND_NODE_TYPES.md)
- 状态机：[`F03_TASK_COLLABORATION_WORKFLOW.md`](F03_TASK_COLLABORATION_WORKFLOW.md)
- 关系子底座：[`F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md`](F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md)
- 命令族：[`../../../command/SPEC/features/CMD_task.md`](../../../command/SPEC/features/CMD_task.md)
- npc_agent 类型：[`../../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md`](../../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)
