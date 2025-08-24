"""
SSH控制台模块
提供命令行交互界面，集成现有命令系统
"""

import re
import logging
import threading
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime

import paramiko

from app.ssh.session import SSHSession, SessionManager
from app.ssh.commands import SSHCommandRegistry, SSHCommand, register_builtin_commands
from app.ssh.input_handler import InputHandler
from app.ssh.progress import StatusDisplay
from app.core.permissions import permission_checker


class SSHConsole:
    """SSH控制台实现"""
    
    def __init__(self, channel: paramiko.Channel, ssh_interface):
        self.channel = channel
        self.ssh_interface = ssh_interface
        self.logger = logging.getLogger(__name__)
        
        # 控制台状态
        self.running = False
        self.prompt = "campusworld> "
        self.continuation_prompt = "  ...> "
        
        # 命令处理
        self.command_registry = SSHCommandRegistry()
        self.current_session: Optional[SSHSession] = None
        
        # 输入缓冲
        self.input_buffer = ""
        self.command_history: List[str] = []
        self.history_index = 0
        
        # 设置通道参数
        self.channel.settimeout(1.0)
        
        # 创建增强的输入处理器
        self.input_handler = InputHandler(self)
        
        # 创建状态显示管理器
        self.status_display = StatusDisplay(self.channel)
        
        # 注册内置命令
        register_builtin_commands(self.command_registry)
    
    def _register_builtin_commands(self):
        """注册内置命令（已废弃，使用register_builtin_commands函数）"""
        pass
    
    def run(self):
        """运行控制台"""
        self.running = True
        
        try:
            # 显示欢迎信息
            self._display_welcome()
            
            # 主循环
            while self.running and not self.channel.closed:
                try:
                    # 显示提示符
                    self._display_prompt()
                    
                    # 读取输入（使用增强的输入处理器）
                    line = self.input_handler.read_line()
                    if line is None:
                        continue
                    
                    # 处理输入
                    self._process_input(line)
                    
                except Exception as e:
                    self.logger.error(f"Console error: {e}")
                    self.status_display.show_error(f"Console error: {e}")
                    
        except Exception as e:
            self.logger.error(f"Console run error: {e}")
        finally:
            self._cleanup()
    
    def _display_welcome(self):
        """显示欢迎信息"""
        welcome = f"""
╔══════════════════════════════════════════════════════════════╗
║                    Welcome to CampusWorld                    ║
║                        SSH Console                          ║
║                                                              ║
║  Type 'help' for available commands                         ║
║  Type 'exit' or 'quit' to disconnect                        ║
║                                                              ║
║  Keyboard Shortcuts:                                        ║
║    Tab        - Command completion                          ║
║    ↑/↓       - Navigate command history                    ║
║    Ctrl+A    - Move to beginning of line                   ║
║    Ctrl+E    - Move to end of line                         ║
║    Ctrl+K    - Delete to end of line                       ║
║    Ctrl+U    - Delete to beginning of line                 ║
║    Ctrl+W    - Delete word backward                         ║
║    Ctrl+L    - Clear screen                                 ║
╚══════════════════════════════════════════════════════════════╝

"""
        self.channel.send(welcome)
    
    def _display_prompt(self):
        """显示提示符"""
        if self.current_session:
            username = self.current_session.username
            self.channel.send(f"{username}@{self.prompt}")
        else:
            self.channel.send(self.prompt)
    
    def _read_line(self) -> Optional[str]:
        """读取一行输入"""
        line = ""
        while self.running and not self.channel.closed:
            try:
                char = self.channel.recv(1).decode('utf-8')
                if not char:
                    continue
                
                if char == '\r':
                    continue
                elif char == '\n':
                    break
                elif char == '\b' or char == '\x7f':  # Backspace
                    if line:
                        line = line[:-1]
                        # 发送退格序列
                        self.channel.send('\b \b')
                elif char == '\x03':  # Ctrl+C
                    self.channel.send('^C\n')
                    return None
                elif char == '\x04':  # Ctrl+D
                    self.channel.send('^D\n')
                    return None
                else:
                    line += char
                    self.channel.send(char)
                    
            except Exception as e:
                if "timeout" in str(e).lower():
                    continue
                else:
                    self.logger.error(f"Read error: {e}")
                    break
        
        return line.strip() if line else None
    
    def _process_input(self, line: str):
        """处理输入行"""
        if not line:
            return
        
        # 添加到历史记录
        self.command_history.append(line)
        self.history_index = len(self.command_history)
        
        # 解析命令
        try:
            command_parts = self._parse_command(line)
            if command_parts:
                command_name = command_parts[0]
                args = command_parts[1:]
                
                # 执行命令
                self._execute_command(command_name, args)
            else:
                self.channel.send("Invalid command format\n")
                
        except Exception as e:
            self.logger.error(f"Command processing error: {e}")
            self.status_display.show_error(f"Command processing error: {e}")
    
    def _parse_command(self, line: str) -> Optional[List[str]]:
        """解析命令字符串"""
        # 简单的命令解析，支持引号
        parts = []
        current = ""
        in_quotes = False
        quote_char = None
        
        for char in line:
            if char in ['"', "'"] and not in_quotes:
                in_quotes = True
                quote_char = char
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
            elif char == ' ' and not in_quotes:
                if current:
                    parts.append(current)
                    current = ""
            else:
                current += char
        
        if current:
            parts.append(current)
        
        return parts if parts else None
    
    def _execute_command(self, command_name: str, args: List[str]):
        """执行命令"""
        try:
            # 查找命令
            command = self.command_registry.get_command(command_name)
            if command:
                # 检查权限
                if self._check_command_permission(command, args):
                    # 执行命令
                    result = command.execute(self, args)
                    if result:
                        self.channel.send(f"{result}\n")
                else:
                    self.status_display.show_error("Permission denied")
            else:
                self.status_display.show_warning(f"Command not found: {command_name}")
                self.status_display.show_info("Type 'help' for available commands")
                
        except Exception as e:
            self.logger.error(f"Command execution error: {e}")
            self.status_display.show_error(f"Command execution error: {e}")
    
    def _check_command_permission(self, command: 'SSHCommand', args: List[str]) -> bool:
        """检查命令权限"""
        if not self.current_session:
            return False
        
        # 检查命令是否需要特定权限
        if command.required_permission:
            return permission_checker.check_permission(
                self.current_session.roles, 
                command.required_permission
            )
        
        # 检查命令是否需要特定角色
        if command.required_role:
            return permission_checker.check_role(
                self.current_session.roles, 
                command.required_role
            )
        
        # 检查命令是否需要特定访问级别
        if command.required_access_level:
            return permission_checker.check_access_level(
                self.current_session.access_level, 
                command.required_access_level
            )
        
        return True
    
    def set_session(self, session: SSHSession):
        """设置当前会话"""
        self.current_session = session
        self.logger.info(f"Session set for user: {session.username}")
    
    def get_session(self) -> Optional[SSHSession]:
        """获取当前会话"""
        return self.current_session
    
    def send_output(self, message: str):
        """发送输出到客户端"""
        if self.channel and not self.channel.closed:
            self.channel.send(message)
    
    def _cleanup(self):
        """清理资源"""
        self.running = False
        if self.current_session:
            self.current_session.cleanup()
        
        self.logger.info("Console cleanup completed")


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
    
    def execute(self, console: SSHConsole, args: List[str]) -> str:
        """执行命令"""
        raise NotImplementedError("Subclasses must implement execute method")
    
    def get_help(self) -> str:
        """获取帮助信息"""
        return f"{self.name}: {self.description}"


class SSHHelpCommand(SSHCommand):
    """帮助命令"""
    
    def __init__(self):
        super().__init__("help", "Show available commands")
    
    def execute(self, console: SSHConsole, args: List[str]) -> str:
        if args:
            # 显示特定命令的帮助
            command_name = args[0]
            command = console.command_registry.get_command(command_name)
            if command:
                return command.get_help()
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
    
    def execute(self, console: SSHConsole, args: List[str]) -> str:
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


class SSHUserInfoCommand(SSHCommand):
    """用户信息命令"""
    
    def __init__(self):
        super().__init__("user", "Show user information")
    
    def execute(self, console: SSHConsole, args: List[str]) -> str:
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
    
    def execute(self, console: SSHConsole, args: List[str]) -> str:
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
    
    def execute(self, console: SSHConsole, args: List[str]) -> str:
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
    
    def execute(self, console: SSHConsole, args: List[str]) -> str:
        console.running = False
        return "Goodbye!"


class SSHCommandRegistry:
    """SSH命令注册表"""
    
    def __init__(self):
        self.commands: Dict[str, SSHCommand] = {}
    
    def register_command(self, command: SSHCommand):
        """注册命令"""
        self.commands[command.name] = command
    
    def get_command(self, name: str) -> Optional[SSHCommand]:
        """获取命令"""
        return self.commands.get(name)
    
    def get_all_commands(self) -> List[SSHCommand]:
        """获取所有命令"""
        return list(self.commands.values())
    
    def unregister_command(self, name: str):
        """注销命令"""
        if name in self.commands:
            del self.commands[name]
