# Intent classifier training

## Environment (Conda `campusworld`)

与仓库其余后端开发一致：**在 Conda 环境 `campusworld` 中**安装依赖并运行训练/评估脚本（见根目录 `CLAUDE.md`「Python 执行环境（Conda `campusworld`）」）。勿在 `base` 或未对齐 `requirements` 的解释器上安装 PyTorch，以免与项目 Python/依赖版本不一致。

```bash
conda activate campusworld
cd backend
# 按需选择 PyTorch 安装方式：https://pytorch.org/get-started/locally/
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements/ml-intent-classifier.txt
```

无需持久激活时，可在 `backend` 目录下单次执行：

```bash
conda run -n campusworld pip install -r requirements/ml-intent-classifier.txt
conda run -n campusworld python -m app.models.agent_model.intent_classifier.train.train_intent_classifier --help
```

训练栈**不在**默认 `requirements/dev.txt` 中；普通后端开发与 `pytest` 不需要安装本节依赖。微调时需先在 **`campusworld`** 中安装与本机匹配的 PyTorch，再安装 `requirements/ml-intent-classifier.txt`。

## Train (LoRA supervised fine-tuning)

Runs chat-template supervised fine-tuning where each sample teaches the assistant to emit strict JSON aligned with `runtime/schema.json`.

```bash
conda activate campusworld
cd backend
python -m app.models.agent_model.intent_classifier.train.train_intent_classifier \
  --data app/models/agent_model/intent_classifier/data/seed/intent_seed_v1.jsonl \
  --output-dir app/models/agent_model/intent_classifier/artifacts/run001 \
  --model-version intent-classifier-v0 \
  --data-version intent-seed-v1
```

Use `--base-model-id`, `--epochs`, `--lr`, `--seed` for quick iterations. Defaults live under `config/defaults.yaml` in the `training:` section.

**Preset orientation (~10k JSONL + Qwen3 4B):** defaults target `Qwen/Qwen3-4B-Instruct-2507` with ~10% validation split, 3 epochs, effective batch ~16 (`per_device_train_batch_size` × `gradient_accumulation_steps`), LoRA `r=32` / `alpha=64`, LR `1e-4`. If you hit OOM, use batch size `1`, increase accumulation to preserve effective batch, switch to `Qwen/Qwen3-1.7B`, or enable `bf16: true` on supported GPUs via a YAML overlay.

Optional YAML overlay:

```bash
conda activate campusworld
cd backend
python -m app.models.agent_model.intent_classifier.train.train_intent_classifier \
  --data ... \
  --output-dir ... \
  --config path/to/local_training_overlay.yaml
```

## Outputs

For full training (`--stub-metadata-only` **not** set), each run writes:

- `export_meta.json` — versions, timestamps, metrics summary
- `training_config.json` — merged hyperparameters + resolved `base_model_id`
- `lora_adapter/` — tokenizer + LoRA weights (`PeftModel.save_pretrained`)
- `hf_trainer/` — HF Trainer checkpoints/logs

CI-friendly stub (no Torch; still use `campusworld` 与后端一致):

```bash
conda activate campusworld
cd backend
python -m app.models.agent_model.intent_classifier.train.train_intent_classifier \
  --data app/models/agent_model/intent_classifier/data/seed/intent_seed_v1.jsonl \
  --output-dir /tmp/intent_stub \
  --stub-metadata-only
```

## Evaluate

Greedy decoding accuracy against a labeled JSONL (requires the same ML stack as training):

```bash
conda activate campusworld
cd backend
python -m app.models.agent_model.intent_classifier.train.eval_intent_classifier \
  --artifact-dir app/models/agent_model/intent_classifier/artifacts/run001 \
  --data app/models/agent_model/intent_classifier/data/seed/intent_seed_v1.jsonl
```

## Dataset module

`dataset_builder.py` validates labels, builds chat turns, and exposes deterministic train/val splits used by the trainer.
