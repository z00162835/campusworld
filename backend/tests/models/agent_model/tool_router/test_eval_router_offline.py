"""Tests for offline router-head metrics (no torch)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys
from unittest.mock import patch

from app.models.agent_model.tool_router.train.eval_router_offline import (
    GoldRow,
    PredRow,
    align_gold_pred,
    evaluate_pairs,
    macro_f1_multilabel,
    normalize_tool_names,
)


@pytest.mark.unit
def test_normalize_tool_names_dedupes_casefold() -> None:
    assert normalize_tool_names(["Look", " look ", "n"]) == ["look", "n"]


@pytest.mark.unit
def test_macro_f1_perfect() -> None:
    pairs = [({"a", "b"}, {"a", "b"}), ({"a"}, {"a"})]
    assert macro_f1_multilabel(pairs) == pytest.approx(1.0)


@pytest.mark.unit
def test_macro_f1_partial() -> None:
    pairs = [({"a"}, {"a", "b"})]
    # label a: TP=1 FP=0 FN=0 -> F1=1; label b: TP=0 FP=0 FN=1 -> F1=0
    assert macro_f1_multilabel(pairs) == pytest.approx(0.5)


@pytest.mark.unit
def test_evaluate_pairs_subset_and_mandatory() -> None:
    gold = [
        GoldRow(None, ["look"], [], "synthetic"),
        GoldRow(None, ["go", "inventory"], ["go"], "human"),
    ]
    pred = [
        PredRow(None, ["look"]),
        PredRow(None, ["go"]),  # missing inventory; mandatory go satisfied
    ]
    r = evaluate_pairs(list(zip(gold, pred)))
    assert r["n_pairs"] == 2
    assert r["subset_exact_match_rate"] == pytest.approx(0.5)
    assert r["mandatory_evaluated_n"] == 1
    assert r["mandatory_recall"] == pytest.approx(1.0)


@pytest.mark.unit
def test_align_by_example_id() -> None:
    g = [GoldRow("x", ["a"], [], "synthetic"), GoldRow("y", ["b"], [], "synthetic")]
    p = [PredRow("y", ["b"]), PredRow("x", ["a"])]
    pairs = align_gold_pred(g, p)
    assert {(gl.example_id, tuple(pr.predicted_tool_names)) for gl, pr in pairs} == {
        ("x", ("a",)),
        ("y", ("b",)),
    }


@pytest.mark.unit
def test_pred_accepts_tool_names_alias(tmp_path: Path) -> None:
    gold = tmp_path / "g.jsonl"
    pred = tmp_path / "p.jsonl"
    gold.write_text(
        json.dumps(
            {
                "user_message": "hi",
                "gold_tool_names": ["look"],
                "mandatory_subset": [],
                "data_source": "synthetic",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    pred.write_text(json.dumps({"tool_names": ["look"]}) + "\n", encoding="utf-8")
    from app.models.agent_model.tool_router.train.eval_router_offline import (
        _load_jsonl,
        align_gold_pred,
        evaluate_pairs,
        parse_gold_rows,
        parse_pred_rows,
    )

    pairs = align_gold_pred(parse_gold_rows(_load_jsonl(gold)), parse_pred_rows(_load_jsonl(pred)))
    r = evaluate_pairs(pairs)
    assert r["subset_exact_match_rate"] == 1.0


@pytest.mark.unit
def test_cli_eval_tmp_files(tmp_path: Path) -> None:
    from app.models.agent_model.tool_router.train import eval_router_offline as ev

    gold = tmp_path / "g.jsonl"
    pred = tmp_path / "p.jsonl"
    gold.write_text(
        json.dumps(
            {
                "example_id": "1",
                "user_message": "hi",
                "gold_tool_names": ["look"],
                "mandatory_subset": [],
                "data_source": "synthetic",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    pred.write_text(
        json.dumps({"example_id": "1", "predicted_tool_names": ["look"]}) + "\n",
        encoding="utf-8",
    )
    import io
    from contextlib import redirect_stdout

    argv = [
        "eval_router_offline",
        "--gold-jsonl",
        str(gold),
        "--pred-jsonl",
        str(pred),
        "--validate-gold",
    ]
    buf = io.StringIO()
    with patch.object(sys, "argv", argv):
        with redirect_stdout(buf):
            code = ev.main()
    assert code == 0
    out = json.loads(buf.getvalue())
    assert out["subset_exact_match_rate"] == 1.0
    assert out["macro_f1"] == 1.0
