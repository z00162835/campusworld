"""
协议处理器基类
定义协议无关的命令执行接口
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.commands.base import CommandContext, CommandResult


class ProtocolHandler(ABC):
    """协议处理器基类 - 协议无关"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"protocol.{self.__class__.__name__}")
    
    @abstractmethod
    def handle_interactive_command(self, user_id: str, session_id: str, 
                                 permissions: List[str], command_line: str,
                                 game_state: Optional[Dict[str, Any]] = None) -> str:
        """处理交互式命令"""
        pass
    
    @abstractmethod
    def get_prompt(self, username: str, game_state: Optional[Dict[str, Any]] = None) -> str:
        """获取提示符"""
        pass

    
    def create_context(self, user_id: str, username: str, session_id: str, permissions: List[str],
                      game_state: Optional[Dict[str, Any]] = None) -> CommandContext:
        """创建命令上下文"""
        return CommandContext(
            user_id=user_id,
            username=username,
            session_id=session_id,
            permissions=permissions,
            game_state=game_state
        )
