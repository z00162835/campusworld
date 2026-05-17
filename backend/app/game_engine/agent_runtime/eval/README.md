# AICO Live Tool Eval

Evaluates AICO tool use through the **real SSH `aico` command path** (default and
recommended). Each case runs as `aico <message>` or `aico -nd <message>` in one
shared SSH shell per eval run, then scores DB `command_trace` plus optional AICO
log excerpts.

**Config (single source of truth):** `app/game_engine/agent_runtime/eval/config.json`  
**Data directory:** `app/game_engine/agent_runtime/eval/data/`

> Dev-only: set `aico.invoke_via` to a non-`ssh` value to run in-process via
> `execute_aico_command` (not comparable to live SSH results). Default remains SSH.

## Quick Start (Streamlit — default)

One Streamlit app covers the full local loop: **edit cases → run eval → analyze →
review → promote**. No need to chain multiple CLI commands for day-to-day work.

```bash
cd backend
pip install -r requirements/agent-tool-eval.txt   # first time only

export AICO_EVAL_SSH_PASSWORD='<ssh-password>'
streamlit run app/game_engine/agent_runtime/eval/streamlit_app.py
```

In the app (top to bottom):

| Step | Section | Action |
| --- | --- | --- |
| 1 | **Run Evaluation** | Choose suite (`gate` / `smoke` / `stress`), click **Run eval now** |
| 2–5 | **Results / Failure / Pair browser / Trace** | Inspect pass rate, failures, per-case DB trace and normalized events |
| 6 | **Review And Promote** | Set review status → **Export corrected pairs** → **Promote to regression** |
| 7 | **Case editor** | Form-based case create/edit (or advanced JSON) |

JSONL/JSON under `eval/data/` remain the source of truth; the UI reads and writes
those files via `config.json` paths.

Optional CLI flags are mirrored in the UI: suite selection, path overrides, enforce
gates, skip dataset governance.

## CLI Runner (automation / CI)

Use the CLI when you need scripting, exit codes in CI, or no browser:

```bash
cd backend
AICO_EVAL_SSH_PASSWORD='<ssh-password>' \
python -m app.game_engine.agent_runtime.eval.runner --suite gate
```

Equivalent script: `python scripts/run_agent_tool_eval.py --suite gate`

Exit codes: `0` pass, `2` gate failure (when `gate_policy.enforce` is true).

Debug flags:

- `--no-enforce-gates` — do not exit non-zero on gate failure
- `--skip-dataset-governance` — skip case metadata/tier validation

### Default suite and files

| Item | Default |
| --- | --- |
| Suite | `gate` (`--suite gate`) |
| Cases | `data/aico_initial_cases.jsonl` |
| Smoke | `data/aico_smoke_cases.jsonl` (`--suite smoke`) |
| Stress | `data/aico_stress_cases.jsonl` (`--suite stress`) |
| Output pairs | `data/pairs.live.jsonl` |
| Report | `data/report.live.json` |
| Reviewed export | `data/corrected_pairs.jsonl` |
| Regression | `data/cases.regression.jsonl` |

Override paths:

```bash
python -m app.game_engine.agent_runtime.eval.runner \
  --config app/game_engine/agent_runtime/eval/config.json \
  --suite gate \
  --cases path/to/cases.jsonl \
  --out path/to/pairs.live.jsonl \
  --report path/to/report.live.json
```

## Workflow

**Recommended (Streamlit):**

```text
streamlit run …/streamlit_app.py
  → edit cases (section 7)
  → Run eval now (section 1)
  → analyze (sections 2–5)
  → export corrected_pairs.jsonl (section 6)
  → promote to cases.regression.jsonl (section 6)
```

**Automation (CLI):**

```text
runner --suite gate → pairs.live.jsonl + report.live.json
  → review_cli (optional) → corrected_pairs.jsonl
  → promote → cases.regression.jsonl
```

## Live Hard Gates

After writing `report.live.json`, runner enforces `gate_policy` when
`gate_policy.enforce` is true (config default). On failure: **exit code `2`** and a
JSON summary on stdout (CLI) or an error banner (Streamlit). Bypass with
`--no-enforce-gates` or uncheck **Enforce gates** in the UI.

Default live thresholds (`gate_policy.live` in config):

| Metric | Op | Threshold |
| --- | --- | --- |
| `live_trace_presence` | `gte` | `1.0` |
| `final_reply_after_tool` | `gte` | `1.0` |
| `illegal_tool_rate` | `lte` | `0.0` |
| `schema_violation_rate` | `lte` | `0.0` |

Operators: `gte`, `lte`, `eq` (with `gate_policy.tolerance`).

## Environment

| Variable | Purpose |
| --- | --- |
| `AICO_EVAL_SSH_PASSWORD` | SSH password (required for default SSH path) |
| `AICO_EVAL_NEW_DIALOGUE=1` | Use `aico -nd` for all cases |
| `AICO_EVAL_LOG_PATH` | Override AICO observability log path |

In-process path only (when `invoke_via` is not `ssh`):

| Variable | Purpose |
| --- | --- |
| `AICO_EVAL_USER_ID` | Override eval user id |
| `AICO_EVAL_USERNAME` | Override eval username |
| `AICO_EVAL_PERMISSIONS` | Comma-separated permissions |
| `AICO_EVAL_ROLES` | Comma-separated roles |

SSH uses `paramiko` from backend base requirements. Streamlit UI extras:
`requirements/agent-tool-eval.txt`

Do not store SSH passwords in `config.json`; use `ssh_password_env` only.

## How Live Evaluation Works

1. One SSH shell per eval run; cases run sequentially in that shell.
2. Default: `aico <user_message>`; with `metadata.aico_new_dialogue` or
   `AICO_EVAL_NEW_DIALOGUE=1`: `aico -nd <user_message>`.
3. Adapter loads latest `agent_run_records` after the command (`after_run_id`).
4. Graders score tools, args, sequence, forbidden/mandatory tools, DB trace,
   schema violations, and final reply after tool use.

`aico.require_db_trace` defaults to `true`. Missing DB trace → `live_trace_presence`
failure and `live_trace_missing` event (echo-only / passthrough runs are invalid).

## Is AICO Really Running?

For SSH runs, check pair metadata (Trace Viewer in Streamlit):

| Evidence | Healthy signal |
| --- | --- |
| `invoke_via` | `ssh` |
| `command_success` | `true` (derived from SSH + trace evidence) |
| `db_trace.found` | `true` |
| `trace` | Tool/phase events from `command_trace` |
| `passthrough_suspected` | `false` |
| `elapsed_ms` | Usually >> a few ms for a real tick |

## Writing Cases

One JSON object per line. Do **not** include the `aico` prefix in `user_message`.
Prefer the Streamlit **Case Form Editor**; use `data/aico_initial_cases.jsonl` as
reference.

Governance fields are required by default:

- `tags` (non-empty)
- `metadata.intent`
- `metadata.dataset_tier` (must match suite, e.g. `gate`)

Minimal case:

```jsonl
{"example_id":"manual_whoami_001","agent_id":"aico","user_message":"whoami","available_tools":[{"name":"whoami","description":"Show current user"}],"expected_tools":["whoami"],"mandatory_tools":["whoami"],"expected_args":{"whoami":[{"name":"whoami","args":[]}]},"tags":["identity","manual"],"data_source":"human","language":"en","metadata":{"intent":"execute","dataset_tier":"gate","dataset_version":"manual-v1"}}
```

## Review And Promote (CLI alternative)

```bash
python -m app.game_engine.agent_runtime.eval.review_cli
python -m app.game_engine.agent_runtime.eval.promote
```

Scripts: `scripts/review_agent_tool_pairs.py`, `scripts/promote_corrected_pairs.py`

## Verification

Unit tests (no live DB/LLM):

```bash
conda run -n campusworld pytest tests/game_engine/test_agent_tool_eval.py -q
```

Live eval (manual): use Streamlit **Run eval now**, or CLI:

```bash
AICO_EVAL_SSH_PASSWORD='<ssh-password>' \
python -m app.game_engine.agent_runtime.eval.runner --suite gate
```
