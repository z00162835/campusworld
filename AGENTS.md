# CampusWorld Agent Guide

CampusWorld is a world-semantic Campus OS: graph nodes model people, places, devices, worlds, tasks, and agents; commands are the protocol-neutral interaction layer.

## Source Of Truth

- Project overview: `README.md`, `QUICKSTART.md`
- Logging & bilingual terms (normative for log strings): `docs/glossary/TERMINOLOGY.md`
- Architecture: `docs/architecture/README.md`
- Models and Agent runtime: `docs/models/SPEC/SPEC.md`
- Command system: `docs/command/SPEC/SPEC.md`
- Frontend: `docs/frontend/SPEC/SPEC.md`
- Testing: `docs/testing/SPEC/SPEC.md`
- HiCampus world package: `docs/games/hicampus/SPEC/SPEC.md`
- Directory map: `PROJECT_STRUCTURE.md`

`AGENTS.md` is the primary instruction source for coding agents. `CLAUDE.md` is a compatibility entry and must not become a parallel source.

## Architecture Invariants

- 万物皆节点；关系即语义。Prefer graph nodes/edges over ad hoc isolated business state.
- `commands/` is protocol-neutral business interaction. SSH, HTTP, WS, and UI layers must not duplicate command behavior.
- Account `location_id` is the authoritative current room. Do not reintroduce `active_world` + `world_location` as `look` fallback.
- `world_entrance` nodes are separate from `world` metadata nodes. `enter <world_id>` resolves entrances only.
- World packages live under `backend/app/games/<world_id>/`; HiCampus package data must not be written into global minimal seed paths.
- Agent runtime follows the L1-L4 model in `docs/models/SPEC/features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md`.
- Implementation comments, docstrings, user-visible text, and identifiers must not use `Fxx` feature labels or SPEC section numbers.

## Auth And Session Invariants

- Refresh tokens live only in backend-managed httpOnly cookies.
- Frontend may keep access tokens only in memory; never persist auth tokens to `localStorage` or `sessionStorage`.
- Auth endpoints (`/auth/login`, `/auth/register`, `/auth/refresh`, `/auth/logout`) must not trigger 401 refresh retries.
- Login failure text is intentionally generic, except network failure.
- Logout must clear local stores immediately and route with `replace('/login')`; backend logout must not block UI exit.
- Backend auth state-changing endpoints must keep short-term CSRF protection via Origin/Referer validation until a stronger token scheme is adopted.

## Logging Language

- **Backend:** Application and library logs (`logging`, `structlog`, `self.logger`, `logging.getLogger(...)`, etc.) MUST use **English only** for human-readable message templates. Follow `docs/glossary/TERMINOLOGY.md` for product terms (e.g. 园区世界 → **CampusWorld**). Variable substitutions may contain arbitrary user/content data.
- **Frontend:** `console.log` / `console.info` / `console.warn` / `console.error` and other developer-facing diagnostic output MUST use **English only**. End-user UI copy stays governed by i18n and product rules, not this section.

## Working Rules

- Read the relevant SPEC and existing implementation before coding.
- Make surgical changes; do not refactor adjacent code or reformat unrelated files.
- Prefer existing local patterns over new abstractions.
- If a behavior change touches a contract, update the matching SPEC, ACCEPTANCE, or TODO.
- Keep generated docs and registry snapshots in sync only when the task requires it.
- Respect dirty worktrees. Never revert user changes unless explicitly asked.

## Verification Matrix

| Area | Minimum verification |
|------|----------------------|
| Backend unit/API | `cd backend && conda run -n campusworld pytest tests/...` |
| Backend quick sweep | `cd backend && conda run -n campusworld pytest -m "not integration and not postgres_integration"` |
| PostgreSQL integration | `cd backend && conda run -n campusworld pytest -m postgres_integration` |
| Frontend | `cd frontend && npm run type-check && npm run test -- --run` |
| Config | `cd backend && python scripts/validate_config.py` |
| HiCampus package | `world validate hicampus` after DB-backed install/reload |

Use the smallest meaningful test set first, then broaden when touching shared contracts, auth/session code, graph persistence, command dispatch, or agent runtime.

## Directory Boundaries

- `backend/app/core/`: config, DB, logging, security, permissions.
- `backend/app/models/`: graph data model and ontology-backed entities.
- `backend/app/commands/`: command contracts and policy-gated execution.
- `backend/app/game_engine/`: world loading, runtime, graph seed, agent runtime.
- `backend/app/api/`, `backend/app/ssh/`, `backend/app/protocols/`: adapters over shared services/commands.
- `backend/app/services/`, `backend/app/repositories/`, `backend/app/schemas/`: service, persistence, and API schema boundaries.
- `frontend/src/api/`: only place for HTTP client calls.
- `frontend/src/stores/`: Pinia state; reset sensitive user-scoped state on logout.
- `docs/**/SPEC/`: single source for module contracts.

## Environment Notes

- Backend local tests assume Conda env `campusworld`. Do not treat failures from base/system Python as code regressions.
- PostgreSQL-backed tests and world graph seed require a reachable configured database.
- Optional ML intent-classifier training dependencies are not part of default backend dev requirements.

## Git And Docs

- Commit style: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
- Keep root `AGENTS.md` under 150 lines. Put module-specific instructions in child `AGENTS.md` files.
- When changing root guidance, check whether `CLAUDE.md` compatibility text still points here.
