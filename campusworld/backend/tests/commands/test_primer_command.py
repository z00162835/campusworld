"""Tests for the `primer` system command and the underlying world context module.

Golden-snapshot tests live alongside this file; the "snapshots" are exact
substring assertions rather than binary files — the primer markdown is
human-reviewed and small enough that targeted assertions are less noisy
than a full-text diff.
"""

from __future__ import annotations

import pytest

from app.commands.base import CommandContext
from app.commands.system_primer_command import PrimerCommand
from app.game_engine.agent_runtime.aico_world_context import (
    PRIMER_SECTIONS,
    build_ontology_primer,
    primer_cache_clear,
    primer_toc,
)


@pytest.fixture(autouse=True)
def _clear_primer_cache():
    """Isolate tests from each other's primer loader cache."""
    primer_cache_clear()
    yield
    primer_cache_clear()


def _ctx(permissions=None) -> CommandContext:
    return CommandContext(
        user_id="u1",
        username="tester",
        session_id="s1",
        permissions=list(permissions or []),
        roles=[],
    )


@pytest.mark.unit
def test_primer_full_document_renders_without_maintainer_banner():
    text = build_ontology_primer()
    assert text.startswith("## 1. Identity\n")
    # Every section must be present in order.
    last = -1
    for _, title in PRIMER_SECTIONS:
        heading = f"## {title}\n"
        idx = text.find(heading)
        assert idx > last, f"section '{title}' missing or out of order"
        last = idx
    # Placeholders must have been substituted (defaults).
    assert "{AICO_SERVICE_ID}" not in text
    assert "{AICO_LOCATION}" not in text
    assert "{PRIMARY_WORLD_ROOT}" not in text


@pytest.mark.unit
def test_primer_raw_preserves_placeholders():
    raw = build_ontology_primer(raw=True)
    assert "{AICO_SERVICE_ID}" in raw
    assert "{AICO_LOCATION}" in raw


@pytest.mark.unit
def test_primer_identity_slice_substitutes_service_id():
    text = build_ontology_primer(section="identity", for_agent="helper-01")
    assert "`service_id = helper-01`" in text
    assert "## 1. Identity" not in text  # heading stripped; body only


@pytest.mark.unit
def test_primer_invariants_slice_mentions_three_rules():
    text = build_ontology_primer(section="invariants")
    assert "1." in text and "2." in text and "3." in text


@pytest.mark.unit
def test_primer_examples_slice_has_whoami_and_primer():
    text = build_ontology_primer(section="examples")
    assert '"whoami"' in text
    assert '"primer"' in text


@pytest.mark.unit
def test_primer_unknown_section_raises():
    with pytest.raises(ValueError):
        build_ontology_primer(section="does_not_exist")


@pytest.mark.unit
def test_primer_toc_lists_all_sections_in_order():
    toc = primer_toc()
    assert [k for k, _ in toc] == [k for k, _ in PRIMER_SECTIONS]


# ----------------- command-layer tests -----------------


@pytest.mark.unit
def test_primer_command_default_returns_full_document():
    res = PrimerCommand().execute(_ctx(), [])
    assert res.success
    assert "## 1. Identity" in res.message
    assert "## 9. Examples" in res.message


@pytest.mark.unit
def test_primer_command_section_argument():
    res = PrimerCommand().execute(_ctx(), ["ontology"])
    assert res.success
    # Ontology lists node type codes.
    assert "room" in res.message
    assert "npc_agent" in res.message


@pytest.mark.unit
def test_primer_command_toc_flag():
    res = PrimerCommand().execute(_ctx(), ["--toc"])
    assert res.success
    for key, _ in PRIMER_SECTIONS:
        assert key in res.message


@pytest.mark.unit
def test_primer_command_raw_requires_permission():
    res = PrimerCommand().execute(_ctx(), ["--raw"])
    assert not res.success
    assert "admin.doc.read" in (res.message or "")
    ok = PrimerCommand().execute(_ctx(permissions=["admin.doc.read"]), ["--raw"])
    assert ok.success
    assert "{AICO_SERVICE_ID}" in ok.message


@pytest.mark.unit
def test_primer_command_for_flag_requires_permission():
    res = PrimerCommand().execute(_ctx(), ["--for", "helper-01"])
    assert not res.success
    ok = PrimerCommand().execute(
        _ctx(permissions=["admin.agent.read"]), ["--for", "helper-01"]
    )
    assert ok.success
    assert "helper-01" in ok.message


@pytest.mark.unit
def test_primer_command_unknown_section_fails_gracefully():
    res = PrimerCommand().execute(_ctx(), ["bogus"])
    assert not res.success
    assert "unknown primer section" in (res.message or "")


@pytest.mark.unit
def test_primer_command_unknown_flag_fails():
    res = PrimerCommand().execute(_ctx(), ["--bogus"])
    assert not res.success
    assert "unknown flag" in (res.message or "")


@pytest.mark.unit
def test_primer_command_duplicate_section_fails():
    res = PrimerCommand().execute(_ctx(), ["identity", "ontology"])
    assert not res.success
