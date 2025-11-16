"""
SSH协议处理器
处理SSH特定的命令执行和交互逻辑
"""

import logging
import time
from typing import List, Dict, Any, Optional
from .base import ProtocolHandler
from app.commands.registry import command_registry
from app.commands.base import CommandContext, CommandResult


class SSHHandler(ProtocolHandler):
    """SSH协议处理器"""
    
    def __init__(self):
        super().__init__()
        self.logger.info("SSH协议处理器已初始化")
    
    def handle_interactive_command(self, user_id: str, username: str, session_id: str, 
                                 permissions: List[str], command_line: str,
                                 session: Optional[Any] = None,
                                 game_state: Optional[Dict[str, Any]] = None) -> str:
        """处理SSH交互式命令"""
        try:
            if not command_line.strip():
                return ""
            
            # 解析命令
            parts = command_line.strip().split()
            command_name = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            # 创建命令上下文
            context = self.create_context(user_id, username, session_id, permissions, session, game_state)
            
            # 查找命令
            command = command_registry.get_command(command_name)
            if not command:
                return self._format_command_not_found(command_name)
            
            # 检查权限
            if not command.check_permission(context):
                return self._format_permission_denied(command_name)
            
            # 执行命令
            result = command.execute(context, args)
            
            # 格式化结果
            return self._format_command_result(result)
            
        except Exception as e:
            self.logger.error(f"命令执行错误: {e}")
            return self._format_error(str(e))
    
    def get_prompt(self, username: str, game_state: Optional[Dict[str, Any]] = None) -> str:
        """获取SSH提示符"""
        timestamp = time.strftime('%H:%M:%S')
        if game_state and game_state.get('current_game'):
            game_name = game_state['current_game']
            return f"[{username}@{timestamp}] {game_name}> "
        else:
            return f"[{username}@{timestamp}] campusworld> "
    
    
    def _format_command_not_found(self, command_name: str) -> str:
        """格式化命令未找到消息"""
        return f"Command '{command_name}' was not found. Type 'help' for available commands.\n"
    
    def _format_permission_denied(self, command_name: str) -> str:
        """格式化权限拒绝消息"""
        return f"Permission denied for command '{command_name}'.\n"
    
    def _format_command_result(self, result: CommandResult) -> str:
        """格式化命令结果"""
        if result.success:
            message = result.message + "\n"
            return message
            
        else:
            return f"Error: {result.message}\n"
    
    def _format_error(self, error: str) -> str:
        """格式化错误消息"""
        return f"System Error: {error}\n"
