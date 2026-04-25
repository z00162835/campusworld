"""
SSH协议处理器
处理SSH特定的命令执行和交互逻辑
"""

import time
from typing import List, Dict, Any, Optional
from .base import ProtocolHandler
from app.commands.at_agent_dispatch import try_dispatch_at_line
from app.commands.registry import command_registry
from app.commands.base import CommandContext, CommandResult
from app.commands.shell_words import split_command_line
from app.core.database import db_session_context


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
            
            with db_session_context() as db_session:
                context = self.create_context(
                    user_id,
                    username,
                    session_id,
                    permissions,
                    session,
                    game_state,
                    db_session=db_session,
                )
                at_res = try_dispatch_at_line(command_line, context)
                if at_res is not None:
                    return self._format_command_result(at_res)

                # 解析命令（支持引号包裹含空格的参数，与常见 MUD/Evennia shell 一致）
                parts = split_command_line(command_line)
                command_name = parts[0].lower()
                args = parts[1:] if len(parts) > 1 else []

                command = command_registry.get_command(command_name)
                if not command:
                    return self._format_command_not_found(command_name)

                decision = command_registry.authorize_command(command, context)
                if not decision.allowed:
                    return self._format_permission_denied(command_name)

                result = command.execute(context, args)

                return self._format_command_result(result)
            
        except Exception:
            self.logger.exception("命令执行错误")
            return self._format_unexpected_error()
    
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
        """格式化错误消息（已弃用对终端直出内部异常串；保留供显式需要时调用）。"""
        return f"System Error: {error}\n"

    def _format_unexpected_error(self) -> str:
        """未分类异常：不向用户暴露实现细节。"""
        return "System Error: An unexpected error occurred.\n"
