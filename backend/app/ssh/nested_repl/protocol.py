"""Nested REPL driver protocol for SSH (session-owned, console delegates I/O)."""
from __future__ import annotations
from typing import Protocol, runtime_checkable

@runtime_checkable
class NestedReplDriver(Protocol):
    """Runs a read/eval loop until exit; SSHConsole provides raw I/O via SshReplIo."""

    def run(self, io: 'SshReplIo') -> None:
        ...

    def binds_aico_progress_emit(self) -> bool:
        """When True, SSHHandler attaches plain-text agent progress for this REPL."""
        ...
