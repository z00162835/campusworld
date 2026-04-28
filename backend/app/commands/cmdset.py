# 文件：app/commands/cmdset.py
"""
命令集合系统 - 扩展现有命令系统

基于现有CommandRegistry，添加Evennia式的CmdSet机制
"""

from typing import Dict, List, Optional, Any, Set
from abc import ABC, abstractmethod
from .base import BaseCommand, CommandResult, CommandContext, CommandType
from .registry import command_registry
from app.core.log import get_logger, LoggerNames


class CmdSet(ABC):
    """
    命令集合基类 - 参考Evennia设计
    
    每个对象都有自己的命令集合，管理该对象可执行的命令
    与现有CommandRegistry兼容
    """
    
    def __init__(self):
        self.commands: Dict[str, BaseCommand] = {}
        self.aliases: Dict[str, str] = {}
        self.priority = 0  # 优先级，数字越大优先级越高
        self.duplicates = False  # 是否允许重复命令
        self.logger = get_logger(LoggerNames.COMMAND)
    
    def add_command(self, command: BaseCommand) -> bool:
        """添加命令到集合"""
        try:
            # 检查是否已存在
            if command.name in self.commands and not self.duplicates:
                self.logger.warning(f"命令 '{command.name}' 已存在，跳过添加")
                return False
            
            # 添加主命令
            self.commands[command.name] = command
            
            # 添加别名
            for alias in command.aliases:
                if alias not in self.aliases:
                    self.aliases[alias] = command.name
            
            return True
        except Exception as e:
            self.logger.error(f"添加命令 '{command.name}' 失败: {e}")
            return False
    
    def remove_command(self, command_name: str) -> bool:
        """从集合移除命令"""
        if command_name in self.commands:
            command = self.commands[command_name]
            
            # 移除主命令
            del self.commands[command_name]
            
            # 移除别名
            aliases_to_remove = [alias for alias, cmd_name in self.aliases.items() 
                               if cmd_name == command_name]
            for alias in aliases_to_remove:
                del self.aliases[alias]
            
            return True
        return False
    
    def get_command(self, command_name: str) -> Optional[BaseCommand]:
        """获取命令"""
        # 先检查主命令
        if command_name in self.commands:
            return self.commands[command_name]
        
        # 再检查别名
        if command_name in self.aliases:
            actual_name = self.aliases[command_name]
            return self.commands.get(actual_name)
        
        return None
    
    def has_command(self, command_name: str) -> bool:
        """检查是否有命令"""
        return self.get_command(command_name) is not None
    
    def get_commands(self) -> Dict[str, BaseCommand]:
        """获取所有命令"""
        return self.commands.copy()
    
    def get_command_names(self) -> List[str]:
        """获取所有命令名称"""
        return list(self.commands.keys())
    
    def get_aliases(self) -> Dict[str, str]:
        """获取所有别名"""
        return self.aliases.copy()
    
    def clear(self):
        """清空命令集合"""
        self.commands.clear()
        self.aliases.clear()
        self.logger.debug("CmdSet已清空")
    
    def merge(self, other_cmdset: 'CmdSet') -> bool:
        """合并另一个命令集合"""
        try:
            for command_name, command in other_cmdset.get_commands().items():
                self.add_command(command)
            return True
        except Exception as e:
            self.logger.error(f"合并CmdSet失败: {e}")
            return False


class DefaultCmdSet(CmdSet):
    """
    默认命令集合
    
    包含所有对象都有的基础命令
    """
    
    def __init__(self):
        super().__init__()
        self.priority = 0
        self._init_default_commands()
    
    def _init_default_commands(self):
        """初始化默认命令"""
        # 添加一些基础命令
        pass


class CharacterCmdSet(CmdSet):
    """
    角色命令集合
    
    包含角色特有的命令
    """
    
    def __init__(self):
        super().__init__()
        self.priority = 10
        self._init_character_commands()
    
    def _init_character_commands(self):
        """初始化角色命令"""
        from .character import CHARACTER_COMMANDS
        
        for command in CHARACTER_COMMANDS:
            self.add_command(command)


class PlayerCmdSet(CmdSet):
    """
    玩家命令集合
    
    包含玩家特有的命令
    """
    
    def __init__(self):
        super().__init__()
        self.priority = 20
        self._init_player_commands()
    
    def _init_player_commands(self):
        """初始化玩家命令"""
        # 玩家特有命令
        pass


class NPCCmdSet(CmdSet):
    """
    NPC命令集合
    
    包含NPC特有的命令
    """
    
    def __init__(self):
        super().__init__()
        self.priority = 15
        self._init_npc_commands()
    
    def _init_npc_commands(self):
        """初始化NPC命令"""
        # NPC特有命令
        pass


class CmdSetManager:
    """
    命令集合管理器
    
    管理对象的命令集合，支持优先级和合并
    与现有CommandRegistry兼容
    """
    
    def __init__(self):
        self.cmdset_stack: List[CmdSet] = []
        self.logger = get_logger(LoggerNames.COMMAND)
    
    def add_cmdset(self, cmdset: CmdSet):
        """添加命令集合"""
        # 按优先级插入
        inserted = False
        for i, existing_cmdset in enumerate(self.cmdset_stack):
            if cmdset.priority > existing_cmdset.priority:
                self.cmdset_stack.insert(i, cmdset)
                inserted = True
                break
        
        if not inserted:
            self.cmdset_stack.append(cmdset)
        
    
    def remove_cmdset(self, cmdset: CmdSet):
        """移除命令集合"""
        if cmdset in self.cmdset_stack:
            self.cmdset_stack.remove(cmdset)
    
    def get_command(self, command_name: str) -> Optional[BaseCommand]:
        """获取命令（按优先级查找）"""
        for cmdset in self.cmdset_stack:
            command = cmdset.get_command(command_name)
            if command:
                return command
        return None
    
    def has_command(self, command_name: str) -> bool:
        """检查是否有命令"""
        return self.get_command(command_name) is not None
    
    def get_all_commands(self) -> Dict[str, BaseCommand]:
        """获取所有命令"""
        all_commands = {}
        for cmdset in self.cmdset_stack:
            all_commands.update(cmdset.get_commands())
        return all_commands
    
    def get_commands_by_priority(self) -> List[BaseCommand]:
        """按优先级获取所有命令"""
        commands = []
        for cmdset in self.cmdset_stack:
            commands.extend(cmdset.get_commands().values())
        return commands
    
    def clear(self):
        """清空所有命令集合"""
        self.cmdset_stack.clear()
        self.logger.debug("所有CmdSet已清空")
    
    def get_cmdset_info(self) -> Dict[str, Any]:
        """获取CmdSet信息"""
        return {
            'total_cmdsets': len(self.cmdset_stack),
            'total_commands': len(self.get_all_commands()),
            'cmdsets': [
                {
                    'name': cmdset.__class__.__name__,
                    'priority': cmdset.priority,
                    'commands': len(cmdset.get_commands())
                }
                for cmdset in self.cmdset_stack
            ]
        }
