"""Single entry point for HTTP-layer command execution."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.commands.base import CommandContext, CommandResult
from app.commands.init_commands import ensure_commands_initialized
from app.commands.registry import command_registry
from app.commands.shell_words import split_command_line

from .types import WorldActor


@dataclass(frozen=True)
class CommandRunOptions:
    stream_emit: Optional[Callable[[str], None]] = None
    supports_aico_stream: bool = False
    stream_cancel_event: Optional[Event] = None


class CommandRunner:
    """Builds CommandContext and dispatches through the command registry."""

    def run(
        self,
        session: Session,
        actor: WorldActor,
        command_line: str,
        *,
        options: CommandRunOptions | None = None,
    ) -> CommandResult:
        opts = options or CommandRunOptions()
        ensure_commands_initialized()
        parts = split_command_line(str(command_line or "").strip())
        if not parts:
            return CommandResult.error_result("Command is empty", error="command.empty")
        command_name = parts[0].lower()
        args = parts[1:]
        command = command_registry.get_command(command_name)
        if not command:
            return CommandResult.error_result(f"Command '{command_name}' not found", error="command.not_found")
        context = CommandContext(
            user_id=actor.user_id,
            username=actor.username,
            session_id=f"http_{actor.user_id}",
            permissions=actor.permissions,
            roles=actor.roles,
            db_session=session,
        )
        if opts.stream_emit is not None:
            context.stream_emit = opts.stream_emit
        if opts.supports_aico_stream:
            context.supports_aico_stream = True
        if opts.stream_cancel_event is not None:
            if context.metadata is None:
                context.metadata = {}
            context.metadata['aico_stream_cancel_event'] = opts.stream_cancel_event
        decision = command_registry.authorize_command(command, context)
        if not decision.allowed:
            return CommandResult.error_result(
                f"Permission denied for command '{command_name}'",
                error="command.permission_denied",
            )
        return command.execute(context, args)
