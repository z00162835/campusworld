# Agent Tool Semantic Review Gate

This gate is required before rollout of tool semantic changes related to:
`interaction_profile`, `subcommand_profiles`, `manifest_tier`, `routing_hint`,
`invocation_guard`, and prompt/primer routing wording.

## Source of truth

- **L1 (registry)**: each `BaseCommand` subclass declares `tool_semantics: ClassVar[CommandToolSemantics]`.
  Default is `read` with `manifest_tier=none`. Resolver:
  `backend/app/commands/command_tool_semantics.py` → `resolve_command_tool_semantics(name, args=...)`.
- **L2 (graph mirror)**: `ability_sync` mirrors profile, guard, `semantic_pending`, and `manifest_tier`
  from registry. Ops may override **`agent_observation_policy` only**; profile/guard are not weakened via DB.
- **L3 (defaults)**: read → observation `full`; mutate → `summary`; unregistered / `semantic_pending` → `summary`.
- **Audit**: `docs/command/SPEC/_generated/registry_snapshot.json` includes per-command `tool_semantics`;
  validate with `backend/scripts/validate_command_tool_semantics.py` (ignores snapshot `git_commit` / `generated_at`).

## Required checks

- Semantic consistency
  - Each registered command declares `tool_semantics` on its class (or inherits `DEFAULT_READ_SEMANTICS`).
  - Aggregated commands (`task`, `world`, `notice`, `agent`) use `subcommand_profiles`; longest `arg_prefix` wins.
  - Class-level `mutate` commands (`task`, `create`, `notice`, `world`) include guard rules where applicable.
  - No central command-name frozensets or per-command observation hardcoding (e.g. no `space`-specific `data_keys`).
- Bilingual quality
  - `routing_hint` Chinese and English are equivalent in meaning.
  - Single hint field size is <= 512 bytes (UTF-8).
- Guard policy integrity
  - Instance override only tightens class-level guard policy.
  - No override weakens confirmation or allowed intents.
- Locale fallback
  - Locale source uses `CommandContext.metadata["locale"]`.
  - Fallback path matches `tool_manifest_locale()` behavior.
- Manifest tier
  - Default `manifest_tier=none`; only commands with explicit `manifest_tier=informational` enter AICO Plan manifest.
  - Informational tier is declared per command class, not via a global allowlist constant.
- Observability and snapshots
  - Snapshot `tool_semantics` diff passes after export.
  - Guard traces are reviewable for pass/block reasons.

## Minimum sample commands

- `task` (subcommand read/mutate split)
- `create`
- `notice` (`list`/`view` read; `publish`/`edit`/`archive` mutate)
- `help`
- `primer`
- `find`
- `describe`
- `agent` (`tool add`/`del` mutate; `list`/`show`/`status`/`tool` query read)
- `space` (read + informational manifest; same observation rules as other read commands)

## Review record template

- Reviewer:
- Review date:
- Scope (commands / hints / guard rules / manifest_tier):
- Findings (high/medium/low):
- Verdict (pass / conditional pass / fail):
- Required follow-ups:
