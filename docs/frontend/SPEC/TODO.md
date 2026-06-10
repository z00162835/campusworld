# TODO - Frontend Development Tasks

Active plan: [`_generated/CAMPUSWORLD_NEXT_UI_IMPLEMENTATION_PLAN.md`](_generated/CAMPUSWORLD_NEXT_UI_IMPLEMENTATION_PLAN.md)  
App shell refactor plan: `app_shell_nav_refactor`（CampusWorld 下拉导航、全宽 Tab、设置保留账号/退出）

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
- [ ] `GlobalCommandSearch` → `world-search` results overlay (thread write already shared).
- [ ] Bottom utility drawer: read-only display of archived AICO/Command history from `GET /world-history/summary`.
- [ ] Align decision `task` event type enum in TS + API.
- [ ] Mobile §29: top bar order and `CampusWorld / ⌘ / ☰` compression.
- [ ] Expand real task selection once world-scoped task search is productized.
- [ ] Add authenticated browser regression coverage for `/works`.
- [ ] Extend WebSocket state patch handling beyond the initial adapter path.
- [ ] Agent attention items, EventTriage L2, achievements, HiCampus full demo path.
