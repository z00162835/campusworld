"""AICO skill_refs default backfill idempotency for upgraded installations."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from db.seed_data import _AICO_DEFAULT_SKILL_REFS, ensure_aico_npc_agent


def _existing_aico_node(*, attrs: dict) -> MagicMock:
    node = MagicMock()
    node.attributes = dict(attrs)
    return node


def _session_with_existing(node: MagicMock) -> MagicMock:
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = node
    return session


@pytest.mark.unit
def test_existing_aico_backfills_skill_refs_when_missing():
    node = _existing_aico_node(attrs={
        "service_id": "aico",
        "mode_models": {"fast": "gpt-4o-mini"},
        "phase_llm": {"plan": {"mode": "fast"}, "do": {"mode": "skip"}, "check": {"mode": "fast"}, "act": {"mode": "skip"}},
    })
    session = _session_with_existing(node)

    ensure_aico_npc_agent(session)

    assert node.attributes["skill_refs"] == list(_AICO_DEFAULT_SKILL_REFS)
    session.commit.assert_called_once()


@pytest.mark.unit
def test_existing_aico_preserves_custom_skill_refs():
    custom = ["custom_skill"]
    node = _existing_aico_node(attrs={
        "service_id": "aico",
        "skill_refs": custom,
        "mode_models": {"fast": "gpt-4o-mini"},
        "phase_llm": {"plan": {"mode": "fast"}, "do": {"mode": "skip"}, "check": {"mode": "fast"}, "act": {"mode": "skip"}},
    })
    session = _session_with_existing(node)

    ensure_aico_npc_agent(session)

    assert node.attributes["skill_refs"] == custom
    session.commit.assert_not_called()


@pytest.mark.unit
def test_existing_aico_skill_refs_backfill_is_idempotent():
    node = _existing_aico_node(attrs={
        "service_id": "aico",
        "mode_models": {"fast": "gpt-4o-mini"},
        "phase_llm": {"plan": {"mode": "fast"}, "do": {"mode": "skip"}, "check": {"mode": "fast"}, "act": {"mode": "skip"}},
    })
    session = _session_with_existing(node)

    ensure_aico_npc_agent(session)
    first_refs = list(node.attributes["skill_refs"])
    session.reset_mock()

    ensure_aico_npc_agent(session)

    assert node.attributes["skill_refs"] == first_refs
    session.commit.assert_not_called()
