# Agent Model Directory Rules

This directory hosts shared, reusable model assets for agent-runtime capabilities.

## Scope
- Contains classifier assets and contracts used across multiple agents.
- Focuses on pre-execution intent understanding and tool-selection guidance.
- Does not implement execution fallback routing based on command success/failure.

## Intent Classifier Boundary
- Purpose: classify user intent into `informational`, `verify_state`, `execute`.
- Output is advisory input for planning/tool selection.
- Runtime execution authorization remains in execution gate / policy layers.
- On classifier failure, default to `informational`.

## Multi-agent Policy
- Classifier output schema is shared globally.
- Conflict strategy and KPI thresholds are configurable per agent.
- Shared interface must remain stable across agent implementations.

## Data and Training Discipline
- Keep seed datasets and templates versioned under `intent_classifier/data/`.
- Keep reproducible training configs under `intent_classifier/train/`.
- Record model version, data version, and eval summary for each export.

