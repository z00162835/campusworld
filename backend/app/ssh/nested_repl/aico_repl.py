"""AICO interactive nested REPL for native SSH (`aico -i`)."""

from __future__ import annotations

import select
import time
from typing import Optional

from app.commands.aico_exec import AICO_STREAM_EPHEMERAL_KEY
from app.core.log import LoggerNames, get_logger
from app.ssh.nested_repl.io import SshReplIo

AICO_REPL_PROMPT = b"\r\naico> "

logger = get_logger(LoggerNames.SSH)


class AicoNestedReplDriver:
    """Session-attached driver; SSHConsole runs via SshReplIo only."""

    __slots__ = ()

    def binds_aico_progress_emit(self) -> bool:
        return True

    def run(self, io: SshReplIo) -> None:
        while io.running and io.session is not None:
            sess = io.session
            if getattr(sess, "nested_repl", None) is not self:
                break
            if not self._send_prompt(io):
                break
            line = self._read_line(io)
            if line is None:
                break
            stripped = line.strip()
            if not stripped:
                continue
            low = stripped.lower()
            if low in ("exit", "quit", "/exit"):
                self._clear_repl_state(sess)
                io.safe_send_output("(left AICO interactive mode)\n")
                break
            self._dispatch_line(io, stripped)

    def _send_prompt(self, io: SshReplIo) -> bool:
        try:
            if not io.check_channel_status():
                return False
            io.channel.send(AICO_REPL_PROMPT)
            time.sleep(0.01)
            return True
        except Exception as e:
            logger.error(f"aico repl prompt send failed: {e}")
            return False

    def _clear_repl_state(self, sess: object) -> None:
        setattr(sess, "nested_repl", None)
        ep = getattr(sess, "command_ephemeral", None)
        if isinstance(ep, dict):
            ep.pop(AICO_STREAM_EPHEMERAL_KEY, None)

    def _dispatch_line(self, io: SshReplIo, line: str) -> None:
        if line.startswith("!"):
            inner = line[1:].strip()
            il = inner.lower()
            if il == "aico" or il.startswith("aico ") or il.startswith("aico\t"):
                io.safe_send_output(
                    "Error: nested aico is not allowed from interactive mode.\n"
                )
                return
            cmd_line = inner
        else:
            cmd_line = f"aico {line}"
        io.invoke_interactive_command(cmd_line)

    def _read_line(self, io: SshReplIo) -> Optional[str]:
        buf: list[str] = []
        while io.running:
            try:
                ready, _, _ = select.select([io.channel], [], [], 0.25)
                if not ready:
                    continue
                data = io.channel.recv(4096)
                if not data:
                    continue
                text = data.decode("utf-8", errors="ignore")
                for char in text:
                    if char == "\x11":
                        sess = io.session
                        if sess is not None:
                            self._clear_repl_state(sess)
                        io.safe_send_output("\n(left AICO interactive mode)\n")
                        return None
                    if char == "\x03":
                        io.safe_send_output("^C\n")
                        buf.clear()
                        continue
                    if char in ("\r", "\n"):
                        io.send_char_echo("\r\n")
                        return "".join(buf)
                    if char in ("\b", "\x7f"):
                        if buf:
                            buf.pop()
                            io.send_char_echo("\b \b")
                        continue
                    if ord(char) >= 32:
                        buf.append(char)
                        io.send_char_echo(char)
            except Exception as e:
                logger.debug(f"aico repl read: {e}")
                break
        return None
