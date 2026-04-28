# Task System TODO

> Phase A 已就 SPEC 定稿；本清单跟踪 Phase B/C 实施任务。与 [`SPEC.md`](SPEC.md) §6 与 [`ACCEPTANCE.md`](ACCEPTANCE.md) 对齐。

## Phase A — SPEC 定稿（本目录）

- [x] `SPEC.md` 主锚（设计律、SSOT、I1–I6、权限、可见性矩阵、备忘录）
- [x] `ACCEPTANCE.md` 文档级 + 实现级清单
- [x] `features/F01_TASK_ONTOLOGY_AND_NODE_TYPES.md`
- [x] `features/F02_TASK_POOL_AND_CLAIM_PROTOCOL.md`
- [x] `features/F03_TASK_COLLABORATION_WORKFLOW.md`
- [x] `features/F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md`
- [x] `features/F05_TASK_POOL_FIRST_CLASS_REGISTRY.md`（v1 起池一等实体 + ACL + 默认值 + MQ-ready）
- [x] `docs/command/SPEC/features/CMD_task.md`（父命令 + 子命令概述节，含 `task pool *` 与 `task publish`）
- [x] `docs/models/SPEC/SPEC.md` Feature Specs 列表追加 task 主 SPEC 链接
- [x] `docs/models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md` §4 末追加"任务接单契约"段落

## Phase B — 本体、表、基础命令

> 实施 SSOT：[`PLAN_PHASE_B.md`](PLAN_PHASE_B.md) — 6 PR 线性合并；I1/I3/I4/I5/I6/I2(局部) 全部覆盖；I7/I8 留 Phase C。事件集 = `create / publish / claim / assign / complete`。

### B.1 Ontology

- [x] 在 [`graph_seed_node_types.yaml`](../../../backend/db/ontology/graph_seed_node_types.yaml) 注册 `task` 类型与 `schema_definition.properties`（对齐 F01 §3，含 `pool_id`）。**(PR1)**
- [x] 在 [`backend/app/constants/trait_mask.py`](../../../backend/app/constants/trait_mask.py) 评审并写入 `trait_class=TASK` 与 `trait_mask=1089` 位编号。**(PR1)**
- [x] 在 `node_types.tags` 添加 `task`、`graph_seed` 等约定标签。**(PR1)**

### B.2 数据库迁移

- [x] 建表：`task_workflow_definitions / task_pools / task_details / task_assignments / task_state_transitions / task_runs / task_events / task_outbox`（DDL 见 F04 §3，落于 [`db/schemas/database_schema.sql`](../../../backend/db/schemas/database_schema.sql) `task_system` 段，由 `ensure_task_system_schema()` 幂等装载）。**(PR2)**
- [x] `task_assignments` 预留列 `lease_expires_at` / `last_heartbeat_at`（OQ-19 v1 NULL，Phase C 启用）+ `idx_task_assignments_lease_expiring` partial。**(PR2)**
- [x] `task_state_transitions` 预留列 `idempotency_expires_at`（OQ-26，7d TTL）+ shape CHECK。**(PR2)**
- [x] `task_runs` 支持 `phase='expansion'` + `extra.expansion_state` jsonb（OQ-21）字段就位（worker Phase C）。**(PR2)**
- [x] seed `task_workflow_definitions(key='default_v1', version=1, spec=...)`（F03 默认状态机，含 `fail → failed`）。**(PR2)**
- [x] seed `task_pools`：`hicampus.cleaning / hicampus.security / hicampus.maintenance`（F05 §9）。**(PR2)**
- [x] `nodes` 表 7 个 JSONB expression index 全部建立（F04 §3.9）。**(PR2)**
- [x] 索引齐全；`event_seq / idempotency_key` 唯一约束生效；`task_pools.key` 命名 CHECK 生效。**(PR2)**
- [x] 外键 `ON DELETE RESTRICT` 全表统一。**(PR2)**

### B.3 服务层

- [x] 新建 `app/services/task/__init__.py`、`app/services/task/task_state_machine.py`、`app/services/task/task_pool_service.py`。**(PR4)**
- [x] 实现 `transition(task_id, event, actor_principal, expected_version, *, idempotency_key=None, correlation_id=None, payload=None) -> TransitionResult`，**Phase B 仅放行 5 事件 `create / publish / claim / assign / complete`**；其余 Phase C 事件由白名单显式拒绝（`WorkflowEventNotAllowed`）。**(PR4)**
- [x] `workflow_ref` 创建时 pin 版本（B1-3 / OQ-23）：同事务 `SELECT MAX(version) WHERE is_active`；后续校验按 pin 版本。**(PR4)**
- [ ] 父任务 rollup 逻辑（B2-3 / I8）：留 Phase C — Phase B 任务无父子 rollup（`children_summary` 字段已就位但不写入）。**(Phase C)**
- [x] 单事务覆盖 F03 §3 模板的 8 步骤（不含 step 6' 父 rollup）；加锁顺序 `nodes → task_assignments → task_state_transitions → task_outbox`。**(PR4)**
- [x] 池 ACL 评估器 `evaluate_acl(actor, acl_dict)` 共用模块（F05 §4.1）。**(PR3)**
- [x] `task_pool_service`：`list_pools / get_pool_by_key`（pool CRUD 走命令直写表层）；`publish_to_pool` 已并入 `task_state_machine.transition('publish', ...)`；`get_pool_stats` 留 Phase C。**(PR4 / PR5)**
- [x] `OptimisticLockError` / 幂等命中 / `PoolInactive` / `PublishAclDenied` / `ConsumeAclDenied` 各自独立分支。**(PR3 / PR4)**
- [x] `correlation_id / trace_id` 自动从 `CommandContext` 提取（fallback 自动生成 UUID）。**(PR4 / PR5)**

### B.4 权限

- [x] 在 [`permissions.py`](../../../backend/app/core/permissions.py) 注册 §1.4 全部权限码（含 `task.publish` / `task.pool.admin`）—— Phase B 通过 `app/services/task/permissions.py::register_task_permissions_into_admin()` 在启动时把 `task.*` 注入 `ADMIN` 角色；`system` 虚拟主体（id=0, kind='system'）默认权限就位。**(PR3)**
- [x] 装饰器接入命令层：`require_permission(ctx, 'task.create')` 等（`app/commands/game/task/_helpers.py`）。**(PR5)**

### B.5 命令

- [x] 新建命令族 `app/commands/game/task/`：`task_command.py`（实现 `create / list / show / claim / assign / publish / complete`）、`task_pool_command.py`（实现 pool `list / show / create / update / disable / enable`，`stats` 留 Phase C）；Phase C 事件命令 `start / submit-review / approve / reject / handoff / fail / cancel / expand` 留 Phase C。**(PR5)**
- [x] `task create` 命令层执行 `scope_selector` bounds 校验（B2-6）；`--blocked-by` 环检测留 Phase C（命令未暴露该参数）。**(PR5 / PR3)**
- [x] 通过 [`app/commands/game/__init__.py::GAME_COMMANDS`](../../../backend/app/commands/game/__init__.py) 注册到命令注册表。**(PR5)**
- [x] i18n：`backend/app/commands/i18n/locales/{zh-CN,en-US}.yaml` 增补 `commands.task.*`（含 `pool_not_found / pool_inactive / publish_denied / consume_denied / cycle_detected / selector_bounds_exceeded` 等 Phase B 范围错误码）；`children_not_terminal / expansion_backpressure` 留 Phase C。**(PR5)**
- [x] 命令支持 `--idempotency-key` 选项；`task create` 支持 `--to-pool`；`task list` 支持 `--pool <key>`；`task fail --reason / --error-code` 留 Phase C。**(PR5)**

### B.6 测试

- [x] `tests/services/test_task_state_machine_unit.py`：状态/事件矩阵单元测试（5 事件白名单 + Phase C 拒绝路径）。**(PR4)**
- [x] `tests/services/test_task_acl.py`（含 `system` principal 与 ACL 各分支）。**(PR3)**
- [x] `tests/services/test_task_selector_validate.py`：bounds min/max + 未知 trait 名称违规路径。**(PR3)**
- [x] `tests/services/test_task_blocked_by_cycle.py`：环检测 + 深度 64 兜底。**(PR3)**
- [x] `tests/integration/test_task_invariants.py`：I1 / I4 / I5 / I6 集成测试（真 PostgreSQL，含 ACL 拒绝 + workflow_pin）。**(PR4)**
- [x] `tests/integration/test_task_invariants_i2.py`：I2 — `draft → open → claimed → done` 各状态 active roles ⊆ expected_roles。**(PR6)**
- [ ] `tests/integration/test_task_concurrency.py`：父子 rollup 并发 — Phase C；乐观锁 + 并发认领已在 `test_task_invariants.py` 与 `task_bench.py B2` 覆盖。**(Phase C)**
- [x] `tests/integration/test_task_pool_lifecycle.py`：`pool create → publish → claim → complete` 端到端 + ACL 拒绝路径，落于 [`tests/contracts/test_task_dual_protocol.py`](../../../backend/tests/contracts/test_task_dual_protocol.py)。**(PR5)**
- [ ] `tests/integration/test_task_expand_async.py`：异步 expand worker — Phase C。
- [x] workflow_pin：旧任务版本稳定（已并入 `tests/integration/test_task_invariants.py::test_workflow_pin_survives_new_version_seed`）。**(PR4)**
- [ ] `tests/integration/test_task_idempotency_ttl.py`：7d 过期复用键 — Phase C（TTL 已落 `idempotency_expires_at` 列；过期回收由 audit worker 实现）。
- [ ] `tests/integration/test_task_outbox_gc.py`：90d retention + audit GC — Phase C。
- [x] `tests/commands/test_task_command_parsing.py` + `tests/commands/test_task_i18n_keys_complete.py`：基础命令解析、权限、idempotency_key 派生、i18n 双语完整。**(PR5)**
- [x] `tests/contracts/test_task_dual_protocol.py`：SSH / REST 同源 + 池生命周期端到端。**(PR5)**
- [ ] `tests/chaos/test_task_chaos.py`：连接抖动 / 主备切换 / 时钟漂移 — Phase C。
- [x] `tests/bench/task_bench.py`：4 项 Phase B 性能基线（B1 transition 热路径 P99 ≤ 50ms / B2 32-agent claim ≥ 200 req/s / B3 池视图 / B4 selector 校验 ≤ 200ms）+ 烟雾测试 `tests/bench/test_task_bench_smoke.py`。**(PR6)**

## Phase C — 协作接力 / 池调度 / 观测 / Bulk

### C.1 状态机扩展

- [ ] `task_state_machine` 支持事件 `submit-review / approve / reject / handoff / cancel / expand`（基础事件已 B2 入 Phase B）。
- [ ] Lease / Heartbeat 启用（OQ-19 方案 B Phase C）：新增事件 `heartbeat / lease_expired`；audit worker 检测项；`task_assignments.lease_expires_at / last_heartbeat_at` 开始写入。
- [ ] `_resolve_effective_principal_for_event` 钩子点（为审批委托 v2 预留，v1 直接返回 `actor`）。

### C.2 命令扩展

- [ ] `task submit-review / approve / reject / handoff / cancel / expand` 命令。
- [ ] `task bulk-approve / bulk-claim` 命令（命令层循环 + 错误聚合，幂等键衍生）。
- [ ] `task workflow list|show <key>:<version>` 只读命令。
- [ ] `task pool stats <key>` 聚合实现（pending / claimed / in_progress / pending_review / 1h 完成数 / 平均认领等待时长）。

### C.3 Selector 与 Agent 接单

- [ ] `app/services/task/scope_selector.py` 解析器（include/exclude、descendants_of_anchor、type_code、tags_any）。
- [ ] `task expand` 子任务按需物化逻辑（含 workflow 上限护栏）。
- [ ] 执行实例 freeze：在 `task_runs.started_at` 时写 `graph_ops_summary.resolved_targets[]`。
- [ ] `npc_agent.subscription_bindings` 模板 `kind=pool, pool_key=<task_pools.key>`，含 `*` 通配展开缓存（默认 30s TTL）。

### C.4 观测

- [ ] structlog 事件接入：`task.created / opened / published / claimed / assigned / started / review_submitted / approved / rejected / failed / handoff / completed / cancelled / state_changed / expansion_started / expansion_progressed / expansion_completed / expansion_failed / children_rolled_up / consistency_drift / outbox_gc / outbox_pending / idempotency_expired / lease_expired(v2)`。
- [ ] `task.consistency_audit` 巡检 worker（默认 60s，可配置；**v1 仅检测 + outbox/idempotency 常态 GC**）：覆盖 I1 / I2 / I7 / I8 / `event_seq` 单调。
- [ ] `task.expand_worker` 异步 expand worker（OQ-21）：`FOR UPDATE SKIP LOCKED` 拉取 `task_runs(phase=expansion, status=running)`；按 `cursor` 分批推进；并发 `expand_concurrent_runs=4`。
- [ ] 集成测试覆盖 `agent1 → admin → agent2` 完整链路。
- [ ] 属性测试（`hypothesis`）随机事件序列保持 I1–I6。

## v2+ 备忘录（详见 [`SPEC.md`](SPEC.md) §10.2）

- [ ] 审批委托 `task_approval_delegations`。
- [ ] Lease/Heartbeat 启用（OQ-19 字段已预留，Phase C 实现）。
- [ ] `task migrate <id> --to <key>:<ver>`（OQ-23 跨版本迁移）。
- [ ] `retry` 一等事件与 `max_retries`。
- [ ] `suspended/paused` 状态。
- [ ] DB 级 I1 / I8 触发器防御（OQ-25 当前不引入）。
- [ ] Outbox 消费者 / MQ 接入（按 `task_outbox.pool_key` 路由到 MQ 主题；无池任务走 `task.system`）。
- [ ] 池配额执行（`task_pools.quota`：`max_inflight / max_pending / max_publish_rate`）。
- [ ] 池 consumer group / 分片键（多 agent 订阅同 pool 的热点分摊）。
- [ ] 池 ACL 升级为 policy engine（OPA / Casbin，OQ-27）。
- [ ] 池间合并 / 拆分迁移工具（admin CLI + 审计）。
- [ ] `task_snapshots` 快照回放加速。
- [ ] Audit tamper-proof hash chain。
- [ ] 表分区迁移（OQ-29 触发阈值见 F04 §10）。
- [ ] SLA 引擎（cron + `time.elapsed` 事件）。
- [ ] Token-bucket 抢单公平性。
- [ ] `task_template` 节点类型。
- [ ] `task_comments` 评论流。
- [ ] 多语言 `task_details_i18n`。
- [ ] 任务 DAG 依赖。
- [ ] 跨世界任务联邦。
- [ ] 向量化检索 / GraphRAG 整合。
- [ ] CQRS 读侧投影 `user_task_inbox`。
- [ ] 通知 fan-out 适配器（Slack / 邮件 / WebSocket）。
- [ ] `PARENT_OF` 自动 rollup（workflow opt-in）。
- [ ] 审计长保留与冷归档（分区表）。
- [ ] 物理删除路径 ADR。
