"""
抽象命令基类
基于单一职责原则，命令与协议无关
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class CommandType(Enum):
    """命令类型枚举"""
    SYSTEM = "system"
    GAME = "game"
    ADMIN = "admin"


@dataclass
class CommandContext:
    """命令执行上下文"""
    user_id: str
    session_id: str
    permissions: List[str]
    game_state: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def has_permission(self, permission: str) -> bool:
        """检查是否有指定权限"""
        return permission in self.permissions
    
    def get_game_state(self, key: str, default: Any = None) -> Any:
        """获取游戏状态"""
        if not self.game_state:
            return default
        return self.game_state.get(key, default)


@dataclass
class CommandResult:
    """命令执行结果"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    command_type: Optional[CommandType] = None
    
    @classmethod
    def success_result(cls, message: str, data: Optional[Dict[str, Any]] = None, 
                      command_type: Optional[CommandType] = None) -> 'CommandResult':
        return cls(success=True, message=message, data=data, command_type=command_type)
    
    @classmethod
    def error_result(cls, message: str, error: Optional[str] = None, 
                    command_type: Optional[CommandType] = None) -> 'CommandResult':
        return cls(success=False, message=message, error=error, command_type=command_type)


class BaseCommand(ABC):
    """抽象命令基类 - 协议无关"""
    
    def __init__(self, name: str, description: str = "", aliases: List[str] = None,
                 command_type: CommandType = CommandType.SYSTEM):
        self.name = name
        self.description = description
        self.aliases = aliases or []
        self.command_type = command_type
        self.logger = logging.getLogger(f"command.{name}")
    
    @abstractmethod
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        """执行命令 - 子类必须实现"""
        pass
    
    def validate_args(self, args: List[str]) -> bool:
        """验证参数 - 子类可重写"""
        return True
    
    def check_permission(self, context: CommandContext) -> bool:
        """检查权限 - 子类可重写"""
        return True
    
    def get_help(self) -> str:
        """获取帮助信息"""
        return f"{self.name}: {self.description}"
    
    def get_usage(self) -> str:
        """获取使用说明"""
        return f"Usage: {self.name} [options]"
    
    def get_detailed_help(self) -> str:
        """获取详细帮助信息"""
        help_text = f"""
{self.name} 命令帮助
{'=' * (len(self.name) + 8)}

描述: {self.description}
类型: {self.command_type.value}
用法: {self.get_usage()}
"""
        
        if self.aliases:
            help_text += f"别名: {', '.join(self.aliases)}\n"
        
        help_text += self._get_specific_help()
        return help_text.strip()
    
    def _get_specific_help(self) -> str:
        """获取特定帮助信息 - 子类可重写"""
        return ""


class SystemCommand(BaseCommand):
    """系统命令基类"""
    
    def __init__(self, name: str, description: str = "", aliases: List[str] = None,
                 required_permission: str = None):
        super().__init__(name, description, aliases, CommandType.SYSTEM)
        self.required_permission = required_permission
    
    def check_permission(self, context: CommandContext) -> bool:
        """检查系统权限"""
        if not self.required_permission:
            return True
        return context.has_permission(self.required_permission)


class GameCommand(BaseCommand):
    """游戏命令基类"""
    
    def __init__(self, name: str, description: str = "", aliases: List[str] = None,
                 game_name: str = ""):
        super().__init__(name, description, aliases, CommandType.GAME)
        self.game_name = game_name
        self.required_permission = f"game.{game_name}"
    
    def check_permission(self, context: CommandContext) -> bool:
        """检查游戏权限"""
        if not self.required_permission:
            return True
        return context.has_permission(self.required_permission)
    
    def is_game_running(self, context: CommandContext) -> bool:
        """检查游戏是否运行"""
        return context.get_game_state('is_running', False)
    
    def get_game_info(self, context: CommandContext) -> Dict[str, Any]:
        """获取游戏信息"""
        return context.get_game_state('game_info', {})


class AdminCommand(BaseCommand):
    """管理员命令基类"""
    
    def __init__(self, name: str, description: str = "", aliases: List[str] = None,
                 required_permission: str = "admin"):
        super().__init__(name, description, aliases, CommandType.ADMIN)
        self.required_permission = required_permission
    
    def check_permission(self, context: CommandContext) -> bool:
        """检查管理员权限"""
        return context.has_permission(self.required_permission)

