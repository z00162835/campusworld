"""
命令注册表
管理所有命令的注册、查找和分类
"""

from typing import Dict, List, Optional, Set, Any
from .base import BaseCommand, CommandContext, CommandType
from app.core.log import get_logger, LoggerNames

class CommandRegistry:
    """命令注册表 - 协议无关"""
    
    def __init__(self):
        self.logger = get_logger(LoggerNames.COMMAND)
        self.commands: Dict[str, BaseCommand] = {}
        self.aliases: Dict[str, str] = {}
        self.commands_by_type: Dict[CommandType, List[BaseCommand]] = {
            CommandType.SYSTEM: [],
            CommandType.GAME: [],
            CommandType.ADMIN: []
        }
        self.command_groups: Dict[str, List[BaseCommand]] = {}
    
    def register_command(self, command: BaseCommand) -> bool:
        """注册命令"""
        try:
            # 验证命令
            if not isinstance(command, BaseCommand):
                self.logger.error(f"无效的命令类型: {type(command)}")
                return False
            
            if not command.name:
                self.logger.error("命令名称不能为空")
                return False
            
            # 检查命令名是否已存在
            if command.name in self.commands:
                self.logger.warning(f"命令 '{command.name}' 已存在，将被覆盖")
            
            # 注册主命令名
            self.commands[command.name] = command
            
            # 注册别名
            for alias in command.aliases:
                if alias in self.aliases and self.aliases[alias] != command.name:
                    self.logger.warning(f"别名 '{alias}' 已被命令 '{self.aliases[alias]}' 使用")
                else:
                    self.aliases[alias] = command.name
            
            # 按类型分类
            self.commands_by_type[command.command_type].append(command)
            
            # 按组分类
            if hasattr(command, 'group') and command.group:
                group = command.group
                if group not in self.command_groups:
                    self.command_groups[group] = []
                self.command_groups[group].append(command)
            
            self.logger.info(f"命令 '{command.name}' 注册成功 (类型: {command.command_type.value})")
            return True
            
        except Exception as e:
            self.logger.error(f"注册命令 '{command.name}' 失败: {e}")
            return False
    
    def unregister_command(self, command_name: str) -> bool:
        """注销命令"""
        try:
            if command_name not in self.commands:
                self.logger.warning(f"命令 '{command_name}' 未注册")
                return True
            
            command = self.commands[command_name]
            
            # 移除别名
            for alias in command.aliases:
                if alias in self.aliases and self.aliases[alias] == command_name:
                    del self.aliases[alias]
            
            # 从类型分类中移除
            if command in self.commands_by_type[command.command_type]:
                self.commands_by_type[command.command_type].remove(command)
            
            # 从组分类中移除
            if hasattr(command, 'group') and command.group:
                group = command.group
                if group in self.command_groups and command in self.command_groups[group]:
                    self.command_groups[group].remove(command)
            
            # 移除命令
            del self.commands[command_name]
            
            self.logger.info(f"命令 '{command_name}' 已注销")
            return True
            
        except Exception as e:
            self.logger.error(f"注销命令 '{command_name}' 失败: {e}")
            return False
    
    def get_command(self, name: str) -> Optional[BaseCommand]:
        """获取命令"""
        # 检查别名
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
            if command.check_permission(context):
                available_commands.append(command)
        
        return available_commands
    
    def search_commands(self, keyword: str, context: Optional[CommandContext] = None) -> List[BaseCommand]:
        """搜索命令"""
        results = []
        keyword = keyword.lower()
        
        commands_to_search = self.get_available_commands(context) if context else self.get_all_commands()
        
        for command in commands_to_search:
            if (keyword in command.name.lower() or 
                keyword in command.description.lower() or
                any(keyword in alias.lower() for alias in command.aliases)):
                results.append(command)
        
        return results
    
    def get_command_help(self, command_name: str) -> Optional[str]:
        """获取命令帮助"""
        command = self.get_command(command_name)
        if command:
            return command.get_detailed_help()
        return None
    
    def get_commands_summary(self, context: Optional[CommandContext] = None) -> Dict[str, Any]:
        """获取命令摘要"""
        commands = self.get_available_commands(context) if context else self.get_all_commands()
        
        summary = {
            "total_commands": len(commands),
            "by_type": {},
            "by_group": {}
        }
        
        # 按类型统计
        for cmd_type in CommandType:
            type_commands = [cmd for cmd in commands if cmd.command_type == cmd_type]
            summary["by_type"][cmd_type.value] = len(type_commands)
        
        # 按组统计
        for group, group_commands in self.command_groups.items():
            available_group_commands = [cmd for cmd in group_commands if cmd in commands]
            summary["by_group"][group] = len(available_group_commands)
        
        return summary


# 全局命令注册表实例
command_registry = CommandRegistry()
