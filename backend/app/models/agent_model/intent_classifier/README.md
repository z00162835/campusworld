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

