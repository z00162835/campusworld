"""
抽象命令基类
基于单一职责原则，命令与协议无关
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from app.core.log import get_logger, LoggerNames

class CommandType(Enum):
    """命令类型枚举"""
    SYSTEM = "system"
    GAME = "game"
    ADMIN = "admin"


@dataclass
class CommandContext:
    """命令执行上下文"""
    user_id: str
    username: str
    session_id: str
    permissions: List[str]
    session: Optional[Any] = None
    caller: Optional[str] = None
    game_state: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    db_session: Optional[Any] = None
    roles: List[str] = field(default_factory=list)

    def get_caller(self):
        if self.caller is None and self.session:
            if hasattr(self.session, 'user_object'):
                self.caller = self.session.user_object
            elif hasattr(self.session, '_load_user_object'):
                self.caller = self.session._load_user_object()
        return self.caller
    
    def has_permission(self, permission: str) -> bool:
        """检查是否有指定权限"""
        return permission in self.permissions
    
    def get_game_state(self, key: str, default: Any = None) -> Any:
        """获取场景状态"""
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
    should_exit: bool = False
    
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
        self.logger = get_logger(LoggerNames.COMMAND)
    
    @abstractmethod
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        """执行命令 - 子类必须实现"""
        pass
    
    def validate_args(self, args: List[str]) -> bool:
        """验证参数 - 子类可重写"""
        return True
    
    def get_help(self) -> str:
        """获取帮助信息"""
        return f"{self.name}: {self.description}"
    
    def get_usage(self) -> str:
        """获取使用说明"""
        return f"{self.name} [options]"
    
    def get_localized_description(self, locale: str) -> str:
        """One-line description: centralized YAML in ``i18n/locales/`` first, then legacy table, then ``description``."""
        from app.commands.i18n.command_resource import get_localized_string_from_resource
        from app.commands.i18n.locale_text import FALLBACK_CHAIN, pick_i18n, normalize_locale

        loc = normalize_locale(locale)
        from_resource = get_localized_string_from_resource(self.name, "description", loc)
        if from_resource:
            return from_resource
        i18n = getattr(self, "description_i18n", None)
        if isinstance(i18n, dict) and i18n:
            return pick_i18n(i18n, loc, fallbacks=FALLBACK_CHAIN, legacy_default=self.description).value
        return self.description

    def get_localized_usage(self, locale: str) -> str:
        from app.commands.i18n.locale_text import FALLBACK_CHAIN, pick_i18n, normalize_locale

        loc = normalize_locale(locale)
        i18n = getattr(self, "usage_i18n", None)
        if isinstance(i18n, dict) and i18n:
            return pick_i18n(i18n, loc, fallbacks=FALLBACK_CHAIN, legacy_default=self.get_usage()).value
        return self.get_usage()

    def get_detailed_help(self) -> str:
        """Default detailed help (``zh-CN`` shell); prefer :meth:`get_detailed_help_for_locale` when a locale is known."""
        from app.commands.i18n.locale_text import DEFAULT_LOCALE

        return self.get_detailed_help_for_locale(DEFAULT_LOCALE)

    def get_detailed_help_for_locale(self, locale: str) -> str:
        from app.commands.i18n.locale_text import help_shell_for_locale, normalize_locale

        loc = normalize_locale(locale)
        shell = help_shell_for_locale(loc)
        title = shell["title_detail"].format(name=self.name)
        sep = "=" * max(8, len(title))
        help_text = f"""
{title}
{sep}
{shell["line_description"].format(text=self.get_localized_description(loc))}
{shell["line_type"].format(text=self.command_type.value)}
{shell["line_usage"].format(text=self.get_localized_usage(loc))}
"""
        if self.aliases:
            help_text += shell["line_aliases"].format(items=", ".join(self.aliases)) + "\n"
        help_text += self._get_specific_help()
        return help_text.strip()
    
    def _get_specific_help(self) -> str:
        """获取特定帮助信息 - 子类可重写"""
        return ""


class SystemCommand(BaseCommand):
    """系统命令基类"""
    
    def __init__(self, name: str, description: str = "", aliases: List[str] = None):
        super().__init__(name, description, aliases, CommandType.SYSTEM)


class GameCommand(BaseCommand):
    """场景命令基类"""
    
    def __init__(self, name: str, description: str = "", aliases: List[str] = None,
                 game_name: str = ""):
        super().__init__(name, description, aliases, CommandType.GAME)
        self.game_name = game_name
    
    def is_game_running(self, context: CommandContext) -> bool:
        """检查场景是否运行"""
        return context.get_game_state('is_running', False)
    
    def get_game_info(self, context: CommandContext) -> Dict[str, Any]:
        """获取场景信息"""
        return context.get_game_state('game_info', {})


class AdminCommand(BaseCommand):
    """管理员命令基类"""
    
    def __init__(self, name: str, description: str = "", aliases: List[str] = None):
        super().__init__(name, description, aliases, CommandType.ADMIN)

