# Frontend Acceptance Checklist

## App Shell (transition)

- [x] No fixed left `Sidebar`; primary app nav is CampusWorld dropdown on `NavBar` (Works → History).
- [x] `NavBar` right **设置** keeps account profile (`/profile` tab) and logout; Guest/session not duplicated on `WorldTopBar`.
- [x] `TabBar` spans full width below `NavBar`; default tab is Works (`/works`).
- [x] Menu items open or activate separate tabs via `openAppTab`.
- [x] `/works` tab content uses flush layout (no extra `tab-content` padding).

## CampusWorld Interaction

- [x] `/works` renders the CampusWorld world interaction view.
- [x] `WorldTopBar` keeps world anchor, search, and Focus/Map view mode (no duplicate CampusWorld brand; app brand on `NavBar`).
- [x] `ProductWorldSwitcher` can enter another world and leave the current world.
- [x] State restoration uses account `location_id` through backend aggregation.
- [x] API, service, store, component, and type names avoid phase-specific labels.
- [x] Decision actions are submitted as `decision_event_id + option_id`.
- [x] `/` in the decision input opens `Command` / `AICO` mode selection.
- [x] Command mode calls graph search / command capabilities.
- [x] AICO mode uses HTTP SSE (`POST /decision-center/query/stream`) with Stop (Abort + stream cancel); **Send during stream** stops current stream and submits new query (scheme A).
- [x] Stream request carries optional `thread_id`; backend auto-cancels prior stream for same user+thread.
- [x] Plan-phase blocking LLM HTTP honours stream cancel within seconds (`LlmRequestCancelled`).
- [x] SSE `error.code=llm_timeout` maps to localized timeout copy (zh/en).
- [x] SSE `error.code=draft_incomplete` maps to localized incomplete-answer copy (zh/en).
- [x] AICO SSE: anti-buffer headers; `scope=activity` status (`working`/`tool`/`writing`/`rewrite`); provider token deltas only from the tick **presentation anchor** phase (Act if enabled, else Do, else Plan last ReAct round); queue poll ≤50ms; `state_patch` refresh without full session reload.
- [x] Presentation layer decoupled from PDCA: stream anchor matches `final_text` source; no Plan/Do internal or JSON tool-plan leakage; default AICO seed `act: skip` → anchor Plan; UI does not show plan/do/check/act phase names; `rewrite` on Check retry or before Act polish.
- [x] Decision input clears immediately on submit (before SSE completes).
- [x] Map, decision center, context summary, and utility drawer render as separate regions.
- [x] Decision center: task-zone / conversation-zone split; session area scrolls independently.
- [x] Decision center: three-state task fold (collapsed / split / maximized); hinge draggable in split mode; submit from maximized restores collapsed + conversation.
- [x] Decision center: zone headers, `zone-divider`, and surface contrast distinguish tasks vs conversation (CampusWorld workbench, not HMI).
- [x] Works default view mode is Focus; map pane collapsed strip on Focus; Map mode expands map pane.
- [x] Active task card and next-best action always visible; `viewFilter` only filters pending events.
- [x] Quick-query chips removed; backend `quickQueries` returns `[]`.
- [x] Command query applies `state_patch` and shows expandable results (`results[]` / `command_result.message`).
- [x] AICO: new conversation + thread switcher; Command single thread (50-message FIFO cap).
- [x] Logout archives AICO threads and Command conversation via `POST /world-history/conversations/archive`.

## Backend Adapter

- [x] `GET /api/v1/world-sessions/current` returns current interaction state.
- [x] `GET /api/v1/worlds/available` returns selectable worlds.
- [x] `POST /api/v1/world-sessions/enter-world` dispatches `enter <world_id>`.
- [x] `POST /api/v1/world-sessions/leave-world` dispatches `leave`.
- [x] `POST /api/v1/decision-center/actions` dispatches generated decision actions through command/task execution.
- [x] `POST /api/v1/decision-center/query` supports command and AICO modes.
- [x] `GET /api/v1/semantic-map/focus` returns drillable `focus_map` (`view_layer`, `anchor_id`, `mode`).
- [x] `POST /api/v1/semantic-map/actions` supports `drill` and `select` (no map move).
- [x] `GET /api/v1/semantic-map/space-summary` returns `space` command SSOT summary.
- [x] `POST /api/v1/semantic-map/query` returns a map patch.
- [x] `POST /api/v1/world-search` searches world entities and commands.
- [x] `GET /api/v1/world-history/summary` returns grouped history summary.

## Verification

- [x] `cd backend && conda run -n campusworld pytest tests/api/test_world_interaction_endpoints.py tests/services/test_task_visibility_sql.py tests/services/test_user_task_queue_mapping.py -q`
- [x] `cd frontend && npm run type-check`
- [x] `cd frontend && npm run test -- --run`
- [x] `cd frontend && npm run build`
- [x] `cd backend && conda run -n campusworld pytest tests/api -q`
- [x] `cd backend && conda run -n campusworld python scripts/validate_config.py`
- [x] `cd backend && conda run -n campusworld python scripts/validate_command_aliases.py`
- [ ] `cd backend && python scripts/validate_spec_layout.py`

## Phase 1 Milestone (admin @ singularity room)

- [x] Decision center cards map from user task queue (`task_visibility_sql` / `task_assignments` / pool visibility).
- [x] `GET /world-sessions/current` aggregate fields covered by mock API test (`lastHandledTask`, `mapDefaultCollapsed`, task `decisionEvents`).
- [x] No aggregator-side `task create` for device discovery (e.g. projector).
- [x] Context shows current space and optional `lastHandledTask`.
- [x] Map and context columns collapsible per `display_policy`.
- [x] `mapDefaultCollapsed` and `contextDefaultCollapsed` in display policy payload.
- [x] Minimal admin demo tasks seeded idempotently after task system seed.

## Deferred Notes

- SPEC layout validation currently fails on the pre-existing command feature filename `docs/command/SPEC/features/ALIAS_GOVERNANCE.md`.
- Browser inspection reached the login redirect for `/works`; authenticated visual inspection still needs a valid Web UI session.
- [x] Semantic map Phase A/B: north-up compass room layer; edge direction labels; map click → highlight + space summary (no default `go`); drill building/floor/campus via breadcrumb; floor grid layout when `map_grid_*` present, else list +「平面图未就绪」.
- [x] Semantic map Phase C: campus layer uses `campus_grid_col/row` and `layout: campus-grid` (distinct from floor `grid`); search「F3」highlights building on campus view; minimap + mapPatch `viewLayer`/`highlightedNodeIds` via WS/state_patch.
- Phase 2+ remainder: bottom drawer read-only archived history, `task` type enum alignment, mobile §29 layout order, Agent attention, EventTriage L2, HiCampus eight-step demo path.
