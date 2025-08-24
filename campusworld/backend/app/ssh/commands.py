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
        session_manager = console.ssh_interface.session_manager
        stats = session_manager.get_session_stats()
        
        info = f"""
Session Information:
===================
Total Sessions: {stats['total_sessions']}
Active Sessions: {stats['active_sessions']}
Users Connected: {len(stats['user_stats'])}

User Sessions:
"""
        for username, user_info in stats['user_stats'].items():
            info += f"  {username}: {user_info['session_count']} sessions, {user_info['total_commands']} commands\n"
        
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
        session_manager = console.ssh_interface.session_manager
        active_sessions = session_manager.get_active_sessions()
        
        if not active_sessions:
            return "No active sessions"
        
        info = "Online Users:\n"
        info += "=" * 50 + "\n"
        info += f"{'Username':<15} {'Connected':<20} {'Last Activity':<20} {'Commands':<10}\n"
        info += "-" * 50 + "\n"
        
        for session in active_sessions:
            connected = session.connected_at.strftime('%H:%M:%S')
            last_activity = session.last_activity.strftime('%H:%M:%S')
            commands = len(session.command_history)
            info += f"{session.username:<15} {connected:<20} {last_activity:<20} {commands:<10}\n"
        
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
            session_manager = console.ssh_interface.session_manager
            session_stats = session_manager.get_session_stats()
            
            status = f"""
System Status:
==============
CPU Usage: {cpu_percent}%
Memory: {memory.percent}% used ({memory.used // (1024**3)} GB / {memory.total // (1024**3)} GB)
Disk: {disk.percent}% used ({disk.used // (1024**3)} GB / {disk.total // (1024**3)} GB)

SSH Sessions:
=============
Active Sessions: {session_stats['active_sessions']}
Total Sessions: {session_stats['total_sessions']}
Users Connected: {len(session_stats['user_stats'])}
"""
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
