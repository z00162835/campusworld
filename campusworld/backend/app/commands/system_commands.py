"""
系统命令定义
基于新的命令系统架构
"""

import time
import platform
import psutil
from typing import List, Dict, Any
from .base import SystemCommand, CommandResult, CommandType


class HelpCommand(SystemCommand):
    """帮助命令"""
    
    def __init__(self):
        super().__init__("help", "Show available commands", ["h", "?"])
    
    def execute(self, context, args: List[str]) -> CommandResult:
        if args:
            # 显示特定命令的帮助
            command_name = args[0]
            from .registry import command_registry
            command = command_registry.get_command(command_name)
            if command:
                help_text = f"""
Command: {command.name}
Description: {command.description}
Usage: {command.get_usage()}
"""
                return CommandResult.success_result(help_text)
            else:
                return CommandResult.error_result(f"Command not found: {command_name}")
        else:
            # 显示所有可用命令
            from .registry import command_registry
            commands = command_registry.get_available_commands(context)
            help_text = "Available commands:\n"
            for cmd in commands:
                help_text += f"  {cmd.name:<15} - {cmd.description}\n"
            help_text += "\nType 'help <command>' for detailed help"
            return CommandResult.success_result(help_text)


class StatsCommand(SystemCommand):
    """统计命令"""
    
    def __init__(self):
        super().__init__("stats", "Show system statistics", ["stat", "system"])
    
    def execute(self, context, args: List[str]) -> CommandResult:
        try:
            # 系统信息
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            stats_text = f"""
System Statistics:
==================
CPU Usage: {cpu_percent}%
Memory: {memory.percent}% used ({memory.used // (1024**3)} GB / {memory.total // (1024**3)} GB)
Disk: {disk.percent}% used ({disk.used // (1024**3)} GB / {disk.total // (1024**3)} GB)
Platform: {platform.system()} {platform.release()}
Python: {platform.python_version()}
Uptime: {time.strftime('%Y-%m-%d %H:%M:%S')}
"""
            return CommandResult.success_result(stats_text)
        except Exception as e:
            return CommandResult.error_result(f"Failed to get system stats: {e}")


class VersionCommand(SystemCommand):
    """版本命令"""
    
    def __init__(self):
        super().__init__("version", "Show version information", ["ver"])
    
    def execute(self, context, args: List[str]) -> CommandResult:
        version_text = f"""
CampusWorld System
==================
Version: 0.1.0
Environment: development
Python: {platform.python_version()}
Platform: {platform.system()} {platform.release()}
"""
        return CommandResult.success_result(version_text)


class QuitCommand(SystemCommand):
    """退出命令"""
    
    def __init__(self):
        super().__init__("quit", "Exit system", ["exit", "q"])
    
    def execute(self, context, args: List[str]) -> CommandResult:
        result = CommandResult.success_result("Goodbye!")
        result.should_exit = True
        return result


class TimeCommand(SystemCommand):
    """时间命令"""
    
    def __init__(self):
        super().__init__("time", "Show current time", ["date"])
    
    def execute(self, context, args: List[str]) -> CommandResult:
        current_time = time.strftime('%Y-%m-%d %H:%M:%S')
        return CommandResult.success_result(f"Current time: {current_time}")


# 系统命令列表
SYSTEM_COMMANDS = [
    HelpCommand(),
    StatsCommand(),
    VersionCommand(),
    QuitCommand(),
    TimeCommand(),
]
