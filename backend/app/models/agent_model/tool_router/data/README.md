# Tool router training data

Place JSONL shards under `shards/` or paths referenced by `registry.yaml`. Two **separate** supervision tracks:

## 1) Slot SLM

Rows carry **structured slot labels** validated against `../schemas/tool_router_slot_output.schema.json`. Context fields should match runtime EnrichQuery inputs.

Suggested fields per line:

- `example_id` (optional but recommended for eval joins)
- `user_message`
- `snapshot_features` (string or JSON object)
- `stm_snippet` (optional)
- `manifest_revision`, `lexicon_active_id` (optional strings)
- `slot_labels` — gold object conforming to the slot schema

## 2) Router head supervision (multi-label tools)

For offline training / evaluation of **tool-name labels** (multi-label set, mandatory subset). Schema: `../schemas/tool_router_train_row.schema.json`.

Required fields:

- `user_message`
- `gold_tool_names` (array of command/tool names)
- `data_source`: `synthetic` | `human` | `llm_generated`

Optional:

- `example_id`
- `snapshot_features`, `stm_snippet`, `manifest_revision`, `lexicon_active_id`
- `mandatory_subset` — subset of `gold_tool_names` used for **mandatory recall** in offline metrics

**Training target JSON** (model output): `{"tool_names": [...]}` with the same tools as `gold_tool_names` (see `train_router_head.py`).

Predictions for `eval_router_offline`: JSONL lines with `predicted_tool_names` or `tool_names` (array) and optional `example_id`; if ids are omitted, lines pair by order with gold.

## Registry

See `registry.yaml.example` for a reproducible layout (train/val/test shard lists).
