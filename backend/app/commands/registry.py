"""
命令注册表
管理所有命令的注册、查找和分类
"""
from typing import Dict, List, Optional, Set, Any
from .base import BaseCommand, CommandContext, CommandType
from .policy import CommandPolicyEvaluator, AuthzDecision
from app.core.log import get_logger, LoggerNames

class CommandRegistry:
    """命令注册表 - 协议无关"""

    def __init__(self):
        self.logger = get_logger(LoggerNames.COMMAND)
        self.commands: Dict[str, BaseCommand] = {}
        self.aliases: Dict[str, str] = {}
        self.policy_evaluator = CommandPolicyEvaluator()
        self.commands_by_type: Dict[CommandType, List[BaseCommand]] = {CommandType.SYSTEM: [], CommandType.GAME: [], CommandType.ADMIN: []}
        self.command_groups: Dict[str, List[BaseCommand]] = {}

    def validate_command_tokens(self, command: BaseCommand, *, reserved_tokens: Optional[Set[str]]=None, allow_replace: bool=True) -> bool:
        """Validate that command name and aliases share one unambiguous input namespace."""
        if not isinstance(command, BaseCommand):
            self.logger.error(f'Invalid command type: {type(command)}')
            return False
        if not command.name:
            self.logger.error('Command name must not be empty')
            return False
        reserved_tokens = reserved_tokens or set()
        if command.name in reserved_tokens:
            self.logger.error(f"Command token '{command.name}' is already reserved in current batch")
            return False
        if command.name in self.commands and (not allow_replace):
            self.logger.error(f"Command name '{command.name}' already registered")
            return False
        alias_owner = self.aliases.get(command.name)
        if alias_owner and (alias_owner != command.name or not allow_replace):
            self.logger.error(f"Command name '{command.name}' collides with alias owned by '{alias_owner}'")
            return False
        command_tokens: Set[str] = {command.name}
        for alias in command.aliases:
            if not alias:
                self.logger.error(f"Command '{command.name}' has empty alias")
                return False
            if alias == command.name:
                self.logger.error(f"Command '{command.name}' alias equals command name: {alias}")
                return False
            if alias in command_tokens:
                self.logger.error(f"Command '{command.name}' has duplicate token: {alias}")
                return False
            if alias in reserved_tokens:
                self.logger.error(f"Command token '{alias}' is already reserved in current batch")
                return False
            if alias in self.commands:
                self.logger.error(f"Command '{command.name}' alias '{alias}' collides with registered command name")
                return False
            owner = self.aliases.get(alias)
            if owner and owner != command.name:
                self.logger.error(f"Command '{command.name}' alias '{alias}' collides with alias owned by '{owner}'")
                return False
            command_tokens.add(alias)
        return True

    def register_command(self, command: BaseCommand) -> bool:
        """注册命令"""
        try:
            if not self.validate_command_tokens(command):
                return False
            if command.name in self.commands:
                self.unregister_command(command.name)
            self.commands[command.name] = command
            for alias in command.aliases:
                if alias in self.aliases and self.aliases[alias] != command.name:
                    self.logger.warning(f"Alias '{alias}' already has command '{self.aliases[alias]}' using")
                else:
                    self.aliases[alias] = command.name
            self.commands_by_type[command.command_type].append(command)
            if hasattr(command, 'group') and command.group:
                group = command.group
                if group not in self.command_groups:
                    self.command_groups[group] = []
                self.command_groups[group].append(command)
            return True
        except Exception as e:
            self.logger.error(f"Register command '{command.name}' failed: {e}")
            return False

    def unregister_command(self, command_name: str) -> bool:
        """注销命令"""
        try:
            if command_name not in self.commands:
                self.logger.warning(f"command '{command_name}' not registered")
                return True
            command = self.commands[command_name]
            for alias in command.aliases:
                if alias in self.aliases and self.aliases[alias] == command_name:
                    del self.aliases[alias]
            if command in self.commands_by_type[command.command_type]:
                self.commands_by_type[command.command_type].remove(command)
            if hasattr(command, 'group') and command.group:
                group = command.group
                if group in self.command_groups and command in self.command_groups[group]:
                    self.command_groups[group].remove(command)
            del self.commands[command_name]
            return True
        except Exception as e:
            self.logger.error(f"Unregister command '{command_name}' failed: {e}")
            return False

    def get_command(self, name: str) -> Optional[BaseCommand]:
        """获取命令"""
        if name in self.aliases:
            name = self.aliases[name]
        return self.commands.get(name)

    def get_commands_by_type(self, command_type: CommandType) -> List[BaseCommand]:
        """获取指定类型的命令"""
        return self.commands_by_type.get(command_type, [])

    def get_commands_by_group(self, group: str) -> List[BaseCommand]:
        """获取指定组的命令"""
        return self.command_groups.get(group, [])

    def get_all_commands(self) -> List[BaseCommand]:
        """获取所有命令"""
        return list(self.commands.values())

    def get_available_commands(self, context: CommandContext) -> List[BaseCommand]:
        """获取用户可用的命令"""
        available_commands = []
        for command in self.commands.values():
            decision = self.policy_evaluator.evaluate(command, context)
            if decision.allowed:
                available_commands.append(command)
        return available_commands

    def authorize_command(self, command: BaseCommand, context: CommandContext) -> AuthzDecision:
        return self.policy_evaluator.evaluate(command, context)

    def execute(self, command_name: str, context: CommandContext, args: List[str]):
        command = self.get_command(command_name)
        if not command:
            return None
        decision = self.authorize_command(command, context)
        if not decision.allowed:
            return None
        return command.execute(context, args)

    @staticmethod
    def _search_blob_for_locale(command: BaseCommand, locale: str) -> str:
        """Match plan D5-C: name + aliases + the one-line description for ``locale`` only (not other languages)."""
        parts: List[str] = [command.name.lower()]
        for a in command.aliases or []:
            parts.append(str(a).lower())
        try:
            loc_desc = (command.get_localized_description(locale) or '').lower()
        except Exception:
            loc_desc = (command.description or '').lower()
        parts.append(loc_desc)
        return ' '.join(parts)

    def search_commands(self, keyword: str, context: Optional[CommandContext]=None) -> List[BaseCommand]:
        """搜索命令（有 ``context`` 时仅匹配该上下文字符串下的展示描述，与 help 语言一致）。"""
        from app.commands.i18n.locale_text import DEFAULT_LOCALE, resolve_locale
        results = []
        keyword = keyword.lower()
        loc = resolve_locale(context) if context is not None else DEFAULT_LOCALE
        commands_to_search = self.get_available_commands(context) if context else self.get_all_commands()
        for command in commands_to_search:
            if keyword in self._search_blob_for_locale(command, loc):
                results.append(command)
        return results

    def get_command_help(self, command_name: str, context: Optional[CommandContext]=None) -> Optional[str]:
        """获取命令帮助; 传入 ``context`` 时按该上下文的语言输出。"""
        command = self.get_command(command_name)
        if command:
            if context is not None:
                from app.commands.i18n.locale_text import resolve_locale
                return command.get_detailed_help_for_locale(resolve_locale(context))
            return command.get_detailed_help()
        return None

    def get_commands_summary(self, context: Optional[CommandContext]=None) -> Dict[str, Any]:
        """获取命令摘要"""
        commands = self.get_available_commands(context) if context else self.get_all_commands()
        summary = {'total_commands': len(commands), 'by_type': {}, 'by_group': {}}
        for cmd_type in CommandType:
            type_commands = [cmd for cmd in commands if cmd.command_type == cmd_type]
            summary['by_type'][cmd_type.value] = len(type_commands)
        for (group, group_commands) in self.command_groups.items():
            available_group_commands = [cmd for cmd in group_commands if cmd in commands]
            summary['by_group'][group] = len(available_group_commands)
        return summary
command_registry = CommandRegistry()
