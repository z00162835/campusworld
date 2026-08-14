"""Tests for policy configuration coercion."""
from __future__ import annotations

from app.game_engine.agent_runtime.policy.config import load_policy_config


def test_invalid_true_default_bool_string_keeps_default(tmp_path):
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
gate:
  enable_side_effect_detector: treu
  enable_data_classification_detector: nope
quality:
  enable_quality_score: maybe
  enable_stop_dimensions: "??"
""",
        encoding="utf-8",
    )

    config = load_policy_config(policy_path)

    assert config.gate.enable_side_effect_detector is True
    assert config.gate.enable_data_classification_detector is True
    assert config.quality.enable_quality_score is False
    assert config.quality.enable_stop_dimensions is False


def test_explicit_false_bool_string_still_disables(tmp_path):
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
gate:
  enable_side_effect_detector: "false"
quality:
  enable_stop_dimensions: "off"
""",
        encoding="utf-8",
    )

    config = load_policy_config(policy_path)

    assert config.gate.enable_side_effect_detector is False
    assert config.quality.enable_stop_dimensions is False
