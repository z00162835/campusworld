# Plan And TODO Governance

## Purpose

Define one governance contract for planning artifacts and execution checklists under `docs/**/SPEC/`, so that implementation plans, TODO lists, and acceptance gates stay consistent.

## Scope

This standard applies to module-level docs under:

- `docs/<module>/SPEC/`
- `docs/<module>/SPEC/features/`
- `docs/<module>/SPEC/_generated/` (if present)

## Document Roles

### Stable contract

- `SPEC.md` and `features/*.md` are the long-lived behavior contract.
- They describe invariants, interfaces, and accepted semantics.
- They must not use temporary rollout state (`in-flight`, `PR1-PR6`) as normative truth.

### Execution checklist

- `TODO.md` is the active backlog/checklist for implementation work.
- `ACCEPTANCE.md` is the acceptance gate and release-ready criteria.
- `TODO.md` and `ACCEPTANCE.md` should reference stable contract sections by link.

### Execution snapshot

- Rolling plans, phase rollout logs, and one-time implementation playbooks belong to `SPEC/_generated/`.
- `_generated/` docs are archival execution snapshots, not behavior contracts.
- Snapshot docs should include `Status` and `Generated/Archived date` metadata.

## Single-Active-Plan Rule

Per module and per phase, only one plan may be marked active at a time.

- Active plan should be linked from `TODO.md` if still in execution.
- When a plan is completed, it must be marked archived and moved or retained under `_generated/`.
- New phase planning should start a new snapshot instead of rewriting old rollout history.

## Migration And Compatibility

If an old root-level plan path must remain temporarily:

1. Keep a short compatibility stub at the old path.
2. Stub must include:
   - canonical replacement link under `_generated/`
   - deprecation/removal target version or date
3. Remove the stub after one migration cycle.

## Consistency Rules

When updating a module phase status:

1. Update `TODO.md` checklist states.
2. Update `ACCEPTANCE.md` gate status or explicit defer notes.
3. Keep `SPEC.md` focused on stable contract text.
4. Avoid contradictory statuses across `SPEC.md` / `TODO.md` / `ACCEPTANCE.md` / plan snapshot.

## Review Checklist

Before merge, verify:

- no execution-only plan is treated as module SSOT
- `TODO.md` and `ACCEPTANCE.md` point to current active/archived snapshot correctly
- compatibility stubs include replacement link and removal target
- naming/placement still comply with `DOC_NAMING_SPEC.md`
