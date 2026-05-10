# Backend Agent Guide

Follow root `AGENTS.md` first. This file covers backend-specific execution rules.

## Source Of Truth

- Architecture: `../docs/architecture/README.md`
- Models: `../docs/models/SPEC/SPEC.md`
- Commands: `../docs/command/SPEC/SPEC.md`
- API: `../docs/api/SPEC/SPEC.md`
- Testing: `../docs/testing/SPEC/SPEC.md`

## Boundaries

- `app/core/`: config, database, security, logging, permissions.
- `app/models/`: graph model and ontology-backed data.
- `app/commands/`: protocol-neutral command logic. Commands inherit `BaseCommand`.
- `app/game_engine/`: world runtime, loader, graph seed, agent runtime.
- `app/api/`, `app/ssh/`, `app/protocols/`: adapters; avoid duplicating business logic here.
- `app/services/` and `app/repositories/`: service orchestration and persistence boundaries.

## Non-Negotiables

- Prefer graph nodes and relationships for domain facts.
- Keep command authorization through `CommandPolicyEvaluator` / registry paths.
- Do not reintroduce world navigation fallbacks that bypass `account.location_id`.
- Keep `world_entrance` separate from `world` metadata nodes.
- Auth refresh failures must clear backend httpOnly cookies.
- Auth state-changing HTTP endpoints keep Origin/Referer validation until a CSRF token scheme replaces it.
- Do not store refresh tokens in frontend-readable responses for browser-only flows unless a non-browser client contract explicitly requires it.

## Testing

- Use `conda run -n campusworld pytest ...` from `backend/`.
- Fast no-DB sweep: `conda run -n campusworld pytest -m "not integration and not postgres_integration"`.
- PostgreSQL tests: `conda run -n campusworld pytest -m postgres_integration`.
- Config validation: `python scripts/validate_config.py`.
- For DB sessions in tests, close generators/sessions with `try/finally`.

## Change Discipline

- Add or update tests for API, auth, command dispatch, graph persistence, and world loader behavior changes.
- Avoid long-held row locks and inconsistent multi-row lock order in integration tests.
- Do not put `Fxx` labels or SPEC section numbers into implementation comments or user-visible text.
