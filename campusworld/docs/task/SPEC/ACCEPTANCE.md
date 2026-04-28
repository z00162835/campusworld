# Task System ACCEPTANCE

> Phase A 文档级与 Phase B/C 实现级接受度清单。与 [`SPEC.md`](SPEC.md) §7 对齐。

## A. Phase A — 文档级 ACCEPTANCE

- [ ] 主 SPEC `SPEC.md` 设计律 D1–D3、SSOT 字段表、I1–I8 不变式（含 I7 Outbox 保留、I8 父子 rollup）经评审无异议。
- [ ] 可见性矩阵 §1.5 与 [F11 `data_access`](../../api/SPEC/features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md) 表达式无冲突。
- [ ] 权限码 §1.4 与 [`backend/app/core/permissions.py`](../../../backend/app/core/permissions.py) 既有命名习惯一致。
- [ ] jsonb `_schema_version` 约定 §1.6 在 8 张表 DDL 中一致体现。
- [ ] F01 属性辞典与 [`backend/db/ontology/graph_seed_node_types.yaml`](../../../backend/db/ontology/graph_seed_node_types.yaml) 既有结构（如 `npc_agent`）保持同形。
- [ ] F02 池可见性 SQL 谓词与 §1.5 矩阵一致；并发认领的乐观锁路径明确。
- [ ] F03 单事务模板覆盖加锁顺序、`event_seq` 取值、幂等命中、Outbox 同事务；审批接力示例（agent1 → admin → agent2）与 `task_assignments` 行变化自洽。
- [ ] F04 八张表 DDL 字段命名与本仓库约定（`agent_run_records / agent_memory_entries`）一致；`ON DELETE RESTRICT` 与软删策略 §1.7 自洽；`task_pools` 含 `key` 命名 CHECK + `pool_key` 在 outbox 冗余列。
- [ ] F05 池一等模型：`task_pools` 字段、ACL schema、默认值合并语义、命名规范、seed 池清单、MQ 路由键预留齐备；与 [F11 `data_access`](../../api/SPEC/features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md) 的级联关系明确。
- [ ] 命令族 [`CMD_task`](../../command/SPEC/features/CMD_task.md) 与统一状态机入口约束一致；只读命令不经状态机；写命令均接受 `--idempotency-key`；含 `task pool list/show/create/update/disable/enable/stats` 与 `task publish` 子命令；`task create --to-pool <key>` 路径完整。
- [ ] 与 [F02 npc_agent](../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md) 的 `subscription_bindings.kind=pool, pool_key=...` 接单契约自洽，含通配 `pool_key='<x>.*'` 展开。
- [ ] §10 备忘录覆盖所有已答复决策与未来扩展项；OQ-11 ~ OQ-30 对照实现位置准确。
- [ ] 性能基线（§1.8.2）与 Chaos 测试（§1.8.1）条款评审通过；基准脚本 `task_bench.py` 在 Phase B 发布前完成跑测。

## B. Phase B — 实现级 ACCEPTANCE

> 实施 SSOT：[`PLAN_PHASE_B.md`](PLAN_PHASE_B.md)。**Phase B 的状态机事件白名单 = `create / publish / claim / assign / complete`**；其余事件由 `task_state_machine.transition` 显式拒绝（`WorkflowEventNotAllowed`），并标注下方为 "→ Phase C"。

### B.1 Ontology 与迁移

- [x] `task` 节点类型注册到 `graph_seed_node_types.yaml`，含 `current_state / state_version / workflow_ref / pool_id / scope_selector / children_summary / title / priority / due_at / assignee_kind / visibility / tags`。 **(PR1)**
- [x] 八张关系表迁移落地：`task_workflow_definitions / task_pools / task_details / task_assignments / task_state_transitions / task_runs / task_events / task_outbox`（落于 [`db/schemas/database_schema.sql`](../../../backend/db/schemas/database_schema.sql) `task_system` 段，由 `db/schema_migrations.py::ensure_task_system_schema` 幂等装载）。 **(PR2)**
- [x] 索引与唯一约束齐全：`task_state_transitions(task_node_id, event_seq)` UNIQUE、`(task_node_id, idempotency_key) WHERE NOT NULL` UNIQUE partial、`task_pools(key)` UNIQUE + key 格式 CHECK、`task_state_transitions` idempotency shape CHECK、`task_assignments idx_..._lease_expiring` partial index 就位但 v1 无行写入。 **(PR2)**
- [x] `nodes` 表 7 个 JSONB expression index 全部建立（`current_state / pool_id / assignee_kind / visibility / priority / workflow_key / due_at`）；典型查询 `EXPLAIN ANALYZE` 命中（[`tests/db/test_task_system_schema_postgres.py`](../../../backend/tests/db/test_task_system_schema_postgres.py)）。 **(PR2)**
- [x] `task_assignments` 的 group CHECK 约束生效（`principal_kind='group'` ↔ `principal_tag IS NOT NULL AND principal_id IS NULL`）。 **(PR2)**
- [x] `trait_class=TASK` 位图编号经评审写入 [`backend/app/constants/trait_mask.py`](../../../backend/app/constants/trait_mask.py)（`TASK_MARKER=1<<10`，`TASK = CONCEPTUAL | EVENT_BASED | TASK_MARKER = 1089`）。 **(PR1)**
- [x] Seed 池写入：`hicampus.cleaning / hicampus.security / hicampus.maintenance`（详见 [F05 §9](features/F05_TASK_POOL_FIRST_CLASS_REGISTRY.md#9-默认-seed-池phase-b-写入)）。 **(PR2)**

### B.2 服务与权限

- [x] `app/services/task/task_state_machine.py::transition` 实现，参数含 `idempotency_key / correlation_id / payload`，**Phase B 仅放行事件 `create / publish / claim / assign / complete`**；其余事件 (`start / submit-review / approve / reject / handoff / fail / cancel / expand`) → Phase C。 **(PR4)**
- [x] `transition` 单事务覆盖：幂等命中 → FOR UPDATE → 池 ACL 校验 → 校验 → `event_seq` → SSOT 更新（`current_state / state_version / pool_id`）→ assignments 维护 → transitions 追加（含 `idempotency_expires_at = now()+7d`）→ outbox（带 `pool_key`）。父 rollup（`children_summary` / step 6'）→ Phase C。 **(PR4)**
- [x] 加锁顺序固定 `nodes → task_assignments → task_state_transitions → task_outbox`（Phase B 无父子，故无 `nodes(parent)`）；并发 claim 用 32-agent bench 验证。 **(PR4 / PR6)**
- [x] RBAC 权限码 §1.4 注册到 `permissions.py`（含 `task.publish` / `task.pool.admin`）—— Phase B 通过 `app/services/task/permissions.py::register_task_permissions_into_admin()` 启动时注入 `ADMIN` 角色；命令层装饰器引用；`system` 虚拟主体（id=0, kind='system'）默认权限就位。 **(PR3)**
- [x] 默认 `workflow_definition` 行 `(key='default_v1', version=1)` 由 seed 写入；`task create` 同事务 pin `MAX(version) WHERE is_active`，新版本上线后旧任务继续按 v=1 校验（`tests/integration/test_task_invariants.py::test_workflow_pin_survives_new_version_seed`）。 **(PR2 / PR4)**
- [x] `task_pool_service` 实现 `list_pools / get_pool_by_key`；`publish_to_pool` 已并入 `task_state_machine.transition('publish', ...)`；`get_pool_stats` → Phase C。池 CRUD 经命令直写表层（`app/commands/game/task/task_pool_command.py`）。 **(PR4 / PR5)**
- [ ] `fail / failed` 事件与终态集成测试 → **Phase C**（事件白名单未放行）。
- [x] `BLOCKED_BY` 环检测：`app/services/task/blocked_by.py` 实现递归 CTE + 深度 64 兜底；A→B→C→A / 65 深度链均命中 `CycleDetected`。 **(PR3)**
- [x] `scope_selector.bounds`：`validate_selector` + `enforce_bounds` 实现 min/max 校验，`max=10` 场景解析 15 目标返回 `SelectorBoundsExceeded`。 **(PR3)**
- [ ] 异步 expand：N=200 worker 崩溃恢复 → **Phase C**（`task_runs.phase='expansion'` 列已就位）。
- [ ] `task.consistency_audit` worker → **Phase C**（I1/I7/I8 漂移、outbox 90d GC、idempotency 过期回收均由该 worker 处理；I3 已由 PR3 静态检查防御）。

### B.3 命令

- [x] `task create / list / show / claim / assign / complete / publish` + `task pool list / show / create / update / disable / enable` 命令实现（`app/commands/game/task/`），SSH `cmdset` 与 `POST /api/v1/command/execute` 同源（[`tests/contracts/test_task_dual_protocol.py`](../../../backend/tests/contracts/test_task_dual_protocol.py)）；`task pool stats` → Phase C。 **(PR5)**
- [x] `task create --to-pool <key>` 自动应用池默认值并经 `task_state_machine.transition('publish', ...)` evaluate `publish_acl`；缺权限返回 `PublishAclDenied`。 **(PR5)**
- [x] 所有写命令支持 `--idempotency-key`（缺省由 `(actor, command, args_hash, correlation_id)` 派生）；幂等命中返回原 `TransitionResult` 且 `idempotent_replay=true`。 **(PR5)**
- [x] i18n 键 `commands.task.*`（含 `pool_not_found / pool_inactive / publish_denied / consume_denied / cycle_detected / selector_bounds_exceeded` 等）在 `backend/app/commands/i18n/locales/{zh-CN,en-US}.yaml` 落值；CI 以 [`tests/commands/test_task_i18n_keys_complete.py`](../../../backend/tests/commands/test_task_i18n_keys_complete.py) 防漂移。 **(PR5)**

### B.4 测试

- [x] 单元：`task_state_machine` Phase B 5 事件矩阵 + Phase C 拒绝路径（`tests/services/test_task_state_machine_unit.py`）；selector 解析（含 bounds / trait_*）；workflow_definition 校验；池 ACL 评估器；`BLOCKED_BY` 环检测。 **(PR3 / PR4)**
- [x] 集成：I1 / I3（CI 静态）/ I4 / I5 / I6 + I2 局部覆盖（`tests/integration/test_task_invariants.py`、`test_task_invariants_i2.py`）；池 `publish_acl` 拒绝路径；`workflow_ref` pin；`pool_id` 不存在拒绝。父子 rollup 并发 / async expand / I7 / I8 / I2 完整非 Phase B 状态 → **Phase C**。 **(PR4 / PR6)**
- [x] 契约：SSH 与 `POST /api/v1/command/execute` 同源（[`tests/contracts/test_task_dual_protocol.py`](../../../backend/tests/contracts/test_task_dual_protocol.py)）；`pool create → task create → publish → claim → complete` 端到端绿。 **(PR5)**
- [x] 性能：[`tests/bench/task_bench.py`](../../../backend/tests/bench/task_bench.py) 覆盖 Phase B 4 项基线（B1 transition 热路径 / B2 32-agent claim / B3 池视图 / B4 selector 校验）；smoke 模式在 CI 跑通；release 模式手动；首版基线允许 ≥ 70% 余量。 **(PR6)**
- [ ] Chaos：连接抖动 / 主备切换 / 时钟漂移 → **Phase C**。

## C. Phase C — 协作 / 接力 / 池调度 / 观测

- [ ] 状态机扩展事件 `submit-review / approve / reject / handoff / cancel / expand` 实现。
- [ ] `agent1 → admin → agent2` 接力链路集成测试通过；`task_assignments` 行变化与 `task_state_transitions.event_seq` 单调一致。
- [ ] `npc_agent` 订阅 `kind=pool, pool_key=<task_pools.key>` 含 `*` 通配落地；通配展开缓存策略明确；agent 自主认领可达端到端。
- [ ] `task_outbox.pool_key` 列与 `payload.pool_key` 一致；非池任务为 `task.system`；为 v2 MQ dispatcher 提供路由就绪格式。
- [ ] selector 解析器 + late-binding freeze：`task_runs.graph_ops_summary.resolved_targets[]` 在 `started_at` 写入。
- [ ] `task.consistency_audit` 巡检 worker 实现；不一致写 `task_events.kind=consistency_drift` + structlog 告警；**v1 不自愈**。
- [ ] 属性测试（`hypothesis`）随机事件序列保持 I1–I6。
- [ ] Bulk 命令 `task bulk-approve / bulk-claim` 命令层循环 + 错误聚合返回；幂等键 `<bulk_id>:<task_id>` 衍生。
- [ ] structlog 事件名清单与 F04 §"事件名" 一致：`task.created / published / claimed / assigned / state_changed / approved / rejected / completed / cancelled / handoff / consistency_drift / outbox_pending`。
