from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.agent_model.intent_classifier.train.dataset_builder import (
    build_chat_turns,
    build_classifier_payload,
    load_jsonl,
    split_samples,
    train_val_indices,
)
from app.models.agent_model.intent_classifier.train.train_intent_classifier import (
    load_training_defaults,
    merge_training_dict,
)


@pytest.mark.unit
def test_load_jsonl_seed_file_loads_expected_rows():
    backend_root = Path(__file__).resolve().parents[3]
    seed_path = backend_root / "app/models/agent_model/intent_classifier/data/seed/intent_seed_v1.jsonl"
    rows = load_jsonl(seed_path)
    assert len(rows) >= 10
    labels = {r.label for r in rows}
    assert labels == {"informational", "verify_state", "execute"}


@pytest.mark.unit
def test_split_samples_is_deterministic_and_partitions_indices():
    backend_root = Path(__file__).resolve().parents[3]
    seed_path = backend_root / "app/models/agent_model/intent_classifier/data/seed/intent_seed_v1.jsonl"
    rows = load_jsonl(seed_path)
    train_idx, val_idx = split_samples(rows, val_ratio=0.2, seed=123)
    assert sorted(train_idx + val_idx) == list(range(len(rows)))
    assert set(train_idx).isdisjoint(set(val_idx))


@pytest.mark.unit
def test_train_val_indices_handles_small_n():
    assert train_val_indices(1, val_ratio=0.3, seed=1) == ([0], [])
    train_idx, val_idx = train_val_indices(5, val_ratio=0.4, seed=7)
    assert len(train_idx) + len(val_idx) == 5
    assert len(val_idx) >= 1


@pytest.mark.unit
def test_build_chat_turns_produces_parseable_assistant_json():
    backend_root = Path(__file__).resolve().parents[3]
    prompt_path = backend_root / "app/models/agent_model/intent_classifier/prompts/intent_classifier_system_prompt.txt"
    system_prompt = prompt_path.read_text(encoding="utf-8")
    rows = load_jsonl(backend_root / "app/models/agent_model/intent_classifier/data/seed/intent_seed_v1.jsonl")
    turns = build_chat_turns(system_prompt, rows[0])
    assert turns[0]["role"] == "system"
    assert turns[1]["role"] == "user"
    assert turns[2]["role"] == "assistant"
    parsed = json.loads(turns[2]["content"])
    assert parsed["intent"] == rows[0].label
    assert "confidence" in parsed and "reason_tokens" in parsed


@pytest.mark.unit
def test_build_classifier_payload_conflict_case_lowers_confidence():
    from app.models.agent_model.intent_classifier.train.dataset_builder import IntentTrainSample

    plain = IntentTrainSample(text="x", label="execute", conflict_case=False)
    conflict = IntentTrainSample(text="x", label="execute", conflict_case=True)
    assert float(build_classifier_payload(conflict)["confidence"]) < float(build_classifier_payload(plain)["confidence"])


@pytest.mark.unit
def test_load_training_defaults_contains_expected_keys():
    cfg = dict(load_training_defaults())
    assert "base_model_id" in cfg
    assert "lora_r" in cfg


@pytest.mark.unit
def test_merge_training_dict_overrides_none_skipped():
    base = {"learning_rate": 1e-4, "seed": 1}
    merged = merge_training_dict(base, {"learning_rate": 2e-4, "seed": None})
    assert merged["learning_rate"] == 2e-4
    assert merged["seed"] == 1
