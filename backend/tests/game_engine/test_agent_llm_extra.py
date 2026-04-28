"""Tests for agent_llm_extra helpers."""

from __future__ import annotations

import pytest

from app.game_engine.agent_runtime.agent_llm_extra import parse_bool_extra


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw,expected",
    [
        (True, True),
        (False, False),
        ("true", True),
        ("FALSE", False),
        ("1", True),
        ("0", False),
        ("yes", True),
        ("off", False),
    ],
)
def test_parse_bool_extra_explicit(raw, expected):
    assert parse_bool_extra({"prepend_primer_tier1": raw}, "prepend_primer_tier1", default=True) is expected


@pytest.mark.unit
def test_parse_bool_extra_missing_uses_default():
    assert parse_bool_extra({}, "prepend_primer_tier1", default=True) is True
    assert parse_bool_extra({}, "prepend_primer_tier1", default=False) is False
    assert parse_bool_extra(None, "prepend_primer_tier1", default=False) is False
