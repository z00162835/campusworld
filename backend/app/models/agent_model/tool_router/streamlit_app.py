from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
import yaml

# Allow running via `streamlit run backend/app/.../streamlit_app.py`
# from either repository root or `backend/` without PYTHONPATH setup.
BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.agent_model.tool_router.streamlit_hub import (
    backend_root,
    build_eval_args,
    build_router_train_args,
    build_slot_train_args,
    build_training_output_dir,
    create_job,
    default_router_row,
    default_slot_row,
    extract_last_json_object,
    list_jobs,
    list_jsonl_shards,
    load_jsonl,
    load_job_report,
    load_registry,
    read_log_tail,
    refresh_job,
    registry_split_shards,
    save_job,
    save_job_report,
    save_registry,
    start_job,
    tool_router_data_dir,
    validate_row,
    validate_rows,
    write_jsonl,
)
from app.models.agent_model.tool_router.streamlit_config import load_streamlit_config

APP_SCOPE = "tool_router_hub"
STREAMLIT_CFG = load_streamlit_config()
MODEL_PRESETS: Dict[str, Dict[str, Any]] = STREAMLIT_CFG.model_presets
if "Custom" not in MODEL_PRESETS:
    MODEL_PRESETS["Custom"] = {}
UI_DEFAULTS = STREAMLIT_CFG.ui_defaults
NOISY_LOGGERS = tuple(STREAMLIT_CFG.noisy_loggers)
DEPRECATED_MODEL_IDS = STREAMLIT_CFG.deprecated_model_ids
TRAINING_LIMITS = STREAMLIT_CFG.training_limits


def _configure_streamlit_eval_logging() -> None:
    # Silence noisy filesystem watcher debug logs in Streamlit console.
    for name in NOISY_LOGGERS:
        logger = logging.getLogger(name)
        logger.setLevel(logging.WARNING)


def skey(name: str) -> str:
    return f"{APP_SCOPE}::{name}"


def _limit_value(metric: str, key: str, default: float) -> float:
    bucket = TRAINING_LIMITS.get(metric, {})
    raw = bucket.get(key, default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def _validate_training_value(metric: str, value: float) -> Optional[str]:
    lo = _limit_value(metric, "min", value)
    hi = _limit_value(metric, "max", value)
    if value < lo or value > hi:
        return f"{metric}={value} out of allowed range [{lo}, {hi}]"
    return None


def rel_backend(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(backend_root()))
    except ValueError:
        return str(path)


def abs_backend(path: str) -> Path:
    p = Path(path).expanduser()
    if p.is_absolute():
        return p
    return backend_root() / p


def dataset_key(mode: str, path: str) -> str:
    clean = path.replace("/", "_").replace(":", "_")
    return skey(f"rows::{mode}::{clean}")


def _selection_key(mode: str, path: str) -> str:
    clean = path.replace("/", "_").replace(":", "_")
    return skey(f"selected::{mode}::{clean}")


def _pending_selection_key(mode: str, path: str) -> str:
    clean = path.replace("/", "_").replace(":", "_")
    return skey(f"pending_selected::{mode}::{clean}")


def _editor_key(mode: str, path: str) -> str:
    clean = path.replace("/", "_").replace(":", "_")
    return skey(f"editor::{mode}::{clean}")


def _editor_seed_key(mode: str, path: str) -> str:
    clean = path.replace("/", "_").replace(":", "_")
    return skey(f"editor_seed::{mode}::{clean}")


def queue_selection(mode: str, path: str, token: str) -> None:
    st.session_state[_pending_selection_key(mode, path)] = token


def apply_pending_selection(mode: str, path: str) -> None:
    pending_key = _pending_selection_key(mode, path)
    selection_key = _selection_key(mode, path)
    pending = st.session_state.pop(pending_key, None)
    if pending is not None:
        st.session_state[selection_key] = pending


def _row_tokens(rows: List[Dict[str, Any]]) -> List[str]:
    tokens = ["__new__"]
    for idx, row in enumerate(rows):
        example_id = str(row.get("example_id") or "").strip()
        label = example_id if example_id else f"row_{idx + 1}"
        tokens.append(label)
    return tokens


def _resolve_selected_index(selected_token: str, rows: List[Dict[str, Any]]) -> Optional[int]:
    if selected_token == "__new__":
        return None
    for idx, row in enumerate(rows):
        eid = str(row.get("example_id") or "").strip()
        label = eid if eid else f"row_{idx + 1}"
        if label == selected_token:
            return idx
    return None


def _load_rows_if_needed(mode: str, path: str) -> List[Dict[str, Any]]:
    path = path.strip()
    key = dataset_key(mode, path)
    if key not in st.session_state:
        st.session_state[key] = load_jsonl(abs_backend(path))
    return st.session_state[key]


def _set_rows(mode: str, path: str, rows: List[Dict[str, Any]]) -> None:
    st.session_state[dataset_key(mode, path)] = rows


def _seed_editor(mode: str, path: str, row: Dict[str, Any]) -> None:
    editor_key = _editor_key(mode, path)
    seed_key = _editor_seed_key(mode, path)
    seed_value = json.dumps(row, indent=2, ensure_ascii=False)
    if st.session_state.get(seed_key) != seed_value:
        st.session_state[seed_key] = seed_value
        st.session_state[editor_key] = seed_value


def render_samples_tab() -> None:
    st.subheader("Samples")
    mode = st.radio("Sample mode", options=["router", "slot"], horizontal=True, key=skey("sample_mode"))

    shard_options = list_jsonl_shards()
    default_path = str(UI_DEFAULTS.get("sample_default_path_router") or "app/models/agent_model/tool_router/data/shards/router_train_part00.jsonl")
    if mode == "slot":
        default_path = str(UI_DEFAULTS.get("sample_default_path_slot") or "app/models/agent_model/tool_router/data/shards/slot_train_part00.jsonl")
    if default_path not in shard_options and shard_options:
        default_path = shard_options[0]

    path_state_key = skey(f"sample_path::{mode}")
    if path_state_key not in st.session_state:
        st.session_state[path_state_key] = default_path
    sample_path = st.text_input("JSONL path", key=path_state_key).strip()
    if not sample_path:
        st.error("JSONL path cannot be empty.")
        return
    sample_file = abs_backend(sample_path)
    if sample_file.is_dir():
        st.error(f"JSONL path points to a directory, not a file: {rel_backend(sample_file)}")
        return

    c1, c2 = st.columns([1, 1])
    if c1.button("Reload rows", key=skey(f"reload::{mode}")):
        try:
            _set_rows(mode, sample_path, load_jsonl(sample_file))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            st.error(f"Failed to load rows: {exc}")
    if c2.button("Create file if missing", key=skey(f"create_file::{mode}")):
        p = sample_file
        if not p.exists():
            write_jsonl(p, [])
            st.success(f"Created {rel_backend(p)}")
    try:
        rows = _load_rows_if_needed(mode, sample_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        st.error(f"Failed to load rows: {exc}")
        return
    st.caption(f"Loaded rows: {len(rows)}")
    st.dataframe(rows, use_container_width=True, height=220)

    apply_pending_selection(mode, sample_path)
    tokens = _row_tokens(rows)
    selected_token = st.selectbox(
        "Edit row",
        options=tokens,
        key=_selection_key(mode, sample_path),
    )
    selected_index = _resolve_selected_index(selected_token, rows)
    current_row = (rows[selected_index] if selected_index is not None else (default_router_row() if mode == "router" else default_slot_row()))
    _seed_editor(mode, sample_path, current_row)
    row_text = st.text_area("Row JSON", key=_editor_key(mode, sample_path), height=260)

    p1, p2, p3, p4 = st.columns([1, 1, 1, 1])
    if p1.button("Validate row", key=skey(f"validate_row::{mode}")):
        try:
            parsed = json.loads(row_text)
            errors = validate_row(parsed, mode=mode)
            if errors:
                for msg in errors:
                    st.error(msg)
            else:
                st.success("Row is valid.")
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")

    if p2.button("Upsert row", key=skey(f"upsert::{mode}")):
        try:
            parsed = json.loads(row_text)
            errors = validate_row(parsed, mode=mode)
            if errors:
                for msg in errors:
                    st.error(msg)
            else:
                updated = list(rows)
                if selected_index is None:
                    updated.append(parsed)
                    queue_selection(mode, sample_path, str(parsed.get("example_id") or f"row_{len(updated)}"))
                else:
                    updated[selected_index] = parsed
                _set_rows(mode, sample_path, updated)
                st.success("Row updated in memory.")
                st.rerun()
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")

    if p3.button("Delete row", key=skey(f"delete::{mode}"), disabled=selected_index is None):
        if selected_index is not None:
            updated = list(rows)
            updated.pop(selected_index)
            _set_rows(mode, sample_path, updated)
            queue_selection(mode, sample_path, "__new__")
            st.success("Row deleted in memory.")
            st.rerun()

    if p4.button("Save file", key=skey(f"save_file::{mode}")):
        issues = validate_rows(rows, mode=mode)
        if issues:
            st.error(f"Cannot save: {len(issues)} validation issue(s).")
            for msg in issues[:20]:
                st.error(msg)
        else:
            try:
                path = abs_backend(sample_path)
                if path.is_dir():
                    st.error(f"Save target is a directory: {rel_backend(path)}")
                else:
                    write_jsonl(path, rows)
                    st.success(f"Saved {len(rows)} row(s) to {rel_backend(path)}")
            except OSError as exc:
                st.error(f"Failed to save rows: {exc}")

    st.markdown("### Registry")
    reg = load_registry()
    registry_editor_key = skey("registry_yaml")
    if registry_editor_key not in st.session_state:
        st.session_state[registry_editor_key] = yaml.safe_dump(reg, sort_keys=False, allow_unicode=True)
    registry_text = st.text_area("registry.yaml", key=registry_editor_key, height=220)
    r1, r2 = st.columns([1, 1])
    if r1.button("Reload registry", key=skey("reload_registry")):
        st.session_state[registry_editor_key] = yaml.safe_dump(load_registry(), sort_keys=False, allow_unicode=True)
        st.rerun()
    if r2.button("Save registry", key=skey("save_registry")):
        try:
            parsed = yaml.safe_load(registry_text) or {}
            if not isinstance(parsed, dict):
                st.error("registry.yaml must be a mapping object.")
            else:
                save_registry(parsed)
                st.success(f"Saved {rel_backend(tool_router_data_dir() / 'registry.yaml')}")
        except yaml.YAMLError as exc:
            st.error(f"Invalid YAML: {exc}")


def _pick_shard_input(label: str, key: str, mode: str, split: str) -> str:
    reg = load_registry()
    options = registry_split_shards(reg, mode=mode, split=split)
    fallback = f"app/models/agent_model/tool_router/data/shards/{mode}_{split}_part00.jsonl"
    if key not in st.session_state:
        if options:
            st.session_state[key] = f"app/models/agent_model/tool_router/data/{options[0]}"
        else:
            st.session_state[key] = fallback
    return st.text_input(label, key=key)


def render_training_tab() -> None:
    st.subheader("Training")
    task = st.selectbox("Task type", options=["router_train", "slot_train"], key=skey("train_task"))
    preset_key = st.selectbox("Model preset", options=list(MODEL_PRESETS.keys()), key=skey("model_preset"))
    preset = MODEL_PRESETS[preset_key]
    is_custom = preset_key == "Custom"
    apply_preset_clicked = st.button("Apply preset defaults", key=skey("apply_model_preset"), disabled=is_custom)

    base_model_key = skey("base_model")
    if base_model_key not in st.session_state:
        st.session_state[base_model_key] = "Qwen/Qwen2.5-0.5B-Instruct"
    if apply_preset_clicked:
        st.session_state[base_model_key] = str(preset.get("base_model") or st.session_state[base_model_key])
        st.session_state[skey("epochs")] = int(preset.get("epochs", 2))
        st.session_state[skey("batch_size")] = int(preset.get("batch_size", 2))
        st.session_state[skey("grad_accum")] = int(preset.get("grad_accum", 8))
        st.session_state[skey("lr")] = float(preset.get("lr", 2e-4))
        st.session_state[skey("max_seq_len")] = int(preset.get("max_seq_len", 2048))
        st.session_state[skey("completion_tokens")] = int(
            preset.get("completion_tokens_router" if task == "router_train" else "completion_tokens_slot", 256)
        )
        st.session_state[skey("bf16")] = bool(preset.get("bf16", True))
    elif not is_custom and st.session_state.get(base_model_key) != str(preset.get("base_model") or ""):
        st.session_state[base_model_key] = str(preset.get("base_model") or st.session_state[base_model_key])

    base_model = st.text_input(
        "Base model",
        key=base_model_key,
        disabled=not is_custom,
        help="Use Custom preset to edit model id manually.",
    )
    replacement = DEPRECATED_MODEL_IDS.get(base_model.strip())
    if replacement:
        st.warning(f"`{base_model.strip()}` is deprecated here; use `{replacement}`.")
    output_default = (
        str(UI_DEFAULTS.get("training_output_dir_router") or "artifacts/tool_router/router_head/manual_run")
        if task == "router_train"
        else str(UI_DEFAULTS.get("training_output_dir_slot") or "artifacts/tool_router/slot/manual_run")
    )
    output_dir = st.text_input("Output dir", value=output_default, key=skey("output_dir"))
    st.caption("Final artifacts are auto-isolated as `<output dir>/<base_model>/<timestamp>/` to prevent overwrite.")
    if not is_custom:
        st.caption(f"Preset base model: `{preset.get('base_model', '')}`")
    st.caption("Train in this tab, then run offline eval in the Evaluation tab with your prediction JSONL.")

    c1, c2, c3 = st.columns(3)
    epochs = c1.number_input(
        "Epochs",
        min_value=int(_limit_value("epochs", "min", 1)),
        max_value=int(_limit_value("epochs", "max", 50)),
        value=2,
        step=int(_limit_value("epochs", "step", 1)),
        key=skey("epochs"),
    )
    batch_size = c2.number_input(
        "Batch size",
        min_value=int(_limit_value("batch_size", "min", 1)),
        max_value=int(_limit_value("batch_size", "max", 64)),
        value=2,
        step=int(_limit_value("batch_size", "step", 1)),
        key=skey("batch_size"),
    )
    grad_accum = c3.number_input(
        "Grad accum",
        min_value=int(_limit_value("grad_accum", "min", 1)),
        max_value=int(_limit_value("grad_accum", "max", 128)),
        value=8,
        step=int(_limit_value("grad_accum", "step", 1)),
        key=skey("grad_accum"),
    )
    d1, d2, d3 = st.columns(3)
    lr = d1.number_input(
        "Learning rate",
        min_value=_limit_value("lr", "min", 1e-7),
        max_value=_limit_value("lr", "max", 1e-1),
        value=2e-4,
        step=_limit_value("lr", "step", 1e-4),
        format="%.7f",
        key=skey("lr"),
    )
    max_seq_len = d2.number_input(
        "Max seq len",
        min_value=int(_limit_value("max_seq_len", "min", 64)),
        max_value=int(_limit_value("max_seq_len", "max", 8192)),
        value=2048,
        step=int(_limit_value("max_seq_len", "step", 64)),
        key=skey("max_seq_len"),
    )
    completion_tokens = d3.number_input(
        "Completion tokens",
        min_value=int(_limit_value("completion_tokens", "min", 32)),
        max_value=int(_limit_value("completion_tokens", "max", 2048)),
        value=256,
        step=int(_limit_value("completion_tokens", "step", 32)),
        key=skey("completion_tokens"),
    )
    bf16 = st.checkbox("Use bf16", value=True, key=skey("bf16"))

    if task == "router_train":
        train_jsonl = _pick_shard_input("Train JSONL", skey("router_train_jsonl"), "router", "train")
        val_jsonl = _pick_shard_input("Val JSONL (optional)", skey("router_val_jsonl"), "router", "val")
        args = build_router_train_args(
            train_jsonl=train_jsonl,
            output_dir=output_dir,
            base_model=base_model,
            epochs=int(epochs),
            batch_size=int(batch_size),
            grad_accum=int(grad_accum),
            lr=float(lr),
            max_seq_len=int(max_seq_len),
            completion_tokens=int(completion_tokens),
            bf16=bf16,
            val_jsonl=val_jsonl,
        )
    else:
        data_jsonl = _pick_shard_input("Data JSONL", skey("slot_data_jsonl"), "slot", "train")
        args = build_slot_train_args(
            data_jsonl=data_jsonl,
            output_dir=output_dir,
            base_model=base_model,
            epochs=int(epochs),
            batch_size=int(batch_size),
            grad_accum=int(grad_accum),
            lr=float(lr),
            max_seq_len=int(max_seq_len),
            completion_tokens=int(completion_tokens),
            bf16=bf16,
        )

    if st.button("Submit training job", key=skey("submit_train")):
        limit_errors = [
            _validate_training_value("epochs", float(epochs)),
            _validate_training_value("batch_size", float(batch_size)),
            _validate_training_value("grad_accum", float(grad_accum)),
            _validate_training_value("lr", float(lr)),
            _validate_training_value("max_seq_len", float(max_seq_len)),
            _validate_training_value("completion_tokens", float(completion_tokens)),
        ]
        limit_errors = [msg for msg in limit_errors if msg]
        if limit_errors:
            for msg in limit_errors:
                st.error(msg)
            return
        kind = "router_train" if task == "router_train" else "slot_train"
        final_output_dir = build_training_output_dir(
            kind=kind,
            requested_output_dir=output_dir,
            base_model=base_model,
        )
        try:
            output_flag_index = args.index("--output-dir")
            args[output_flag_index + 1] = final_output_dir
        except (ValueError, IndexError):
            st.error("Training command construction error: missing --output-dir.")
            return
        job = create_job(kind=kind, args=args, cwd=backend_root(), output_dir=final_output_dir)
        start = start_job(job)
        st.success(f"Submitted {start.job_id}")
        st.info(f"Artifacts path: `{final_output_dir}`")
        st.rerun()


def _extract_report_from_log(text: str) -> Optional[Dict[str, Any]]:
    return extract_last_json_object(text)


def render_eval_tab() -> None:
    st.subheader("Offline Evaluation")
    gold_default = str(UI_DEFAULTS.get("eval_gold_default") or "app/models/agent_model/tool_router/data/shards/router_test_part00.jsonl")
    pred_default = str(UI_DEFAULTS.get("eval_pred_default") or "app/models/agent_model/tool_router/data/shards/router_pred.jsonl")
    gold_jsonl = st.text_input("Gold JSONL", value=gold_default, key=skey("eval_gold"))
    pred_jsonl = st.text_input("Prediction JSONL", value=pred_default, key=skey("eval_pred"))
    validate_gold = st.checkbox(
        "Validate gold against schema",
        value=bool(UI_DEFAULTS.get("eval_validate_gold_default", True)),
        key=skey("eval_validate_gold"),
    )

    if st.button("Run offline eval", key=skey("submit_eval")):
        args = build_eval_args(gold_jsonl=gold_jsonl, pred_jsonl=pred_jsonl, validate_gold=validate_gold)
        job = create_job(kind="offline_eval", args=args, cwd=backend_root(), output_dir="")
        start_job(job)
        st.success(f"Submitted {job.job_id}")
        st.rerun()

    jobs = [refresh_job(job) for job in list_jobs() if job.kind == "offline_eval"]
    if not jobs:
        st.info("No offline eval runs yet.")
        return
    selected_id = st.selectbox("Select eval run", options=[j.job_id for j in jobs], key=skey("eval_select"))
    selected = next((j for j in jobs if j.job_id == selected_id), None)
    if selected is None:
        return
    st.write({"status": selected.status, "exit_code": selected.exit_code, "log": rel_backend(Path(selected.log_path))})
    log_text = read_log_tail(selected.log_path, max_chars=int(UI_DEFAULTS.get("log_tail_max_chars", 20000)))
    st.code(log_text or "(no logs yet)")
    report = load_job_report(selected)
    if report is None:
        report = _extract_report_from_log(log_text)
        if report and selected.status == "success":
            save_job_report(selected, report)
    if report:
        c1, c2, c3 = st.columns(3)
        c1.metric("subset_exact_match_rate", f"{report.get('subset_exact_match_rate', 0):.4f}")
        c2.metric("macro_f1", f"{report.get('macro_f1', 0):.4f}")
        mr = report.get("mandatory_recall")
        c3.metric("mandatory_recall", "n/a" if mr is None else f"{mr:.4f}")
        st.json(report.get("by_data_source", {}))

    st.markdown("### Compare runs")
    completed = [j for j in jobs if j.status == "success"]
    if len(completed) < 2:
        st.info("At least two successful eval runs are required for comparison.")
        return
    base_id = st.selectbox("Base run", options=[j.job_id for j in completed], key=skey("cmp_base"))
    cand_options = [j.job_id for j in completed if j.job_id != base_id]
    cand_id = st.selectbox("Candidate run", options=cand_options, key=skey("cmp_cand"))
    base_job = next((j for j in completed if j.job_id == base_id), None)
    cand_job = next((j for j in completed if j.job_id == cand_id), None)
    if base_job is None or cand_job is None:
        return
    base_report = load_job_report(base_job) or _extract_report_from_log(
        read_log_tail(base_job.log_path, max_chars=int(UI_DEFAULTS.get("log_tail_max_chars", 20000)))
    )
    cand_report = load_job_report(cand_job) or _extract_report_from_log(
        read_log_tail(cand_job.log_path, max_chars=int(UI_DEFAULTS.get("log_tail_max_chars", 20000)))
    )
    if not base_report or not cand_report:
        st.warning("Unable to load one or both run reports.")
        return
    m1, m2, m3 = st.columns(3)
    for col, metric_name in zip(
        [m1, m2, m3],
        ["subset_exact_match_rate", "macro_f1", "mandatory_recall"],
    ):
        b = base_report.get(metric_name)
        c = cand_report.get(metric_name)
        if b is None or c is None:
            col.metric(metric_name, "n/a", "n/a")
        else:
            col.metric(metric_name, f"{c:.4f}", f"{(c - b):+.4f}")


def render_jobs_tab() -> None:
    st.subheader("Jobs")
    jobs = [refresh_job(job) for job in list_jobs()]
    if not jobs:
        st.info("No jobs yet.")
        return
    rows = []
    for job in jobs:
        rows.append(
            {
                "job_id": job.job_id,
                "kind": job.kind,
                "status": job.status,
                "created_at": job.created_at,
                "finished_at": job.finished_at,
                "exit_code": job.exit_code,
                "output_dir": job.output_dir or "",
            }
        )
        save_job(job)
    st.dataframe(rows, use_container_width=True, height=240)

    selected_id = st.selectbox("Inspect job", options=[r["job_id"] for r in rows], key=skey("job_select"))
    selected = next((j for j in jobs if j.job_id == selected_id), None)
    if selected is None:
        return
    st.write({"command": selected.command, "cwd": rel_backend(Path(selected.cwd))})
    st.code(read_log_tail(selected.log_path, max_chars=int(UI_DEFAULTS.get("log_tail_max_chars", 20000))) or "(no logs yet)")


def render_runtime_readiness() -> None:
    st.subheader("Runtime Backend Readiness")
    factory_path = backend_root() / "app" / "game_engine" / "agent_runtime" / "model_backends" / "factories.py"
    text = factory_path.read_text(encoding="utf-8")
    non_stub_present = "return StubChatGenerativeBackend()" not in text
    if non_stub_present:
        st.success("Factory appears to include non-stub backends.")
    else:
        st.warning("Factory currently resolves to stub backends. Training artifacts are not wired into runtime yet.")

    jobs = [refresh_job(j) for j in list_jobs() if j.kind in {"router_train", "slot_train"} and j.status == "success"]
    if not jobs:
        st.info("No successful training run found yet.")
        return
    st.write("Successful runs:")
    st.dataframe([{"job_id": j.job_id, "kind": j.kind, "output_dir": j.output_dir or ""} for j in jobs], use_container_width=True)


def main() -> None:
    _configure_streamlit_eval_logging()
    st.set_page_config(page_title="Tool Router Streamlit Hub", layout="wide")
    st.title("Tool Router Streamlit Hub")
    st.caption("Edit datasets, launch async training jobs, and run offline evaluation in one place.")
    tab_samples, tab_train, tab_eval, tab_jobs, tab_ready = st.tabs(
        ["Samples", "Training", "Evaluation", "Jobs", "Readiness"]
    )
    with tab_samples:
        render_samples_tab()
    with tab_train:
        render_training_tab()
    with tab_eval:
        render_eval_tab()
    with tab_jobs:
        render_jobs_tab()
    with tab_ready:
        render_runtime_readiness()


if __name__ == "__main__":
    main()
