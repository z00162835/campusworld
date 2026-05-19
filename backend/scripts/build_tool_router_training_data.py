"""Build tool-router training shards from eval case datasets.

Generates:
- app/models/agent_model/tool_router/data/shards/router_{train,val,test}_part00.jsonl
- app/models/agent_model/tool_router/data/shards/slot_{train,val,test}_part00.jsonl
- app/models/agent_model/tool_router/data/registry.yaml

This script is deterministic and safe to re-run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import yaml

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.agent_model.tool_router.train.train_common import (
    ROUTER_TRAIN_SCHEMA_PATH,
    SLOT_OUTPUT_SCHEMA_PATH,
    load_router_training_rows,
    load_slot_training_rows,
    schema_validator,
)


TOOL_CANONICAL_ALIASES = {
    "agent_capabilities": "agent",
    "agents": "agent",
}

LONG_TAIL_TOOLS = {"agent", "primer", "look", "space", "help"}


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _dedupe_keep_order(values: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in values:
        name = str(raw or "").strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _canonical_tool_name(raw: str) -> str:
    name = str(raw or "").strip().lower()
    if not name:
        return ""
    return TOOL_CANONICAL_ALIASES.get(name, name)


def _normalize_tools(values: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in values:
        name = _canonical_tool_name(raw)
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _sanitize_mandatory_subset(expected_tools: Sequence[str], mandatory_tools: Sequence[str]) -> List[str]:
    expected = _normalize_tools(expected_tools)
    expected_set = set(expected)
    return [name for name in _normalize_tools(mandatory_tools) if name in expected_set]


def _split_bucket(*, key: str) -> str:
    """Deterministic 80/10/10 split by SHA1 nibble."""
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()
    v = int(h[:8], 16) % 10
    if v == 0:
        return "test"
    if v == 1:
        return "val"
    return "train"


def _stable_u32(text: str) -> int:
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _looks_zh(text: str) -> bool:
    return any(("\u4e00" <= ch <= "\u9fff" for ch in text or ""))


def _with_prefix(msg: str, *, zh: bool) -> str:
    core = (msg or "").strip()
    if not core:
        return core
    return f"请按步骤处理：{core}" if zh else f"Please handle this step-by-step: {core}"


def _with_suffix(msg: str, *, zh: bool) -> str:
    core = (msg or "").strip()
    if not core:
        return core
    return f"{core}，请严格按工具链执行。" if zh else f"{core} Please follow the required tool chain."


def _find_step_args(case: Dict[str, Any], tool_name: str) -> List[str]:
    seq = case.get("expected_tool_sequence") if isinstance(case.get("expected_tool_sequence"), list) else []
    for step in seq:
        if not isinstance(step, dict):
            continue
        if str(step.get("name") or "").strip().lower() != tool_name.strip().lower():
            continue
        args = step.get("args")
        if isinstance(args, list):
            return [str(x) for x in args]
    return []


def _infer_find_type_code(case: Dict[str, Any]) -> str:
    args = _find_step_args(case, "find")
    for i, token in enumerate(args):
        if token == "-t" and i + 1 < len(args):
            return str(args[i + 1]).strip()
    return ""


def _infer_type_query_term(case: Dict[str, Any]) -> str:
    args = _find_step_args(case, "type")
    for token in args:
        t = str(token).strip()
        if t and t != "-a" and t != "--all":
            return t
    return ""


def _contains_command_name(message: str, tool_name: str) -> bool:
    msg = (message or "").strip()
    if not msg:
        return False
    name = (tool_name or "").strip()
    if not name:
        return False
    if name.isascii() and name.replace("_", "").isalnum():
        # Lowercase token-aware match for Latin command names.
        msg_l = msg.lower()
        name_l = name.lower()
        padded = f" {msg_l} "
        return f" {name_l} " in padded or f"`{name_l}`" in msg_l
    return name in msg


def _slot_named_spans(message: str, expected_tools: Sequence[str]) -> List[Dict[str, str]]:
    spans: List[Dict[str, str]] = []
    for tool in _normalize_tools(expected_tools):
        if _contains_command_name(message, tool):
            spans.append({"text": tool, "type": "command_ref"})
    return spans


def _slot_entities(message: str) -> List[Dict[str, str]]:
    text = message or ""
    out: List[Dict[str, str]] = []
    for token in ("AICO", "hicampus", "HiCampus"):
        if token in text:
            out.append({"normalized_text": token, "entity_type": "organization"})
    if "#" in text:
        # Keep extraction simple and schema-safe.
        for part in text.split():
            if part.startswith("#") and part[1:].isdigit():
                out.append({"normalized_text": part, "entity_type": "other"})
                break
    # De-duplicate while preserving order.
    seen = set()
    deduped: List[Dict[str, str]] = []
    for row in out:
        k = (row["normalized_text"], row["entity_type"])
        if k in seen:
            continue
        seen.add(k)
        deduped.append(row)
    return deduped


def _router_row(*, suite: str, case: Dict[str, Any]) -> Dict[str, Any]:
    metadata = case.get("metadata") if isinstance(case.get("metadata"), dict) else {}
    example_id = str(case.get("example_id") or "").strip()
    user_message = str(case.get("user_message") or "").strip()
    snapshot_features: Dict[str, Any] = {
        "suite": suite,
        "context_snapshot": str(case.get("context_snapshot") or ""),
        "intent": str(metadata.get("intent") or ""),
        "language": str(case.get("language") or ""),
        "tags": [str(x) for x in (case.get("tags") or [])],
    }
    row: Dict[str, Any] = {
        "example_id": f"{suite}::{example_id}",
        "user_message": user_message,
        "snapshot_features": snapshot_features,
        "stm_snippet": case.get("stm_snippet"),
        "manifest_revision": str(metadata.get("dataset_version") or "") or None,
        "lexicon_active_id": None,
        "gold_tool_names": _dedupe_keep_order([str(x) for x in (case.get("expected_tools") or [])]),
        "mandatory_subset": _sanitize_mandatory_subset(
            [str(x) for x in (case.get("expected_tools") or [])],
            [str(x) for x in (case.get("mandatory_tools") or [])],
        ),
        "data_source": str(case.get("data_source") or "synthetic"),
    }
    return row


def _router_row_from_labels(
    *,
    suite: str,
    case: Dict[str, Any],
    user_message: str,
    expected_tools: Sequence[str],
    mandatory_tools: Sequence[str],
    variant_tag: str,
    data_source: str,
) -> Dict[str, Any]:
    metadata = case.get("metadata") if isinstance(case.get("metadata"), dict) else {}
    base_example_id = str(case.get("example_id") or "").strip()
    example_id = f"{suite}::{base_example_id}::{variant_tag}"
    snapshot_features: Dict[str, Any] = {
        "suite": suite,
        "source_suite": suite,
        "parent_example_id": base_example_id,
        "variant_tag": variant_tag,
        "context_snapshot": str(case.get("context_snapshot") or ""),
        "intent": str(metadata.get("intent") or ""),
        "language": str(case.get("language") or ""),
        "tags": [str(x) for x in (case.get("tags") or [])],
    }
    expected_norm = _normalize_tools(expected_tools)
    mandatory_norm = _sanitize_mandatory_subset(expected_norm, mandatory_tools)
    return {
        "example_id": example_id[:128],
        "user_message": str(user_message or "").strip(),
        "snapshot_features": snapshot_features,
        "stm_snippet": case.get("stm_snippet"),
        "manifest_revision": str(metadata.get("dataset_version") or "") or None,
        "lexicon_active_id": None,
        "gold_tool_names": expected_norm,
        "mandatory_subset": mandatory_norm,
        "data_source": data_source,
    }


def _slot_row(*, suite: str, case: Dict[str, Any]) -> Dict[str, Any]:
    metadata = case.get("metadata") if isinstance(case.get("metadata"), dict) else {}
    expected_tools = _normalize_tools([str(x) for x in (case.get("expected_tools") or [])])
    mandatory = _sanitize_mandatory_subset(
        [str(x) for x in (case.get("expected_tools") or [])],
        [str(x) for x in (case.get("mandatory_tools") or [])],
    )
    user_message = str(case.get("user_message") or "").strip()
    if expected_tools:
        if len(expected_tools) == 1:
            target_hint = expected_tools[0]
        else:
            target_hint = " -> ".join(expected_tools[:4])
    else:
        target_hint = None
    row: Dict[str, Any] = {
        "example_id": f"{suite}::{str(case.get('example_id') or '').strip()}",
        "suite": suite,
        "user_message": user_message,
        "snapshot_features": {
            "context_snapshot": str(case.get("context_snapshot") or ""),
            "intent": str(metadata.get("intent") or ""),
            "language": str(case.get("language") or ""),
            "tags": [str(x) for x in (case.get("tags") or [])],
        },
        "stm_snippet": case.get("stm_snippet"),
        "manifest_revision": str(metadata.get("dataset_version") or "") or None,
        "lexicon_active_id": None,
        "slot_labels": {
            "target_hint": target_hint,
            "named_spans": _slot_named_spans(user_message, expected_tools),
            "entities": _slot_entities(user_message),
            "mandatory_tools": mandatory,
        },
    }
    return row


def _slot_row_from_labels(
    *,
    suite: str,
    case: Dict[str, Any],
    user_message: str,
    expected_tools: Sequence[str],
    mandatory_tools: Sequence[str],
    variant_tag: str,
) -> Dict[str, Any]:
    metadata = case.get("metadata") if isinstance(case.get("metadata"), dict) else {}
    expected_norm = _normalize_tools([str(x) for x in expected_tools])
    mandatory_norm = _sanitize_mandatory_subset(expected_norm, mandatory_tools)
    if expected_norm:
        target_hint = expected_norm[0] if len(expected_norm) == 1 else " -> ".join(expected_norm[:4])
    else:
        target_hint = None
    base_example_id = str(case.get("example_id") or "").strip()
    example_id = f"{suite}::{base_example_id}::{variant_tag}"
    return {
        "example_id": example_id[:128],
        "suite": suite,
        "user_message": str(user_message or "").strip(),
        "snapshot_features": {
            "suite": suite,
            "source_suite": suite,
            "parent_example_id": base_example_id,
            "variant_tag": variant_tag,
            "context_snapshot": str(case.get("context_snapshot") or ""),
            "intent": str(metadata.get("intent") or ""),
            "language": str(case.get("language") or ""),
            "tags": [str(x) for x in (case.get("tags") or [])],
        },
        "stm_snippet": case.get("stm_snippet"),
        "manifest_revision": str(metadata.get("dataset_version") or "") or None,
        "lexicon_active_id": None,
        "slot_labels": {
            "target_hint": target_hint,
            "named_spans": _slot_named_spans(str(user_message or ""), expected_norm),
            "entities": _slot_entities(str(user_message or "")),
            "mandatory_tools": mandatory_norm,
        },
    }


def _positive_variants(case: Dict[str, Any]) -> List[Tuple[str, List[str], List[str], str, str]]:
    """Return (msg, expected, mandatory, variant_tag, data_source)."""
    base_msg = str(case.get("user_message") or "").strip()
    expected = _normalize_tools([str(x) for x in (case.get("expected_tools") or [])])
    mandatory = _sanitize_mandatory_subset(
        [str(x) for x in (case.get("expected_tools") or [])],
        [str(x) for x in (case.get("mandatory_tools") or [])],
    )
    zh = _looks_zh(base_msg) or str(case.get("language") or "").strip().lower().startswith("zh")
    rows: List[Tuple[str, List[str], List[str], str, str]] = []
    rows.append((base_msg, expected, mandatory, "base", str(case.get("data_source") or "synthetic")))

    # Keep one lightweight paraphrase by deterministic hash to reduce llm_generated skew.
    pref = _with_prefix(base_msg, zh=zh)
    suff = _with_suffix(base_msg, zh=zh)
    pick_prefix = (_stable_u32(str(case.get("example_id") or base_msg)) % 2) == 0
    if pick_prefix:
        if pref and pref != base_msg:
            rows.append((pref, expected, mandatory, "paraphrase_prefix", "llm_generated"))
    else:
        if suff and suff != base_msg:
            rows.append((suff, expected, mandatory, "paraphrase_suffix", "llm_generated"))

    # Add deterministic synthetic templates for long-tail tool families.
    exp_set = set(expected)
    if exp_set & LONG_TAIL_TOOLS:
        if zh:
            msg = f"请严格使用工具链处理：{base_msg}"
        else:
            msg = f"Use the required tool chain for this request: {base_msg}"
        rows.append((msg, expected, mandatory, "template_longtail_toolchain", "synthetic"))

        if len(expected) == 1:
            t0 = expected[0]
            if zh:
                msg_single = f"请调用 `{t0}` 处理这个请求：{base_msg}"
            else:
                msg_single = f"Please call `{t0}` for this request: {base_msg}"
            rows.append((msg_single, expected, mandatory, "template_longtail_single_tool", "synthetic"))
    return rows


def _hard_negative_variants(case: Dict[str, Any]) -> List[Tuple[str, List[str], List[str], str, str]]:
    """Near-miss negatives for route disambiguation."""
    expected = _normalize_tools([str(x) for x in (case.get("expected_tools") or [])])
    zh = _looks_zh(str(case.get("user_message") or "")) or str(case.get("language") or "").strip().lower().startswith("zh")
    out: List[Tuple[str, List[str], List[str], str, str]] = []
    expected_set = set(expected)
    type_code = _infer_find_type_code(case) or "furniture"
    type_term = _infer_type_query_term(case) or ("家具" if zh else "furniture")

    if {"type", "find"} <= expected_set:
        msg = (
            f"直接用 find -t {type_code} 查询，不需要先解析“{type_term}”类型。"
            if zh
            else f"Use find -t {type_code} directly; no type lookup needed for {type_term}."
        )
        out.append((msg, ["find"], ["find"], "hardneg_find_only_with_typecode", "llm_generated"))

    if {"find", "describe"} <= expected_set:
        msg = "直接描述 #42 节点，不需要先查找。" if zh else "Describe node #42 directly; skip the find step."
        out.append((msg, ["describe"], ["describe"], "hardneg_describe_direct_id", "llm_generated"))

    if {"find", "space"} <= expected_set:
        msg = "直接查看 #35 的空间汇总，不需要先 find building。" if zh else "Show space rollup for #35 directly; no prior find step needed."
        out.append((msg, ["space"], ["space"], "hardneg_space_direct_id", "llm_generated"))

    if expected == ["primer"]:
        msg = "用一句话解释一般意义上的 ontology 概念，不引用 CampusWorld 文档。" if zh else "Give a one-line general definition of ontology, not CampusWorld-specific docs."
        out.append((msg, [], [], "hardneg_general_ontology_no_tool", "llm_generated"))

    return out


def _write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def _is_priority_llm_row(row: Dict[str, Any]) -> bool:
    snapshot = row.get("snapshot_features") if isinstance(row.get("snapshot_features"), dict) else {}
    variant_tag = str(snapshot.get("variant_tag") or "")
    if variant_tag.startswith("hardneg_"):
        return True
    tools = set(_normalize_tools([str(x) for x in (row.get("gold_tool_names") or [])]))
    return bool(tools & LONG_TAIL_TOOLS)


def _rebalance_by_data_source(
    router_rows_by_bucket: Dict[str, List[Dict[str, Any]]],
    slot_rows_by_bucket: Dict[str, List[Dict[str, Any]]],
    *,
    target_llm_ratio: float = 1.2,
) -> None:
    paired: List[Tuple[str, int, Dict[str, Any], Dict[str, Any]]] = []
    for bucket in ("train", "val", "test"):
        rr = router_rows_by_bucket[bucket]
        sr = slot_rows_by_bucket[bucket]
        if len(rr) != len(sr):
            raise ValueError(f"router/slot row count mismatch in bucket={bucket}: {len(rr)} vs {len(sr)}")
        for idx, (router_row, slot_row) in enumerate(zip(rr, sr)):
            paired.append((bucket, idx, router_row, slot_row))

    synthetic = [item for item in paired if str(item[2].get("data_source") or "") != "llm_generated"]
    llm_rows = [item for item in paired if str(item[2].get("data_source") or "") == "llm_generated"]
    max_llm = int(len(synthetic) * target_llm_ratio)
    if len(llm_rows) <= max_llm:
        return

    keep_llm: List[Tuple[str, int, Dict[str, Any], Dict[str, Any]]] = []
    rest_llm: List[Tuple[str, int, Dict[str, Any], Dict[str, Any]]] = []
    for item in llm_rows:
        if _is_priority_llm_row(item[2]):
            keep_llm.append(item)
        else:
            rest_llm.append(item)

    remaining = max(0, max_llm - len(keep_llm))
    rest_llm.sort(key=lambda x: _stable_u32(str(x[2].get("example_id") or "")))
    keep_llm.extend(rest_llm[:remaining])

    keep_ids = {str(item[2].get("example_id") or "") for item in synthetic + keep_llm}
    for bucket in ("train", "val", "test"):
        router_rows_by_bucket[bucket] = [
            row for row in router_rows_by_bucket[bucket] if str(row.get("example_id") or "") in keep_ids
        ]
        slot_rows_by_bucket[bucket] = [
            row for row in slot_rows_by_bucket[bucket] if str(row.get("example_id") or "") in keep_ids
        ]


def _build_registry(*, output_data_dir: Path) -> None:
    registry_path = output_data_dir / "registry.yaml"
    obj = {
        "version": "1",
        "datasets": {
            "slot_slm_v1": {
                "description": "Gold slot SLM rows (tool_router_slot_output.schema.json labels)",
                "train": ["shards/slot_train_part00.jsonl"],
                "val": ["shards/slot_val_part00.jsonl"],
                "test": ["shards/slot_test_part00.jsonl"],
            },
            "router_head_v1": {
                "description": "Multi-label tool routing supervision (tool_router_train_row.schema.json)",
                "train": ["shards/router_train_part00.jsonl"],
                "val": ["shards/router_val_part00.jsonl"],
                "test": ["shards/router_test_part00.jsonl"],
            },
        },
    }
    registry_path.write_text(
        yaml.safe_dump(obj, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build tool-router training datasets from eval cases.")
    parser.add_argument(
        "--backend-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Backend root path (default: inferred from script location).",
    )
    args = parser.parse_args()

    backend_root = args.backend_root.resolve()
    eval_data_dir = backend_root / "app" / "game_engine" / "agent_runtime" / "eval" / "data"
    output_data_dir = backend_root / "app" / "models" / "agent_model" / "tool_router" / "data"
    shards_dir = output_data_dir / "shards"

    suite_files = {
        "gate": eval_data_dir / "aico_initial_cases.jsonl",
        "smoke": eval_data_dir / "aico_smoke_cases.jsonl",
        "stress": eval_data_dir / "aico_stress_cases.jsonl",
    }
    missing = [str(p) for p in suite_files.values() if not p.exists()]
    if missing:
        raise SystemExit(f"Missing eval case files: {missing}")

    router_rows_by_bucket: Dict[str, List[Dict[str, Any]]] = {"train": [], "val": [], "test": []}
    slot_rows_by_bucket: Dict[str, List[Dict[str, Any]]] = {"train": [], "val": [], "test": []}
    global_seen = set()

    for suite, path in suite_files.items():
        for case in _read_jsonl(path):
            eid = str(case.get("example_id") or "").strip()
            if not eid:
                continue
            seen_keys = set()
            variants = _positive_variants(case) + _hard_negative_variants(case)
            for (msg, exp_tools, mand_tools, variant_tag, data_source) in variants:
                msg_norm = str(msg or "").strip()
                if not msg_norm:
                    continue
                dedupe_key = (
                    msg_norm.lower(),
                    tuple(_normalize_tools(exp_tools)),
                    tuple(_sanitize_mandatory_subset(exp_tools, mand_tools)),
                )
                if dedupe_key in global_seen:
                    continue
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                global_seen.add(dedupe_key)
                key = f"{dedupe_key[0]}::{','.join(dedupe_key[1])}::{','.join(dedupe_key[2])}"
                bucket = _split_bucket(key=key)
                router_rows_by_bucket[bucket].append(
                    _router_row_from_labels(
                        suite=suite,
                        case=case,
                        user_message=msg_norm,
                        expected_tools=exp_tools,
                        mandatory_tools=mand_tools,
                        variant_tag=variant_tag,
                        data_source=data_source,
                    )
                )
                slot_rows_by_bucket[bucket].append(
                    _slot_row_from_labels(
                        suite=suite,
                        case=case,
                        user_message=msg_norm,
                        expected_tools=exp_tools,
                        mandatory_tools=mand_tools,
                        variant_tag=variant_tag,
                    )
                )

    _rebalance_by_data_source(router_rows_by_bucket, slot_rows_by_bucket, target_llm_ratio=1.2)

    # Write shards.
    paths = {
        "router_train": shards_dir / "router_train_part00.jsonl",
        "router_val": shards_dir / "router_val_part00.jsonl",
        "router_test": shards_dir / "router_test_part00.jsonl",
        "slot_train": shards_dir / "slot_train_part00.jsonl",
        "slot_val": shards_dir / "slot_val_part00.jsonl",
        "slot_test": shards_dir / "slot_test_part00.jsonl",
    }
    _write_jsonl(paths["router_train"], router_rows_by_bucket["train"])
    _write_jsonl(paths["router_val"], router_rows_by_bucket["val"])
    _write_jsonl(paths["router_test"], router_rows_by_bucket["test"])
    _write_jsonl(paths["slot_train"], slot_rows_by_bucket["train"])
    _write_jsonl(paths["slot_val"], slot_rows_by_bucket["val"])
    _write_jsonl(paths["slot_test"], slot_rows_by_bucket["test"])

    _build_registry(output_data_dir=output_data_dir)

    # Schema validation pass to ensure training scripts can consume outputs.
    router_validator = schema_validator(ROUTER_TRAIN_SCHEMA_PATH)
    slot_validator = schema_validator(SLOT_OUTPUT_SCHEMA_PATH)
    for key in ("router_train", "router_val", "router_test"):
        load_router_training_rows(paths[key], validator=router_validator)
    for key in ("slot_train", "slot_val", "slot_test"):
        load_slot_training_rows(paths[key], validator=slot_validator)

    summary = {
        "router": {k: len(v) for k, v in router_rows_by_bucket.items()},
        "slot": {k: len(v) for k, v in slot_rows_by_bucket.items()},
        "output_dir": str(output_data_dir),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
