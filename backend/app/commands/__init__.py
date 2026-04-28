"""
命令系统包

基于单一职责原则的命令系统，支持多协议
"""

from .base import BaseCommand, SystemCommand, GameCommand, CommandContext, CommandResult
from .registry import CommandRegistry, command_registry
from .system_commands import *

__all__ = [
    "BaseCommand",
    "SystemCommand", 
    "GameCommand",
    "CommandContext",
    "CommandResult",
    "CommandRegistry",
    "command_registry"
]
