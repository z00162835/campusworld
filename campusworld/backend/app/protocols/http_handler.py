"""
HTTP协议处理器
处理HTTP特定的命令执行和交互逻辑
"""

import logging
import json
from typing import List, Dict, Any, Optional
from .base import ProtocolHandler
from app.commands.registry import command_registry
from app.commands.base import CommandContext, CommandResult


class HTTPHandler(ProtocolHandler):
    """HTTP协议处理器"""
    
    def __init__(self):
        super().__init__()
        self.logger.info("HTTP协议处理器已初始化")
    
    def handle_interactive_command(self, user_id: str, session_id: str, 
                                 permissions: List[str], command_line: str,
                                 game_state: Optional[Dict[str, Any]] = None) -> str:
        """处理HTTP交互式命令"""
        try:
            if not command_line.strip():
                return json.dumps({"success": True, "message": ""})
            
            # 解析命令
            parts = command_line.strip().split()
            command_name = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            # 创建命令上下文
            context = self.create_context(user_id, session_id, permissions, game_state)
            
            # 查找命令
            command = command_registry.get_command(command_name)
            if not command:
                return json.dumps({
                    "success": False,
                    "error": f"Command '{command_name}' not found"
                })
            
            # 检查权限
            if not command.check_permission(context):
                return json.dumps({
                    "success": False,
                    "error": f"Permission denied for command '{command_name}'"
                })
            
            # 执行命令
            result = command.execute(context, args)
            
            # 返回JSON格式结果
            return json.dumps({
                "success": result.success,
                "message": result.message,
                "data": result.data,
                "error": result.error
            })
            
        except Exception as e:
            self.logger.error(f"命令执行错误: {e}")
            return json.dumps({
                "success": False,
                "error": f"System Error: {str(e)}"
            })
    
    def get_prompt(self, username: str, game_state: Optional[Dict[str, Any]] = None) -> str:
        """获取HTTP提示符"""
        if game_state and game_state.get('current_game'):
            game_name = game_state['current_game']
            return f"{username}@{game_name}> "
        else:
            return f"{username}@campusworld> "
    