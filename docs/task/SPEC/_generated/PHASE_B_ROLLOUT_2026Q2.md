# Task System — Phase B Rollout Snapshot (Archived)

> **Status**: archived
>
> **Archived at**: 2026-05-15
>
> This document is the archived implementation snapshot for Task System Phase B.
> It is not the normative behavior contract. Stable contract remains in:
> - [`../SPEC.md`](../SPEC.md)
> - [`../TODO.md`](../TODO.md)
> - [`../ACCEPTANCE.md`](../ACCEPTANCE.md)

## Scope Anchor

- Invariant set: `SPEC.md` I1-I8
- Phase B targets: I1 / I3 / I4 / I5 / I6, I2 partial
- Event set: `create / publish / claim / assign / complete`

## PR Rollout (Archived Summary)

| PR | Title | Primary area |
|---|---|---|
| PR1 | Ontology + traits | `graph_seed_node_types.yaml`, `trait_mask.py` |
| PR2 | Schema + seed | `db/schemas/database_schema.sql`, migrations, seed |
| PR3 | RBAC + utilities + CI gate | ACL/permissions + static write-path guard |
| PR4 | State machine | `app/services/task/task_state_machine.py` |
| PR5 | Commands + i18n + dual-protocol | `app/commands/game/task/*`, i18n locales |
| PR6 | I2 integration + bench + docs | integration tests, benchmark, docs sync |

## Acceptance Snapshot

Phase B was considered done when:

1. Core integration invariants passed (I1/I4/I5/I6).
2. I2 Phase B path test passed.
3. Dual protocol contract test passed (SSH/REST).
4. Bench smoke reached baseline threshold.
5. CLI flow `create -> claim -> complete` passed.

## Phase C Carryover

Deferred to Phase C:

- extended events (`submit-review`, `approve`, `reject`, `handoff`, `cancel`, `fail`, `start`, `expand`)
- async expand worker
- audit worker full suite (I7/I8 paths)
- bulk commands and advanced chaos/property tests
