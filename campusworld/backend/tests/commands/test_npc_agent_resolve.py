"""Unit tests for F04 npc_agent_resolve."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.commands.npc_agent_resolve import normalize_handle, resolve_npc_agent_by_handle
from app.models.graph import Node


@pytest.mark.unit
def test_normalize_handle():
    assert normalize_handle("  AICO  ") == "aico"


@pytest.mark.unit
def test_resolve_empty_handle():
    session = MagicMock()
    node, err = resolve_npc_agent_by_handle(session, "   ")
    assert node is None and err == "invalid agent handle"


@pytest.mark.unit
def test_resolve_matches_service_id():
    agent = MagicMock()
    agent.id = 42
    agent.attributes = {"service_id": "mybot", "enabled": True}

    session = MagicMock()
    chain = session.query.return_value
    chain.filter.return_value = chain
    chain.all.return_value = [agent]

    out, err = resolve_npc_agent_by_handle(session, "mybot")
    assert err is None and out is agent
    session.query.assert_called_once_with(Node)


@pytest.mark.unit
def test_resolve_matches_handle_alias():
    agent = MagicMock()
    agent.id = 7
    agent.attributes = {"service_id": "internal", "handle_aliases": ["bot", "b"], "enabled": True}

    session = MagicMock()
    chain = session.query.return_value
    chain.filter.return_value = chain
    chain.all.return_value = [agent]

    out, err = resolve_npc_agent_by_handle(session, "bot")
    assert err is None and out is agent


@pytest.mark.unit
def test_resolve_ambiguous_service_id():
    a = MagicMock()
    a.id = 1
    a.attributes = {"service_id": "dup", "enabled": True}
    b = MagicMock()
    b.id = 2
    b.attributes = {"service_id": "dup", "enabled": True}

    session = MagicMock()
    chain = session.query.return_value
    chain.filter.return_value = chain
    chain.all.return_value = [a, b]

    _, err = resolve_npc_agent_by_handle(session, "dup")
    assert err and "ambiguous" in err.lower()


@pytest.mark.unit
def test_resolve_disabled():
    agent = MagicMock()
    agent.id = 1
    agent.attributes = {"service_id": "off", "enabled": False}

    session = MagicMock()
    chain = session.query.return_value
    chain.filter.return_value = chain
    chain.all.return_value = [agent]

    _, err = resolve_npc_agent_by_handle(session, "off")
    assert err and "disabled" in err.lower()


@pytest.mark.unit
def test_resolve_unknown():
    session = MagicMock()
    chain = session.query.return_value
    chain.filter.return_value = chain
    chain.all.return_value = []

    _, err = resolve_npc_agent_by_handle(session, "nope")
    assert err and "unknown" in err.lower() and "help" in err.lower()
