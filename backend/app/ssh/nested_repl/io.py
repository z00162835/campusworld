"""Narrow I/O surface for nested REPL drivers over SSHConsole (no agent semantics)."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict, Optional
if TYPE_CHECKING:
    from app.ssh.console import SSHConsole

class SshReplIo:
    """Delegates PTY/channel helpers; keeps nested drivers free of SSHConsole subclasses."""
    __slots__ = ('_console',)

    def __init__(self, console: SSHConsole):
        self._console = console

    @property
    def running(self) -> bool:
        return self._console.running

    @property
    def channel(self) -> Any:
        return self._console.channel

    @property
    def session(self) -> Any:
        return self._console.current_session

    @property
    def ssh_handler(self) -> Any:
        return self._console.ssh_handler

    @property
    def session_manager(self) -> Optional[Any]:
        return self._console.session_manager

    @property
    def game_handler(self) -> Optional[Any]:
        return self._console.game_handler

    def check_channel_status(self) -> bool:
        return self._console._check_channel_status()

    def safe_send_output(self, message: str) -> bool:
        return self._console._safe_send_output(message)

    def send_command_output_newline(self) -> bool:
        return self._console._send_command_output_newline()

    def send_char_echo(self, char: str) -> bool:
        return self._console._send_char_echo(char)

    def get_game_state(self) -> Dict[str, Any]:
        return self._console._get_game_state()

    def invoke_interactive_command(self, cmd_line: str) -> None:
        """Dispatch one shell line through the same path as the main SSH loop."""
        c = self._console
        sess = c.current_session
        if not sess:
            return
        user_id = str(sess.user_id)
        username = sess.username
        session_id = sess.session_id
        permissions = sess.permissions
        game_state = self.get_game_state()
        context_metadata: Dict[str, Any] = {}
        if c.session_manager is not None:
            context_metadata['session_manager'] = c.session_manager
        if c.game_handler is not None:
            context_metadata['game_handler'] = c.game_handler
        result = c.ssh_handler.handle_interactive_command(user_id=user_id, username=username, session_id=session_id, permissions=permissions, command_line=cmd_line, session=sess, game_state=game_state, metadata=context_metadata or None)
        if result:
            c._safe_send_output(result)
        c._send_command_output_newline()
