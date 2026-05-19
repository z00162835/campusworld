# Tool router — training & offline eval

Train outside the default API hot path. The default training entry is the unified Streamlit hub.

## Default entry (recommended): Streamlit Hub

Use Streamlit as the primary workflow for:

- edit router/slot training samples
- launch asynchronous training jobs
- run offline evaluation and compare runs

Run from `backend/`:

```bash
streamlit run app/models/agent_model/tool_router/streamlit_app.py
```

## 1) Environment setup

### Required

- Conda env: `campusworld`
- Python dependencies:

```bash
cd backend
pip install -r requirements/tool-router-train.txt
```

Do not merge these into default `requirements/dev.txt` CI installs unless the pipeline explicitly supports GPU/train.

### PyTorch

Install a PyTorch build suitable for your device (CPU/CUDA) from [pytorch.org](https://pytorch.org/).

Notes:

- Disable `bf16` on CPU-only environments.
- For GPU runs, start with smaller `batch_size` and increase gradually.

## 2) Data preparation and schema

See:

- [`../data/README.md`](../data/README.md)
- [`../data/registry.yaml.example`](../data/registry.yaml.example)

In-app data workflow (**Samples** tab):

1. choose mode (`router` or `slot`)
2. load/edit row JSON
3. click **Validate row**
4. click **Upsert row**
5. click **Save file** (validates all rows before write)

Registry can be edited in the same tab and saved as YAML.

## 3) Training in Streamlit

In **Training** tab, choose task:

- `router_train` -> `train_router_head.py`
- `slot_train` -> `train_slot_lora.py`

Model presets in the unified Streamlit app:

- `Qwen2.5-0.5B (baseline)` -> `Qwen/Qwen2.5-0.5B-Instruct`
- `Qwen3-4B (candidate)` -> `Qwen/Qwen3-4B-Instruct-2507`
- `Custom` -> manual model id entry

Preset values are sourced from:

- `app/models/agent_model/tool_router/streamlit_config.json`

The same config file also carries UI/system defaults such as:

- sample tab default JSONL paths
- training output default directories
- offline eval default gold/pred paths
- noisy logger suppression list
- log tail max chars in run viewer
- training parameter limits/whitelist ranges (epochs, batch_size, grad_accum, lr, max_seq_len, completion_tokens)

Recommended starting parameters:

- `epochs`: 2
- `batch_size`: 2
- `grad_accum`: 8
- `lr`: 2e-4
- `max_seq_len`: 2048
- `completion_tokens`: 256 (router) / 384 (slot)
- `bf16`: enabled on supported GPU, disabled on CPU

For `Qwen3-4B` on a single GPU, start conservatively with:

- `batch_size`: 1
- `grad_accum`: 16
- `lr`: 1.5e-4

Training outputs are written to your configured `output_dir` and typically include:

- adapter weights / model artifacts
- tokenizer files
- `train_meta.json`

The Streamlit job runner stores job metadata/logs under:

- `artifacts/tool_router/runs/<job_id>/job.json`
- `artifacts/tool_router/runs/<job_id>/run.log`

## 4) Offline evaluation in Streamlit

In **Evaluation** tab:

1. provide `gold_jsonl` and `pred_jsonl`
2. optionally enable `validate_gold`
3. run offline eval

Displayed metrics:

- `subset_exact_match_rate`
- `macro_f1`
- `mandatory_recall`
- `by_data_source`

For successful eval jobs, parsed report JSON is persisted to:

- `artifacts/tool_router/runs/<job_id>/report.json`

Use **Compare runs** to inspect metric deltas between two completed reports.

## 5) CLI mode (advanced / automation)

CLI remains supported for CI, scripted experiments, and non-UI automation.

### Slot SLM CLI

```bash
cd backend
python -m app.models.agent_model.tool_router.train.train_slot_lora \
  --data-jsonl app/models/agent_model/tool_router/data/shards/slot_train_part00.jsonl \
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

### Router head CLI

```bash
cd backend
python -m app.models.agent_model.tool_router.train.train_router_head \
  --train-jsonl app/models/agent_model/tool_router/data/shards/router_train_part00.jsonl \
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

### Offline eval CLI

```bash
python -m app.models.agent_model.tool_router.train.eval_router_offline \
  --gold-jsonl path/to/gold.jsonl \
  --pred-jsonl path/to/pred.jsonl \
  --validate-gold
```

## 6) Troubleshooting

### OOM / GPU memory errors

- reduce `batch_size`
- reduce `max_seq_len`
- reduce `completion_tokens`
- keep `grad_accum` for effective global batch size

### Truncated JSON outputs

- increase `completion_tokens`
- reduce prompt noise in samples
- ensure slot labels are concise and schema-conformant

### Schema validation errors

- validate row before upsert
- validate full file before save
- ensure required keys match schema (`gold_tool_names`, `slot_labels`, `data_source`, etc.)

### Job interrupted or terminal closed

- jobs are external processes; inspect `run.log` and `job.json`
- failed jobs stay in history with `exit_code`
- relaunch with adjusted parameters

## 7) Runtime integration boundary

The hub trains/evaluates artifacts but does not directly wire runtime backend factories.

Use **Readiness** tab to check whether runtime factories still resolve to stubs.

## 8) Reproducibility checklist

- record dataset revision (`registry.yaml`) and split ids
- record seed, `torch` / `transformers` / `peft` versions
- record base model revision and key hyperparameters
- keep training/eval prompts aligned with `train_common.py` to avoid format drift
