from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from app.game_engine.agent_runtime.intent_classifier_interface import ChainedIntentClassifier, RuleFallbackIntentClassifier
from app.game_engine.agent_runtime.intent_classifier_runtime import (
    backend_root,
    build_intent_classifier_for_tick,
    merge_intent_classifier_settings,
    resolve_intent_classifier_runtime,
)


@pytest.mark.unit
def test_merge_intent_classifier_settings_node_overrides_extra():
    extra = {"use_intent_slm": False, "artifact_dir": "from_yaml"}
    node = {"intent_classifier": {"use_intent_slm": True, "max_new_tokens": 64}}
    merged = merge_intent_classifier_settings(extra, node)
    assert merged["use_intent_slm"] is True
    assert merged["artifact_dir"] == "from_yaml"
    assert merged["max_new_tokens"] == 64


@pytest.mark.unit
def test_resolve_clamps_max_new_tokens():
    cfg = resolve_intent_classifier_runtime({"use_intent_slm": False, "max_new_tokens": 9000}, {})
    assert cfg.max_new_tokens == 256


@pytest.mark.unit
def test_resolve_system_prompt_denied_outside_allowlist(tmp_path):
    backend = tmp_path / "backend"
    allowed = backend / "app/models/agent_model/intent_classifier/artifacts"
    allowed.mkdir(parents=True)
    evil = tmp_path / "evil_secret"
    evil.mkdir()
    secret = evil / "prompt.txt"
    secret.write_text("SECRET_PROMPT_BODY_XYZ", encoding="utf-8")
    cfg = resolve_intent_classifier_runtime(
        {
            "use_intent_slm": False,
            "system_prompt_file": str(secret),
            "intent_classifier_allowed_path_prefixes": [str(allowed)],
        },
        {},
        backend=backend,
    )
    assert "SECRET_PROMPT_BODY_XYZ" not in cfg.system_prompt_text
    assert "intent classifier" in cfg.system_prompt_text.lower()


@pytest.mark.unit
def test_resolve_denies_path_outside_allowlist(tmp_path):
    backend = tmp_path / "backend"
    allowed = backend / "app/models/agent_model/intent_classifier/artifacts"
    allowed.mkdir(parents=True)
    evil = tmp_path / "evil"
    evil.mkdir()
    cfg = resolve_intent_classifier_runtime(
        {
            "use_intent_slm": True,
            "artifact_dir": str(evil),
            "intent_classifier_allowed_path_prefixes": [str(allowed)],
        },
        {},
        backend=backend,
    )
    assert cfg.use_intent_slm is True
    assert cfg.artifact_root is None
    assert cfg.resolve_error == "artifact_dir_not_allowlisted"


@pytest.mark.unit
def test_resolve_accepts_layout_under_allowlist(tmp_path):
    backend = tmp_path / "backend"
    root = backend / "app/models/agent_model/intent_classifier/artifacts/run_ok"
    (root / "lora_adapter").mkdir(parents=True)
    (root / "training_config.json").write_text(json.dumps({"base_model_id": "dummy"}), encoding="utf-8")
    cfg = resolve_intent_classifier_runtime(
        {
            "use_intent_slm": True,
            "artifact_dir": "app/models/agent_model/intent_classifier/artifacts/run_ok",
        },
        {},
        backend=backend,
    )
    assert cfg.resolve_error is None
    assert cfg.artifact_root == root.resolve()


@pytest.mark.unit
def test_build_classifier_none_when_slm_off():
    cfg = resolve_intent_classifier_runtime({"use_intent_slm": False}, {})
    assert build_intent_classifier_for_tick(cfg) is None


@pytest.mark.unit
def test_chained_classifier_falls_back_on_primary_failure():
    class Boom:
        def classify_intent(self, user_message, *, agent_id=None, metadata=None):
            raise RuntimeError("boom")

    chain = ChainedIntentClassifier(primary=Boom(), fallback=RuleFallbackIntentClassifier())
    out = chain.classify_intent("给一个task例子")
    assert out.intent == "informational"
    assert out.source == "rule_fallback"


@pytest.mark.unit
def test_chained_classifier_logs_primary_failure(caplog):
    class Boom:
        def classify_intent(self, user_message, *, agent_id=None, metadata=None):
            raise RuntimeError("boom")

    caplog.set_level(logging.WARNING, logger="app.games")
    chain = ChainedIntentClassifier(primary=Boom(), fallback=RuleFallbackIntentClassifier())
    chain.classify_intent("hello")
    assert any("intent_classifier_primary_failed" in r.getMessage() for r in caplog.records)


@pytest.mark.unit
def test_backend_root_points_at_backend_folder():
    br = backend_root()
    assert br.name == "backend"
    assert (br / "campusworld.py").is_file()
