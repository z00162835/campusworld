"""
SSH命令模块
定义SSH控制台可用的命令
"""

import os
import sys
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.core.database import SessionLocal
from app.models.graph import Node, NodeType
from app.core.permissions import permission_checker


class SSHCommand:
    """SSH命令基类"""
    
    def __init__(self, name: str, description: str = "", 
                 required_permission: str = None,
                 required_role: str = None,
                 required_access_level: str = None):
        self.name = name
        self.description = description
        self.required_permission = required_permission
        self.required_role = required_role
        self.required_access_level = required_access_level
    
    def execute(self, console, args: List[str]) -> str:
        """执行命令"""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def get_help(self) -> str:
        """获取帮助信息"""
        return f"{self.name}: {self.description}"
    
    def get_usage(self) -> str:
        """获取使用说明"""
        return f"Usage: {self.name} [options]"


class SSHCommandRegistry:
    """SSH命令注册表"""
    
    def __init__(self):
        self.commands: Dict[str, SSHCommand] = {}
        self.aliases: Dict[str, str] = {}  # 命令别名映射
    
    def register_command(self, command: SSHCommand):
        """注册命令"""
        self.commands[command.name] = command
    
    def get_command(self, name: str) -> Optional[SSHCommand]:
        """获取命令"""
        # 检查别名
        if name in self.aliases:
            name = self.aliases[name]
        return self.commands.get(name)
    
    def get_all_commands(self) -> List[SSHCommand]:
        """获取所有命令"""
        return list(self.commands.values())
    
    def unregister_command(self, name: str):
        """注销命令"""
        if name in self.commands:
            del self.commands[name]
    
    def add_alias(self, alias: str, command_name: str):
        """添加命令别名"""
        if command_name in self.commands:
            self.aliases[alias] = command_name
    
    def remove_alias(self, alias: str):
        """移除命令别名"""
        if alias in self.aliases:
            del self.aliases[alias]
    
    def get_aliases(self) -> Dict[str, str]:
        """获取所有别名"""
        return self.aliases.copy()


# ==================== 内置命令实现 ====================

class SSHHelpCommand(SSHCommand):
    """帮助命令"""
    
    def __init__(self):
        super().__init__("help", "Show available commands")
    
    def execute(self, console, args: List[str]) -> str:
        if args:
            # 显示特定命令的帮助
            command_name = args[0]
            command = console.command_registry.get_command(command_name)
            if command:
                help_text = f"""
Command: {command.name}
Description: {command.description}
Usage: {command.get_usage()}
"""
                return help_text
            else:
                return f"Command not found: {command_name}"
        else:
            # 显示所有可用命令
            commands = console.command_registry.get_all_commands()
            help_text = "Available commands:\n"
            for cmd in commands:
                help_text += f"  {cmd.name:<15} - {cmd.description}\n"
            help_text += "\nType 'help <command>' for detailed help"
            return help_text


class SSHSystemInfoCommand(SSHCommand):
    """系统信息命令"""
    
    def __init__(self):
        super().__init__("system", "Show system information")
    
    def execute(self, console, args: List[str]) -> str:
        try:
            import platform
            import psutil
            
            info = f"""
System Information:
==================
OS: {platform.system()} {platform.release()}
Python: {platform.python_version()}
CPU: {platform.processor()}
Memory: {psutil.virtual_memory().total // (1024**3)} GB
Uptime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            return info
        except ImportError:
            return "psutil not available for detailed system information"


class SSHUserInfoCommand(SSHCommand):
    """用户信息命令"""
    
    def __init__(self):
        super().__init__("user", "Show user information")
    
    def execute(self, console, args: List[str]) -> str:
        session = console.get_session()
        if not session:
            return "No active session"
        
        info = f"""
User Information:
=================
Username: {session.username}
User ID: {session.user_id}
Roles: {', '.join(session.roles)}
Access Level: {session.access_level}
Connected: {session.connected_at.strftime('%Y-%m-%d %H:%M:%S')}
Last Activity: {session.last_activity.strftime('%Y-%m-%d %H:%M:%S')}
Commands Executed: {len(session.command_history)}
"""
        return info


class SSHSessionCommand(SSHCommand):
    """会话管理命令"""
    
    def __init__(self):
        super().__init__("sessions", "Show session information", 
                        required_permission="system.view")
    
    def execute(self, console, args: List[str]) -> str:
        session = console.get_session()
        if not session:
            return "No active session"
        
        info = f"""
Session Information:
===================
Username: {session.username}
User ID: {session.user_id}
Connected: {session.connected_at.strftime('%Y-%m-%d %H:%M:%S')}
Last Activity: {session.last_activity.strftime('%Y-%m-%d %H:%M:%S')}
Commands Executed: {len(session.command_history)}
"""
        return info


class SSHPermissionCommand(SSHCommand):
    """权限检查命令"""
    
    def __init__(self):
        super().__init__("permission", "Check permission for specific action")
    
    def execute(self, console, args: List[str]) -> str:
        if not args:
            return "Usage: permission <permission_name>"
        
        session = console.get_session()
        if not session:
            return "No active session"
        
        permission = args[0]
        has_permission = permission_checker.check_permission(
            session.roles, permission
        )
        
        return f"Permission '{permission}': {'GRANTED' if has_permission else 'DENIED'}"


class SSHExitCommand(SSHCommand):
    """退出命令"""
    
    def __init__(self):
        super().__init__("exit", "Exit SSH console")
    
    def execute(self, console, args: List[str]) -> str:
        console.running = False
        return "Goodbye!"


class SSHQuitCommand(SSHCommand):
    """退出命令别名"""
    
    def __init__(self):
        super().__init__("quit", "Exit SSH console")
    
    def execute(self, console, args: List[str]) -> str:
        console.running = False
        return "Goodbye!"


class SSHWhoCommand(SSHCommand):
    """查看在线用户命令"""
    
    def __init__(self):
        super().__init__("who", "Show online users")
    
    def execute(self, console, args: List[str]) -> str:
        session = console.get_session()
        if not session:
            return "No active session"
        
        info = f"""
Online User:
============
Username: {session.username}
Connected: {session.connected_at.strftime('%H:%M:%S')}
Last Activity: {session.last_activity.strftime('%H:%M:%S')}
Commands Executed: {len(session.command_history)}
"""
        return info


class SSHHistoryCommand(SSHCommand):
    """命令历史记录命令"""
    
    def __init__(self):
        super().__init__("history", "Show command history")
    
    def execute(self, console, args: List[str]) -> str:
        session = console.get_session()
        if not session:
            return "No active session"
        
        if not session.command_history:
            return "No command history"
        
        # 解析参数
        limit = 20  # 默认显示最近20条
        if args and args[0].isdigit():
            limit = int(args[0])
        
        history = session.command_history[-limit:]
        
        info = f"Command History (last {len(history)} commands):\n"
        info += "=" * 50 + "\n"
        
        for i, cmd in enumerate(history, 1):
            info += f"{i:3d}: {cmd}\n"
        
        return info


class SSHClearCommand(SSHCommand):
    """清屏命令"""
    
    def __init__(self):
        super().__init__("clear", "Clear the screen")
    
    def execute(self, console, args: List[str]) -> str:
        # 发送清屏序列
        console.channel.send('\033[2J\033[H')
        return ""


class SSHDateCommand(SSHCommand):
    """日期时间命令"""
    
    def __init__(self):
        super().__init__("date", "Show current date and time")
    
    def execute(self, console, args: List[str]) -> str:
        now = datetime.now()
        return now.strftime('%Y-%m-%d %H:%M:%S')


class SSHVersionCommand(SSHCommand):
    """版本信息命令"""
    
    def __init__(self):
        super().__init__("version", "Show system version information")
    
    def execute(self, console, args: List[str]) -> str:
        from app.core.config import get_setting
        
        version_info = f"""
CampusWorld SSH Console
=======================
Version: {get_setting('app.version', '0.1.0')}
Environment: {get_setting('app.environment', 'development')}
Python: {sys.version}
"""
        return version_info


class SSHStatusCommand(SSHCommand):
    """状态信息命令"""
    
    def __init__(self):
        super().__init__("status", "Show system status")
    
    def execute(self, console, args: List[str]) -> str:
        try:
            import psutil
            
            # 系统状态
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # 会话状态
            session = console.get_session()
            session_info = ""
            if session:
                session_info = f"""
SSH Session:
============
Username: {session.username}
Connected: {session.connected_at.strftime('%H:%M:%S')}
Last Activity: {session.last_activity.strftime('%H:%M:%S')}
Commands Executed: {len(session.command_history)}
"""
            
            status = f"""
System Status:
==============
CPU Usage: {cpu_percent}%
Memory: {memory.percent}% used ({memory.used // (1024**3)} GB / {memory.total // (1024**3)} GB)
Disk: {disk.percent}% used ({disk.used // (1024**3)} GB / {disk.total // (1024**3)} GB)
{session_info}"""
            return status
            
        except ImportError:
            return "psutil not available for detailed status information"


class SSHConfigCommand(SSHCommand):
    """配置查看命令"""
    
    def __init__(self):
        super().__init__("config", "Show configuration information", 
                        required_permission="system.view")
    
    def execute(self, console, args: List[str]) -> str:
        from app.core.config import get_setting
        
        if args:
            # 显示特定配置项
            config_key = args[0]
            value = get_setting(config_key, "Not found")
            return f"{config_key}: {value}"
        else:
            # 显示所有配置
            config_info = f"""
Configuration:
==============
App Name: {get_setting('app.name', 'CampusWorld')}
Version: {get_setting('app.version', '0.0.0')}
Environment: {get_setting('app.environment', 'development')}
Debug: {get_setting('app.debug', False)}
API Prefix: {get_setting('api.v1_prefix', '/api/v1')}
"""
            return config_info


class SSHAliasCommand(SSHCommand):
    """命令别名管理命令"""
    
    def __init__(self):
        super().__init__("alias", "Manage command aliases")
    
    def execute(self, console, args: List[str]) -> str:
        if not args:
            # 显示所有别名
            aliases = console.command_registry.get_aliases()
            if not aliases:
                return "No aliases defined"
            
            result = "Command Aliases:\n"
            result += "=" * 30 + "\n"
            for alias, command in aliases.items():
                result += f"{alias:<15} -> {command}\n"
            return result
        
        elif len(args) == 1:
            # 显示特定别名
            alias = args[0]
            aliases = console.command_registry.get_aliases()
            if alias in aliases:
                return f"Alias '{alias}' -> '{aliases[alias]}'"
            else:
                return f"Alias '{alias}' not found"
        
        elif len(args) == 2:
            # 设置别名
            alias, command = args[0], args[1]
            
            # 检查命令是否存在
            if command not in console.command_registry.commands:
                return f"Command '{command}' not found"
            
            # 检查别名是否已存在
            existing_aliases = console.command_registry.get_aliases()
            if alias in existing_aliases:
                old_command = existing_aliases[alias]
                console.command_registry.remove_alias(alias)
                console.command_registry.add_alias(alias, command)
                return f"Alias '{alias}' updated: '{old_command}' -> '{command}'"
            else:
                console.command_registry.add_alias(alias, command)
                return f"Alias '{alias}' -> '{command}' created"
        
        else:
            return "Usage: alias [alias_name] [command_name]"


class SSHGameEngineCommand(SSHCommand):
    """游戏引擎管理命令"""
    
    name = "game"
    aliases = ["g", "games"]
    description = "管理游戏引擎和游戏"
    usage = "game <subcommand> [args...]"
    required_permission = "admin"
    
    def execute(self, console, args):
        """执行游戏引擎管理命令"""
        try:
            if not args:
                return self._show_help()
            
            subcommand = args[0].lower()
            
            if subcommand == "list":
                return self._list_games(console)
            elif subcommand == "status":
                return self._show_engine_status(console)
            elif subcommand == "load":
                if len(args) < 2:
                    return "用法: game load <游戏名>"
                return self._load_game(console, args[1])
            elif subcommand == "unload":
                if len(args) < 2:
                    return "用法: game unload <游戏名>"
                return self._unload_game(console, args[1])
            elif subcommand == "reload":
                if len(args) < 2:
                    return "用法: game reload <游戏名>"
                return self._reload_game(console, args[1])
            elif subcommand == "start":
                return self._start_engine(console)
            elif subcommand == "stop":
                return self._stop_engine(console)
            elif subcommand == "help":
                return self._show_help()
            else:
                return f"未知子命令: {subcommand}\n{self._show_help()}"
                
        except Exception as e:
            return f"游戏引擎管理命令执行失败: {str(e)}"
    
    def _show_help(self):
        """显示帮助信息"""
        return """
游戏引擎管理命令帮助
==================

用法: game <子命令> [参数...]

子命令:
  list     - 列出所有可用游戏
  status   - 显示引擎状态
  load     - 加载指定游戏
  unload   - 卸载指定游戏
  reload   - 重新加载指定游戏
  start    - 启动游戏引擎
  stop     - 停止游戏引擎
  help     - 显示此帮助信息

示例:
  game list              - 列出所有游戏
  game status            - 显示引擎状态
  game load campus_life  - 加载校园生活游戏
  game unload campus_life - 卸载校园生活游戏
  game start             - 启动游戏引擎
"""
    
    def _list_games(self, console):
        """列出所有游戏"""
        try:
            from app.game_engine import game_engine_manager
            
            available_games = game_engine_manager.list_games()
            loaded_games = game_engine_manager.get_engine().loader.get_loaded_games() if game_engine_manager.get_engine() else []
            
            result = "可用游戏列表\n"
            result += "=" * 20 + "\n"
            
            if not available_games:
                result += "没有找到可用游戏\n"
            else:
                for game_name in available_games:
                    status = "已加载" if game_name in loaded_games else "未加载"
                    result += f"{game_name:<15} - {status}\n"
            
            result += f"\n总计: {len(available_games)} 个游戏，{len(loaded_games)} 个已加载"
            return result
            
        except Exception as e:
            return f"列出游戏失败: {str(e)}"
    
    def _show_engine_status(self, console):
        """显示引擎状态"""
        try:
            from app.game_engine import game_engine_manager
            
            status = game_engine_manager.get_engine_status()
            
            result = "游戏引擎状态\n"
            result += "=" * 20 + "\n"
            
            if status["status"] == "not_initialized":
                result += "状态: 未初始化\n"
            else:
                result += f"名称: {status['name']}\n"
                result += f"版本: {status['version']}\n"
                result += f"状态: {'运行中' if status['is_running'] else '已停止'}\n"
                result += f"启动时间: {status['start_time'] or '未启动'}\n"
                result += f"游戏数量: {status['games_count']}\n"
                result += f"已加载游戏: {', '.join(status['loaded_games']) if status['loaded_games'] else '无'}\n"
                result += f"可用游戏: {', '.join(status['available_games']) if status['available_games'] else '无'}\n"
            
            return result
            
        except Exception as e:
            return f"获取引擎状态失败: {str(e)}"
    
    def _load_game(self, console, game_name):
        """加载游戏"""
        try:
            from app.game_engine import game_engine_manager
            
            if game_engine_manager.load_game(game_name):
                return f"游戏 '{game_name}' 加载成功"
            else:
                return f"游戏 '{game_name}' 加载失败"
                
        except Exception as e:
            return f"加载游戏 '{game_name}' 失败: {str(e)}"
    
    def _unload_game(self, console, game_name):
        """卸载游戏"""
        try:
            from app.game_engine import game_engine_manager
            
            if game_engine_manager.unload_game(game_name):
                return f"游戏 '{game_name}' 卸载成功"
            else:
                return f"游戏 '{game_name}' 卸载失败"
                
        except Exception as e:
            return f"卸载游戏 '{game_name}' 失败: {str(e)}"
    
    def _reload_game(self, console, game_name):
        """重新加载游戏"""
        try:
            from app.game_engine import game_engine_manager
            
            if game_engine_manager.reload_game(game_name):
                return f"游戏 '{game_name}' 重新加载成功"
            else:
                return f"游戏 '{game_name}' 重新加载失败"
                
        except Exception as e:
            return f"重新加载游戏 '{game_name}' 失败: {str(e)}"
    
    def _start_engine(self, console):
        """启动引擎"""
        try:
            from app.game_engine import game_engine_manager
            
            if game_engine_manager.start_engine():
                return "游戏引擎启动成功"
            else:
                return "游戏引擎启动失败"
                
        except Exception as e:
            return f"启动游戏引擎失败: {str(e)}"
    
    def _stop_engine(self, console):
        """停止引擎"""
        try:
            from app.game_engine import game_engine_manager
            
            if game_engine_manager.stop_engine():
                return "游戏引擎停止成功"
            else:
                return "游戏引擎停止失败"
                
        except Exception as e:
            return f"停止游戏引擎失败: {str(e)}"


# 命令注册函数
def register_builtin_commands(registry: SSHCommandRegistry):
    """注册所有内置命令"""
    commands = [
        SSHHelpCommand(),
        SSHSystemInfoCommand(),
        SSHUserInfoCommand(),
        SSHSessionCommand(),
        SSHPermissionCommand(),
        SSHExitCommand(),
        SSHQuitCommand(),
        SSHWhoCommand(),
        SSHAliasCommand(),
        SSHHistoryCommand(),
        SSHClearCommand(),
        SSHDateCommand(),
        SSHVersionCommand(),
        SSHStatusCommand(),
        SSHConfigCommand(),
        SSHGameEngineCommand(),
    ]
    
    for command in commands:
        registry.register_command(command)
    
    # 添加默认别名
    registry.add_alias("h", "help")
    registry.add_alias("?", "help")
    registry.add_alias("sys", "system")
    registry.add_alias("u", "user")
    registry.add_alias("q", "quit")
    registry.add_alias("cls", "clear")
    registry.add_alias("ver", "version")
    registry.add_alias("stat", "status")
    registry.add_alias("conf", "config")
    
    return registry
