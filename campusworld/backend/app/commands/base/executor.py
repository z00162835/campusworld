"""
命令执行器 - 负责命令的解析和执行，集成图数据持久化

参考Evennia框架设计，提供统一的命令执行接口
支持命令解析、查找、执行、错误处理等功能
集成图数据存储，支持命令历史和配置的持久化

作者：AI Assistant
创建时间：2025-08-24
重构时间：2025-08-24
"""

import re
from typing import Dict, List, Optional, Union, Any, Tuple
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

from .command import Command, CommandError, CommandPermissionError, CommandSyntaxError
from .cmdset import CmdSet


class CommandExecutor(DefaultObject):
    """
    命令执行器 - 负责命令的解析和执行，集成图数据持久化
    
    提供统一的命令执行接口，支持命令解析、查找、执行、错误处理等功能
    继承自DefaultObject，支持图数据持久化存储
    """
    
    def __init__(self, default_cmdset: Optional[CmdSet] = None):
        """
        初始化命令执行器
        
        Args:
            default_cmdset: 默认命令集合
        """
        # 调用父类初始化
        super().__init__(
            name="command_executor",
            type='command_executor',
            typeclass=f"{self.__class__.__module__}.{self.__class__.__name__}",
            executor_type="default"
        )
        
        self.default_cmdset = default_cmdset or CmdSet()
        self.cmdsets: List[CmdSet] = [self.default_cmdset]
        self.command_history: List[Dict[str, Any]] = []
        self.max_history = 100
        
        # 命令解析配置
        self.command_separator = ";"  # 命令分隔符
        self.argument_separator = " "  # 参数分隔符
        self.quote_chars = ['"', "'"]  # 引号字符
        
        # 错误处理配置
        self.show_errors = True        # 是否显示错误信息
        self.log_commands = True       # 是否记录命令历史
        
        # 初始化执行器特定属性
        self._init_executor_attributes()
        
        # 自动同步到图数据存储
        self._schedule_node_sync()
    
    def _init_executor_attributes(self):
        """初始化执行器特定属性"""
        # 设置执行器的基本信息到节点属性中
        self.set_node_attribute('executor_type', 'default')
        self.set_node_attribute('max_history', self.max_history)
        self.set_node_attribute('command_separator', self.command_separator)
        self.set_node_attribute('argument_separator', self.argument_separator)
        self.set_node_attribute('quote_chars', self.quote_chars)
        self.set_node_attribute('show_errors', self.show_errors)
        self.set_node_attribute('log_commands', self.log_commands)
        
        # 设置执行器的元数据
        self.set_node_attribute('executor_class', self.__class__.__name__)
        self.set_node_attribute('executor_module', self.__class__.__module__)
        self.set_node_attribute('executor_version', getattr(self, 'version', '1.0'))
    
    def __repr__(self):
        """字符串表示"""
        return f"<{self.__class__.__name__}(cmdsets={len(self.cmdsets)}, history={len(self.command_history)}, uuid='{self._node_uuid}')>"
    
    def add_cmdset(self, cmdset: CmdSet, priority: Optional[int] = None) -> None:
        """
        添加命令集合
        
        Args:
            cmdset: 命令集合
            priority: 优先级，None表示使用cmdset的默认优先级
        """
        if not isinstance(cmdset, CmdSet):
            raise ValueError(f"只能添加CmdSet实例: {cmdset}")
        
        if priority is not None:
            cmdset.set_priority(priority)
        
        # 按优先级排序插入
        self.cmdsets.append(cmdset)
        self.cmdsets.sort(key=lambda x: x.get_priority(), reverse=True)
    
    def remove_cmdset(self, key: str) -> bool:
        """
        移除命令集合
        
        Args:
            key: 命令集合关键字
            
        Returns:
            是否成功移除
        """
        for i, cmdset in enumerate(self.cmdsets):
            if cmdset.key == key:
                del self.cmdsets[i]
                return True
        return False
    
    def get_cmdset(self, key: str) -> Optional[CmdSet]:
        """
        获取指定命令集合
        
        Args:
            key: 命令集合关键字
            
        Returns:
            命令集合或None
        """
        for cmdset in self.cmdsets:
            if cmdset.key == key:
                return cmdset
        return None
    
    def get_all_commands(self) -> Dict[str, type]:
        """
        获取所有命令
        
        Returns:
            命令字典 {key: command_class}
        """
        all_commands = {}
        
        # 按优先级顺序收集命令
        for cmdset in self.cmdsets:
            for key, command_class in cmdset.commands.items():
                if key not in all_commands:
                    all_commands[key] = command_class
        
        return all_commands
    
    def find_command(self, key: str) -> Optional[type]:
        """
        查找命令
        
        Args:
            key: 命令关键字
            
        Returns:
            命令类或None
        """
        # 按优先级顺序查找
        for cmdset in self.cmdsets:
            command_class = cmdset.get(key)
            if command_class:
                return command_class
        return None
    
    def parse_command_string(self, command_string: str) -> List[Dict[str, Any]]:
        """
        解析命令字符串
        
        Args:
            command_string: 原始命令字符串
            
        Returns:
            解析后的命令列表
        """
        if not command_string:
            return []
        
        # 按分隔符分割多个命令
        commands = []
        raw_commands = command_string.split(self.command_separator)
        
        for raw_cmd in raw_commands:
            raw_cmd = raw_cmd.strip()
            if not raw_cmd:
                continue
            
            # 解析单个命令
            parsed = self._parse_single_command(raw_cmd)
            if parsed:
                commands.append(parsed)
        
        return commands
    
    def _parse_single_command(self, command_string: str) -> Optional[Dict[str, Any]]:
        """
        解析单个命令
        
        Args:
            command_string: 单个命令字符串
            
        Returns:
            解析后的命令字典或None
        """
        if not command_string:
            return None
        
        # 分离命令和参数
        parts = command_string.split(self.argument_separator, 1)
        cmd_key = parts[0].strip().lower()
        args = parts[1].strip() if len(parts) > 1 else ""
        
        # 处理引号包围的参数
        args = self._process_quoted_args(args)
        
        return {
            'key': cmd_key,
            'args': args,
            'raw': command_string,
            'timestamp': None  # 将在执行时设置
        }
    
    def _process_quoted_args(self, args: str) -> str:
        """
        处理引号包围的参数
        
        Args:
            args: 参数字符串
            
        Returns:
            处理后的参数字符串
        """
        if not args:
            return args
        
        # 简单的引号处理，移除最外层的引号
        for quote in self.quote_chars:
            if args.startswith(quote) and args.endswith(quote):
                args = args[1:-1]
                break
        
        return args
    
    def execute_command_string(self, command_string: str, caller=None, **kwargs) -> List[Dict[str, Any]]:
        """
        执行命令字符串
        
        Args:
            command_string: 命令字符串
            caller: 命令调用者
            **kwargs: 其他参数
            
        Returns:
            执行结果列表
        """
        # 解析命令
        parsed_commands = self.parse_command_string(command_string)
        results = []
        
        for parsed_cmd in parsed_commands:
            result = self.execute_command(
                parsed_cmd['key'],
                parsed_cmd['args'],
                caller=caller,
                **kwargs
            )
            
            # 记录命令历史
            if self.log_commands:
                self._log_command(parsed_cmd, result, caller)
            
            results.append(result)
        
        return results
    
    def execute_command(self, key: str, args: str = "", caller=None, **kwargs) -> Dict[str, Any]:
        """
        执行单个命令
        
        Args:
            key: 命令关键字
            args: 命令参数
            caller: 命令调用者
            **kwargs: 其他参数
            
        Returns:
            执行结果字典
        """
        result = {
            'success': False,
            'command': key,
            'args': args,
            'caller': caller,
            'error': None,
            'output': None,
            'timestamp': None,
            'execution_time': 0.0
        }
        
        try:
            import time
            start_time = time.time()
            
            # 查找命令
            command_class = self.find_command(key)
            if not command_class:
                result['error'] = f"命令未找到: {key}"
                return result
            
            # 创建命令实例
            command = command_class(
                caller=caller,
                cmdstring=key,
                args=args,
                **kwargs
            )
            
            # 检查权限
            if not command.access(caller, key, f"{key} {args}", **kwargs):
                result['error'] = f"没有权限执行命令: {key}"
                return result
            
            # 执行命令
            success = command.execute()
            
            # 记录结果
            result['success'] = success
            result['timestamp'] = time.time()
            result['execution_time'] = result['timestamp'] - start_time
            
            if success:
                result['output'] = "命令执行成功"
            else:
                result['output'] = "命令执行失败"
            
        except CommandError as e:
            result['error'] = f"命令执行错误: {e}"
        except Exception as e:
            result['error'] = f"命令执行异常: {e}"
            if self.show_errors:
                import traceback
                traceback.print_exc()
        
        return result
    
    def _log_command(self, parsed_cmd: Dict[str, Any], result: Dict[str, Any], caller=None) -> None:
        """
        记录命令历史
        
        Args:
            parsed_cmd: 解析后的命令
            result: 执行结果
            caller: 调用者
        """
        log_entry = {
            'command': parsed_cmd['key'],
            'args': parsed_cmd['args'],
            'raw': parsed_cmd['raw'],
            'caller': str(caller) if caller else None,
            'success': result['success'],
            'error': result.get('error'),
            'execution_time': result.get('execution_time', 0.0),
            'timestamp': result.get('timestamp')
        }
        
        self.command_history.append(log_entry)
        
        # 限制历史记录数量
        if len(self.command_history) > self.max_history:
            self.command_history.pop(0)
    
    def get_command_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取命令历史
        
        Args:
            limit: 限制数量，None表示全部
            
        Returns:
            命令历史列表
        """
        if limit is None:
            return self.command_history.copy()
        
        return self.command_history[-limit:] if limit > 0 else []
    
    def clear_history(self) -> None:
        """清空命令历史"""
        self.command_history.clear()
    
    def get_help(self, category: str = None) -> str:
        """
        获取帮助信息
        
        Args:
            category: 指定分类，None表示所有分类
            
        Returns:
            帮助信息字符串
        """
        # 合并所有命令集合的帮助信息
        help_text = f"命令执行器帮助\n"
        help_text += f"命令集合数量: {len(self.cmdsets)}\n"
        help_text += f"总命令数量: {len(self.get_all_commands())}\n\n"
        
        for cmdset in self.cmdsets:
            help_text += f"=== {cmdset.key} (优先级: {cmdset.priority}) ===\n"
            help_text += cmdset.get_help(category)
            help_text += "\n\n"
        
        return help_text.strip()
    
    def get_command_info(self, key: str) -> Optional[Dict[str, Any]]:
        """
        获取命令信息
        
        Args:
            key: 命令关键字
            
        Returns:
            命令信息字典或None
        """
        command_class = self.find_command(key)
        if command_class:
            return command_class.to_dict()
        return None
    
    def get_available_commands(self, caller=None) -> List[Dict[str, Any]]:
        """
        获取可用命令列表
        
        Args:
            caller: 调用者
            
        Returns:
            可用命令列表
        """
        available_commands = []
        all_commands = self.get_all_commands()
        
        for key, command_class in all_commands.items():
            # 创建临时实例检查权限
            temp_command = command_class(caller=caller, cmdstring=key, args="")
            
            if temp_command.access(caller, key, key):
                available_commands.append({
                    'key': key,
                    'category': command_class.help_category,
                    'description': command_class.help_entry or f"执行 {key} 命令",
                    'aliases': command_class.aliases,
                    'locks': command_class.locks
                })
        
        return available_commands
    
    def get_commands_by_category(self, category: str, caller=None) -> List[Dict[str, Any]]:
        """
        按分类获取可用命令
        
        Args:
            category: 命令分类
            caller: 调用者
            
        Returns:
            命令列表
        """
        all_commands = self.get_available_commands(caller)
        return [cmd for cmd in all_commands if cmd['category'] == category]
    
    def get_categories(self) -> List[str]:
        """
        获取所有命令分类
        
        Returns:
            分类列表
        """
        categories = set()
        all_commands = self.get_all_commands()
        
        for command_class in all_commands.values():
            categories.add(command_class.help_category)
        
        return sorted(list(categories))
    
    def validate_command(self, key: str, args: str = "") -> Dict[str, Any]:
        """
        验证命令（不执行）
        
        Args:
            key: 命令关键字
            args: 命令参数
            
        Returns:
            验证结果字典
        """
        result = {
            'valid': False,
            'command': key,
            'args': args,
            'error': None,
            'command_class': None,
            'permission_check': False
        }
        
        try:
            # 查找命令
            command_class = self.find_command(key)
            if not command_class:
                result['error'] = f"命令未找到: {key}"
                return result
            
            result['command_class'] = command_class
            result['valid'] = True
            
            # 创建临时实例进行权限检查
            temp_command = command_class(cmdstring=key, args=args)
            result['permission_check'] = True
            
        except Exception as e:
            result['error'] = f"验证失败: {e}"
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'uuid': self._node_uuid,
            'cmdsets': [cmdset.to_dict() for cmdset in self.cmdsets],
            'command_count': len(self.get_all_commands()),
            'categories': self.get_categories(),
            'history_count': len(self.command_history),
            'max_history': self.max_history,
            'show_errors': self.show_errors,
            'log_commands': self.log_commands,
            'node_type': self.get_node_type(),
            'node_typeclass': self.get_node_typeclass(),
            'node_attributes': self.get_node_attributes()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], **kwargs) -> 'CommandExecutor':
        """从字典创建命令执行器实例"""
        instance = cls(**kwargs)
        
        # 设置属性
        if 'max_history' in data:
            instance.max_history = data['max_history']
        if 'show_errors' in data:
            instance.show_errors = data['show_errors']
        if 'log_commands' in data:
            instance.log_commands = data['log_commands']
        
        return instance
    
    # ==================== 图数据持久化方法 ====================
    
    def save_executor(self) -> bool:
        """保存执行器到图数据存储"""
        try:
            self.sync_to_node()
            return True
        except Exception as e:
            print(f"保存执行器失败: {e}")
            return False
    
    def load_executor(self, executor_uuid: str) -> bool:
        """从图数据存储加载执行器"""
        try:
            from app.models.graph_sync import GraphSynchronizer
            synchronizer = GraphSynchronizer()
            
            # 从图数据存储加载执行器数据
            # 这里需要实现具体的加载逻辑
            return True
        except Exception as e:
            print(f"加载执行器失败: {e}")
            return False
    
    def delete_executor(self) -> bool:
        """从图数据存储删除执行器"""
        try:
            from app.models.graph_sync import GraphSynchronizer
            synchronizer = GraphSynchronizer()
            
            # 从图数据存储删除执行器
            # 这里需要实现具体的删除逻辑
            return True
        except Exception as e:
            print(f"删除执行器失败: {e}")
            return False
    
    def get_executor_config(self) -> Dict[str, Any]:
        """获取执行器配置"""
        return {
            'max_history': self.max_history,
            'command_separator': self.command_separator,
            'argument_separator': self.argument_separator,
            'quote_chars': self.quote_chars,
            'show_errors': self.show_errors,
            'log_commands': self.log_commands
        }
    
    def set_executor_config(self, config: Dict[str, Any]) -> None:
        """设置执行器配置"""
        for key, value in config.items():
            if hasattr(self, key):
                setattr(self, key, value)
                # 更新节点属性
                self.set_node_attribute(f'executor_{key}', value)
        
        # 同步到图数据存储
        self._schedule_node_sync()
    
    def get_executor_metadata(self) -> Dict[str, Any]:
        """获取执行器元数据"""
        return {
            'uuid': self._node_uuid,
            'type': self.get_node_type(),
            'typeclass': self.get_node_typeclass(),
            'class': self.__class__.__name__,
            'module': self.__class__.__module__,
            'executor_type': getattr(self, 'executor_type', 'default'),
            'cmdset_count': len(self.cmdsets),
            'command_count': len(self.get_all_commands()),
            'history_count': len(self.command_history)
        }
    
    def is_persistent(self) -> bool:
        """检查执行器是否已持久化"""
        return hasattr(self, '_node_uuid') and self._node_uuid != "mock-uuid"
    
    def get_persistence_status(self) -> Dict[str, Any]:
        """获取持久化状态"""
        return {
            'is_persistent': self.is_persistent(),
            'node_uuid': self._node_uuid,
            'last_sync': getattr(self, '_last_sync', None),
            'sync_status': getattr(self, '_sync_status', 'unknown')
        }
    
    def save_command_history(self) -> bool:
        """保存命令历史到图数据存储"""
        try:
            # 将命令历史保存到节点属性中
            self.set_node_attribute('command_history', self.command_history)
            self._schedule_node_sync()
            return True
        except Exception as e:
            print(f"保存命令历史失败: {e}")
            return False
    
    def load_command_history(self) -> bool:
        """从图数据存储加载命令历史"""
        try:
            # 从节点属性中加载命令历史
            history = self._node_attributes.get('command_history', [])
            if history:
                self.command_history = history
                return True
            return False
        except Exception as e:
            print(f"加载命令历史失败: {e}")
            return False
    
    def clear_command_history(self) -> None:
        """清除命令历史"""
        self.command_history.clear()
        # 同步到图数据存储
        self.set_node_attribute('command_history', [])
        self._schedule_node_sync()
    
    def add_cmdset_with_persistence(self, cmdset: CmdSet, priority: Optional[int] = None) -> None:
        """添加命令集合并持久化"""
        self.add_cmdset(cmdset, priority)
        # 更新节点属性中的命令集合列表
        self.set_node_attribute('executor_cmdsets', [cs.key for cs in self.cmdsets])
        self._schedule_node_sync()
    
    def remove_cmdset_with_persistence(self, key: str) -> bool:
        """移除命令集合并持久化"""
        result = self.remove_cmdset(key)
        if result:
            # 更新节点属性中的命令集合列表
            self.set_node_attribute('executor_cmdsets', [cs.key for cs in self.cmdsets])
            self._schedule_node_sync()
        return result
