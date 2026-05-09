# Tool router — training & offline eval

Train **outside** the default API hot path. Use Conda env `campusworld`, install **PyTorch for your platform**, then the extra requirements file.

## 1. Dependencies

Install PyTorch from https://pytorch.org/ (pick CUDA / CPU build). Then:

```bash
cd backend
pip install -r requirements/tool-router-train.txt
```

Do **not** merge these into default `requirements/dev.txt` CI installs unless the pipeline explicitly supports GPU/train.

## 2. Data layout

See [`../data/README.md`](../data/README.md). Copy [`../data/registry.yaml.example`](../data/registry.yaml.example) to `registry.yaml` if you track shard lists.

| Track | Schema file | Train CLI |
|-------|-------------|-----------|
| Slot SLM | `schemas/tool_router_slot_output.schema.json` | `train_slot_lora.py` |
| Router head (multi-label tools) | `schemas/tool_router_train_row.schema.json` | `train_router_head.py` |

## 3. Slot SLM (structured JSON)

Gold JSONL lines include `slot_labels` (object) plus context fields (`user_message`, `snapshot_features`, …). Each `slot_labels` must validate against `tool_router_slot_output.schema.json`.

**Train** (LoRA on a chat base model, default Qwen2.5 0.5B Instruct):

```bash
cd backend
python -m app.models.agent_model.tool_router.train.train_slot_lora \
  --data-jsonl app/models/agent_model/tool_router/data/shards/slot_train.jsonl \
  --output-dir artifacts/tool_router/slot/run001 \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --epochs 2 \
  --batch-size 2 \
  --grad-accum 8 \
  --lr 2e-4 \
  --max-seq-len 2048 \
  --completion-tokens 384 \
  --bf16
```

Drop `--bf16` on CPU. Tune `--completion-tokens` if your JSON targets are long.

**Artifacts**: adapter + tokenizer under `--output-dir`; `train_meta.json` records row counts. Point runtime `agents.llm.*.extra.tool_router.slot_chat_backend` at this directory after merging or loading as PeFT (per your HF deployment).

## 4. Router head (multi-label `tool_names`)

Gold JSONL lines must validate against `tool_router_train_row.schema.json` (required: `user_message`, `gold_tool_names`, `data_source`). The model is trained to emit **only** JSON: `{"tool_names":[...]}` (same key you can use in prediction files for `eval_router_offline`).

**Train**:

```bash
cd backend
python -m app.models.agent_model.tool_router.train.train_router_head \
  --train-jsonl app/models/agent_model/tool_router/data/shards/router_train.jsonl \
  --output-dir artifacts/tool_router/router_head/run001 \
  --base-model Qwen/Qwen2.5-0.5B-Instruct \
  --epochs 2 \
  --batch-size 2 \
  --grad-accum 8 \
  --lr 2e-4 \
  --max-seq-len 2048 \
  --completion-tokens 256 \
  --bf16
```

`--val-jsonl` is reserved for a future eval hook; validation loss can be wired similarly to `Trainer` eval_dataset.

**Inference note**: Use the same system prompt as training (`ROUTER_SYSTEM_PROMPT` in `train_common.py`) so decoded JSON aligns with offline eval and any downstream parser.

## 5. Offline metrics (gold vs predictions)

Prediction JSONL lines: `predicted_tool_names` **or** `tool_names` (array), plus optional `example_id` to join gold rows.

```bash
python -m app.models.agent_model.tool_router.train.eval_router_offline \
  --gold-jsonl path/to/gold.jsonl \
  --pred-jsonl path/to/pred.jsonl \
  --validate-gold
```

## 6. Reproducibility

Record dataset revision (`registry.yaml`), train/val/test split ids, `--seed`, versions of `torch` / `transformers` / `peft`, and base model revision in your run log (align with the tool-router SPEC reproducibility checklist).

## 7. Non-Qwen bases

`train_hf_utils.py` sets LoRA `target_modules` for common Llama/Qwen-style attention and MLP projections. If loading another architecture fails with missing module names, adjust `target_modules` to match that model’s linear layer names.
