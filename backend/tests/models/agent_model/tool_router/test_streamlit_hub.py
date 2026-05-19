from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.agent_model.tool_router import streamlit_hub as hub


@pytest.mark.unit
def test_validate_router_row() -> None:
    row = {
        "user_message": "find chair",
        "gold_tool_names": ["type", "find"],
        "data_source": "synthetic",
    }
    assert hub.validate_row(row, mode="router") == []


@pytest.mark.unit
def test_validate_slot_row_missing_slot_labels() -> None:
    row = {
        "user_message": "go north",
        "data_source": "synthetic",
    }
    errors = hub.validate_row(row, mode="slot")
    assert any("slot_labels" in msg for msg in errors)


@pytest.mark.unit
def test_registry_split_shards_datasets_shape() -> None:
    registry = {
        "version": "1",
        "datasets": {
            "router_head_v1": {"train": ["shards/router_train_part00.jsonl"]},
            "slot_slm_v1": {"train": ["shards/slot_train_part00.jsonl"]},
        },
    }
    assert hub.registry_split_shards(registry, mode="router", split="train") == [
        "shards/router_train_part00.jsonl"
    ]
    assert hub.registry_split_shards(registry, mode="slot", split="train") == [
        "shards/slot_train_part00.jsonl"
    ]


@pytest.mark.unit
def test_extract_last_json_object() -> None:
    text = "line1\nline2\n{\n  \"subset_exact_match_rate\": 0.5,\n  \"macro_f1\": 0.6\n}\n"
    parsed = hub.extract_last_json_object(text)
    assert parsed is not None
    assert parsed["macro_f1"] == 0.6


@pytest.mark.unit
def test_router_train_args_contains_flags() -> None:
    args = hub.build_router_train_args(
        train_jsonl="a.jsonl",
        output_dir="out",
        base_model="Qwen/Qwen2.5-0.5B-Instruct",
        epochs=2,
        batch_size=2,
        grad_accum=8,
        lr=2e-4,
        max_seq_len=2048,
        completion_tokens=256,
        bf16=True,
        val_jsonl="val.jsonl",
    )
    assert "--train-jsonl" in args
    assert "--val-jsonl" in args
    assert "--bf16" in args


@pytest.mark.unit
def test_refresh_job_reads_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hub, "jobs_root", lambda: tmp_path)
    job = hub.create_job(kind="offline_eval", args=["python", "-V"], cwd=tmp_path)
    job.status = "running"
    hub.save_job(job)
    exit_path = Path(job.job_dir) / "exit_code.txt"
    exit_path.write_text("0\n", encoding="utf-8")
    updated = hub.refresh_job(job)
    assert updated.status == "success"
    assert updated.exit_code == 0
    meta = json.loads((Path(job.job_dir) / "job.json").read_text(encoding="utf-8"))
    assert meta["status"] == "success"


@pytest.mark.unit
def test_load_jsonl_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(IsADirectoryError):
        hub.load_jsonl(tmp_path)


@pytest.mark.unit
def test_backend_root_points_to_backend_dir() -> None:
    assert hub.backend_root().name == "backend"


@pytest.mark.unit
def test_training_model_bucket_resolves_alias() -> None:
    bucket = hub.training_model_bucket("Qwen/Qwen3-4B-Instruct")
    assert bucket == "Qwen--Qwen3-4B-Instruct-2507"


@pytest.mark.unit
def test_build_training_output_dir_uses_model_and_timestamp_shape() -> None:
    out = hub.build_training_output_dir(
        kind="router_train",
        requested_output_dir="artifacts/tool_router/router_head",
        base_model="Qwen/Qwen2.5-0.5B-Instruct",
    )
    assert out.startswith("artifacts/tool_router/router_head/Qwen--Qwen2.5-0.5B-Instruct/")
    assert len(out.rsplit("/", maxsplit=1)[-1]) == 15  # YYYYMMDD_HHMMSS


@pytest.mark.unit
def test_build_training_output_dir_compats_manual_run_root() -> None:
    out = hub.build_training_output_dir(
        kind="slot_train",
        requested_output_dir="artifacts/tool_router/slot/manual_run",
        base_model="Qwen/Qwen2.5-0.5B-Instruct",
    )
    assert out.startswith("artifacts/tool_router/slot/Qwen--Qwen2.5-0.5B-Instruct/")
