"""
系统命令定义
基于新的命令系统架构
"""

import time
import platform
import psutil
from datetime import datetime
from collections import Counter
from typing import List, Dict, Any, Optional
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
        from app.commands.i18n.command_resource import get_command_i18n_text
        from app.commands.i18n.locale_text import resolve_locale

        loc = resolve_locale(context)
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            title = get_command_i18n_text("stats", "title", loc, "System Statistics")
            stats_text = (
                f"\n{title}:\n"
                "==================\n"
                f"CPU Usage: {cpu_percent}%\n"
                f"Memory: {memory.percent}% used "
                f"({memory.used // (1024**3)} GB / {memory.total // (1024**3)} GB)\n"
                f"Disk: {disk.percent}% used "
                f"({disk.used // (1024**3)} GB / {disk.total // (1024**3)} GB)\n"
                f"Platform: {platform.system()} {platform.release()}\n"
                f"Python: {platform.python_version()}\n"
                f"Uptime: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            return CommandResult.success_result(stats_text)
        except Exception as e:
            err_template = get_command_i18n_text(
                "stats", "error", loc, "Failed to get system stats: {error}"
            )
            return CommandResult.error_result(err_template.format(error=e))


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
        from app.commands.i18n.command_resource import get_command_i18n_text
        from app.commands.i18n.locale_text import resolve_locale

        loc = resolve_locale(context)
        message = get_command_i18n_text("quit", "goodbye", loc, "Goodbye!")
        result = CommandResult.success_result(message)
        result.should_exit = True
        return result


class TimeCommand(SystemCommand):
    """时间命令"""
    
    def __init__(self):
        super().__init__("time", "Show current time", ["date"])
    
    def execute(self, context, args: List[str]) -> CommandResult:
        from app.commands.i18n.command_resource import get_command_i18n_text
        from app.commands.i18n.locale_text import resolve_locale

        loc = resolve_locale(context)
        current_time = time.strftime('%Y-%m-%d %H:%M:%S')
        template = get_command_i18n_text("time", "format", loc, "Current time: {time}")
        return CommandResult.success_result(template.format(time=current_time))

class WhoamiCommand(SystemCommand):
    """显示当前用户命令"""
    
    def __init__(self):
        super().__init__("whoami", "Show current user", [])
    
    def execute(self, context, args: List[str]) -> CommandResult:
        from app.commands.i18n.command_resource import get_command_i18n_text
        from app.commands.i18n.locale_text import resolve_locale

        loc = resolve_locale(context)
        template = get_command_i18n_text(
            "whoami", "current_user", loc, "Current user: {username}"
        )
        return CommandResult.success_result(template.format(username=context.username))


class WhoCommand(SystemCommand):
    """显示当前在线会话列表（独立命令，不是 whoami 别名）。"""

    def __init__(self):
        super().__init__("who", "List online users and sessions", [])

    @staticmethod
    def _format_idle(seconds: Optional[float]) -> str:
        if seconds is None:
            return "0m"
        total = max(0, int(seconds))
        if total < 3600:
            return f"{total // 60}m"
        return f"{total // 3600}h"

    @staticmethod
    def _format_duration(seconds: Optional[float]) -> str:
        if seconds is None:
            return "0m"
        total = max(0, int(seconds))
        if total < 3600:
            return f"{total // 60}m"
        if total < 86400:
            return f"{total // 3600}h"
        return f"{total // 86400}d"

    @staticmethod
    def _seconds_since(ts: Any, now: datetime) -> Optional[float]:
        if ts is None:
            return None
        if isinstance(ts, datetime):
            return (now - ts).total_seconds()
        if isinstance(ts, (int, float)):
            # Handle unix timestamp style values.
            return now.timestamp() - float(ts)
        if isinstance(ts, str):
            try:
                return (now - datetime.fromisoformat(ts)).total_seconds()
            except ValueError:
                return None
        return None

    @staticmethod
    def _who_text(locale: str, key_path: str, default: str) -> str:
        """Resolve nested ``commands.who.*`` locale text via the shared helper."""
        from app.commands.i18n.command_resource import get_command_i18n_text

        return get_command_i18n_text("who", key_path, locale, default)

    def execute(self, context, args: List[str]) -> CommandResult:
        from app.commands.i18n.locale_text import resolve_locale
        from app.ssh.game_handler import game_handler

        loc = resolve_locale(context)
        metadata = getattr(context, "metadata", None) or {}
        session_manager = metadata.get("session_manager")
        if session_manager is None or not hasattr(session_manager, "get_active_sessions"):
            return CommandResult.error_result(
                self._who_text(loc, "error.unavailable", "Online user list unavailable."),
                error="session_manager not available in context",
            )

        sessions = list(session_manager.get_active_sessions() or [])
        if not sessions:
            return CommandResult.success_result(
                self._who_text(loc, "error.no_sessions", "No users online.")
            )

        gh = metadata.get("game_handler") if metadata.get("game_handler") is not None else game_handler
        now = datetime.now()
        username_counter = Counter(str(getattr(s, "username", "unknown")) for s in sessions)
        lines = [
            self._who_text(loc, "title", "CampusWorld Online Users"),
            "========================",
            f"{self._who_text(loc, 'header.player', 'Player'):<12} "
            f"{self._who_text(loc, 'header.location', 'Location'):<28} "
            f"{self._who_text(loc, 'header.idle', 'Idle'):<5}  "
            f"{self._who_text(loc, 'header.duration', 'Duration'):<8}",
            "----------   ----------------------------  -----  --------",
        ]

        location_error = False
        for sess in sessions:
            username = str(getattr(sess, "username", "unknown"))
            if username_counter[username] > 1:
                username = f"{username} (x{username_counter[username]})"
            user_id = getattr(sess, "user_id", None)
            location = "-"
            if gh is not None and hasattr(gh, "get_user_location") and user_id is not None:
                try:
                    loc_data = gh.get_user_location(str(user_id))
                    if isinstance(loc_data, dict):
                        location = str(loc_data.get("name") or "-")
                except Exception:
                    location_error = True
                    location = "-"
            idle = self._format_idle(
                self._seconds_since(getattr(sess, "last_activity", None), now)
            )
            duration = self._format_duration(
                self._seconds_since(getattr(sess, "connected_at", None), now)
            )
            lines.append(f"{username:<12} {location:<28} {idle:<5}  {duration:<8}")

        lines.append("")
        lines.append(
            self._who_text(
                loc,
                "footer",
                "{n} users online ({m} active sessions).",
            ).format(n=len(sessions), m=len(sessions))
        )
        if location_error:
            lines.append(
                self._who_text(
                    loc,
                    "warning.location_unavailable",
                    "Location information unavailable.",
                )
            )
        return CommandResult.success_result("\n".join(lines))

# 系统命令列表
SYSTEM_COMMANDS = [
    HelpCommand(),
    StatsCommand(),
    VersionCommand(),
    QuitCommand(),
    TimeCommand(),
    WhoCommand(),
    WhoamiCommand(),
]
