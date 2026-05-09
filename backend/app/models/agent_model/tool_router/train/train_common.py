"""JSONL loading and schema validation for tool_router train scripts (no torch)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import jsonschema

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"
SLOT_OUTPUT_SCHEMA_PATH = SCHEMAS_DIR / "tool_router_slot_output.schema.json"
ROUTER_TRAIN_SCHEMA_PATH = SCHEMAS_DIR / "tool_router_train_row.schema.json"

SLOT_SYSTEM_PROMPT = (
    "Output a single JSON object only. Keys: target_hint (string|null); "
    "named_spans (array of {text,type}); entities (array of "
    "{normalized_text,entity_type}); mandatory_tools (array of command names, may be empty)."
)

ROUTER_SYSTEM_PROMPT = (
    'Output a single JSON object only with key "tool_names" (array of strings). '
    "List every applicable registered tool/command name for this turn; use [] if none."
)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def schema_validator(schema_path: Path) -> jsonschema.Draft202012Validator:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


def format_snapshot_blob(snapshot_features: Any) -> str:
    if snapshot_features is None:
        return ""
    if isinstance(snapshot_features, str):
        return snapshot_features
    return json.dumps(snapshot_features, ensure_ascii=False)


def build_slot_user_content(row: Dict[str, Any]) -> str:
    parts: List[str] = []
    snap = format_snapshot_blob(row.get("snapshot_features"))
    if snap.strip():
        parts.append(f"World snapshot:\n{snap.strip()}")
    stm = row.get("stm_snippet")
    if isinstance(stm, str) and stm.strip():
        parts.append(f"STM:\n{stm.strip()}")
    mr = row.get("manifest_revision")
    if isinstance(mr, str) and mr.strip():
        parts.append(f"manifest_revision: {mr.strip()}")
    lx = row.get("lexicon_active_id")
    if isinstance(lx, str) and lx.strip():
        parts.append(f"lexicon_active_id: {lx.strip()}")
    um = row.get("user_message", "")
    parts.append(f"User:\n{um}")
    return "\n\n".join(parts)


def build_router_user_content(row: Dict[str, Any]) -> str:
    parts: List[str] = []
    snap = format_snapshot_blob(row.get("snapshot_features"))
    if snap.strip():
        parts.append(f"World snapshot:\n{snap.strip()}")
    stm = row.get("stm_snippet")
    if isinstance(stm, str) and stm.strip():
        parts.append(f"STM:\n{stm.strip()}")
    mr = row.get("manifest_revision")
    if isinstance(mr, str) and mr.strip():
        parts.append(f"manifest_revision: {mr.strip()}")
    lx = row.get("lexicon_active_id")
    if isinstance(lx, str) and lx.strip():
        parts.append(f"lexicon_active_id: {lx.strip()}")
    ds = row.get("data_source")
    if ds:
        parts.append(f"data_source: {ds}")
    um = row.get("user_message", "")
    parts.append(f"User:\n{um}")
    return "\n\n".join(parts)


def load_slot_training_rows(path: Path, *, validator: jsonschema.Draft202012Validator) -> List[Dict[str, Any]]:
    rows = load_jsonl(path)
    out: List[Dict[str, Any]] = []
    for i, row in enumerate(rows):
        labels = row.get("slot_labels")
        if not isinstance(labels, dict):
            raise ValueError(f"line {i}: slot_labels must be an object")
        try:
            validator.validate(labels)
        except jsonschema.ValidationError as e:
            raise ValueError(f"line {i}: slot_labels schema: {e.message}") from e
        out.append(row)
    return out


def load_router_training_rows(path: Path, *, validator: jsonschema.Draft202012Validator) -> List[Dict[str, Any]]:
    rows = load_jsonl(path)
    out: List[Dict[str, Any]] = []
    for i, row in enumerate(rows):
        try:
            validator.validate(row)
        except jsonschema.ValidationError as e:
            raise ValueError(f"line {i}: {e.message}") from e
        out.append(row)
    return out
