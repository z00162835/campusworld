"""Schema paths and JSONL helpers for tool_router training (no torch)."""

from __future__ import annotations

import json

import pytest

from app.models.agent_model.tool_router.train.train_common import (
    ROUTER_TRAIN_SCHEMA_PATH,
    SLOT_OUTPUT_SCHEMA_PATH,
    load_router_training_rows,
    load_slot_training_rows,
    schema_validator,
)


@pytest.mark.unit
def test_schema_files_exist() -> None:
    assert SLOT_OUTPUT_SCHEMA_PATH.is_file()
    assert ROUTER_TRAIN_SCHEMA_PATH.is_file()
    slot = json.loads(SLOT_OUTPUT_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert slot.get("title") == "ToolRouterSlotOutput"
    router = json.loads(ROUTER_TRAIN_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert router.get("title") == "ToolRouterTrainRow"


@pytest.mark.unit
def test_load_slot_training_rows(tmp_path) -> None:
    v = schema_validator(SLOT_OUTPUT_SCHEMA_PATH)
    p = tmp_path / "x.jsonl"
    labels = {
        "target_hint": None,
        "named_spans": [],
        "entities": [],
        "mandatory_tools": ["look"],
    }
    p.write_text(
        json.dumps({"user_message": "look", "slot_labels": labels}) + "\n",
        encoding="utf-8",
    )
    rows = load_slot_training_rows(p, validator=v)
    assert len(rows) == 1
    assert rows[0]["slot_labels"]["mandatory_tools"] == ["look"]


@pytest.mark.unit
def test_load_router_training_rows(tmp_path) -> None:
    v = schema_validator(ROUTER_TRAIN_SCHEMA_PATH)
    p = tmp_path / "r.jsonl"
    row = {
        "user_message": "go north",
        "gold_tool_names": ["north"],
        "data_source": "synthetic",
    }
    p.write_text(json.dumps(row) + "\n", encoding="utf-8")
    rows = load_router_training_rows(p, validator=v)
    assert rows[0]["gold_tool_names"] == ["north"]
