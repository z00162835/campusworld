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
- [x] AICO mode calls the AICO command path.
- [x] Map, decision center, context summary, and utility drawer render as separate regions.

## Backend Adapter

- [x] `GET /api/v1/world-sessions/current` returns current interaction state.
- [x] `GET /api/v1/worlds/available` returns selectable worlds.
- [x] `POST /api/v1/world-sessions/enter-world` dispatches `enter <world_id>`.
- [x] `POST /api/v1/world-sessions/leave-world` dispatches `leave`.
- [x] `POST /api/v1/decision-center/actions` dispatches generated decision actions through command/task execution.
- [x] `POST /api/v1/decision-center/query` supports command and AICO modes.
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
- Phase 2+: semantic-map/focus, world-search overlay, WebSocket patches, Agent attention, EventTriage L2, HiCampus eight-step demo path.
