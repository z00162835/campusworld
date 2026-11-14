# Frontend Acceptance Checklist

## F03 Implementation Activation Gates

Active implementation plan: [`_generated/F03_QUEST_WORLD_INTERACTION_IMPLEMENTATION_PLAN.md`](_generated/F03_QUEST_WORLD_INTERACTION_IMPLEMENTATION_PLAN.md)

- [x] G0: F03/F06/F09/F12/F16 contracts, P01–P16 and C01–C13 decisions, terminology, release mapping, capability negotiation, API/mutation types, Memory source, and three-plane policy composition are approved.
- [ ] G1: Multiple graph-persisted Quest tracking edges, account-wide Objective focus, canonical Observation Clue pins, multi-Agent collaboration, authoritative monotonic projection revision, and permission-filtered Journal graph pass tests.
- [ ] G2: Structured authorized Quest conversation, immutable Quest/Agent/collaboration thread binding, Quest governance + F16 behavior + final command authorization composition, truthful consequences/gates, and localized action keys pass tests.
- [ ] G3: Situation-based World Pulse with account-scoped attention persistence, R2 explicit command-based Agent automation, auditable World Feedback, and scoped conversation-to-Memory handoff pass tests.
- [ ] G4: Map-canvas/HUD desktop-mobile UI, accessibility, build, authenticated E2E, and measurable human experience review pass.

F03 is **approved for implementation** after G0 and remains non-Active until G1–G4 pass. Existing checked items below describe implemented UI slices and do not by themselves promote F03 to Active.

### Foundation submission verification — 2026-11-14

- Command mutations that already return a projection revision commit without recording a duplicate projection event; read-only and failed commands do not commit. Regression coverage is included.
- Focused backend API/projection/command-query tests: 43 passed.
- Backend non-integration sweep: 1778 passed, 4 failed, 66 deselected. Remaining failures are the three NDJSON event-position assertions and the Streamlit evaluation temporary-path validation, matching the previously reported baseline issues; the sweep is not green.
- Frontend: type-check and production build passed; all 151 tests passed with `NODE_OPTIONS=--no-experimental-webstorage` to disable Node's conflicting experimental storage implementation. The default invocation still fails in the auth suite under this local Node environment.
- PostgreSQL integration and authenticated browser/accessibility/user-experience acceptance were not executed for this submission. G1–G4 remain open; this submission is a foundation slice, not feature activation.

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
- [x] Quest-backed work renders as a Mission Card with Situation assertion, Goal desired state, risk, trigger provenance, confidence, and governance-reference count.
- [x] Legacy tasks without a Quest remain operable as a clearly degraded Objective view; the UI does not invent semantic context.
- [x] Objective completion copy does not imply Quest acceptance or Goal satisfaction.
- [x] Mission `subjectRef` can select the corresponding semantic-map entity without moving the account location.
- [x] Map `selectedInspect` drives the Context Summary focus and related-Mission highlight; clearing selection changes UI focus only.
- [x] Active Quest exposes contextual “next step / explain basis” interaction and renders AICO as a Quest companion Agent rather than a separate generic assistant.
- [x] Quest contextual questions reuse the AICO stream while execution remains behind command/service and policy gates.
- [x] `/works` primary language and hierarchy use World Pulse, Quest Journal, Tracked Quest, Companion Agent, map markers, and world feedback instead of Inbox/Dashboard/work-order navigation.
- [x] Quest assistance begins with contextual dialogue choices; free-form conversation remains secondary and attached to the Quest Journal.
- [x] Enterprise governance appears as contextual risk, gate, evidence, or consequence—not as the primary workspace metaphor.
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
- [x] Frontend semantic map rendering contract documented in [`features/F02_SEMANTIC_MAP_FRONTEND.md`](features/F02_SEMANTIC_MAP_FRONTEND.md) (store, layouts, viewport, patch application).
- Phase 2+ remainder: bottom drawer read-only archived history, `task` type enum alignment, mobile §29 layout order, Agent attention, EventTriage L2, HiCampus eight-step demo path.

- [ ] 地图内 `MapEntityInspectSheet`：点击人/物/设备/Agent/空间互斥展示 inspect；决策中心无 `MapSpaceSummaryCard`。
