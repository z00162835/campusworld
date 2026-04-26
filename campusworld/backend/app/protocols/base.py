"""
协议处理器基类
定义协议无关的命令执行接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.commands.base import CommandContext, CommandResult
from app.commands.i18n.locale_text import initial_metadata_for_session
from app.core.log import get_logger, LoggerNames
logger = get_logger(LoggerNames.PROTOCOL)


class ProtocolHandler(ABC):
    """协议处理器基类 - 协议无关"""
    
    def __init__(self):
        self.logger = get_logger(LoggerNames.PROTOCOL)
    
    @abstractmethod
    def handle_interactive_command(self, user_id: str, username: str, session_id: str,
                                 permissions: List[str], command_line: str,
                                 session: Optional[Any] = None,
                                 game_state: Optional[Dict[str, Any]] = None,
                                 metadata: Optional[Dict[str, Any]] = None) -> str:
        """处理交互式命令"""
        pass
    
    @abstractmethod
    def get_prompt(self, username: str, game_state: Optional[Dict[str, Any]] = None) -> str:
        """获取提示符"""
        pass

    
    def create_context(
        self,
        user_id: str,
        username: str,
        session_id: str,
        permissions: List[str],
        session: Optional[Any] = None,
        game_state: Optional[Dict[str, Any]] = None,
        db_session: Optional[Any] = None,
        roles: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CommandContext:
        """创建命令上下文"""
        caller = None
        if session and hasattr(session, 'user_object'):
            caller = session.user_object
        resolved_roles = list(roles or [])
        if not resolved_roles and session and hasattr(session, "roles"):
            resolved_roles = list(getattr(session, "roles", []) or [])
        md = initial_metadata_for_session(
            db_session=db_session,
            user_id=user_id,
            username=username,
            extra=metadata,
        )
        return CommandContext(
            user_id=user_id,
            username=username,
            session_id=session_id,
            permissions=permissions,
            caller=caller,
            session=session,
            game_state=game_state,
            db_session=db_session,
            roles=resolved_roles,
            metadata=md,
        )
    