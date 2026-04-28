# F05 — 任务池一等注册与治理

> **Architecture Role：** 把任务池升格为**一等实体**（`task_pools` 独立表），承载 **池身份 / 默认值 / 发布与认领 ACL / 未来配额 / MQ 路由键**；与 [`task_workflow_definitions`](F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md#31-task_workflow_definitions) 同形治理。任务与池之间为 **1 : N**（**单任务归属至多 1 个池**），契合 Camunda External Task `topic`、Kafka topic、AWS SQS queue 的工业惯例；多业务域可由多个池表达。
>
> **依赖：** [`SPEC.md`](../SPEC.md) §1.4 RBAC、§1.5 可见性矩阵；[`F01`](F01_TASK_ONTOLOGY_AND_NODE_TYPES.md) `attributes.pool_id`；[`F02`](F02_TASK_POOL_AND_CLAIM_PROTOCOL.md) 池查询与认领；[`F03`](F03_TASK_COLLABORATION_WORKFLOW.md) 状态机 `publish` 事件；[`F04`](F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md) `task_pools` DDL。

**文档状态：Draft（v1）**

> Phase B 说明：池默认可见性当前仅支持 `private / explicit / pool_open`。
> `role_scope / world_scope` 保留为扩展枚举，后续版本启用。

---

## 1. Goal

- 提供 **池注册表 `task_pools`**：池有 `key / display_name / owner / 默认 workflow / 默认可见性 / 默认优先级 / publish_acl / consume_acl / quota（v2） / is_active`。
- 把"发布"与"认领"做成**对称的可治理路径**：
  - **发布（publish）**：用户/服务通过 `task create --to-pool <key>` 或 `task publish <id> --to-pool <key>`，受 `publish_acl` 约束。
  - **认领（claim）**：Agent/用户通过 `task claim <id>`，受 `consume_acl` 约束（与 RBAC `task.claim` 叠加）。
- **MQ-ready**：池 `key` 即未来 MQ 主题名（`task.pool.<key>` 一一对应），`task_outbox.payload.pool_key` 已为消费者预留路由键。
- **单池模型**：`task.attributes.pool_id`（FK → `task_pools.id`）至多 1 个；多池语义经"一任务一池 + 父子任务多池"组合表达，避免一票多归属带来的 ACL/默认值合并复杂性。

## 2. Non-Goals（v1）

- **不**支持单任务归属多池（任意分摊）。
- **不**实现配额执行（`quota` 字段在表中预留，运行时不生效；v2 启用）。
- **不**实现池间合并/拆分迁移工具（v2 admin CLI）。
- **不**支持池继承层级（"子池继承父池 ACL"）；v1 平面命名空间。
- **不**实现 MQ dispatcher；仅完成 `task_outbox` 的字段对齐与 schema 预留（与 [F04 §3.7](F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md#37-task_outbox) 一致）。

## 3. 池模型

### 3.1 字段语义

| 字段 | 类型 | 含义 | 治理责任 |
|---|---|---|---|
| `id` | BIGSERIAL | 内部主键 | 系统 |
| `key` | VARCHAR(64) UNIQUE | 池唯一标识；规范命名 `<scope>.<domain>`（如 `hicampus.cleaning`） | admin |
| `display_name` | TEXT | 人类可读名称 | admin |
| `description` | TEXT | 池用途说明 | admin |
| `owner_principal_id` | BIGINT NULL | 池所有者（user 或 npc_agent 节点 id） | admin |
| `owner_principal_kind` | VARCHAR(16) NULL | `user / agent / system` | admin |
| `default_workflow_ref` | JSONB | `{key, version}`；新任务未显式指定 workflow 时填充 | pool owner |
| `default_visibility` | VARCHAR(32) | 5 枚举之一（[SPEC §1.5](../SPEC.md#15-可见性谓词矩阵)） | pool owner |
| `default_priority` | VARCHAR(16) | `low/normal/high/urgent` | pool owner |
| `publish_acl` | JSONB | 谁可发布到本池（详见 §4） | pool owner |
| `consume_acl` | JSONB | 谁可认领本池任务（详见 §4） | pool owner |
| `quota` | JSONB | `{max_inflight, max_pending, max_publish_rate}`（v2 启用） | pool owner |
| `attributes` | JSONB | 扩展元数据；含 `_schema_version` | pool owner |
| `is_active` | BOOLEAN | 软停用；池停用后禁止新发布与新认领，已在执行任务不受影响 | admin |
| `created_at / updated_at` | TIMESTAMPTZ | — | 系统 |

DDL 见 [F04 §3.8](F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md#38-task_pools)。

### 3.2 命名规范

- `key` 强制 `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,3}$`，最长 64。
- 推荐两段式 `<world>.<domain>`，必要时三段 `<world>.<domain>.<subdomain>`：
  - `hicampus.cleaning` / `hicampus.security` / `hicampus.maintenance`
  - `hicampus.security.patrol` / `hicampus.security.incident`
- 命名空间不支持继承（同 §2 Non-Goals）；每个 key 独立治理。

### 3.3 默认值合并语义

`task create --to-pool <key>` 时字段补齐顺序：

```
任务最终字段 = 命令显式参数 OR 池默认值 OR 系统默认值
```

例：`task create --to-pool hicampus.cleaning --title "F1 卫生间"`：
- `workflow_ref` ← `task_pools.default_workflow_ref` ← `{default_v1, 1}`
- `visibility` ← `task_pools.default_visibility` ← `pool_open`
- `priority` ← `task_pools.default_priority` ← `normal`
- `assignee_kind` ← 自动 `pool`（因为指定 `--to-pool`）
- `pool_id` ← 池 id（解析 `key` → id）

`task create --to-pool hicampus.security --priority urgent` 显式覆盖。

## 4. ACL 模型

`publish_acl` 与 `consume_acl` 共享同一 schema：

```json
{
  "_schema_version": 1,
  "principals": [123, 456],
  "principal_kinds": ["user", "agent"],
  "roles": ["facility_manager"],
  "groups": ["facility"],
  "data_access_predicate": {
    "scope_anchor_in_world": "hicampus"
  },
  "default": "deny"
}
```

| 字段 | 含义 |
|---|---|
| `principals` | 显式允许的 principal id |
| `principal_kinds` | 允许的主体类（白名单；空数组 = 全允） |
| `roles` | RBAC 角色白名单（与 `task.publish` / `task.claim` 权限码 AND） |
| `groups` | `principal_kind=group` 的标签集合 |
| `data_access_predicate` | [F11](../../../api/SPEC/features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md) 表达式片段，用于把池绑定到特定世界/区域 |
| `default` | `allow` 或 `deny`；当其它字段全空时的兜底；推荐 `deny` |

### 4.1 评估顺序

```
def evaluate_acl(actor: Principal, acl: dict) -> bool:
    # 1) RBAC 命令权限码已在装饰器层校验（task.publish 或 task.claim）
    # 2) 池级 ACL 进一步收窄
    if actor.id in acl.get("principals", []): return True
    if acl.get("principal_kinds") and actor.kind in acl["principal_kinds"]:
        if actor.roles & set(acl.get("roles", [])): return True
        if acl.get("groups") and actor.group_tags & set(acl["groups"]): return True
    if acl.get("data_access_predicate"):
        return f11_evaluate(actor, acl["data_access_predicate"])
    return acl.get("default", "deny") == "allow"
```

### 4.2 默认 ACL

- 池创建时若未提供 `publish_acl`：默认 `{default: "allow"}`（向已具 `task.publish` 权限的主体开放）。
- 默认 `consume_acl`：`{default: "allow"}`（向已具 `task.claim` 权限的主体开放）。
- 严格治理场景下，admin 应在 `task pool create` 时显式提供 ACL。

### 4.3 与 [F11 `data_access`](../../../api/SPEC/features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md) 的边界

- 池 ACL 与 F11 是**串联**关系：F11 仍按 `scope_anchor` 校验数据访问；池 ACL 在其上做"是否能用本池"的二级校验。
- 推荐：跨世界共享池极少，绝大多数池绑定到特定世界，由 `data_access_predicate.scope_anchor_in_world` 锁定。

## 5. 发布路径（Publish）

### 5.1 命令

| 子命令 | 用法 | 行为 |
|---|---|---|
| `task create --to-pool <key> [...]` | 创建任务并发布到池 | 解析 key → pool_id；填默认值；evaluate `publish_acl`；初始事件 `open` |
| `task publish <task_id> --to-pool <key>` | 把已存在的 `draft / open` 任务发布到（或迁移到）某池 | 状态机事件 `publish`；要求当前态 ∈ `{draft, open}` 且无 active executor |
| `task unpublish <task_id>` | 从池中撤回（v2 评估） | — |

### 5.2 状态机事件 `publish`

```yaml
publish:
  from: [draft, open]
  to:   open                      # 不改变 current_state，仅迁移 pool 归属
  required_role: owner
  preconditions: [no_active_executor]
  side_effects:
    - update_pool(pool_id=:payload.pool_id)
    - check_publish_acl(:payload.pool_id)
```

事务模板与 [F03 §3](F03_TASK_COLLABORATION_WORKFLOW.md#3-单事务原子写入模板) 一致；`task_state_transitions.event='publish'`，`metadata` 含 `{from_pool_id, to_pool_id}`；`task_outbox` 同事务写 `event_kind='task.published'`，`payload.pool_key` 即池 key（MQ 路由键预留）。

### 5.3 错误形态

| 错误 | 触发 |
|---|---|
| `PoolNotFound` | `key` 解析失败 |
| `PoolInactive` | `is_active=false` |
| `PublishAclDenied` | actor 未通过 `publish_acl` |
| `TaskAlreadyClaimed` | 已存在 `is_active=true AND role='executor'` 行 |

## 6. 认领路径（Consume）

### 6.1 改动点（相对 [F02](F02_TASK_POOL_AND_CLAIM_PROTOCOL.md)）

- **池可见性查询**：从 jsonb tag 过滤 → JOIN `task_pools`：

```sql
SELECT n.id
  FROM nodes n
  JOIN task_pools p ON p.id = (n.attributes->>'pool_id')::bigint
 WHERE n.type_code = 'task'
   AND n.attributes->>'assignee_kind' = 'pool'
   AND n.attributes->>'current_state' IN ('open', 'rejected')
   AND p.is_active
   AND NOT EXISTS (
     SELECT 1 FROM task_assignments a
      WHERE a.task_node_id = n.id AND a.is_active AND a.role = 'executor')
   AND <evaluate(actor, p.consume_acl)>                  -- 由命令层 / 仓储拼装
   AND <F11 data_access predicate on SCOPED_AT 锚点>
   AND p.key = ANY(:subscribed_pool_keys)                -- agent 订阅家族
 ORDER BY
   CASE n.attributes->>'priority'
     WHEN 'urgent' THEN 0 WHEN 'high' THEN 1
     WHEN 'normal' THEN 2 WHEN 'low' THEN 3
   END,
   n.created_at ASC;
```

- **`task claim <id>`**：状态机服务在 `event=claim` 事务内额外校验 `consume_acl`（拒绝 → `ConsumeAclDenied`）。

### 6.2 Agent 订阅模型改造

在 [`docs/models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md`](../../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md) §7 `subscription_bindings` 既有结构上**约定 v1 用法**：

```yaml
# 旧：queue_name = "task.pool.<tag>"   # 弃用
# 新：
subscription_bindings:
  - kind: pool                         # 新增显式 kind 字段；老路径 kind=queue 保留给非任务系统
    pool_key: hicampus.cleaning        # 直接对齐 task_pools.key
    message_format_version: "1"
  - kind: pool
    pool_key: hicampus.security
    message_format_version: "1"
```

- v1 同时**支持通配**：`pool_key: "hicampus.security.*"`（单层 `*` 匹配；解析在订阅评估阶段完成，SQL 层 `LIKE 'hicampus.security.%'`）。
- 不再支持基于 jsonb tag 的家族匹配；新构建无需兼容旧 `pool_tags`。

## 7. 池治理命令

| 子命令 | 权限 | 行为 |
|---|---|---|
| `task pool list [--scope <world>]` | `task.read` | 列活跃池：key / display_name / owner / 默认值摘要 |
| `task pool show <key>` | `task.read` | 池详情：含 ACL 摘要、当前 in-flight / pending 计数 |
| `task pool create <key> --display-name <N> [--owner @h] [--workflow <k>:<v>] [--visibility ...] [--priority ...] [--publish-acl @file] [--consume-acl @file]` | `task.pool.admin` | 创建池 |
| `task pool update <key> [--display-name ...] [--workflow ...] [--publish-acl @file] [--consume-acl @file]` | `task.pool.admin` | 更新池非 key 字段 |
| `task pool disable <key>` / `task pool enable <key>` | `task.pool.admin` | 软停 / 软启 |
| `task pool stats <key>` | `task.read` | 池可观测：pending（无 executor）/ claimed / in_progress / pending_review / 最近 1h 完成数 / 平均认领等待时长 |

> v1 不提供 `task pool delete`；停用即足够，保留 `is_active=false` 的池历史以支持任务归属审计。

## 8. RBAC 权限码扩展

在 [SPEC §1.4](../SPEC.md#14-rbac-权限码) 基础上新增：

| 权限码 | 适用 |
|---|---|
| `task.publish` | 发布任务到任意池（与 `publish_acl` AND） |
| `task.pool.admin` | 创建 / 修改 / 停用池；查看任意池 stats |

`task.create` 仍可创建非池任务（`assignee_kind ∈ {user, agent, group}`）；创建池任务必须叠加 `task.publish`。

## 9. 默认 seed 池（Phase B 写入）

随 [`graph_seed_node_types.yaml`](../../../../backend/db/ontology/graph_seed_node_types.yaml) 配套，新增 `backend/db/seed/task_pools.yaml`：

```yaml
- key: hicampus.cleaning
  display_name: HiCampus 清洁池
  default_workflow_ref: { key: default_v1, version: 1 }
  default_visibility: pool_open
  default_priority: normal
  publish_acl:
    _schema_version: 1
    roles: [facility_manager, admin]
    default: deny
  consume_acl:
    _schema_version: 1
    principal_kinds: [agent, user]
    data_access_predicate: { scope_anchor_in_world: hicampus }
    default: deny

- key: hicampus.security
  display_name: HiCampus 安防池
  default_workflow_ref: { key: review_handoff_v1, version: 1 }
  default_visibility: role_scope
  default_priority: high
  publish_acl:
    roles: [security_officer, admin]
    principal_kinds: [user, agent, system]   # system = 告警触发自动发布（OQ-28）
    default: deny
  consume_acl:
    principal_kinds: [agent, user]
    data_access_predicate: { scope_anchor_in_world: hicampus }
    default: deny

- key: hicampus.maintenance
  display_name: HiCampus 运维池
  default_workflow_ref: { key: default_v1, version: 1 }
  default_visibility: world_scope
  default_priority: normal
  publish_acl: { default: allow }
  consume_acl: { default: allow }
```

## 10. MQ 接入预留（v2）

- `task_pools.key` 即未来 MQ 主题名（前缀 `task.pool.`）。
- `task_outbox.payload` 含 `{ "pool_key": "<key>", "event": "task.published|claimed|state_changed|completed", ... }`，dispatcher 按 `pool_key` 路由到对应主题。
- 设计上保证 **任何任务系统对外通知** 都已带 `pool_key`（无池任务 dispatcher 可走默认主题 `task.system`）。
- v2 dispatcher 选型（Debezium / 内建 worker / Kafka producer）由 [SPEC §10.2](../SPEC.md#102-未来扩展v2-候选) 备忘录追踪。

## 11. 业界类比

| 系统 | 池抽象 | 与本 SPEC 对应 |
|---|---|---|
| **Camunda External Task** | `topic`（字符串 + 可选 priority） | `task_pools.key` + `default_priority`；`task claim` ≈ `fetchAndLock(topics)` |
| **Kafka topic** | 一等实体 + 分区 + ACL | 同`task_pools` + `consume_acl`；分区留 v2（高吞吐时） |
| **AWS SQS Queue** | 一等队列 + IAM policy + DLQ | 同 + `consume_acl`；DLQ 留 v2 |
| **GCP Pub/Sub** | topic + subscription（一等） | 一致；subscription 概念由 npc_agent.subscription_bindings 表达 |
| **GitLab CI runner tags** | 标签集合（无注册表） | 旧 `pool_tags` 模型，已弃用 |
| **K8s nodeSelector / taints** | 标签 + 双向匹配 | 同上，已弃用 |

**取舍依据**：v1 即升 Kafka 风格的一等实体，避免后期表迁移；与未来 MQ 选型同构，dispatcher 工作量最小。

## 12. ACCEPTANCE

- [ ] `task_pools` 表迁移落地，字段、唯一约束、默认值就位（详见 [F04 §3.8](F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md#38-task_pools)）。
- [ ] §9 三个 seed 池写入；`task pool list` 能列出。
- [ ] `task create --to-pool hicampus.cleaning` 自动填池默认值；缺 `task.publish` 权限或 `publish_acl` 拒绝时返回 `PublishAclDenied`。
- [ ] `task publish <id> --to-pool <key>` 在已 claim 任务上失败 `TaskAlreadyClaimed`；在 draft/open 任务上成功并写 `task_state_transitions(event='publish')`。
- [ ] `task pool disable <key>` 后，新 `task create --to-pool` / `task publish` 失败 `PoolInactive`；已认领任务正常推进。
- [ ] 多 agent 订阅 `pool_key=hicampus.security.*` 通配，能正确匹配 `hicampus.security` / `hicampus.security.patrol` 等池。
- [ ] `task_outbox.payload.pool_key` 字段在每次状态迁移事件中存在；非池任务 `pool_key` 为 `null` 或 `task.system`。
- [ ] `task pool stats <key>` 返回的计数与底层 `task_assignments` / `nodes` 状态一致。

## 13. 相关

- 主 SPEC：[`../SPEC.md`](../SPEC.md)
- 任务本体：[`F01_TASK_ONTOLOGY_AND_NODE_TYPES.md`](F01_TASK_ONTOLOGY_AND_NODE_TYPES.md)
- 任务池查询与认领：[`F02_TASK_POOL_AND_CLAIM_PROTOCOL.md`](F02_TASK_POOL_AND_CLAIM_PROTOCOL.md)
- 状态机（`publish` 事件）：[`F03_TASK_COLLABORATION_WORKFLOW.md`](F03_TASK_COLLABORATION_WORKFLOW.md)
- DDL：[`F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md`](F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md)
- 命令族：[`../../../command/SPEC/features/CMD_task.md`](../../../command/SPEC/features/CMD_task.md)
- npc_agent 订阅契约：[`../../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md`](../../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)
- 数据访问策略：[`../../../api/SPEC/features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md`](../../../api/SPEC/features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md)
