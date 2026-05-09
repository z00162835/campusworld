"""Offline metrics for router-head labels (subset exact, mandatory recall, macro-F1 per tool).

Reads gold JSONL (``tool_router_train_row.schema.json``) and prediction JSONL with the same
``example_id`` or aligned line order. Does not import torch.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple

from app.models.agent_model.tool_router.train.train_common import ROUTER_TRAIN_SCHEMA_PATH


def normalize_tool_names(names: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for raw in names:
        k = (raw or "").strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out


def subset_exact_match(pred: Set[str], gold: Set[str]) -> bool:
    return pred == gold


def mandatory_recall_satisfied(pred: Set[str], mandatory: Set[str]) -> bool:
    if not mandatory:
        return True
    return mandatory <= pred


def _per_label_counts(
    pairs: Sequence[Tuple[Set[str], Set[str]]],
) -> Tuple[MutableMapping[str, int], MutableMapping[str, int], MutableMapping[str, int]]:
    tp: Dict[str, int] = {}
    fp: Dict[str, int] = {}
    fn: Dict[str, int] = {}
    for pred, gold in pairs:
        labels = pred | gold
        for t in labels:
            pin = t in pred
            gin = t in gold
            if pin and gin:
                tp[t] = tp.get(t, 0) + 1
            elif pin and not gin:
                fp[t] = fp.get(t, 0) + 1
            elif not pin and gin:
                fn[t] = fn.get(t, 0) + 1
    return tp, fp, fn


def macro_f1_multilabel(pairs: Sequence[Tuple[Set[str], Set[str]]]) -> float:
    """Macro-averaged F1 over tools that appear as labels in any pair."""
    tp, fp, fn = _per_label_counts(pairs)
    labels = set(tp) | set(fp) | set(fn)
    if not labels:
        return 1.0
    f1s: List[float] = []
    for t in sorted(labels):
        t_tp = tp.get(t, 0)
        t_fp = fp.get(t, 0)
        t_fn = fn.get(t, 0)
        prec = t_tp / (t_tp + t_fp) if (t_tp + t_fp) else 0.0
        rec = t_tp / (t_tp + t_fn) if (t_tp + t_fn) else 0.0
        if prec + rec == 0:
            f1s.append(0.0)
        else:
            f1s.append(2 * prec * rec / (prec + rec))
    return sum(f1s) / len(f1s)


@dataclass
class GoldRow:
    example_id: Optional[str]
    gold_tool_names: List[str]
    mandatory_subset: List[str]
    data_source: str


@dataclass
class PredRow:
    example_id: Optional[str]
    predicted_tool_names: List[str]


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def parse_gold_rows(raw: Iterable[Mapping[str, Any]]) -> List[GoldRow]:
    out: List[GoldRow] = []
    for i, obj in enumerate(raw):
        eid = obj.get("example_id")
        if eid is not None and not isinstance(eid, str):
            raise ValueError(f"gold row {i}: example_id must be string or omitted")
        gtn = obj.get("gold_tool_names")
        if not isinstance(gtn, list):
            raise ValueError(f"gold row {i}: gold_tool_names must be a list")
        ms = obj.get("mandatory_subset", [])
        if ms is None:
            ms = []
        if not isinstance(ms, list):
            raise ValueError(f"gold row {i}: mandatory_subset must be a list")
        ds = obj.get("data_source", "")
        if not isinstance(ds, str):
            raise ValueError(f"gold row {i}: data_source must be string")
        out.append(
            GoldRow(
                example_id=eid if isinstance(eid, str) and eid.strip() else None,
                gold_tool_names=[str(x) for x in gtn],
                mandatory_subset=[str(x) for x in ms],
                data_source=ds,
            )
        )
    return out


def parse_pred_rows(raw: Iterable[Mapping[str, Any]]) -> List[PredRow]:
    out: List[PredRow] = []
    for i, obj in enumerate(raw):
        eid = obj.get("example_id")
        if eid is not None and not isinstance(eid, str):
            raise ValueError(f"pred row {i}: example_id must be string or omitted")
        ptn = obj.get("predicted_tool_names")
        if ptn is None:
            ptn = obj.get("tool_names")
        if not isinstance(ptn, list):
            raise ValueError(f"pred row {i}: predicted_tool_names or tool_names must be a list")
        out.append(
            PredRow(
                example_id=eid if isinstance(eid, str) and eid.strip() else None,
                predicted_tool_names=[str(x) for x in ptn],
            )
        )
    return out


def align_gold_pred(
    gold: Sequence[GoldRow], pred: Sequence[PredRow]
) -> List[Tuple[GoldRow, PredRow]]:
    """Match by example_id when present on both sides; else pair by index."""
    keyed_g: Dict[str, GoldRow] = {}
    keyed_p: Dict[str, PredRow] = {}
    for g in gold:
        if g.example_id:
            keyed_g[g.example_id] = g
    for p in pred:
        if p.example_id:
            keyed_p[p.example_id] = p

    common_keys = set(keyed_g) & set(keyed_p)
    if common_keys:
        missing_g = [k for k in keyed_p if k and k not in keyed_g]
        missing_p = [k for k in keyed_g if k and k not in keyed_p]
        if missing_g or missing_p:
            raise ValueError(f"example_id mismatch: missing gold {missing_p!r} missing pred {missing_g!r}")
        return [(keyed_g[k], keyed_p[k]) for k in sorted(common_keys)]

    if len(gold) != len(pred):
        raise ValueError(f"line-aligned eval requires equal counts: gold={len(gold)} pred={len(pred)}")
    return list(zip(gold, pred))


def evaluate_pairs(pairs: Sequence[Tuple[GoldRow, PredRow]]) -> Dict[str, Any]:
    subset_hits = 0
    mand_hits = 0
    mand_count = 0
    f1_pairs: List[Tuple[Set[str], Set[str]]] = []
    by_source: Dict[str, Dict[str, float]] = {}

    for g, p in pairs:
        gold_set = set(normalize_tool_names(g.gold_tool_names))
        pred_set = set(normalize_tool_names(p.predicted_tool_names))
        f1_pairs.append((pred_set, gold_set))
        if subset_exact_match(pred_set, gold_set):
            subset_hits += 1
        ms = set(normalize_tool_names(g.mandatory_subset))
        if ms:
            mand_count += 1
            if mandatory_recall_satisfied(pred_set, ms):
                mand_hits += 1
        src = g.data_source or "unknown"
        bucket = by_source.setdefault(src, {"n": 0, "subset_hits": 0, "mand_n": 0, "mand_hits": 0})
        bucket["n"] += 1
        if pred_set == gold_set:
            bucket["subset_hits"] += 1
        if ms:
            bucket["mand_n"] += 1
            if mandatory_recall_satisfied(pred_set, ms):
                bucket["mand_hits"] += 1

    n = len(pairs)
    macro_f1 = macro_f1_multilabel(f1_pairs)
    out: Dict[str, Any] = {
        "n_pairs": n,
        "subset_exact_match_rate": subset_hits / n if n else 0.0,
        "macro_f1": macro_f1,
        "mandatory_recall": mand_hits / mand_count if mand_count else None,
        "mandatory_evaluated_n": mand_count,
        "by_data_source": {
            k: {
                "n": int(v["n"]),
                "subset_exact_match_rate": v["subset_hits"] / v["n"] if v["n"] else 0.0,
                "mandatory_recall": v["mand_hits"] / v["mand_n"] if v["mand_n"] else None,
            }
            for k, v in sorted(by_source.items())
        },
    }
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Offline router-head metrics (gold vs pred JSONL)")
    p.add_argument("--gold-jsonl", type=Path, required=True)
    p.add_argument("--pred-jsonl", type=Path, required=True)
    p.add_argument(
        "--validate-gold",
        action="store_true",
        help="Validate each gold line against tool_router_train_row.schema.json",
    )
    args = p.parse_args()

    gold_raw = _load_jsonl(args.gold_jsonl)
    pred_raw = _load_jsonl(args.pred_jsonl)

    if args.validate_gold:
        import jsonschema

        schema = json.loads(ROUTER_TRAIN_SCHEMA_PATH.read_text(encoding="utf-8"))
        for i, row in enumerate(gold_raw):
            try:
                jsonschema.validate(instance=row, schema=schema)
            except jsonschema.ValidationError as e:
                raise SystemExit(f"gold line {i}: {e.message}") from e

    gold_rows = parse_gold_rows(gold_raw)
    pred_rows = parse_pred_rows(pred_raw)
    pairs = align_gold_pred(gold_rows, pred_rows)
    report = evaluate_pairs(pairs)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
