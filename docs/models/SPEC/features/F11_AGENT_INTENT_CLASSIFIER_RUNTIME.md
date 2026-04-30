# F11 — Agent Intent Classifier Runtime Contract

## Goal

Define a shared, reusable intent-classifier contract used by multiple agents for
pre-execution routing quality:
- classify intent before tool planning;
- improve informational vs execute tool selection;
- avoid using command execution success/failure as routing strategy.

## Intent labels

- `informational`
- `verify_state`
- `execute`

On classifier failure, runtime defaults to `informational`.

## Shared interface

Runtime entrypoint:
- `app.game_engine.agent_runtime.intent_classifier_interface.classify_intent`

Output shape:
- `intent`
- `confidence`
- `reason_tokens`
- `source`

## Policy model

- Metric definitions are shared globally.
- Conflict strategy and KPI thresholds are configured per-agent.
- Per-agent config defaults in model package; runtime may apply stricter overrides.

## Data and training lifecycle

- Seed dataset and annotation template are versioned.
- Training exports include model version, data version, and train timestamp.
- Human loop: annotate -> review -> train -> validate -> publish.

### Development environment (conda)

Training and offline evaluation scripts assume the repository-standard **Conda `campusworld`** environment (`conda activate campusworld`, working directory `backend`), consistent with backend development and pytest. Install PyTorch for your platform, then `pip install -r requirements/ml-intent-classifier.txt` (optional file; not part of default `dev.txt`). Operational commands and artifact layout: `backend/app/models/agent_model/intent_classifier/train/README.md`.

## Non-goals

- This feature does not replace execution gate authorization.
- This feature does not inject execution-failure-driven safe fallback routing.

