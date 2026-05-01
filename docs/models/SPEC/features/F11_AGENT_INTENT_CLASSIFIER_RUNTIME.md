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

Outermost `classify_intent` defaults to `informational` with `source=fallback_default` when the classifier raises or returns an invalid label. When using `ChainedIntentClassifier`, an SLM failure triggers `RuleFallbackIntentClassifier`, which may still emit `execute` or `verify_state` from rule cues — only the outer wrapper guarantees informational on total failure.

## Shared interface

Runtime entrypoint:
- `app.game_engine.agent_runtime.intent_classifier_interface.classify_intent`

Output shape:
- `intent`
- `confidence`
- `reason_tokens`
- `source`

## Tick wiring (PDCA Plan)

- Before the Plan-phase LLM call, the framework classifies the user message and injects an **Intent hint** block into the Plan user turn (`confidence` and `source` included so the main model can weigh SLM vs rule output). Greedy decode takes the first JSON object from model text (optional markdown fences); implementation lives in `app.models.agent_model.intent_classifier.runtime.inference`.
- Resolver: `app.game_engine.agent_runtime.intent_classifier_runtime.resolve_intent_classifier_runtime` merges YAML `agents.llm.<service>.extra` with `npc_agent.attributes.intent_classifier`.
- Optional LoRA classifier: `app.game_engine.agent_runtime.peft_intent_classifier.PeftIntentClassifier`, lazily loaded and cached per process with a lock. On SLM failure, **`RuleFallbackIntentClassifier` runs next** (chain); primary failures emit `intent_classifier_primary_failed` on the games logger. If `peft` is not importable at tick build time, the worker skips the SLM (`intent_classifier_peft_import_unavailable`) and uses rules only. Resolver warnings (`intent_classifier_*`) use the same games logger (`LoggerNames.GAME`).
- **Execution gate** (`execution_gate`) still authorizes tool execution; the classifier only biases Plan tool choice via the hint text.

### Configuration keys (extra + node `intent_classifier`)

| Key | Meaning |
|-----|---------|
| `use_intent_slm` | Default `false`. When true, load adapter under `artifact_dir` if valid. |
| `artifact_dir` | Training output directory (`lora_adapter/`, `training_config.json`). Relative paths resolve from **`backend/`**. |
| `intent_classifier_allowed_path_prefixes` | Optional list of allowed directory prefixes (resolved like `artifact_dir`). If omitted, defaults to `app/models/agent_model/intent_classifier/artifacts`. |
| `max_new_tokens` | Greedy decode budget (default 96), clamped to \[8, 256\]. |
| `system_prompt_file` | Optional override path for classifier system prompt (default: packaged prompt). Must resolve under `app/models/agent_model/intent_classifier/` **or** under the same allow prefixes as `artifact_dir`. |

Structured logs (games logger): `intent_classified` on each tick (includes `intent_slm_latency_ms` when the winning classification came from the small model); `intent_slm_ok` / `intent_slm_inference_failed` / `intent_slm_bundle_loaded` when SLM is active.

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

