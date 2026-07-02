"""AICO phase_llm default upgrade idempotency.

The seed default moved Check from ``skip`` to ``fast`` (Thin PDCA with a
Check gate). Existing agents still carrying the pre-Check-gate default
(check=skip) must be upgraded idempotently; agents already on the current
default must not be re-upgraded.
"""

from __future__ import annotations

import pytest

from db.seed_data import (
    _AICO_DEFAULT_PHASE_LLM,
    _AICO_PRE_ACT_STREAMING_PHASE_LLM,
    _aico_phase_llm_should_upgrade_to_current_default,
)


@pytest.mark.unit
def test_current_default_has_check_fast():
    assert _AICO_DEFAULT_PHASE_LLM["check"]["mode"] == "fast"
    assert _AICO_DEFAULT_PHASE_LLM["do"]["mode"] == "skip"
    assert _AICO_DEFAULT_PHASE_LLM["act"]["mode"] == "skip"


@pytest.mark.unit
def test_old_check_skip_default_upgrades_to_current():
    """The pre-Check-gate default (check=skip) is a known legacy template and
    triggers an idempotent upgrade to the current default (check=fast)."""
    assert _aico_phase_llm_should_upgrade_to_current_default(_AICO_PRE_ACT_STREAMING_PHASE_LLM) is True


@pytest.mark.unit
def test_current_default_is_not_re_upgraded():
    """An agent already on the current default must not be flagged for upgrade."""
    assert _aico_phase_llm_should_upgrade_to_current_default(_AICO_DEFAULT_PHASE_LLM) is False
