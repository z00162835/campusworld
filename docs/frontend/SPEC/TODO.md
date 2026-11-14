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

- [ ] Follow up the baseline NDJSON event-position tests and Streamlit evaluation temporary-path test; backend quick sweep is not yet green.
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
- [x] 现有 Memory thread 保留实际 `agent_node_id`，持久化不可变 Quest/collaboration 绑定、创建 revision 和 Objective 引用，拒绝跨账户/Agent复用及重新绑定。
- [ ] Quest 生命周期触发 thread 后端归档，并将 account+Agent+Quest 图引用安全交接到 episodic/LTM；world archive 仅作兼容投影。
- [ ] DecisionOption 增加 confirmed/predicted/proposed consequence、provenance/confidence、risk/gate/evidence/reversibility/affected refs。
- [ ] 实现组合 Quest governance、F16 behavior policy 与 command authorization 的 decision facade；三平面保持独立真源和审计。
- [ ] 动作文案改为 `labelKey + labelParams`，后端 `label` 仅兼容 fallback。

### G3 World Pulse and Feedback

- [x] World Pulse 从可读 Situation 投影生成，以 `situation_attention` 保存账户级 seen/snoozed/UI-dismiss，并与业务 dismissed/resolved 区分。
- [x] 从权限过滤的 Objective transition audit 投影 World Feedback，展示 actor、结果、correlation 与时间。
- [ ] 实现基于注册 command/process capability 的显式自动执行编排器；全动态执行延后。
- [ ] 自动失败、越权、缺证和低置信度进入人工 Pulse escalation。
- [x] 移除本地 hide-all 的“clear resolved”语义。

### G4 Game-native UI and release gate

- [ ] 完成 World Pulse、Tracked Quest HUD、Quest Journal、Companion、Choice Consequence 和 World Feedback 的独立组件拆分（当前 World Pulse/Feedback 已进入 QuestTracker slice）。
- [ ] 完成 Map/Quest/Key Clues 多实体双向联动与 Map-canvas + responsive HUD 移动端体验。
- [ ] 完成键盘、读屏、200% zoom、对比度和 reduced-motion 验收（已补充 QuestTracker live announcement、progress label、窄屏排版与 reduced-motion 样式，仍需全路径验收）。
- [ ] 完成 authenticated `/works` E2E，并达到 80% 用户 30 秒内定向、90% 无指导完成受治理行动、授权误解率 ≤5%、stale recovery ≥95%、关键路径键盘覆盖 100%、抽样读屏完成率 ≥90%。

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
