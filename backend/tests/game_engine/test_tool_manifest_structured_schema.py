"""Manifest must surface a command's declared ``CommandToolSemantics.input_schema``.

``build_llm_tool_manifest`` resolves contract fields via
``resolve_command_tool_semantics`` (registry ClassVar, no DB read) and, when a
command declares a structured ``input_schema``, emits that schema in the
manifest entry instead of the default args-array schema derived from
``BaseCommand.execute(context, args)``.
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
def test_manifest_emits_structured_input_schema_when_present():
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
        assert props.get("query", {}).get("type") == "string"
        assert fake.input_schema.get("required") == ["query"]
        # The default args-array schema must NOT leak through when a
        # structured schema is declared.
        assert "args" not in props
    finally:
        command_registry.unregister_command("fakesearch")
