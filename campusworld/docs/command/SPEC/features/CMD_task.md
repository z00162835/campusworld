# `task`

> **Status：** Draft（v1，与 [`docs/task/SPEC/SPEC.md`](../../../task/SPEC/SPEC.md) 同步）。
> **Implementation：** Phase B 落地；本文件先行规范命令族契约，子命令以"概述节"统一收拢，不为每个子命令单独建文件。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `task` |
| `CommandType` | GAME（含 ADMIN 子命令） |
| Class | `app.commands.game.task.TaskCommand`（Phase B 新建） |
| Primary implementation | `backend/app/commands/game/task/`（Phase B 新建命令族目录） |
| Service | [`backend/app/services/task/task_state_machine.py`](../../../../backend/app/services/task/task_state_machine.py)（唯一写入入口） |
| Locale | `commands.task.*` → `backend/app/commands/i18n/locales/{zh-CN,en-US}.yaml`（Phase B 落值） |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-28 |

## Synopsis

```
task <subcommand> [args] [--idempotency-key <K>] [--correlation-id <C>]
```

## Implementation contract（SSOT：[`docs/task/SPEC/`](../../../task/SPEC/)）

### A. 写命令统一约束

- **唯一服务入口**：所有写命令（含 bulk）调用 `app/services/task/task_state_machine.transition(...)`；**禁止**直接 `UPDATE nodes` 或写关系表（不变式 I3，详见 [SPEC §1.3](../../../task/SPEC/SPEC.md#13-不变式-i1i6契约级)）。
- **幂等键**：所有写命令支持 `--idempotency-key <K>`；缺省时由命令层基于 `(actor_id, command_name, args_hash, correlation_id)` 自动派生（**Agent 调用强烈建议显式提供**）。
- **乐观锁**：命令层在调用前 `SELECT attributes` 取 `state_version` 作为 `expected_version`；冲突 → 返回 `commands.task.error.version_stale`。
- **审计上下文**：从 `CommandContext` 提取 `principal_id / principal_kind / correlation_id / trace_id`，下传服务层。
- **RBAC**：装饰器接入 [`backend/app/core/permissions.py`](../../../../backend/app/core/permissions.py) 中的 `task.*` 权限码（[SPEC §1.4](../../../task/SPEC/SPEC.md#14-rbac-权限码)）。

### B. 子命令清单（轻量档摘要）

#### 只读

| 子命令 | 用法 | 行为 |
|---|---|---|
| `task list [--mine\|--pool <key>\|--assigned\|--approver]` | 列表，按可见性矩阵过滤；默认 `--mine`；`--pool <key>` 走 [F02 §3](../../../task/SPEC/features/F02_TASK_POOL_AND_CLAIM_PROTOCOL.md#3-池可见性查询参考-sql) JOIN | 联表 `nodes(task)` + `task_pools`（pool 视图）+ `task_assignments` + 可见性谓词；分页 |
| `task show <id>` | 详情 | 单任务切片：`nodes` + `task_details` + 当前 active assignments + 末 N 条 transitions |
| `task pool list [--scope <world>]` | 列活跃池：key / display_name / owner / 默认值摘要 | 只读 `task_pools WHERE is_active` |
| `task pool show <key>` | 池详情：含 ACL 摘要、in-flight / pending 计数 | 只读 `task_pools` + 聚合 `nodes / task_assignments` |
| `task pool stats <key>` | 池可观测：pending / claimed / in_progress / pending_review / 最近 1h 完成数 / 平均认领等待时长 | 聚合查询 |
| `task workflow list` | 列出 active workflow 定义 | 只读 `task_workflow_definitions WHERE is_active` |
| `task workflow show <key>:<version>` | workflow 详情 | 只读单行 `spec` |

只读命令**不经状态机服务**，直接走仓储查询（Phase B 落 `app/repositories/task_repo.py`）。

> Phase B 子集说明：当前只实现 `create/list/show/claim/assign/publish/complete/pool list|show|create|update|disable|enable`。
> 文档中其余命令与参数保留为扩展位，不代表当前可用。

#### 创建与发布

| 子命令 | 用法 | 行为 |
|---|---|---|
| `task create` | `--title <T> --scoped-at <node_id> [--workflow <key>:<ver>] [--selector @file] [--parent <id>] [--assignee <@handle\|group:<tag>>] [--to-pool <pool_key>] [--priority normal\|high\|...] [--visibility ...]` | 创建图节点 + `OWNED_BY` + `SCOPED_AT` 边 + 可选 `PARENT_OF`；指定 `--to-pool <key>` 时 `assignee_kind=pool`、`pool_id=resolve(key)`、合并池默认值（[F05 §3.3](../../../task/SPEC/features/F05_TASK_POOL_FIRST_CLASS_REGISTRY.md#33-默认值合并语义)）、evaluate `publish_acl`；初始事件 `open`（`--draft` 则保留 `draft`）；默认 `workflow_ref={key:default_v1, version:1}` |
| `task publish <id> --to-pool <key>` | 把 `draft\|open` 任务发布或迁移到目标池 | 状态机 `event=publish`：解析 pool_key、check `publish_acl`、写 `nodes.attributes.pool_id`、`task_state_transitions(event=publish, metadata={from_pool_id, to_pool_id})`、`task_outbox(event_kind=task.published, pool_key=<new_key>)`；前置：无 active executor |

#### 池治理（admin）

| 子命令 | 权限 | 行为 |
|---|---|---|
| `task pool create <key> --display-name <N> [--owner @handle] [--workflow <k>:<v>] [--visibility ...] [--priority ...] [--publish-acl @file] [--consume-acl @file]` | `task.pool.admin` | 插入 `task_pools` 行；`key` 满足 `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,3}$` |
| `task pool update <key> [...]` | `task.pool.admin` | 更新非 `key` / 非 `id` 字段 |
| `task pool disable <key>` / `task pool enable <key>` | `task.pool.admin` | 设置 `is_active=false / true` |

#### 状态迁移（写）

所有迁移通过 `task_state_machine.transition` 走单事务：

| 子命令 | event | from → to（默认 workflow） |
|---|---|---|
| `task claim <id>` | `claim` | `open\|rejected → claimed`；额外评估池 `consume_acl` |
| `task assign <id> <handle>` | `assign` | `open → claimed`（payload.principal=<handle>） |
| `task start <id>` | `start` | `claimed\|rejected → in_progress` |
| `task submit-review <id> [--approver @handle]` | `submit-review` | `in_progress → pending_review` |
| `task approve <id>` | `approve` | `pending_review → approved` |
| `task reject <id> [--reason <R>]` | `reject` | `pending_review → rejected` |
| `task handoff <id> <handle>` | `handoff` | `approved → in_progress`（payload.principal=<handle>） |
| `task complete <id>` | `complete` | `in_progress\|approved → done`（父任务校验 children_all_terminal） |
| `task fail <id> --reason <R> [--error-code <E>]` | `fail` | `claimed\|in_progress → failed`（OQ-20 执行失败终态；payload 含 `failure_reason / error_code / retry_attempt`） |
| `task cancel <id>` | `cancel` | 任意非终态（含 `failed`）→ `cancelled` |
| `task expand <id>` | `expand` | 父任务子任务物化（≤ 50 同步；> 50 走异步协议见 [F01 §5.2](../../../task/SPEC/features/F01_TASK_ONTOLOGY_AND_NODE_TYPES.md#52-大范围-expand-的异步协议)）；异步时立刻返回 `{status:'pending', expansion_run_id}` |
| `task expansion show <run_id>` | — | 只读；返回 `task_runs(phase=expansion)` 行 + `extra.expansion_state` |

#### Bulk（决策 14：逐个 transition）

| 子命令 | 行为 |
|---|---|
| `task bulk-approve <id1,id2,...> [--bulk-id <B>]` | 命令层循环调 `task_state_machine.transition(event=approve)`，每个独立事务；幂等键自动 `<B>:<task_id>` |
| `task bulk-claim <id1,id2,...> [--bulk-id <B>]` | 同上，`event=claim` |

返回结构化 `data`：

```json
{
  "succeeded": [{"id": 1, "to_state": "approved", "event_seq": 6}, ...],
  "failed":    [{"id": 2, "reason": "AlreadyClaimedError"}, ...],
  "bulk_id":   "<B>"
}
```

### C. 错误形态（i18n key 草案）

| 错误 | i18n key |
|---|---|
| `WorkflowEventNotAllowed` | `commands.task.error.invalid_event` |
| `OptimisticLockError` | `commands.task.error.version_stale` |
| `AlreadyClaimedError` | `commands.task.error.already_claimed` |
| `RoleRequiredError` | `commands.task.error.role_required` |
| `PreconditionFailed` | `commands.task.error.precondition_failed` |
| `WorkflowDefinitionNotFound` | `commands.task.error.workflow_not_found` |
| `WorkflowDefinitionInactive` | `commands.task.error.workflow_inactive` |
| `PoolNotFound` | `commands.task.error.pool_not_found` |
| `PoolInactive` | `commands.task.error.pool_inactive` |
| `PublishAclDenied` | `commands.task.error.publish_denied` |
| `ConsumeAclDenied` | `commands.task.error.consume_denied` |
| `ChildrenNotTerminalError` | `commands.task.error.children_not_terminal` |
| `CycleDetected` | `commands.task.error.cycle_detected` |
| `SelectorBoundsExceeded` | `commands.task.error.selector_bounds_exceeded` |
| `ExpansionBackpressure` | `commands.task.error.expansion_backpressure` |
| `PermissionDenied` | `commands.task.error.forbidden` |
| `NotFound` | `commands.task.error.not_found` |
| `IdempotentReplay` | **非异常**；返回 `success` + `data.idempotent_replay=true` |

### D. CommandResult 约定

- **写命令**（迁移成功）：
  ```json
  {
    "success": true,
    "message": "<i18n: commands.task.<event>.success>",
    "data": {
      "task_id": 123,
      "from_state": "open",
      "to_state": "claimed",
      "event_seq": 4,
      "state_version": 5,
      "event": "claim",
      "idempotent_replay": false,
      "correlation_id": "...",
      "trace_id": "..."
    }
  }
  ```
- **只读列表**：`message` 多行表格（对齐 `agent list` 风格），`data` 含 `items[] + total`。
- **只读详情**：`message` 多段文本（标题/状态/角色/最近事件），`data` 含完整 dict。

### E. 副作用

- **写图**：仅在 `task create` 与 `task expand` 涉及创建任务节点（含 `OWNED_BY` / `SCOPED_AT` / `PARENT_OF` 边）；其它写命令仅经状态机服务更新 `nodes.attributes` 与关系表。
- **不直接** `commit session`；状态机服务管理事务边界。
- **i18n**：所有用户可见错误与成功文案来自 `commands.task.*` locales；硬编码字符串在契约中逐字记录。

## Non-Goals / Roadmap

- v1 不实现 `task watch <id>`（订阅事件流）；留 v2。
- v1 不实现 `task comment`（评论流）；见 [SPEC §10.2](../../../task/SPEC/SPEC.md#102-未来扩展v2-候选)。
- v1 不实现 `task delegate`（审批委托）；钩子点见 [F03 §6](../../../task/SPEC/features/F03_TASK_COLLABORATION_WORKFLOW.md#6-审批委托v1-仅文档化决策-13)。
- v1 不实现 `task search`（GraphRAG / 全文检索）；与 [F06 CampusLibrary](../../../models/SPEC/features/F06_CAMPUSLIBRARY_KNOWLEDGE_WORLD.md) 整合留 v2。
- 前端工作台视图不在本命令族范围内；通过 `POST /api/v1/command/execute` 间接复用。

## 相关

- 任务系统主 SPEC：[`../../../task/SPEC/SPEC.md`](../../../task/SPEC/SPEC.md)
- 任务本体（创建命令字段语义）：[`../../../task/SPEC/features/F01_TASK_ONTOLOGY_AND_NODE_TYPES.md`](../../../task/SPEC/features/F01_TASK_ONTOLOGY_AND_NODE_TYPES.md)
- 任务池与认领（`claim` / `assign` / `bulk-claim`）：[`../../../task/SPEC/features/F02_TASK_POOL_AND_CLAIM_PROTOCOL.md`](../../../task/SPEC/features/F02_TASK_POOL_AND_CLAIM_PROTOCOL.md)
- 任务池一等注册与治理（`task pool *` / `task publish` / ACL）：[`../../../task/SPEC/features/F05_TASK_POOL_FIRST_CLASS_REGISTRY.md`](../../../task/SPEC/features/F05_TASK_POOL_FIRST_CLASS_REGISTRY.md)
- 状态机与审批（`submit-review` / `approve` / `handoff` / `complete` / `cancel` / `expand`）：[`../../../task/SPEC/features/F03_TASK_COLLABORATION_WORKFLOW.md`](../../../task/SPEC/features/F03_TASK_COLLABORATION_WORKFLOW.md)
- 关系子底座（错误/事件落表位置）：[`../../../task/SPEC/features/F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md`](../../../task/SPEC/features/F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md)
- 命令模板：[`../template/CMD_COMMAND_TEMPLATE.md`](../template/CMD_COMMAND_TEMPLATE.md)
- npc_agent 接单契约：[`../../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md`](../../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)

## Tests

- `backend/tests/commands/test_task_commands.py`（Phase B 新建）：覆盖六个基础命令 + i18n + `--idempotency-key`。
- `backend/tests/services/test_task_state_machine.py`（Phase B 新建）：状态/事件矩阵单元测试。
- `backend/tests/integration/test_task_invariants.py`（Phase B 新建）：I1–I6 集成测试。
- `backend/tests/integration/test_task_handoff.py`（Phase C 新建）：agent1 → admin → agent2 端到端。
