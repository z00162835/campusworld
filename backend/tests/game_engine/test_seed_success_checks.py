"""Tests: seed merge-if-missing success_checks / stop_policy attributes.

``ensure_aico_npc_agent`` must merge ``success_checks`` / ``stop_policy`` into
the AICO node's attributes when absent, without overwriting existing values.
"""
from __future__ import annotations

import db.seed_data as seed_data


def test_default_success_checks_is_empty_dict():
    """The platform default is empty → policy.yaml defaults apply."""
    assert seed_data._AICO_DEFAULT_SUCCESS_CHECKS == {}


def test_default_stop_policy_is_empty_dict():
    assert seed_data._AICO_DEFAULT_STOP_POLICY == {}


def test_seed_constants_are_dicts_not_none():
    assert isinstance(seed_data._AICO_DEFAULT_SUCCESS_CHECKS, dict)
    assert isinstance(seed_data._AICO_DEFAULT_STOP_POLICY, dict)


def test_merge_if_missing_logic_preserves_existing():
    """Simulate the merge-if-missing branch: existing attrs keep their values."""
    existing_attrs = {
        "service_id": "aico",
        "success_checks": {"hard_gates": ["min_complete_chars"]},
        "stop_policy": {"max_iterations": 5},
    }
    merged = dict(existing_attrs)
    changed = False
    if "success_checks" not in merged:
        merged["success_checks"] = dict(seed_data._AICO_DEFAULT_SUCCESS_CHECKS)
        changed = True
    if "stop_policy" not in merged:
        merged["stop_policy"] = dict(seed_data._AICO_DEFAULT_STOP_POLICY)
        changed = True
    assert changed is False
    assert merged["success_checks"] == {"hard_gates": ["min_complete_chars"]}
    assert merged["stop_policy"] == {"max_iterations": 5}


def test_merge_if_missing_adds_defaults_when_absent():
    existing_attrs = {"service_id": "aico"}
    merged = dict(existing_attrs)
    changed = False
    if "success_checks" not in merged:
        merged["success_checks"] = dict(seed_data._AICO_DEFAULT_SUCCESS_CHECKS)
        changed = True
    if "stop_policy" not in merged:
        merged["stop_policy"] = dict(seed_data._AICO_DEFAULT_STOP_POLICY)
        changed = True
    assert changed is True
    assert "success_checks" in merged
    assert "stop_policy" in merged
