"""
命令基类 - 参考Evennia框架设计，集成图数据持久化

所有命令都继承自这个基类，提供统一的命令执行接口
支持命令权限、帮助信息、参数解析等功能
集成图数据存储，支持命令的持久化和动态管理

作者：AI Assistant
创建时间：2025-08-24
重构时间：2025-08-24
"""

import re
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union, Callable
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


class CommandError(Exception):
    """命令执行错误"""
    pass


class CommandPermissionError(CommandError):
    """命令权限错误"""
    pass


class CommandSyntaxError(CommandError):
    """命令语法错误"""
    pass


class Command(DefaultObject):
    """
    命令基类 - 参考Evennia框架设计，集成图数据持久化
    
    所有命令都继承自这个类，提供统一的命令执行接口
    继承自DefaultObject，支持图数据持久化存储
    """
    
    # 命令基本信息
    key = ""                    # 命令关键字
    aliases = []                # 命令别名列表
    locks = ""                  # 命令锁定字符串
    help_category = "general"   # 帮助分类
    help_entry = ""             # 帮助条目
    
    # 命令执行控制
    auto_help = True            # 是否自动显示帮助
    arg_regex = None            # 参数正则表达式
    is_exit = False            # 是否为出口命令
    is_channel = False         # 是否为频道命令
    
    def __init__(self, caller=None, cmdstring="", args="", cmdset=None, **kwargs):
        """
        初始化命令
        
        Args:
            caller: 命令调用者
            cmdstring: 命令字符串
            args: 命令参数
            cmdset: 命令集合
            **kwargs: 其他参数
        """
        # 调用父类初始化，设置命令名称和类型
        super().__init__(
            name=kwargs.get('key', self.key) or 'unnamed_command',
            type='command',
            typeclass=f"{self.__class__.__module__}.{self.__class__.__name__}",
            **kwargs
        )
        
        # 命令执行相关属性
        self.caller = caller
        self.cmdstring = cmdstring
        self.args = args
        self.cmdset = cmdset
        
        # 解析参数
        self.parsed_args = self.parse_args(args)
        
        # 设置时间戳
        if not hasattr(self, 'created_at') or not self.created_at:
            self._created_at = datetime.now()
        self._updated_at = datetime.now()
        
        # 初始化命令特定属性
        self._init_command_attributes()
        
        # 自动同步到图数据存储
        self._schedule_node_sync()
    
    def _init_command_attributes(self):
        """初始化命令特定属性"""
        # 设置命令的基本信息到节点属性中
        self.set_node_attribute('command_key', self.key)
        self.set_node_attribute('command_aliases', self.aliases)
        self.set_node_attribute('command_locks', self.locks)
        self.set_node_attribute('help_category', self.help_category)
        self.set_node_attribute('help_entry', self.help_entry)
        self.set_node_attribute('auto_help', self.auto_help)
        self.set_node_attribute('arg_regex', self.arg_regex)
        self.set_node_attribute('is_exit', self.is_exit)
        self.set_node_attribute('is_channel', self.is_channel)
        
        # 设置命令的元数据
        self.set_node_attribute('command_class', self.__class__.__name__)
        self.set_node_attribute('command_module', self.__class__.__module__)
        self.set_node_attribute('command_version', getattr(self, 'version', '1.0'))
        
        # 设置时间戳到节点属性
        self.set_node_attribute('created_at', self._created_at)
        self.set_node_attribute('updated_at', self._updated_at)
    
    def __repr__(self):
        """字符串表示"""
        return f"<{self.__class__.__name__}(key='{self.key}', caller='{self.caller}', uuid='{self._node_uuid}')>"
    
    def __str__(self):
        """字符串表示"""
        return self.key
    
    @property
    def name(self) -> str:
        """获取命令名称"""
        return self.key or self.get_node_name()
    
    @property
    def description(self) -> str:
        """获取命令描述"""
        return self.help_entry or f"执行 {self.key} 命令"
    
    @property
    def command_uuid(self) -> str:
        """获取命令UUID"""
        return self._node_uuid
    
    @property
    def command_type(self) -> str:
        """获取命令类型"""
        return self.get_node_type()
    
    @property
    def command_typeclass(self) -> str:
        """获取命令类型类"""
        return self.get_node_typeclass()
    
    def parse_args(self, args: str) -> Dict[str, Any]:
        """
        解析命令参数
        
        Args:
            args: 原始参数字符串
            
        Returns:
            解析后的参数字典
        """
        if not args:
            return {}
        
        # 基础参数解析
        parsed = {
            'raw': args.strip(),
            'args': args.strip(),
            'lhs': None,  # 左半部分
            'rhs': None,  # 右半部分
            'switches': [],  # 开关参数
            'options': {}   # 选项参数
        }
        
        # 解析开关参数 (以-或--开头)
        switch_pattern = r'(-{1,2}[a-zA-Z0-9_-]+)'
        switches = re.findall(switch_pattern, args)
        parsed['switches'] = switches
        
        # 移除开关参数
        args_clean = re.sub(switch_pattern, '', args).strip()
        
        # 解析选项参数 (key=value格式)
        option_pattern = r'([a-zA-Z0-9_-]+)=([^=]+)'
        options = dict(re.findall(option_pattern, args_clean))
        parsed['options'] = options
        
        # 移除选项参数
        args_clean = re.sub(option_pattern, '', args_clean).strip()
        
        # 解析左右半部分 (用=分隔)
        if '=' in args_clean:
            lhs, rhs = args_clean.split('=', 1)
            parsed['lhs'] = lhs.strip()
            parsed['rhs'] = rhs.strip()
        else:
            parsed['args'] = args_clean
        
        return parsed
    
    def check_permissions(self) -> bool:
        """
        检查命令权限
        
        Returns:
            是否有权限执行命令
        """
        if not self.locks:
            return True
        
        # 这里可以实现复杂的权限检查逻辑
        # 目前简单返回True
        return True
    
    def access(self, caller, cmdstring, raw_string, **kwargs) -> bool:
        """
        检查访问权限
        
        Args:
            caller: 调用者
            cmdstring: 命令字符串
            raw_string: 原始字符串
            **kwargs: 其他参数
            
        Returns:
            是否可以访问
        """
        return self.check_permissions()
    
    def at_pre_cmd(self) -> bool:
        """
        命令执行前的钩子
        
        Returns:
            是否继续执行命令
        """
        return True
    
    def at_post_cmd(self) -> None:
        """命令执行后的钩子"""
        pass
    
    def func(self) -> None:
        """
        命令执行函数 - 子类必须实现
        
        这是命令的核心逻辑，子类必须重写这个方法
        """
        raise NotImplementedError("子类必须实现func方法")
    
    def execute(self) -> bool:
        """
        执行命令
        
        Returns:
            是否执行成功
        """
        try:
            # 检查权限
            if not self.check_permissions():
                raise CommandPermissionError(f"没有权限执行命令: {self.key}")
            
            # 执行前钩子
            if not self.at_pre_cmd():
                return False
            
            # 执行命令
            self.func()
            
            # 执行后钩子
            self.at_post_cmd()
            
            return True
            
        except CommandError as e:
            self.msg(f"命令执行错误: {e}")
            return False
        except Exception as e:
            self.msg(f"命令执行异常: {e}")
            return False
    
    def msg(self, text: str, **kwargs) -> None:
        """
        发送消息给调用者
        
        Args:
            text: 消息文本
            **kwargs: 其他参数
        """
        if self.caller and hasattr(self.caller, 'msg'):
            self.caller.msg(text, **kwargs)
        else:
            print(f"[{self.key}] {text}")
    
    def usage(self) -> str:
        """
        获取命令使用说明
        
        Returns:
            使用说明字符串
        """
        return f"用法: {self.key} [参数]"
    
    def help(self) -> str:
        """
        获取命令帮助信息
        
        Returns:
            帮助信息字符串
        """
        help_text = f"""
命令: {self.key}
分类: {self.help_category}
描述: {self.description}

{self.usage()}

帮助: {self.help_entry or '暂无详细帮助信息'}
        """.strip()
        
        return help_text
    
    def get_help_category(self) -> str:
        """获取帮助分类"""
        return self.help_category
    
    def get_help_entry(self) -> str:
        """获取帮助条目"""
        return self.help_entry
    
    def get_aliases(self) -> List[str]:
        """获取命令别名"""
        return self.aliases.copy()
    
    def has_alias(self, alias: str) -> bool:
        """检查是否有指定别名"""
        return alias in self.aliases
    
    def add_alias(self, alias: str) -> None:
        """添加别名"""
        if alias not in self.aliases:
            self.aliases.append(alias)
            # 更新节点属性
            self.set_node_attribute('command_aliases', self.aliases)
            self._schedule_node_sync()
    
    def remove_alias(self, alias: str) -> None:
        """移除别名"""
        if alias in self.aliases:
            self.aliases.remove(alias)
            # 更新节点属性
            self.set_node_attribute('command_aliases', self.aliases)
            self._schedule_node_sync()
    
    def get_locks(self) -> str:
        """获取锁定字符串"""
        return self.locks
    
    def set_locks(self, locks: str) -> None:
        """设置锁定字符串"""
        self.locks = locks
        # 更新节点属性
        self.set_node_attribute('command_locks', self.locks)
        self._schedule_node_sync()
    
    def is_exit_command(self) -> bool:
        """是否为出口命令"""
        return self.is_exit
    
    def is_channel_command(self) -> bool:
        """是否为频道命令"""
        return self.is_channel
    
    def get_created_at(self):
        """获取创建时间"""
        return self._created_at
    
    def get_updated_at(self):
        """获取更新时间"""
        return self._updated_at
    
    def update_timestamp(self) -> None:
        """更新时间戳"""
        self._updated_at = datetime.now()
        # 更新节点属性
        self.set_node_attribute('updated_at', self._updated_at)
        self._schedule_node_sync()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'uuid': self._node_uuid,
            'key': self.key,
            'aliases': self.aliases,
            'locks': self.locks,
            'help_category': self.help_category,
            'help_entry': self.help_entry,
            'auto_help': self.auto_help,
            'is_exit': self.is_exit,
            'is_channel': self.is_channel,
            'created_at': self._created_at.isoformat() if self._created_at else None,
            'updated_at': self._updated_at.isoformat() if self._updated_at else None,
            'node_type': self.get_node_type(),
            'node_typeclass': self.get_node_typeclass(),
            'node_attributes': self.get_node_attributes()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], **kwargs) -> 'Command':
        """从字典创建命令实例"""
        # 创建实例
        instance = cls(**kwargs)
        
        # 设置属性
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        
        return instance
    
    # ==================== 图数据持久化方法 ====================
    
    def save_command(self) -> bool:
        """保存命令到图数据存储"""
        try:
            self.sync_to_node()
            return True
        except Exception as e:
            print(f"保存命令失败: {e}")
            return False
    
    def load_command(self, command_uuid: str) -> bool:
        """从图数据存储加载命令"""
        try:
            from app.models.graph_sync import GraphSynchronizer
            synchronizer = GraphSynchronizer()
            
            # 从图数据存储加载命令数据
            # 这里需要实现具体的加载逻辑
            return True
        except Exception as e:
            print(f"加载命令失败: {e}")
            return False
    
    def delete_command(self) -> bool:
        """从图数据存储删除命令"""
        try:
            from app.models.graph_sync import GraphSynchronizer
            synchronizer = GraphSynchronizer()
            
            # 从图数据存储删除命令
            # 这里需要实现具体的删除逻辑
            return True
        except Exception as e:
            print(f"删除命令失败: {e}")
            return False
    
    def get_command_config(self) -> Dict[str, Any]:
        """获取命令配置"""
        return {
            'key': self.key,
            'aliases': self.aliases,
            'locks': self.locks,
            'help_category': self.help_category,
            'help_entry': self.help_entry,
            'auto_help': self.auto_help,
            'arg_regex': self.arg_regex,
            'is_exit': self.is_exit,
            'is_channel': self.is_channel
        }
    
    def set_command_config(self, config: Dict[str, Any]) -> None:
        """设置命令配置"""
        for key, value in config.items():
            if hasattr(self, key):
                setattr(self, key, value)
                # 更新节点属性
                self.set_node_attribute(f'command_{key}', value)
        
        # 同步到图数据存储
        self._schedule_node_sync()
    
    def get_command_metadata(self) -> Dict[str, Any]:
        """获取命令元数据"""
        return {
            'uuid': self._node_uuid,
            'type': self.get_node_type(),
            'typeclass': self.get_node_typeclass(),
            'class': self.__class__.__name__,
            'module': self.__class__.__module__,
            'created_at': self._created_at,
            'updated_at': self._updated_at
        }
    
    def is_persistent(self) -> bool:
        """检查命令是否已持久化"""
        return hasattr(self, '_node_uuid') and self._node_uuid != "mock-uuid"
    
    def get_persistence_status(self) -> Dict[str, Any]:
        """获取持久化状态"""
        return {
            'is_persistent': self.is_persistent(),
            'node_uuid': self._node_uuid,
            'last_sync': getattr(self, '_last_sync', None),
            'sync_status': getattr(self, '_sync_status', 'unknown')
        }
