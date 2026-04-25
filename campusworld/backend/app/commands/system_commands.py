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
        super().__init__(
            "help",
            "List available commands for the current caller, or show detailed help for one command.",
            ["h", "?"],
        )
    
    def execute(self, context, args: List[str]) -> CommandResult:
        from app.commands.i18n.locale_text import help_shell_for_locale, resolve_locale

        loc = resolve_locale(context)
        shell = help_shell_for_locale(loc)
        if args:
            command_name = args[0]
            from .registry import command_registry
            command = command_registry.get_command(command_name)
            if command:
                return CommandResult.success_result(command.get_detailed_help_for_locale(loc))
            return CommandResult.error_result(shell["err_not_found"].format(name=command_name))
        from .registry import command_registry
        commands = command_registry.get_available_commands(context)
        help_text = f"{shell['title_list']}:\n"
        for cmd in commands:
            help_text += f"  {cmd.name:<15} - {cmd.get_localized_description(loc)}\n"
        help_text += f"\n{shell['footer']}"
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

class WhoamiCommand(SystemCommand):
    """显示当前用户命令"""
    
    def __init__(self):
        super().__init__("whoami", "Show current user", ["who"])
    
    def execute(self, context, args: List[str]) -> CommandResult:
        return CommandResult.success_result(f"Current user: {context.username}")

# 系统命令列表
SYSTEM_COMMANDS = [
    HelpCommand(),
    StatsCommand(),
    VersionCommand(),
    QuitCommand(),
    TimeCommand(),
    WhoamiCommand(),
]
