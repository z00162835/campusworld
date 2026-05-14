# SPEC Layout Audit

Last updated: 2026-05-14

## Scope

- `docs/**/SPEC/*.md` (module root)
- `docs/**/SPEC/features/*.md` (feature docs)

## Baseline Rule

Module SPEC root should only contain:

- `SPEC.md`
- `TODO.md`
- `ACCEPTANCE.md`

Feature-level contracts should be under `features/`.

## Root-Level Outliers

The following files are feature/topic-level docs currently outside `features/`:

- `docs/models/SPEC/CAMPUSWORLD_SYSTEM_PRIMER.md`
- `docs/models/SPEC/AGENT_PDCA_PHASE_MERGE_TRADEOFFS.md`
- `docs/models/SPEC/AGENT_TOOL_SEMANTIC_REVIEW_GATE.md`
- `docs/models/SPEC/AICO_TOOL_DESCRIPTION_AUDIT.md`
- `docs/frontend/SPEC/SPACES.md`
- `docs/task/SPEC/PLAN_PHASE_B.md`

## Naming Heterogeneity

### command module (`docs/command/SPEC/features`)

Mixed prefixes and styles:

- `CMD_*` (command card docs)
- `F01_*`, `F02_*` (deep/topic docs)
- `FAMILY_*` (command family docs)

This increases lookup cost and weakens predictable naming.

### models/hicampus/task modules

Mostly `Fxx_*`, but topic-like docs coexist in module root (`models`) and mixed `*_TEST_SPEC` suffixes (`hicampus`).

## Entry Point Overlap

Overlapping governance and routing responsibilities appear in:

- `docs/README.md`
- `docs/architecture/README.md`
- `AGENTS.md`

## Recommended Migration Priority

1. `models` (root outliers + agent runtime cross-links)
2. `frontend` (`SPACES.md` outlier)
3. `command` (naming normalization and index consistency)
4. `task` (`PLAN_PHASE_B.md` consolidation decision)

## Tracking Note

This file is an audit snapshot, not a normative contract. Naming and structure rules are defined in:

- `docs/standards/DOC_NAMING_SPEC.md`
