# Frontend Acceptance Checklist

## F03 Implementation Activation Gates

Active implementation plan: [`_generated/F03_QUEST_WORLD_INTERACTION_IMPLEMENTATION_PLAN.md`](_generated/F03_QUEST_WORLD_INTERACTION_IMPLEMENTATION_PLAN.md)

- [x] G0: F03/F06/F09/F12/F16 contracts, P01–P16 and C01–C13 decisions, terminology, release mapping, capability negotiation, API/mutation types, Memory source, and three-plane policy composition are approved.
- [ ] G1: Multiple graph-persisted Quest tracking edges, account-wide Objective focus, canonical Observation Clue pins, multi-Agent collaboration, authoritative monotonic projection revision, and permission-filtered Journal graph pass tests.
- [ ] G2: Structured authorized Quest conversation, immutable Quest/Agent/collaboration thread binding, Quest governance + F16 behavior + final command authorization composition, truthful consequences/gates, and localized action keys pass tests.
- [ ] G3: Situation-based World Pulse with account-scoped attention persistence, R2 explicit command-based Agent automation, auditable World Feedback, and scoped conversation-to-Memory handoff pass tests.
- [ ] G4: Map-canvas/HUD desktop-mobile UI, accessibility, build, authenticated E2E, and measurable human experience review pass.

F03 is **approved for implementation** after G0 and remains non-Active until G1–G4 pass. Existing checked items below describe implemented UI slices and do not by themselves promote F03 to Active.

### SPEC / code consistency follow-up — 2026-11-14

- [Consistency review](./_generated/F03_QUEST_SPEC_CODE_CONSISTENCY_REVIEW_20261114.md) records implementation versus acceptance separately; it is not a second active plan.
- Corrected four inconsistencies: locking preview before cursor/object locks; task-dependent rather than foreground-Quest dialogue/old thread reuse; unrestricted Python template formatting; semantic ownership checks incorrectly rejecting task-visible Objectives. Preview/compile is now nonlocking, while the default execution source freshly locks after the executor's scope lock. Only plain Quest/Objective ID substitutions are accepted.
- Dialogue free input and help use current foreground Quest/Objective/revision. Quest/Agent/collaboration identity changes select a distinct thread; untracking no longer carries an old Quest into generic input. Companion remains available without an actionable task. The projected collaboration ID is only a local identity discriminator, never authorization.
- Focused backend regression **197 passed**; frontend type-check, **201 tests**, and production build passed (tests use the documented Node runtime option). Unit SQL assertions establish lock-mode separation, not proof of actual PG concurrency safety.
- Latest non-integration quick sweep: **1888 passed, 4 failed, 68 deselected**. Failures remain the three recorded NDJSON assertions and Streamlit temporary-path validation; the suite is not green. The autostop timing assertion also reproduced in an earlier sweep and one isolated run during this round, although it passed in the latest sweep; it must not be described as passing unconditionally. The stream implementation and timing test were not changed by these fixes. SPEC-layout validation still fails on the existing `ALIAS_GOVERNANCE.md` filename; whitespace checks pass.
- Remaining implementation gaps are explicit in TODO: complete map-focus/pinned-rule/Evidence conversation reference pack, canonical Quest terminal lifecycle/archive hooks, actual Agent scheduler integration and governed source publication/version immutability. No production activation, PostgreSQL integration, authenticated UI acceptance, commit or push was performed.

### Governed execution and compact world layers — 2026-11-14

- G2 implementation: deterministic graph-source governance over exact published Policy/Control/Process versions; preview risk/evidence/approval hints; independent decision composition and final registry command authorization at execution. Agent identity cannot be substituted with a user; enforced Objective writes require a single-use transaction/scope/version-bound permit. Action labels and execution reasons use i18n keys with truthful fallback.
- G3 implementation: explicit finite transactional command executor with scoped replay, domain-version conflict checks, savepoint rollback, SQL timeout and cooperative cancellation/kill switch. Decisions/outcomes use task run/event and Agent run records. Permission-filtered Feedback/Pulse expose real actors and correlation; a newer failure resurfaces after personal dismissal/snooze, and command success does not imply Quest acceptance.
- G4 implementation: all six Quest components are independent and derive from one session projection. Compact view retains the Map canvas and one Quest/Clues overlay, shows the actual foreground Objective or real Pulse, closes the overlay on map location and does not mutate business state on layer changes. Desktop separators support keyboard arrows/Home/End; overlay close returns focus to Map navigation.
- Verification: focused backend governance/execution/permit/memory/projection/command/API/ontology regression **186 passed**. Latest non-integration sweep **1877 passed, 4 failed, 66 deselected**; failures are the three recorded NDJSON event-position assertions and Streamlit macOS temporary-path validation. Sweep is not green. Configuration and diff whitespace validation passed; SPEC-layout validation still reports the existing `docs/command/SPEC/features/ALIAS_GOVERNANCE.md` naming violation.
- Frontend type-check, **195 tests**, and production build passed using `NODE_OPTIONS=--no-experimental-webstorage` for tests. The Node option is a local-runtime workaround, not an auth implementation change.
- PostgreSQL execution success/failure rollback, persisted audit, replay and projection scenarios have been added for later acceptance; collection only, **not executed**. No database migration, production rule publication, live automatic action or authenticated business mutation was performed.
- Gates remain open: Quest completion/closure archive trigger; actual sensing/Agent scheduler entry and governed planning/lifecycle; customer rule publication/activation; PostgreSQL concurrency/transaction acceptance; authenticated mobile/keyboard/read-screen/zoom/contrast and measured experience review. Full asynchronous LearningProposal promotion/publication is a later learning gate, not a standalone blocker for UI activation. N03:B is respected; implementation/component tests do not close G1–G4 or mark the feature Active.

### Foundation submission readiness recheck — 2026-11-14

- Governance results are bound to their exact request context before composition: cross-Quest, cross-Objective, cross-principal, cross-Agent and changed-command reuse is blocked, even with matching rule versions/revision.
- Focused backend memory/decision/projection/API/query regression: 104 passed. Frontend: type-check/build passed, all 181 tests passed with the documented Node option. Configuration validation passed and diff whitespace checks passed.
- Backend quick sweep: 1806 passed, 5 failed, 66 deselected; failures remain the recorded NDJSON event-position assertions, Streamlit temporary-path check and autostop timing case. This is not a green full-suite result.
- SPEC layout validation remains blocked by the unchanged `docs/command/SPEC/features/ALIAS_GOVERNANCE.md` filename. Alias validation reported static namespace/snapshot success, but initialization returned false after sandbox-denied DB access; it is not counted as full initialization validation and was not retried with live database access.
- Eligible only as a partial foundation submission, not G2–G4 completion or release acceptance. Include all required new components, memory/decision tests and isolated fixtures. Production governance evaluation, persistent decision audit, automatic orchestration, PostgreSQL and authenticated UI/accessibility gates remain open.

### Confirmed decisions implementation — 2026-11-14

- N01:A: Explicit owned-thread deletion now replaces scoped episode plaintext with minimal redaction audit and deletes LTM directly derived from those episodes. It uses the same thread lock as archival/ticks; no live user data was deleted during implementation. Unrelated LTM keeps the existing unlink behavior.
- N02:A: A pure decision-composition primitive and isolated read-only fixture scenario use the real Agent PolicyEngine and registered `look` capability. A composed pass only permits requesting command authorization; the isolated CommandRunner scenario confirms later authorization denial still prevents execution. Production governance rule evaluation, persisted decision audit and automatic orchestration remain pending, so G2/G3 are not closed.
- N03:B: Continue component/offline testing. No authenticated browser acceptance or PostgreSQL integration was performed. Frontend type-check and 181 tests passed with the documented Node option. Backend quick sweep: 1799 passed, 5 failed, 66 deselected, matching the previously recorded NDJSON/Streamlit/autostop issues; the sweep remains non-green.
- Final focused decision/memory regression and isolated autostop rerun: 37 passed, including malformed-version checks. The autostop case passed individually; this does not make the full sweep green.

### Review fixes verification — 2026-11-14

- Mission Card now honors `requiresConfirmation`, including cancellation and rejection of an action replaced while the confirmation dialog is open. Confirmation remains a UX safeguard, not policy approval or backend authorization.
- Busy conversation archival has a typed exception and HTTP 409 `conversation_busy`; the client reports a localized retry hint without automatic mutation replay. Focused backend memory/API/query regression: 57 passed.
- Frontend type-check/build passed; all 181 tests passed with the documented Node runtime option. Authenticated UI and PostgreSQL acceptance remain open.
- Backend quick sweep: 1784 passed, 5 failed, 66 deselected. Four failures match the recorded NDJSON/Streamlit baseline; the additional cross-thread autostop timing failure passed on isolated rerun (1 passed). The full sweep remains non-green; no integration tests were run.

### Journal interaction follow-up verification — 2026-11-14

- QuestJournal is a standalone read-only component. Explicit node selection shows only edges whose endpoints remain in the authorized projection; unresolved refs stay non-interactive. Map location is offered only for current Quest map references and excludes business-semantic nodes. Map selection has both a visual and textual Journal marker; clearing Journal selection does not emit a location or business mutation.
- Seven new Journal tests cover relation inspection, allowed-map targeting, missing endpoints, unresolved refs, map reflection, foreground journal change and local selection clearing. Frontend type-check/build passed and all 177 tests passed with the documented Node runtime option.
- Authenticated browser/mobile/assistive-technology acceptance remains pending; the previously checked `/works` browser was redirected to login. This slice does not close G4.

### Pulse and feedback follow-up verification — 2026-11-14

- WorldPulse and WorldFeedback are standalone components. Pulse emits attention intents through the existing authoritative store; it does not resolve business Situations. Feedback shows recorded actor type/ID, Objective state, time and Quest/Objective/correlation references, with explicit missing-data fallbacks; human events are not implicitly attributed to the current user.
- Frontend type-check/build passed; all 170 tests passed using the documented Node runtime option, including ten new Pulse/Feedback cases. Local `/works` browser navigation redirected to login; authenticated visual, keyboard and mobile acceptance was not completed. G3 automation and G4 acceptance remain open.

### Conversation archive follow-up verification — 2026-11-14

- Collaboration replacement/removal now archives bound threads and snapshots scoped historical/unverified raw episodes in the same caller-owned transaction. Account/Agent/thread/Quest references, creation revision, STM messages and rolling summaries are retained; no direct LTM publication or configuration change occurs.
- Focused memory/Quest/query tests: 63 passed, including five new archive/isolation/idempotency/busy-thread tests. Backend non-integration sweep: 1784 passed, the same four previously recorded NDJSON/Streamlit failures, 66 deselected.
- Frontend type-check and 160 tests passed with the documented Node runtime option. PostgreSQL coverage was extended but not executed. Quest completion/closure triggers and asynchronous promotion consumption remain pending; G2/G3 are not closed.

### Choice consequence follow-up verification — 2026-11-14

- Shared consequence rendering is used by Mission Card and decision event choices. It distinguishes confirmed/predicted/proposed summaries, exposes supplied risk/gate/evidence/source/impact metadata, and marks missing or invalid prediction confidence and missing prediction basis explicitly.
- Supplied high/critical risk or irreversible metadata requires action confirmation. This is not approval and does not replace backend execution authorization or the pending policy decision facade.
- Frontend type-check/build passed; 160 tests passed using `NODE_OPTIONS=--no-experimental-webstorage`. Backend option/query/API regression: 37 passed.
- Visual, authenticated browser and accessibility acceptance were not performed; this does not close G2/G4.

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
