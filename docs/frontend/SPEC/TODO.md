# TODO - Frontend Development Tasks

Active plan: [`_generated/F03_QUEST_WORLD_INTERACTION_IMPLEMENTATION_PLAN.md`](_generated/F03_QUEST_WORLD_INTERACTION_IMPLEMENTATION_PLAN.md)

Archived plan: [`_generated/CAMPUSWORLD_NEXT_UI_IMPLEMENTATION_PLAN.md`](_generated/CAMPUSWORLD_NEXT_UI_IMPLEMENTATION_PLAN.md)

App shell refactor plan: `app_shell_nav_refactor`（CampusWorld 下拉导航、全宽 Tab、设置保留账号/退出）

## F03 — Quest World Interaction（approved for implementation）

Stable contract: [`features/F03_AI_NATIVE_QUEST_INTERACTION.md`](features/F03_AI_NATIVE_QUEST_INTERACTION.md)

### G0 Contract

- [x] 冻结 F03 Phase 1→F06 R1、Phase 2/3→R2、Evidence→R3、Learning→R4 的交付映射，并与 F02/F06 对齐。
- [x] 人工按行确认 P01–P16 架构决策，并同步稳定 SPEC 与实施计划。
- [x] 人工按行确认 C01–C13 实现契约，包含多 Quest tracking、Observation、Memory、Policy composition、attention、Journal 与 UX 阈值。
- [x] 审核 `TRACKS_QUEST / FOCUSES_ON / PINS_CLUE / ASSISTED_BY`、Memory 绑定、三平面 Policy decision、Quest projection、DecisionOption v2 与 conversation context 契约。
- [x] 确认用户界面术语与底层领域术语的唯一映射：World Journal 为顶层历史，Quest Journal 为选中 Quest 的任务日志。
- [x] 定义后端 `contractVersion + capabilities + projectionRevision + lastEventId`、mutation envelope 与 stale behavior 契约。

### G1 Authoritative Quest projection — implementation complete; PostgreSQL acceptance pending

- [ ] Follow up the baseline NDJSON event-position tests, Streamlit evaluation temporary-path test and intermittent autostop timing assertion; backend quick sweep is not yet green.
- [ ] Standardize the frontend test Node runtime so the default invocation avoids the experimental Web Storage conflict.
- [ ] Add database-level active account+Quest tracking uniqueness as defense in depth; current protection uses the account revision row lock and service checks.

- [x] 实现多个显式 track、按 Quest untrack、账户唯一 Objective focus、canonical Observation Clue pin/unpin 与可见但不自动持久化的推荐 Quest。
- [x] 实现多 Agent `ASSISTED_BY` 协作关系、角色生命周期与 primary Companion 解析。
- [x] 用完整 Objective 聚合替换 queue-first active task 与合成百分比。
- [x] 增加 `primarySubjectRef / relatedEntityRefs / scopedAtRef`、server projection revision 和 last event id。
- [x] `/world-sessions/current` 聚合权限过滤的 Quest Journal 关系图/Tracked Quest read model。
- [ ] PostgreSQL acceptance：运行 `tests/integration/test_quest_interaction_runtime.py`，验证 graph mutation、权限过滤、协作与投影端到端。

### G2 Companion and governed choices

- [x] AICO SSE 接收并鉴权结构化 `QuestConversationContext`；按当前账户、tracked Quest、Objective、协作 Agent 和投影 revision 校验。
- [ ] 扩展完整对话 reference pack：当前地图焦点、pinned Policy/Process/Quality refs 和可见 Evidence 的结构化引用/摘要须重新鉴权并进入模型上下文；当前服务端主要提供 Quest/Situation/Goal/Objective 摘要，不能宣称完整 pack 已交付。
- [x] 现有 Memory thread 保留实际 `agent_node_id`，持久化不可变 Quest/collaboration 绑定、创建 revision 和 Objective 引用，拒绝跨账户/Agent复用及重新绑定。
  - 前台 Quest 即使没有 actionable task 也提供 Companion 对话；普通输入跟随最新前台上下文。Quest/Agent/协作关系变更隔离本地线程，取消追踪不沿用旧绑定；具体关系身份由服务端投影，最终仍重新鉴权。Objective 使用共享 Task visibility，不用 semantic ownership 错误拒绝可见池任务。
- [ ] Quest 生命周期触发 thread 后端归档，并将 account+Agent+Quest 图引用安全交接到 episodic/LTM；world archive 仅作兼容投影。
  - 协作结束/替换已接入同事务 thread 归档和 `quest_episode_input` raw 输入，保留账户、Agent、thread、Quest、创建 revision、图引用、STM 明文及滚动摘要；busy thread 拒绝归档，归档与会话复用共享线程锁。Quest 完成/关闭入口尚未完成，不能将此项勾选。异步正式记忆晋升/发布为后续学习闭环，不单独阻塞 UI Active。N01:A 的显式删除会清除 episode 明文与直接衍生 LTM，保留最小 redaction 审计。
- [ ] DecisionOption 增加 confirmed/predicted/proposed consequence、provenance/confidence、risk/gate/evidence/reversibility/affected refs。
  - 共享 ChoiceConsequence 已展示风险、门槛、证据、影响范围及预测不确定性；未知值不合成安全结论。受治理选项预览已从精确发布的 Policy/Process 图版本读取并求值，执行时重新求值；生产规则发布和 authenticated 体验验收仍待完成。
- [ ] 实现组合 Quest governance、F16 behavior policy 与 command authorization 的 decision facade；三平面保持独立真源和审计。
  - 已实现 GraphQuestGovernance、独立组合原语、QuestActionExecutor 与 UI decision-action 接入；治理、适用的实际 Agent behavior gate 和最终 registry command authorization 分别审计。复用 task_runs/task_events/AgentRunRecord，并在状态机强制一次性主体/对象/事务/版本绑定许可。隔离 fixture 不发布生产规则；数据库事务/并发验收及 Agent worker 接入仍待完成，不能据此关闭整项门禁。
  - 治理结果已绑定原始 Quest/Objective/主体/Agent/命令上下文；匹配 revision 与规则版本也不能跨请求复用，已补五类拒绝回归。
  - 一致性复核修复：预览/能力编译不加行锁，执行在账户/对象锁后使用独立加锁源重新求值；严格共用 ID 模板渲染器，拒绝属性访问/下标/转换/格式扩展。数据库并发测试仍未执行。
- [ ] 对接正式规则发布入口的版本唯一性、已发布定义不可变及修订新版本约束；不能只依赖 runtime 精确引用查询。接入前不得启用生产 enforced Quest。
- [x] 动作文案改为 `labelKey + labelParams`，后端 `label` 仅兼容 fallback。

### G3 World Pulse and Feedback

- [x] World Pulse 从可读 Situation 投影生成，以 `situation_attention` 保存账户级 seen/snoozed/UI-dismiss，并与业务 dismissed/resolved 区分。
- [x] 从权限过滤的 Objective transition audit 投影 World Feedback，展示 actor、结果、correlation 与时间。
  - WorldFeedback 已拆为独立只读组件，展示实际 actor 类型/ID、Objective 状态、时间和 Quest/Objective/correlation 审计详情；人工事件不再统一写成“你”，缺失时间与关联标识显式降级。
- [ ] 实现基于注册 command/process capability 的显式自动执行编排器；全动态执行延后。
  - 共享显式执行器已实现有限发布模板、实际 Agent 身份、独立授权、幂等 replay、领域版本冲突、savepoint 回滚、SQL 超时与 cooperative cancellation/kill switch。仅允许显式支持托管事务的 DB 命令分支（当前 `look`、`task claim/start/complete`）；不承诺外部 I/O 的撤回或 CPU 强制抢占。真实感知/调度 worker 尚未接入，不自动启用生产规则。
- [ ] 自动失败、越权、缺证和低置信度进入人工 Pulse escalation。
  - 执行器失败/拒绝已写入权限过滤的 Feedback/Pulse；晚于个人隐藏/稍后提醒的新失败重新提示。领域版本冲突在执行前拒绝；不可读对象不公开失败详情。仍需真实 Agent 调度与 PostgreSQL 验收。
- [x] 移除本地 hide-all 的“clear resolved”语义。

### G4 Game-native UI and release gate

- [x] 完成 World Pulse、Tracked Quest HUD、Quest Journal、Companion、Choice Consequence 和 World Feedback 的独立组件拆分。
  - 六个组件复用唯一 worldSession 投影；子组件只发 intent，不复制业务状态或授权。组件测试已覆盖，全路径体验仍待验收。
- [ ] 完成 Map/Quest/Key Clues 多实体双向联动与 Map-canvas + responsive HUD 移动端体验。
  - Journal 支持只读节点/关系检查，过滤缺失端点的边；仅对当前 Quest 明确给出的非业务语义地图实体提供定位，地图选中实体在日志中同步文字标记。未解析引用不可定位；日志局部选择/清除不改变持久化 focus 或位置。窄屏保留 Map 底图，前台 Quest/Objective 紧凑 HUD + 单一任务/线索展开层，定位会收起展开层；切层不发业务 mutation。组件测试覆盖，真实移动端视觉/触控仍待验收。
- [ ] 完成键盘、读屏、200% zoom、对比度和 reduced-motion 验收（已补充 QuestTracker live announcement、progress label、窄屏排版与 reduced-motion 样式，仍需全路径验收）。
- [ ] 完成 authenticated `/works` E2E，并达到 80% 用户 30 秒内定向、90% 无指导完成受治理行动、授权误解率 ≤5%、stale recovery ≥95%、关键路径键盘覆盖 100%、抽样读屏完成率 ≥90%。

## Review follow-up

Latest [SPEC/code consistency review](_generated/F03_QUEST_SPEC_CODE_CONSISTENCY_REVIEW_20261114.md) records the corrected preview lock order, foreground dialogue identity, restricted templates and Objective visibility, plus the still-open implementation/acceptance boundaries.

### Confirmed human review — 2026-11-14

| ID | Decision | A | B |
| --- | --- | --- | --- |
| N01 | Learning-input snapshot retention after explicit thread deletion | Treat episodic plaintext as forgettable memory and clear it with explicit thread deletion, while retaining minimal action audit metadata (recommended) | Retain plaintext separately under an explicitly configured retention/access policy |
| N02 | First governed-runtime implementation scenario | Start with an isolated test scenario using existing registered capabilities and pinned rule/process fixtures; do not invent production enterprise rules (recommended) | Prioritize a customer-supplied versioned SOP/Control scenario; wait for those inputs before the business vertical slice |
| N03 | Authenticated UI acceptance | User signs in to a local test environment and confirms disposable test scope, then perform real-page acceptance (recommended) | Continue component/offline verification; keep authenticated UI gates open |

Confirmed selections: **N01:A, N02:A, N03:B**. Implement explicit thread deletion cleanup of scoped learning plaintext with minimal redaction audit. Use isolated fixtures and existing registered capabilities for the first governance composition scenario; do not publish production rules. Continue offline/component verification and leave authenticated UI gates open. No live data deletion or authenticated business mutation is performed as part of this implementation. Previously approved graph, policy composition and automation boundaries are unchanged.

## App Shell Nav Refactor

- [x] Replace fixed `Sidebar` with `AppNavMenu` on `NavBar` (CampusWorld dropdown).
- [x] Delete `Sidebar.vue` and `sidebar.css`; full-width `app-wrapper` / `TabBar`.
- [x] Keep **设置** on `NavBar` for profile + logout (F01 §0.2 / §6.8).
- [x] `WorldTopBar`: remove duplicate CampusWorld label; world/search/view only.
- [x] `tab-content--flush` for `/works` only.
- [x] SPEC/ACCEPTANCE updated for §0.2 app shell and settings placement.

## CampusWorld World Interaction

- [x] Upgrade `/works` to render `WorldInteractionView`.
- [x] Add stable world interaction API clients without phase-specific names.
- [x] Add Pinia state for world session, decision center, map, context, history, commands, and connection status.
- [x] Add `WorldTopBar` with `ProductWorldSwitcher`.
- [x] Add semantic map, decision center, context summary, and bottom utility drawer regions.
- [x] Add `/` mode selector for `Command` and `AICO`.
- [x] Keep legacy works components available but remove them from the `/works` primary surface.

## Backend Integration

- [x] Add `world-sessions` adapter endpoints.
- [x] Add world availability endpoint.
- [x] Add decision action, decision query, semantic map query, world search, and history summary endpoints.
- [x] Route generated decision actions through command/task execution.
- [x] Restore current state from account `location_id`.

## Phase 1 — Decision center UX (closed)

- [x] Task-zone / conversation-zone layout; remove `QuickQueryChips`.
- [x] Active task + next-best action always visible.
- [x] Command sync query + `state_patch`; expandable `QueryResultCard`.
- [x] AICO SSE stream + Stop + thread switcher; logout conversation archive.
- [x] `DecisionCenterFlow` unit test for always-visible task card.

## Phase 1 (current milestone)

- [x] Decision center driven by `user_task_queue` (Task SPEC §1.5 via `task_visibility_sql.py`, shared with `task list`).
- [x] Remove UI-side `task create` from world interaction aggregator.
- [x] Context `lastHandledTask` + queue-backed `pendingDecisionCount`.
- [x] Collapsible semantic map and context panes (`mapDefaultCollapsed` / `contextDefaultCollapsed`).
- [x] Admin demo tasks via `ensure_world_ui_demo_tasks` (direct assign).
- [x] Logout resets `worldSession`, `worldHistory`, `connection`, `commands`.
- [x] i18n keys under `worldInteraction.*`.

## Follow-Up (Phase 2+)

- [x] Semantic map click linkage (F01 §8.6): browse/highlight/summary decoupled from `go`.
- [x] `GET /api/v1/semantic-map/focus` + `POST /api/v1/semantic-map/actions` (drill/select).
- [x] Phase B drill layers: building/floor/campus breadcrumb + floor grid/list fallback.
- [x] Phase C: campus `campus_grid_*` content (HiCampus buildings + outdoor anchors), minimap (D14), WS `mapPatch` viewLayer/highlightedNodeIds (D19), `semantic-map/query` + GlobalCommandSearch map highlight.
- [x] Frontend semantic map SSOT: [`features/F02_SEMANTIC_MAP_FRONTEND.md`](features/F02_SEMANTIC_MAP_FRONTEND.md).
- [ ] `GlobalCommandSearch` → `world-search` results overlay (thread write already shared).
- [x] Bottom utility drawer: read-only display of archived AICO/Command history from `GET /world-history/summary` (structured fields, loading/error states).
- [ ] Align decision `task` event type enum in TS + API.
- [ ] Mobile §29: top bar order and `CampusWorld / ⌘ / ☰` compression.
- [ ] Expand real task selection once world-scoped task search is productized.
- [ ] Add authenticated browser regression coverage for `/works`.
- [ ] Extend WebSocket state patch handling beyond the initial adapter path.
- [ ] Agent attention items, EventTriage L2, achievements, HiCampus full demo path.

## Semantic Map Entity Inspect

- [ ] **Deferred** Agent inspect dialogue action: wire inspect sheet to Agent Web conversation when generic SSE/stream API is ready (see F02 §14.3).
