"""Golden tests for the LLM tool manifest descriptions.

Locks in the Round-1 description fixes captured in
``docs/models/SPEC/AICO_TOOL_DESCRIPTION_AUDIT.md``. If any of these
descriptions regress (e.g. a ``description=`` change in the command
class) the LLM manifest would leak vague or misleading wording back to
the model; that is exactly what this file is meant to prevent.
"""

from __future__ import annotations

import pytest

from app.commands.init_commands import initialize_commands
from app.commands.registry import command_registry
from app.game_engine.agent_runtime.aico_world_context import (
    build_llm_tool_manifest,
)
from app.game_engine.agent_runtime.resolved_tool_surface import (
    ResolvedToolSurface,
)


@pytest.fixture(scope="module", autouse=True)
def _ensure_commands_loaded():
    initialize_commands()
    yield


def _surface_for(names):
    return ResolvedToolSurface(
        allowed_command_names=frozenset(names),
        tool_command_context=None,  # unused by the manifest builder
    )


@pytest.mark.unit
def test_manifest_contains_updated_help_description():
    surface = _surface_for({"help"})
    text, schemas = build_llm_tool_manifest(surface, command_registry, session=None)
    assert len(schemas) == 1 and schemas[0].name == "help"
    assert "List available commands" in schemas[0].description
    assert "List available commands" in text


@pytest.mark.unit
def test_manifest_contains_updated_find_description():
    surface = _surface_for({"find"})
    text, schemas = build_llm_tool_manifest(surface, command_registry, session=None)
    assert len(schemas) == 1 and schemas[0].name == "find"
    desc = schemas[0].description
    # Shape of the returned payload must be visible in the manifest.
    assert "data.results" in desc
    assert ("total" in desc) and ("next_offset" in desc)
    # Explicit "not semantic" disclaimer prevents LLM hallucination about
    # vector search semantics (v3 short form).
    assert "not semantic" in desc.lower() or "semantic search" in desc.lower()
    # v3 flag surface keywords must be present so an LLM that reads only
    # the manifest knows the modern grammar (see F01 SPEC §3).
    for token in ("-n", "-des", "-a"):
        assert token in desc, f"missing v3 flag {token!r} in description: {desc!r}"
    # Must stay within the default manifest budget.
    assert len(desc) <= 240, f"description is {len(desc)} chars (> 240): {desc!r}"


@pytest.mark.unit
def test_manifest_contains_updated_agent_description():
    surface = _surface_for({"agent"})
    _, schemas = build_llm_tool_manifest(surface, command_registry, session=None)
    assert len(schemas) == 1 and schemas[0].name == "agent"
    desc = schemas[0].description
    # Subcommands must be enumerated so an LLM asked to "list agents"
    # does not skip this tool.
    for sub in ("list", "status", "nlp"):
        assert sub in desc


@pytest.mark.unit
def test_manifest_contains_updated_agent_tools_description():
    surface = _surface_for({"agent_tools"})
    _, schemas = build_llm_tool_manifest(surface, command_registry, session=None)
    assert len(schemas) == 1 and schemas[0].name == "agent_tools"
    desc = schemas[0].description
    # Must make the "registered, not necessarily callable" distinction.
    assert "registered" in desc.lower()
    assert "agent_capabilities" in desc


@pytest.mark.unit
def test_manifest_sorts_tools_and_includes_example_payload():
    surface = _surface_for({"help", "find", "whoami"})
    text, schemas = build_llm_tool_manifest(surface, command_registry, session=None)
    names = [s.name for s in schemas]
    assert names == sorted(names)
    # Every row embeds a JSON example so an LLM that does not support
    # native tool use has a concrete template to mimic.
    for name in ("help", "find", "whoami"):
        assert f"'name': '{name}'" in text or f'"name": "{name}"' in text
