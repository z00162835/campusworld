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


def test_s2_s3_hard_gate_config_defaults_and_coercion(tmp_path):
    """S2/S3 hard_gate config fields default-off with valid coercion."""
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
quality:
  enable_obs_grounded_claims_gate: true
  obs_grounded_gte: "0.30"
  enable_success_criteria_gate: yes
""",
        encoding="utf-8",
    )
    config = load_policy_config(policy_path)
    assert config.quality.enable_obs_grounded_claims_gate is True
    assert config.quality.obs_grounded_gte == 0.30
    assert config.quality.enable_success_criteria_gate is True


def test_s2_s3_hard_gate_config_invalid_keeps_defaults(tmp_path):
    """Invalid values for S2/S3 fields keep defaults (off / 0.15 / off)."""
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
quality:
  enable_obs_grounded_claims_gate: maybe
  obs_grounded_gte: "not-a-number"
  enable_success_criteria_gate: ???
""",
        encoding="utf-8",
    )
    config = load_policy_config(policy_path)
    assert config.quality.enable_obs_grounded_claims_gate is False
    assert config.quality.obs_grounded_gte == 0.15
    assert config.quality.enable_success_criteria_gate is False
    assert config.quality.react_turn_min_criteria_hits == 1


def test_react_turn_min_criteria_hits_config_coercion(tmp_path):
    """D6: react_turn_min_criteria_hits coerces valid int, keeps default 1 on invalid."""
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
quality:
  react_turn_min_criteria_hits: "3"
""",
        encoding="utf-8",
    )
    config = load_policy_config(policy_path)
    assert config.quality.react_turn_min_criteria_hits == 3

    # Invalid value keeps default 1.
    policy_path.write_text(
        """
quality:
  react_turn_min_criteria_hits: "not-a-number"
""",
        encoding="utf-8",
    )
    config = load_policy_config(policy_path)
    assert config.quality.react_turn_min_criteria_hits == 1


# ---------------------------------------------------------------------------
# T9: config coercion for newly-wired keys (H2/H3/H4/H6/H7/H8)
# ---------------------------------------------------------------------------

def test_blocked_skill_activation_modes_coercion(tmp_path):
    """H3: blocked_skill_activation_modes coerces list/str into tuple."""
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
skill:
  blocked_skill_activation_modes: ["manual", "Auto"]
""",
        encoding="utf-8",
    )
    config = load_policy_config(policy_path)
    assert config.skill.blocked_skill_activation_modes == ("manual", "auto")


def test_blocked_data_classifications_coercion(tmp_path):
    """H2: blocked_data_classifications coerces list into tuple."""
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
gate:
  blocked_data_classifications: [Confidential, restricted, internal]
""",
        encoding="utf-8",
    )
    config = load_policy_config(policy_path)
    assert config.gate.blocked_data_classifications == ("confidential", "restricted", "internal")


def test_tool_group_hierarchy_coercion(tmp_path):
    """H4: tool_group_hierarchy coerces dict[str, list] into normalized dict."""
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
gate:
  tool_group_hierarchy:
    read: [Observe, agent_meta]
    scan: [probe]
""",
        encoding="utf-8",
    )
    config = load_policy_config(policy_path)
    assert config.gate.tool_group_hierarchy == {
        "read": ("observe", "agent_meta"),
        "scan": ("probe",),
    }


def test_semantic_weights_coercion(tmp_path):
    """H6: semantic weight floats coerce from strings, keep defaults on invalid."""
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
quality:
  semantic_weight_grounding: "0.6"
  semantic_weight_criteria: 0.25
  semantic_weight_progress: "invalid"
""",
        encoding="utf-8",
    )
    config = load_policy_config(policy_path)
    assert config.quality.semantic_weight_grounding == 0.6
    assert config.quality.semantic_weight_criteria == 0.25
    assert config.quality.semantic_weight_progress == 0.2  # default on invalid


def test_stagnation_cycle_window_multiplier_coercion(tmp_path):
    """H7: stagnation_cycle_window_multiplier coerces int, keeps default on invalid."""
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
quality:
  stagnation_cycle_window_multiplier: "3"
""",
        encoding="utf-8",
    )
    config = load_policy_config(policy_path)
    assert config.quality.stagnation_cycle_window_multiplier == 3

    policy_path.write_text(
        """
quality:
  stagnation_cycle_window_multiplier: "not-a-number"
""",
        encoding="utf-8",
    )
    config = load_policy_config(policy_path)
    assert config.quality.stagnation_cycle_window_multiplier == 2


def test_token_min_length_coercion(tmp_path):
    """H8: token_min_length coerces int, keeps default on invalid."""
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """
quality:
  token_min_length: "4"
""",
        encoding="utf-8",
    )
    config = load_policy_config(policy_path)
    assert config.quality.token_min_length == 4

    policy_path.write_text(
        """
quality:
  token_min_length: "NaN"
""",
        encoding="utf-8",
    )
    config = load_policy_config(policy_path)
    assert config.quality.token_min_length == 2
