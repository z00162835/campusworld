# TODO - Frontend Development Tasks

Active plan: [`_generated/CAMPUSWORLD_NEXT_UI_IMPLEMENTATION_PLAN.md`](_generated/CAMPUSWORLD_NEXT_UI_IMPLEMENTATION_PLAN.md)

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

## Phase 1 (current milestone)

- [x] Decision center driven by `user_task_queue` (Task SPEC §1.5 via `task_visibility_sql.py`, shared with `task list`).
- [x] Remove UI-side `task create` from world interaction aggregator.
- [x] Context `lastHandledTask` + queue-backed `pendingDecisionCount`.
- [x] Collapsible semantic map and context panes (`mapDefaultCollapsed` / `contextDefaultCollapsed`).
- [x] Admin demo tasks via `ensure_world_ui_demo_tasks` (direct assign).
- [x] Logout resets `worldSession`, `worldHistory`, `connection`, `commands`.
- [x] i18n keys under `worldInteraction.*`.

## Follow-Up (Phase 2+)

- [ ] `POST /api/v1/semantic-map/focus` and wire map mode refetch.
- [ ] `GlobalCommandSearch` → `world-search` results overlay.
- [ ] Expand real task selection once world-scoped task search is productized.
- [ ] Add authenticated browser regression coverage for `/works`.
- [ ] Extend WebSocket state patch handling beyond the initial adapter path.
- [ ] Agent attention items, EventTriage L2, achievements, HiCampus full demo path.
