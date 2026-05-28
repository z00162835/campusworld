"""Backward-compatible re-exports; semantics live in command_tool_semantics."""
from app.commands.command_tool_semantics import (  # noqa: F401
    get_command_tool_semantics,
    pick_routing_hint,
    resolve_command_tool_semantics,
)
