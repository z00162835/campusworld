"""
命令执行上下文

提供命令执行的环境，包括输入输出处理、权限检查、执行状态等
参考Evennia框架的命令执行上下文设计

作者：AI Assistant
创建时间：2025-08-24
"""

import time
from typing import Dict, Any, Optional, List, Union
from datetime import datetime


class CommandContext:
    """
    命令执行上下文
    
    提供命令执行所需的环境信息，包括调用者、目标、位置等
    """
    
    def __init__(self, caller=None, target=None, location=None, **kwargs):
        """
        初始化命令执行上下文
        
        Args:
            caller: 命令调用者
            target: 命令目标
            location: 执行位置
            **kwargs: 其他上下文参数
        """
        self.caller = caller
        self.target = target
        self.location = location
        
        # 执行时间
        self.execution_time = time.time()
        self.created_at = datetime.now()
        
        # 执行状态
        self.is_executing = False
        self.execution_success = False
        self.execution_error = None
        
        # 权限信息
        self.required_permissions = []
        self.required_roles = []
        self.access_level = 'normal'
        
        # 输入输出
        self.input_data = {}
        self.output_data = {}
        self.messages = []
        
        # 其他上下文参数
        self.context_data = kwargs.copy()
    
    def __repr__(self):
        return f"<CommandContext(caller={self.caller}, target={self.target}, location={self.location})>"
    
    # ==================== 上下文管理 ====================
    
    def set_caller(self, caller):
        """设置命令调用者"""
        self.caller = caller
        return self
    
    def set_target(self, target):
        """设置命令目标"""
        self.target = target
        return self
    
    def set_location(self, location):
        """设置执行位置"""
        self.location = location
        return self
    
    def add_context_data(self, key: str, value: Any):
        """添加上下文数据"""
        self.context_data[key] = value
        return self
    
    def get_context_data(self, key: str, default: Any = None) -> Any:
        """获取上下文数据"""
        return self.context_data.get(key, default)
    
    def has_context_data(self, key: str) -> bool:
        """检查是否有指定上下文数据"""
        return key in self.context_data
    
    # ==================== 执行状态管理 ====================
    
    def start_execution(self):
        """开始执行"""
        self.is_executing = True
        self.execution_time = time.time()
        return self
    
    def finish_execution(self, success: bool = True, error: str = None):
        """完成执行"""
        self.is_executing = False
        self.execution_success = success
        self.execution_error = error
        return self
    
    def is_execution_complete(self) -> bool:
        """检查执行是否完成"""
        return not self.is_executing
    
    def get_execution_duration(self) -> float:
        """获取执行持续时间"""
        if self.is_executing:
            return time.time() - self.execution_time
        return 0.0
    
    # ==================== 权限管理 ====================
    
    def require_permission(self, permission: str):
        """要求权限"""
        if permission not in self.required_permissions:
            self.required_permissions.append(permission)
        return self
    
    def require_role(self, role: str):
        """要求角色"""
        if role not in self.required_roles:
            self.required_roles.append(role)
        return self
    
    def set_access_level(self, level: str):
        """设置访问级别"""
        self.access_level = level
        return self
    
    def check_permissions(self) -> bool:
        """检查权限"""
        if not self.caller:
            return False
        
        # 检查角色权限
        for role in self.required_roles:
            if not self.caller.has_role(role):
                return False
        
        # 检查具体权限
        for permission in self.required_permissions:
            if not self.caller.has_permission(permission):
                return False
        
        # 检查访问级别
        if hasattr(self.caller, 'access_level'):
            caller_level = self.caller.access_level
            if caller_level == 'normal' and self.access_level == 'admin':
                return False
        
        return True
    
    # ==================== 输入输出管理 ====================
    
    def add_input(self, key: str, value: Any):
        """添加输入数据"""
        self.input_data[key] = value
        return self
    
    def get_input(self, key: str, default: Any = None) -> Any:
        """获取输入数据"""
        return self.input_data.get(key, default)
    
    def add_output(self, key: str, value: Any):
        """添加输出数据"""
        self.output_data[key] = value
        return self
    
    def get_output(self, key: str, default: Any = None) -> Any:
        """获取输出数据"""
        return self.output_data.get(key, default)
    
    def add_message(self, message: str, message_type: str = 'info'):
        """添加消息"""
        self.messages.append({
            'message': message,
            'type': message_type,
            'timestamp': datetime.now()
        })
        return self
    
    def get_messages(self, message_type: str = None) -> List[Dict[str, Any]]:
        """获取消息"""
        if message_type is None:
            return self.messages.copy()
        else:
            return [msg for msg in self.messages if msg['type'] == message_type]
    
    def clear_messages(self):
        """清除消息"""
        self.messages.clear()
        return self
    
    # ==================== 上下文验证 ====================
    
    def validate_context(self) -> Dict[str, Any]:
        """
        验证上下文
        
        Returns:
            验证结果字典
        """
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # 检查必要组件
        if not self.caller:
            validation_result['valid'] = False
            validation_result['errors'].append("命令调用者未设置")
        
        if not self.location:
            validation_result['warnings'].append("执行位置未设置")
        
        # 检查权限
        if not self.check_permissions():
            validation_result['valid'] = False
            validation_result['errors'].append("权限不足")
        
        return validation_result
    
    # ==================== 上下文信息 ====================
    
    def get_context_summary(self) -> Dict[str, Any]:
        """获取上下文摘要"""
        return {
            'caller': str(self.caller) if self.caller else None,
            'target': str(self.target) if self.target else None,
            'location': str(self.location) if self.location else None,
            'execution_time': self.execution_time,
            'created_at': self.created_at.isoformat(),
            'is_executing': self.is_executing,
            'execution_success': self.execution_success,
            'execution_error': self.execution_error,
            'required_permissions': self.required_permissions,
            'required_roles': self.required_roles,
            'access_level': self.access_level,
            'input_data': self.input_data,
            'output_data': self.output_data,
            'message_count': len(self.messages),
            'context_data': self.context_data
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.get_context_summary()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CommandContext':
        """从字典创建"""
        context = cls()
        
        # 设置基本属性
        if 'caller' in data:
            context.caller = data['caller']
        if 'target' in data:
            context.target = data['target']
        if 'location' in data:
            context.location = data['location']
        
        # 设置其他属性
        for key, value in data.items():
            if hasattr(context, key) and key not in ['caller', 'target', 'location']:
                setattr(context, key, value)
        
        return context


class CommandExecutionContext:
    """
    命令执行环境
    
    管理命令的执行环境，包括上下文创建、权限检查、结果处理等
    """
    
    def __init__(self):
        """初始化命令执行环境"""
        self.active_contexts = []
        self.max_contexts = 100
    
    def create_context(self, caller=None, target=None, location=None, **kwargs) -> CommandContext:
        """
        创建命令执行上下文
        
        Args:
            caller: 命令调用者
            target: 命令目标
            location: 执行位置
            **kwargs: 其他参数
            
        Returns:
            命令执行上下文
        """
        context = CommandContext(caller=caller, target=target, location=location, **kwargs)
        
        # 添加到活动上下文列表
        self.active_contexts.append(context)
        
        # 限制活动上下文数量
        if len(self.active_contexts) > self.max_contexts:
            self.active_contexts.pop(0)
        
        return context
    
    def get_active_contexts(self) -> List[CommandContext]:
        """获取活动上下文列表"""
        return self.active_contexts.copy()
    
    def get_context_by_caller(self, caller) -> Optional[CommandContext]:
        """根据调用者获取上下文"""
        for context in self.active_contexts:
            if context.caller == caller:
                return context
        return None
    
    def clear_completed_contexts(self):
        """清除已完成的上下文"""
        self.active_contexts = [ctx for ctx in self.active_contexts if not ctx.is_execution_complete()]
    
    def get_context_statistics(self) -> Dict[str, Any]:
        """获取上下文统计信息"""
        total_contexts = len(self.active_contexts)
        executing_contexts = len([ctx for ctx in self.active_contexts if ctx.is_executing])
        completed_contexts = total_contexts - executing_contexts
        
        return {
            'total_contexts': total_contexts,
            'executing_contexts': executing_contexts,
            'completed_contexts': completed_contexts,
            'max_contexts': self.max_contexts
        }
