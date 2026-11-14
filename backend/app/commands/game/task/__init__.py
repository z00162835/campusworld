"""Task command family (Phase B).

SSOT: ``docs/command/SPEC/features/CMD_task.md``.
"""
from __future__ import annotations
from .semantic_commands import GoalCommand, ObservationCommand, QuestCommand, SituationCommand
from .task_command import TaskCommand
TASK_COMMANDS = [TaskCommand(), ObservationCommand(), SituationCommand(), GoalCommand(), QuestCommand()]
__all__ = ['TaskCommand', 'ObservationCommand', 'SituationCommand', 'GoalCommand', 'QuestCommand', 'TASK_COMMANDS']
