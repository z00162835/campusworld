"""
协议处理器基类
定义协议无关的命令执行接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.commands.base import CommandContext, CommandResult
from app.core.database import SessionLocal
from app.models.graph import Node
from app.models.user import User
from app.core.log import get_logger, LoggerNames
logger = get_logger(LoggerNames.PROTOCOL)


class ProtocolHandler(ABC):
    """协议处理器基类 - 协议无关"""
    
    def __init__(self):
        self.logger = get_logger(LoggerNames.PROTOCOL)
    
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
        caller = self._load_user_object(user_id)
        return CommandContext(
            user_id=user_id,
            username=username,
            session_id=session_id,
            permissions=permissions,
            caller=caller,
            game_state=game_state
        )
    
    def _load_user_object(self, user_id: str):
        try:
            session = SessionLocal()
            user_node = session.query(Node).filter(
                Node.id == int(user_id),
                Node.type_code == 'account',
                Node.is_active == True).first()
            return User.from_node(user_node)
        except Exception as e:
            logger.error(f"加载用户对象失败: {e}")
            return None
        finally:
            session.close()