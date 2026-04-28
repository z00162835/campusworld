"""Task command family (Phase B).

SSOT: ``docs/command/SPEC/features/CMD_task.md``.
"""

from __future__ import annotations

from .task_command import TaskCommand

# `task pool ...` is routed through TaskCommand; TaskPoolCommand remains an
# internal subcommand handler and is not registered as a top-level command.
TASK_COMMANDS = [TaskCommand()]

__all__ = ["TaskCommand", "TASK_COMMANDS"]
