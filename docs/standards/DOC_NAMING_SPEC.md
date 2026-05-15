# DOC Naming SPEC

## Purpose

Define one naming and placement contract for CampusWorld documentation under `docs/`.

## Directory-Level Rules

Allowed module contract layout:

- `docs/<module>/SPEC/SPEC.md`
- `docs/<module>/SPEC/TODO.md` (optional)
- `docs/<module>/SPEC/ACCEPTANCE.md` (optional)
- `docs/<module>/SPEC/features/*.md`

Allowed support directories under `SPEC/`:

- `features/`
- `template/`
- `_generated/`

Do not add other directories under `SPEC/` without updating this file.

## File-Level Rules

### Module root (`docs/<module>/SPEC/`)

Only these file names are allowed:

- `SPEC.md`
- `TODO.md`
- `ACCEPTANCE.md`

Any other markdown file in module root is treated as a migration exception and must be listed in a temporary allowlist in validation tooling.

### Feature docs (`docs/<module>/SPEC/features/`)

Choose one dominant naming style per module and keep it stable:

- **Command-card style**: `CMD_<name>.md` and `CMD_TOPIC_<topic>.md`
- **Feature-id style**: `Fxx_<TOPIC>.md` (example: `F02_TASK_POOL_AND_CLAIM_PROTOCOL.md`)
- **Topic style**: `TOPIC_<topic>.md` (for non-numbered, non-command thematic specs)

Disallowed patterns for new files:

- lowercase prefixes such as `cmd_` or `topic_`
- mixed kebab/snake style in the same module
- ad-hoc roots like `FAMILY_*` (use `CMD_TOPIC_*` for command families)

## Module-Feature Key

Each module `SPEC.md` should include a concise feature index table with:

- file link
- human title
- module feature key (example: `command.find`, `models.agent.f13`)

This avoids cross-module ambiguity such as repeated `F02`.

## Migration and Compatibility

For a renamed or relocated document:

1. New canonical file is created under `features/`.
2. Old path may remain as a short compatibility stub for one migration cycle.
3. Stub must include:
   - replacement file link
   - removal target version/date
4. After the cycle, remove the old file.

## Validation Contract (for CI/script)

Validation must check:

- module root markdown file allowlist compliance
- feature filename pattern compliance
- no new migration exceptions without explicit allowlist update
- `SPEC.md` references at least one `features/` file when `features/` is non-empty

## Cross-Doc Ownership

- Routing and module index: `docs/README.md`
- Architecture-level governance text: `docs/architecture/README.md`
- Agent execution constraints: `AGENTS.md`
- Naming and placement rules: this file (`docs/standards/DOC_NAMING_SPEC.md`)
- Planning and TODO lifecycle rules: `docs/standards/PLAN_TODO_GOVERNANCE.md`
