"""Manifest must always emit the args-array tool input schema.

``build_llm_tool_manifest`` resolves contract fields via
``resolve_command_tool_semantics`` (registry ClassVar, no DB read) but the
LLM tool ``input_schema`` is always the args-array shape matching
``BaseCommand.execute(context, args: List[str])``. A command's declared
``CommandToolSemantics.input_schema`` is contract metadata (mirrored to
``system_command_ability`` for audit) and is NOT emitted as the tool schema:
named-field schemas (e.g. ``{"topic": ...}``, ``{"query": ...}``) diverge
from the positional-arg execution contract and induce mis calls (the model
fills the named field, the adapter flattens key+value into positional args,
and the command reads the field name as ``args[0]``).
"""

from __future__ import annotations

import pytest

from app.commands.base import BaseCommand, CommandContext, CommandResult, CommandType
from app.commands.command_tool_semantics import CommandToolSemantics


class _FakeCmd(BaseCommand):
    tool_semantics = CommandToolSemantics(
        interaction_profile="read",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )

    def __init__(self):
        super().__init__(
            name="fakesearch",
            description="fake search",
            command_type=CommandType.SYSTEM,
        )

    def execute(self, context: CommandContext, args):
        return CommandResult.success_result("ok")


@pytest.mark.unit
def test_manifest_always_emits_args_array_schema():
    from app.commands.registry import command_registry
    from app.game_engine.agent_runtime.aico_world_context import (
        build_llm_tool_manifest,
    )
    from app.game_engine.agent_runtime.resolved_tool_surface import (
        ResolvedToolSurface,
    )

    command_registry.register_command(_FakeCmd())
    try:
        surface = ResolvedToolSurface(
            allowed_command_names=frozenset({"fakesearch"}),
            tool_command_context=None,
        )
        _prose, schemas = build_llm_tool_manifest(
            surface, command_registry, session=None
        )
        fake = next(s for s in schemas if s.name == "fakesearch")
        props = fake.input_schema.get("properties", {})
        # The args-array schema matching BaseCommand.execute(context, args)
        # is always emitted, even when a command declares a structured
        # named-field input_schema.
        assert "args" in props
        assert props["args"]["type"] == "array"
        # The declared named-field schema must NOT leak into the tool schema.
        assert "query" not in props
    finally:
        command_registry.unregister_command("fakesearch")


@pytest.mark.unit
def test_manifest_args_array_schema_for_help():
    from app.commands.init_commands import initialize_commands
    from app.commands.registry import command_registry
    from app.game_engine.agent_runtime.aico_world_context import (
        build_llm_tool_manifest,
    )
    from app.game_engine.agent_runtime.resolved_tool_surface import (
        ResolvedToolSurface,
    )

    initialize_commands(force_reinit=True)
    surface = ResolvedToolSurface(
        allowed_command_names=frozenset({"help"}),
        tool_command_context=None,
    )
    _prose, schemas = build_llm_tool_manifest(surface, command_registry, session=None)
    help_schema = next(s for s in schemas if s.name == "help")
    props = help_schema.input_schema.get("properties", {})
    assert "args" in props
    assert props["args"]["type"] == "array"
    # The legacy "topic" named field must no longer appear.
    assert "topic" not in props
