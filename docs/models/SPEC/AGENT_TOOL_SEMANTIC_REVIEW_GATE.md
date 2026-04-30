# Agent Tool Semantic Review Gate

This gate is required before rollout of tool semantic changes related to:
`interaction_profile`, `routing_hint`, `invocation_guard`, and prompt/primer routing wording.

## Required checks

- Semantic consistency
  - Each command has one primary `interaction_profile`.
  - Aggregated commands (for example `task`) include explicit routing hints for
    usage/example vs execution intent.
  - `mutate` commands include guard rules.
- Bilingual quality
  - `routing_hint` Chinese and English are equivalent in meaning.
  - Single hint field size is <= 512 bytes (UTF-8).
- Guard policy integrity
  - Instance override only tightens class-level guard policy.
  - No override weakens confirmation or allowed intents.
- Locale fallback
  - Locale source uses `CommandContext.metadata["locale"]`.
  - Fallback path matches `tool_manifest_locale()` behavior.
- Observability and snapshots
  - Snapshot coverage includes AICO `system_prompt`, `phase_prompts`, manifest
    sections/routing hints, and primer commands routing rules.
  - Guard traces are reviewable for pass/block reasons.

## Minimum sample commands

- `task`
- `create`
- `notice`
- `help`
- `primer`
- `find`
- `describe`
- `agent`

## Review record template

- Reviewer:
- Review date:
- Scope (commands / hints / guard rules):
- Findings (high/medium/low):
- Verdict (pass / conditional pass / fail):
- Required follow-ups:
