"""Shared helpers for the tool-router Streamlit hub."""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml

from app.models.agent_model.tool_router.train.train_common import (
    ROUTER_TRAIN_SCHEMA_PATH,
    SLOT_OUTPUT_SCHEMA_PATH,
    schema_validator,
)

JobKind = Literal["router_train", "slot_train", "offline_eval"]
DataMode = Literal["router", "slot"]
BASE_MODEL_ALIASES = {
    # Older shorthand used in prior docs/UI.
    "Qwen/Qwen3-4B-Instruct": "Qwen/Qwen3-4B-Instruct-2507",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def backend_root() -> Path:
    return Path(__file__).resolve().parents[4]


def tool_router_data_dir() -> Path:
    return backend_root() / "app" / "models" / "agent_model" / "tool_router" / "data"


def tool_router_shards_dir() -> Path:
    return tool_router_data_dir() / "shards"


def registry_path() -> Path:
    return tool_router_data_dir() / "registry.yaml"


def jobs_root() -> Path:
    return backend_root() / "artifacts" / "tool_router" / "runs"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    if path.is_dir():
        raise IsADirectoryError(f"Expected JSONL file path, got directory: {path}")
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def list_jsonl_shards() -> List[str]:
    root = tool_router_shards_dir()
    if not root.exists():
        return []
    return sorted(str(p.relative_to(backend_root())) for p in root.glob("*.jsonl"))


def default_router_row() -> Dict[str, Any]:
    return {
        "example_id": "",
        "user_message": "",
        "gold_tool_names": [],
        "data_source": "manual",
        "metadata": {},
    }


def default_slot_row() -> Dict[str, Any]:
    return {
        "example_id": "",
        "user_message": "",
        "slot_labels": {},
        "snapshot_features": {},
        "data_source": "manual",
    }


def _router_validator():
    return schema_validator(ROUTER_TRAIN_SCHEMA_PATH)


def _slot_validator():
    return schema_validator(SLOT_OUTPUT_SCHEMA_PATH)


def validate_row(row: Dict[str, Any], mode: DataMode) -> List[str]:
    errors: List[str] = []
    if mode == "router":
        validator = _router_validator()
        for err in validator.iter_errors(row):
            path = ".".join(str(part) for part in err.path) or "<root>"
            errors.append(f"{path}: {err.message}")
        return errors
    labels = row.get("slot_labels")
    if not isinstance(labels, dict):
        errors.append("slot_labels: must be an object")
        return errors
    validator = _slot_validator()
    for err in validator.iter_errors(labels):
        path = ".".join(str(part) for part in err.path) or "slot_labels"
        errors.append(f"{path}: {err.message}")
    return errors


def validate_rows(rows: List[Dict[str, Any]], mode: DataMode) -> List[str]:
    issues: List[str] = []
    for idx, row in enumerate(rows, start=1):
        for msg in validate_row(row, mode):
            issues.append(f"row {idx}: {msg}")
    return issues


def load_registry(path: Optional[Path] = None) -> Dict[str, Any]:
    target = path or registry_path()
    if not target.exists():
        return {"router": {"train": [], "val": [], "test": []}, "slot": {"train": [], "val": [], "test": []}}
    with target.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data


def save_registry(data: Dict[str, Any], path: Optional[Path] = None) -> None:
    target = path or registry_path()
    ensure_parent(target)
    with target.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)


def registry_split_shards(registry: Dict[str, Any], mode: DataMode, split: Literal["train", "val", "test"]) -> List[str]:
    # Preferred schema: datasets.router_head_v1 / datasets.slot_slm_v1
    datasets = registry.get("datasets")
    if isinstance(datasets, dict):
        wanted = "router" if mode == "router" else "slot"
        merged: List[str] = []
        for name, item in datasets.items():
            if not isinstance(name, str) or wanted not in name.lower():
                continue
            if not isinstance(item, dict):
                continue
            rows = item.get(split, [])
            if isinstance(rows, list):
                for raw in rows:
                    if isinstance(raw, str) and raw:
                        merged.append(raw)
        if merged:
            return merged

    # Legacy fallback: top-level router/slot buckets
    bucket = registry.get(mode, {})
    if isinstance(bucket, dict):
        rows = bucket.get(split, [])
        if isinstance(rows, list):
            return [str(v) for v in rows if isinstance(v, str)]
    return []


@dataclass
class JobRecord:
    job_id: str
    kind: JobKind
    status: str
    created_at: str
    cwd: str
    command: str
    job_dir: str
    log_path: str
    exit_code: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    output_dir: Optional[str] = None
    pid: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "status": self.status,
            "created_at": self.created_at,
            "cwd": self.cwd,
            "command": self.command,
            "job_dir": self.job_dir,
            "log_path": self.log_path,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "output_dir": self.output_dir,
            "pid": self.pid,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "JobRecord":
        return cls(
            job_id=str(raw["job_id"]),
            kind=raw["kind"],
            status=str(raw.get("status", "queued")),
            created_at=str(raw.get("created_at", now_iso())),
            cwd=str(raw.get("cwd", str(backend_root()))),
            command=str(raw.get("command", "")),
            job_dir=str(raw["job_dir"]),
            log_path=str(raw["log_path"]),
            exit_code=raw.get("exit_code"),
            started_at=raw.get("started_at"),
            finished_at=raw.get("finished_at"),
            output_dir=raw.get("output_dir"),
            pid=raw.get("pid"),
        )


def _job_meta_path(job_dir: Path) -> Path:
    return job_dir / "job.json"


def _job_exit_path(job_dir: Path) -> Path:
    return job_dir / "exit_code.txt"


def _job_script_path(job_dir: Path) -> Path:
    return job_dir / "run.sh"


def _job_log_path(job_dir: Path) -> Path:
    return job_dir / "run.log"


def job_report_path(job: JobRecord) -> Path:
    return Path(job.job_dir) / "report.json"


def _serialize_shell_command(args: List[str]) -> str:
    return shlex.join(args)


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def create_job(kind: JobKind, args: List[str], cwd: Optional[Path] = None, output_dir: Optional[str] = None) -> JobRecord:
    root = jobs_root()
    root.mkdir(parents=True, exist_ok=True)
    job_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{kind}_{uuid.uuid4().hex[:8]}"
    job_dir = root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    record = JobRecord(
        job_id=job_id,
        kind=kind,
        status="queued",
        created_at=now_iso(),
        cwd=str((cwd or backend_root()).resolve()),
        command=_serialize_shell_command(args),
        job_dir=str(job_dir),
        log_path=str(_job_log_path(job_dir)),
        output_dir=output_dir,
    )
    save_job(record)
    return record


def save_job(job: JobRecord) -> None:
    path = _job_meta_path(Path(job.job_dir))
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(job.to_dict(), fh, ensure_ascii=False, indent=2)


def load_job(job_dir: Path) -> JobRecord:
    with _job_meta_path(job_dir).open("r", encoding="utf-8") as fh:
        return JobRecord.from_dict(json.load(fh))


def list_jobs() -> List[JobRecord]:
    root = jobs_root()
    if not root.exists():
        return []
    jobs: List[JobRecord] = []
    for d in root.iterdir():
        if not d.is_dir():
            continue
        meta = _job_meta_path(d)
        if not meta.exists():
            continue
        try:
            jobs.append(load_job(d))
        except Exception:
            continue
    jobs.sort(key=lambda item: item.created_at, reverse=True)
    return jobs


def start_job(job: JobRecord) -> JobRecord:
    job_dir = Path(job.job_dir)
    script_path = _job_script_path(job_dir)
    exit_path = _job_exit_path(job_dir)
    script = (
        "#!/usr/bin/env bash\n"
        "set +e\n"
        f"cd {shlex.quote(job.cwd)}\n"
        f"{job.command}\n"
        "ec=$?\n"
        f"echo \"$ec\" > {shlex.quote(str(exit_path))}\n"
        "exit $ec\n"
    )
    script_path.write_text(script, encoding="utf-8")
    script_path.chmod(0o755)
    log_file = open(_job_log_path(job_dir), "a", encoding="utf-8")
    proc = subprocess.Popen(
        ["/bin/bash", str(script_path)],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    job.pid = proc.pid
    job.status = "running"
    job.started_at = now_iso()
    save_job(job)
    return job


def refresh_job(job: JobRecord) -> JobRecord:
    if job.status not in {"running", "queued"}:
        return job
    job_dir = Path(job.job_dir)
    exit_path = _job_exit_path(job_dir)
    if exit_path.exists():
        try:
            code = int(exit_path.read_text(encoding="utf-8").strip())
        except ValueError:
            code = 1
        job.exit_code = code
        job.status = "success" if code == 0 else "failed"
        job.finished_at = now_iso()
        save_job(job)
        return job
    if job.pid and not _is_pid_alive(job.pid):
        job.status = "failed"
        job.exit_code = 1
        job.finished_at = now_iso()
        save_job(job)
    return job


def read_log_tail(log_path: str, max_chars: int = 20000) -> str:
    path = Path(log_path)
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def resolve_base_model_id(base_model: str) -> str:
    model = str(base_model or "").strip()
    if not model:
        return model
    return BASE_MODEL_ALIASES.get(model, model)


def training_model_bucket(base_model: str) -> str:
    resolved = resolve_base_model_id(base_model)
    if not resolved:
        return "unknown-model"
    # Keep bucket names filesystem-safe and human-readable.
    compact = resolved.replace("/", "--")
    compact = re.sub(r"[^A-Za-z0-9._-]+", "-", compact)
    compact = compact.strip("-._")
    return compact or "unknown-model"


def build_training_output_dir(kind: JobKind, requested_output_dir: str, base_model: str) -> str:
    raw = str(requested_output_dir or "").strip()
    if raw:
        root = Path(raw)
    elif kind == "router_train":
        root = Path("artifacts/tool_router/router_head")
    else:
        root = Path("artifacts/tool_router/slot")

    # Backward compatibility: old default used a fixed "manual_run" directory.
    if root.name == "manual_run":
        root = root.parent

    run_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(root / training_model_bucket(base_model) / run_tag)


def extract_last_json_object(text: str) -> Optional[Dict[str, Any]]:
    candidates = [idx for idx, ch in enumerate(text) if ch == "{"]
    for idx in reversed(candidates):
        raw = text[idx:].strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def load_job_report(job: JobRecord) -> Optional[Dict[str, Any]]:
    path = job_report_path(job)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def save_job_report(job: JobRecord, report: Dict[str, Any]) -> None:
    path = job_report_path(job)
    ensure_parent(path)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def build_router_train_args(
    train_jsonl: str,
    output_dir: str,
    base_model: str,
    epochs: int,
    batch_size: int,
    grad_accum: int,
    lr: float,
    max_seq_len: int,
    completion_tokens: int,
    bf16: bool,
    val_jsonl: str = "",
) -> List[str]:
    resolved_model = resolve_base_model_id(base_model)
    args = [
        "python",
        "-m",
        "app.models.agent_model.tool_router.train.train_router_head",
        "--train-jsonl",
        train_jsonl,
        "--output-dir",
        output_dir,
        "--base-model",
        resolved_model,
        "--epochs",
        str(epochs),
        "--batch-size",
        str(batch_size),
        "--grad-accum",
        str(grad_accum),
        "--lr",
        str(lr),
        "--max-seq-len",
        str(max_seq_len),
        "--completion-tokens",
        str(completion_tokens),
    ]
    if val_jsonl.strip():
        args.extend(["--val-jsonl", val_jsonl.strip()])
    if bf16:
        args.append("--bf16")
    return args


def build_slot_train_args(
    data_jsonl: str,
    output_dir: str,
    base_model: str,
    epochs: int,
    batch_size: int,
    grad_accum: int,
    lr: float,
    max_seq_len: int,
    completion_tokens: int,
    bf16: bool,
) -> List[str]:
    resolved_model = resolve_base_model_id(base_model)
    args = [
        "python",
        "-m",
        "app.models.agent_model.tool_router.train.train_slot_lora",
        "--data-jsonl",
        data_jsonl,
        "--output-dir",
        output_dir,
        "--base-model",
        resolved_model,
        "--epochs",
        str(epochs),
        "--batch-size",
        str(batch_size),
        "--grad-accum",
        str(grad_accum),
        "--lr",
        str(lr),
        "--max-seq-len",
        str(max_seq_len),
        "--completion-tokens",
        str(completion_tokens),
    ]
    if bf16:
        args.append("--bf16")
    return args


def build_eval_args(gold_jsonl: str, pred_jsonl: str, validate_gold: bool) -> List[str]:
    args = [
        "python",
        "-m",
        "app.models.agent_model.tool_router.train.eval_router_offline",
        "--gold-jsonl",
        gold_jsonl,
        "--pred-jsonl",
        pred_jsonl,
    ]
    if validate_gold:
        args.append("--validate-gold")
    return args
