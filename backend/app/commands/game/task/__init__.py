"""Task command family (Phase B).

SSOT: ``docs/command/SPEC/features/CMD_task.md``.
"""
from __future__ import annotations
from .task_command import TaskCommand
TASK_COMMANDS = [TaskCommand()]
__all__ = ['TaskCommand', 'TASK_COMMANDS']
