# Intent Classifier Package

Shared small-model intent-classification assets for CampusWorld agents.

## Labels
- `informational`: usage/example/syntax/help requests.
- `verify_state`: read-only state verification requests.
- `execute`: explicit execution requests with confirmation signal.

## Training environment

本地微调与离线评估：**在 Conda `campusworld` 环境中**安装可选栈（PyTorch + `backend/requirements/ml-intent-classifier.txt`），与仓库后端/Python 约定一致；详见 [`train/README.md`](train/README.md)。

## Directory Layout
- `config/` classifier and threshold defaults.
- `prompts/` prompt templates for classifier inference.
- `runtime/` I/O schema and adapter contracts.
- `data/seed/` initial labeled samples.
- `data/templates/` human annotation templates.
- `train/` training and export scripts.
- `eval/` evaluation notes and KPI definitions.

## Runtime Contract
- Shared API is exposed via `app.game_engine.agent_runtime.intent_classifier_interface`.
- On classifier errors or invalid outputs, runtime defaults to `informational`.

## Deploying SLM on an npc_agent

1. Train and export a run directory (see [`train/README.md`](train/README.md)) containing `lora_adapter/` and `training_config.json`.
2. Place or reference that directory under an **allowlisted prefix** (default: `backend/app/models/agent_model/intent_classifier/artifacts/`).
3. Set per-service defaults in `agents.llm.by_service_id.<id>.extra` and/or override on the agent node under `attributes.intent_classifier`:
   - `use_intent_slm: true`
   - `artifact_dir: "app/models/agent_model/intent_classifier/artifacts/<run_id>"`
4. Install optional deps in Conda `campusworld`: PyTorch + `requirements/ml-intent-classifier.txt`.
5. Restart workers after changing artifacts or toggling `use_intent_slm`.

When `use_intent_slm` is false or paths are invalid, ticks use **rule fallback only** (no torch load).

