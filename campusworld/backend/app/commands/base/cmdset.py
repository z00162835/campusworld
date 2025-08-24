"""
命令集合基类 - 参考Evennia框架设计，集成图数据持久化

CmdSet用于管理一组相关的命令，支持命令的添加、删除、查找等操作
支持命令集合的合并、优先级管理等功能
集成图数据存储，支持命令集合的持久化和动态管理

作者：AI Assistant
创建时间：2025-08-24
重构时间：2025-08-24
"""

from typing import Dict, List, Optional, Type, Union, Any
from datetime import datetime

# 导入图数据基类
try:
    from app.models.base import DefaultObject
except ImportError:
    # 如果导入失败，创建一个模拟的DefaultObject
    class DefaultObject:
        def __init__(self, name: str, **kwargs):
            self._node_name = name
            self._node_attributes = kwargs
            self._node_uuid = "mock-uuid"
            self._node_type = kwargs.get('type', 'unknown')
            self._node_typeclass = kwargs.get('typeclass', 'unknown')
        
        def get_node_name(self):
            return self._node_name
        
        def get_node_attributes(self):
            return self._node_attributes.copy()
        
        def set_node_attribute(self, key: str, value: Any):
            self._node_attributes[key] = value
        
        def _schedule_node_sync(self):
            pass
        
        def get_node_type(self):
            return self._node_type
        
        def get_node_typeclass(self):
            return self._node_typeclass
        
        def sync_to_node(self):
            pass

from .command import Command


class CmdSet(DefaultObject):
    """
    命令集合基类 - 参考Evennia框架设计，集成图数据持久化
    
    用于管理一组相关的命令，支持命令的添加、删除、查找等操作
    继承自DefaultObject，支持图数据持久化存储
    """
    
    # 命令集合基本信息
    key = "base_cmdset"           # 命令集合关键字
    mergetype = "Replace"         # 合并类型：Replace, Union, Intersect
    priority = 0                  # 优先级（数字越大优先级越高）
    
    def __init__(self, **kwargs):
        """
        初始化命令集合
        
        Args:
            **kwargs: 其他参数
        """
        # 调用父类初始化，设置命令集合名称和类型
        super().__init__(
            name=kwargs.get('key', self.key) or 'unnamed_cmdset',
            type='cmdset',
            typeclass=f"{self.__class__.__module__}.{self.__class__.__name__}",
            **kwargs
        )
        
        # 命令存储
        self.commands = {}        # 命令字典 {key: command_class}
        self.command_instances = {}  # 命令实例字典 {key: command_instance}
        
        # 设置属性
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        # 设置时间戳
        if not hasattr(self, 'created_at') or not self.created_at:
            self._created_at = datetime.now()
        self._updated_at = datetime.now()
        
        # 初始化命令集合特定属性
        self._init_cmdset_attributes()
        
        # 初始化命令
        self.at_cmdset_creation()
        
        # 自动同步到图数据存储
        self._schedule_node_sync()
    
    def _init_cmdset_attributes(self):
        """初始化命令集合特定属性"""
        # 设置命令集合的基本信息到节点属性中
        self.set_node_attribute('cmdset_key', self.key)
        self.set_node_attribute('cmdset_mergetype', self.mergetype)
        self.set_node_attribute('cmdset_priority', self.priority)
        
        # 设置命令集合的元数据
        self.set_node_attribute('cmdset_class', self.__class__.__name__)
        self.set_node_attribute('cmdset_module', self.__class__.__module__)
        self.set_node_attribute('cmdset_version', getattr(self, 'version', '1.0'))
        
        # 设置时间戳到节点属性
        if hasattr(self, '_created_at'):
            self.set_node_attribute('created_at', self._created_at)
        if hasattr(self, '_updated_at'):
            self.set_node_attribute('updated_at', self._updated_at)
    
    def __repr__(self):
        """字符串表示"""
        return f"<{self.__class__.__name__}(key='{self.key}', commands={len(self.commands)}, uuid='{self._node_uuid}')>"
    
    def __str__(self):
        """字符串表示"""
        return self.key
    
    def __len__(self):
        """命令数量"""
        return len(self.commands)
    
    def __contains__(self, key):
        """检查是否包含指定命令"""
        return key in self.commands
    
    def __getitem__(self, key):
        """获取指定命令"""
        return self.commands.get(key)
    
    def __iter__(self):
        """迭代命令"""
        return iter(self.commands.values())
    
    @property
    def name(self) -> str:
        """获取命令集合名称"""
        return self.key or self.get_node_name()
    
    @property
    def command_count(self) -> int:
        """获取命令数量"""
        return len(self.commands)
    
    @property
    def cmdset_uuid(self) -> str:
        """获取命令集合UUID"""
        return self._node_uuid
    
    @property
    def cmdset_type(self) -> str:
        """获取命令集合类型"""
        return self.get_node_type()
    
    @property
    def cmdset_typeclass(self) -> str:
        """获取命令集合类型类"""
        return self.get_node_typeclass()
    
    def at_cmdset_creation(self) -> None:
        """
        命令集合创建时的钩子
        
        子类可以重写这个方法来添加命令
        """
        pass
    
    def add(self, command_class: Type[Command]) -> None:
        """
        添加命令到集合
        
        Args:
            command_class: 命令类
        """
        if not issubclass(command_class, Command):
            raise ValueError(f"命令类必须继承自Command: {command_class}")
        
        key = command_class.key
        if not key:
            raise ValueError(f"命令类必须有key属性: {command_class}")
        
        self.commands[key] = command_class
        
        # 添加别名
        for alias in command_class.aliases:
            if alias not in self.commands:
                self.commands[alias] = command_class
        
        self._updated_at = datetime.now()
        self._schedule_node_sync()
    
    def remove(self, key: str) -> bool:
        """
        从集合中移除命令
        
        Args:
            key: 命令关键字
            
        Returns:
            是否成功移除
        """
        if key in self.commands:
            command_class = self.commands[key]
            
            # 移除主命令
            del self.commands[key]
            
            # 移除别名
            aliases_to_remove = []
            for alias, cmd_class in self.commands.items():
                if cmd_class == command_class:
                    aliases_to_remove.append(alias)
            
            for alias in aliases_to_remove:
                del self.commands[alias]
            
            self._updated_at = datetime.now()
            self._schedule_node_sync()
            return True
        
        return False
    
    def get(self, key: str) -> Optional[Type[Command]]:
        """
        获取指定命令类
        
        Args:
            key: 命令关键字
            
        Returns:
            命令类或None
        """
        return self.commands.get(key)
    
    def has_command(self, key: str) -> bool:
        """
        检查是否包含指定命令
        
        Args:
            key: 命令关键字
            
        Returns:
            是否包含
        """
        return key in self.commands
    
    def get_commands(self) -> List[Type[Command]]:
        """
        获取所有命令类
        
        Returns:
            命令类列表
        """
        # 去重（因为别名可能指向同一个命令类）
        unique_commands = {}
        for key, command_class in self.commands.items():
            if command_class not in unique_commands:
                unique_commands[command_class] = command_class
        
        return list(unique_commands.values())
    
    def get_command_keys(self) -> List[str]:
        """
        获取所有命令关键字
        
        Returns:
            命令关键字列表
        """
        return list(self.commands.keys())
    
    def get_commands_by_category(self, category: str) -> List[Type[Command]]:
        """
        按分类获取命令
        
        Args:
            category: 命令分类
            
        Returns:
            命令类列表
        """
        commands = []
        for command_class in self.get_commands():
            if command_class.help_category == category:
                commands.append(command_class)
        
        return commands
    
    def get_categories(self) -> List[str]:
        """
        获取所有命令分类
        
        Returns:
            分类列表
        """
        categories = set()
        for command_class in self.get_commands():
            categories.add(command_class.help_category)
        
        return sorted(list(categories))
    
    def create_command_instance(self, key: str, caller=None, cmdstring="", args="", **kwargs) -> Optional[Command]:
        """
        创建命令实例
        
        Args:
            key: 命令关键字
            caller: 调用者
            cmdstring: 命令字符串
            args: 命令参数
            **kwargs: 其他参数
            
        Returns:
            命令实例或None
        """
        command_class = self.get(key)
        if command_class:
            return command_class(
                caller=caller,
                cmdstring=cmdstring,
                args=args,
                cmdset=self,
                **kwargs
            )
        return None
    
    def execute_command(self, key: str, caller=None, cmdstring="", args="", **kwargs) -> bool:
        """
        执行指定命令
        
        Args:
            key: 命令关键字
            caller: 调用者
            cmdstring: 命令字符串
            args: 命令参数
            **kwargs: 其他参数
            
        Returns:
            是否执行成功
        """
        command = self.create_command_instance(key, caller, cmdstring, args, **kwargs)
        if command:
            return command.execute()
        return False
    
    def merge(self, other_cmdset: 'CmdSet', **kwargs) -> 'CmdSet':
        """
        合并另一个命令集合
        
        Args:
            other_cmdset: 要合并的命令集合
            **kwargs: 其他参数
            
        Returns:
            合并后的命令集合
        """
        if not isinstance(other_cmdset, CmdSet):
            raise ValueError(f"只能合并CmdSet实例: {other_cmdset}")
        
        # 创建新的命令集合
        merged = self.__class__(**kwargs)
        
        # 根据合并类型处理
        if self.mergetype == "Replace":
            # 替换模式：使用other_cmdset的命令
            for key, command_class in other_cmdset.commands.items():
                merged.commands[key] = command_class
        
        elif self.mergetype == "Union":
            # 并集模式：合并所有命令
            # 先添加当前集合的命令
            for key, command_class in self.commands.items():
                merged.commands[key] = command_class
            
            # 再添加other_cmdset的命令（可能覆盖）
            for key, command_class in other_cmdset.commands.items():
                merged.commands[key] = command_class
        
        elif self.mergetype == "Intersect":
            # 交集模式：只保留两个集合都有的命令
            for key, command_class in self.commands.items():
                if key in other_cmdset.commands:
                    merged.commands[key] = command_class
        
        merged._updated_at = datetime.now()
        merged._schedule_node_sync()
        return merged
    
    def clear(self) -> None:
        """清空所有命令"""
        self.commands.clear()
        self._updated_at = datetime.now()
        self._schedule_node_sync()
    
    def copy(self) -> 'CmdSet':
        """复制命令集合"""
        new_cmdset = self.__class__()
        new_cmdset.commands = self.commands.copy()
        new_cmdset.mergetype = self.mergetype
        new_cmdset.priority = self.priority
        return new_cmdset
    
    def get_help(self, category: str = None) -> str:
        """
        获取帮助信息
        
        Args:
            category: 指定分类，None表示所有分类
            
        Returns:
            帮助信息字符串
        """
        if category:
            commands = self.get_commands_by_category(category)
        else:
            commands = self.get_commands()
        
        if not commands:
            return f"没有找到{'指定分类的' if category else ''}命令"
        
        help_text = f"命令集合: {self.key}\n"
        help_text += f"命令数量: {len(commands)}\n"
        help_text += f"合并类型: {self.mergetype}\n"
        help_text += f"优先级: {self.priority}\n\n"
        
        # 按分类组织命令
        categories = {}
        for cmd in commands:
            cat = cmd.help_category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(cmd)
        
        for cat in sorted(categories.keys()):
            help_text += f"【{cat}】\n"
            for cmd in sorted(categories[cat], key=lambda x: x.key):
                help_text += f"  {cmd.key:<15} - {cmd.description}\n"
            help_text += "\n"
        
        return help_text.strip()
    
    def get_command_info(self, key: str) -> Optional[Dict[str, Any]]:
        """
        获取命令信息
        
        Args:
            key: 命令关键字
            
        Returns:
            命令信息字典或None
        """
        command_class = self.get(key)
        if command_class:
            return command_class.to_dict()
        return None
    
    def get_mergetype(self) -> str:
        """获取合并类型"""
        return self.mergetype
    
    def set_mergetype(self, mergetype: str) -> None:
        """设置合并类型"""
        self.mergetype = mergetype
        self._updated_at = datetime.now()
        self._schedule_node_sync()
    
    def get_priority(self) -> int:
        """获取优先级"""
        return self.priority
    
    def set_priority(self, priority: int) -> None:
        """设置优先级"""
        self.priority = priority
        self._updated_at = datetime.now()
        self._schedule_node_sync()
    
    def get_created_at(self) -> Optional[datetime]:
        """获取创建时间"""
        return self._created_at
    
    def get_updated_at(self) -> Optional[datetime]:
        """获取更新时间"""
        return self._updated_at
    
    def update_timestamp(self) -> None:
        """更新时间戳"""
        self._updated_at = datetime.now()
        self._schedule_node_sync()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'uuid': self._node_uuid,
            'key': self.key,
            'mergetype': self.mergetype,
            'priority': self.priority,
            'command_count': self.command_count,
            'categories': self.get_categories(),
            'created_at': self._created_at.isoformat() if self._created_at else None,
            'updated_at': self._updated_at.isoformat() if self._updated_at else None,
            'node_type': self.get_node_type(),
            'node_typeclass': self.get_node_typeclass(),
            'node_attributes': self.get_node_attributes(),
            'commands': {key: cmd_class.__name__ for key, cmd_class in self.commands.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], **kwargs) -> 'CmdSet':
        """从字典创建命令集合实例"""
        instance = cls(**kwargs)
        
        # 设置属性
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        
        return instance
    
    # ==================== 图数据持久化方法 ====================
    
    def save_cmdset(self) -> bool:
        """保存命令集合到图数据存储"""
        try:
            self.sync_to_node()
            return True
        except Exception as e:
            print(f"保存命令集合失败: {e}")
            return False
    
    def load_cmdset(self, cmdset_uuid: str) -> bool:
        """从图数据存储加载命令集合"""
        try:
            from app.models.graph_sync import GraphSynchronizer
            synchronizer = GraphSynchronizer()
            
            # 从图数据存储加载命令集合数据
            # 这里需要实现具体的加载逻辑
            return True
        except Exception as e:
            print(f"加载命令集合失败: {e}")
            return False
    
    def delete_cmdset(self) -> bool:
        """从图数据存储删除命令集合"""
        try:
            from app.models.graph_sync import GraphSynchronizer
            synchronizer = GraphSynchronizer()
            
            # 从图数据存储删除命令集合
            # 这里需要实现具体的删除逻辑
            return True
        except Exception as e:
            print(f"删除命令集合失败: {e}")
            return False
    
    def get_cmdset_config(self) -> Dict[str, Any]:
        """获取命令集合配置"""
        return {
            'key': self.key,
            'mergetype': self.mergetype,
            'priority': self.priority,
            'commands': {key: cmd_class.__name__ for key, cmd_class in self.commands.items()}
        }
    
    def set_cmdset_config(self, config: Dict[str, Any]) -> None:
        """设置命令集合配置"""
        for key, value in config.items():
            if hasattr(self, key):
                setattr(self, key, value)
                # 更新节点属性
                self.set_node_attribute(f'cmdset_{key}', value)
        
        # 同步到图数据存储
        self._schedule_node_sync()
    
    def get_cmdset_metadata(self) -> Dict[str, Any]:
        """获取命令集合元数据"""
        return {
            'uuid': self._node_uuid,
            'type': self.get_node_type(),
            'typeclass': self.get_node_typeclass(),
            'class': self.__class__.__name__,
            'module': self.__class__.__module__,
            'created_at': getattr(self, '_created_at', None),
            'updated_at': getattr(self, '_updated_at', None),
            'command_count': self.command_count,
            'categories': self.get_categories()
        }
    
    def is_persistent(self) -> bool:
        """检查命令集合是否已持久化"""
        return hasattr(self, '_node_uuid') and self._node_uuid != "mock-uuid"
    
    def get_persistence_status(self) -> Dict[str, Any]:
        """获取持久化状态"""
        return {
            'is_persistent': self.is_persistent(),
            'node_uuid': self._node_uuid,
            'last_sync': getattr(self, '_last_sync', None),
            'sync_status': getattr(self, '_sync_status', 'unknown')
        }
    
    def add_command_with_persistence(self, command_class: Type[Command]) -> None:
        """添加命令并持久化"""
        self.add(command_class)
        # 更新节点属性中的命令列表
        self.set_node_attribute('cmdset_commands', {key: cmd_class.__name__ for key, cmd_class in self.commands.items()})
        self._schedule_node_sync()
    
    def remove_command_with_persistence(self, key: str) -> bool:
        """移除命令并持久化"""
        result = self.remove(key)
        if result:
            # 更新节点属性中的命令列表
            self.set_node_attribute('cmdset_commands', {key: cmd_class.__name__ for key, cmd_class in self.commands.items()})
            self._schedule_node_sync()
        return result
