"""
日志上下文
提供日志上下文管理功能
"""

import threading
from typing import Any, Dict, Optional
from contextvars import ContextVar

class LoggingContext:
    """日志上下文管理器"""
    
    def __init__(self):
        """初始化日志上下文"""
        self._context = ContextVar('logging_context', default={})
        self._local = threading.local()
    
    def set_context(self, **kwargs) -> None:
        """
        设置上下文信息
        
        Args:
            **kwargs: 上下文键值对
        """
        current_context = self._context.get({}).copy()
        current_context.update(kwargs)
        self._context.set(current_context)
    
    def get_context(self) -> Dict[str, Any]:
        """
        获取当前上下文信息
        
        Returns:
            Dict[str, Any]: 上下文信息
        """
        return self._context.get({}).copy()
    
    def clear_context(self) -> None:
        """清空上下文信息"""
        self._context.set({})
    
    def update_context(self, **kwargs) -> None:
        """
        更新上下文信息
        
        Args:
            **kwargs: 上下文键值对
        """
        current_context = self._context.get({}).copy()
        current_context.update(kwargs)
        self._context.set(current_context)
    
    def remove_context(self, *keys) -> None:
        """
        移除指定的上下文信息
        
        Args:
            *keys: 要移除的键
        """
        current_context = self._context.get({}).copy()
        for key in keys:
            current_context.pop(key, None)
        self._context.set(current_context)
    
    def set_user_context(self, user_id: str, username: str = None, session_id: str = None) -> None:
        """
        设置用户上下文
        
        Args:
            user_id: 用户ID
            username: 用户名
            session_id: 会话ID
        """
        self.set_context(
            user_id=user_id,
            username=username,
            session_id=session_id
        )
    
    def set_request_context(self, request_id: str, method: str = None, path: str = None, ip: str = None) -> None:
        """
        设置请求上下文
        
        Args:
            request_id: 请求ID
            method: HTTP方法
            path: 请求路径
            ip: IP地址
        """
        self.set_context(
            request_id=request_id,
            method=method,
            path=path,
            ip=ip
        )
    
    def set_operation_context(self, operation: str, resource: str = None, action: str = None) -> None:
        """
        设置操作上下文
        
        Args:
            operation: 操作名称
            resource: 资源名称
            action: 动作名称
        """
        self.set_context(
            operation=operation,
            resource=resource,
            action=action
        )
    
    def get_user_context(self) -> Dict[str, Any]:
        """
        获取用户上下文
        
        Returns:
            Dict[str, Any]: 用户上下文信息
        """
        context = self.get_context()
        return {
            'user_id': context.get('user_id'),
            'username': context.get('username'),
            'session_id': context.get('session_id')
        }
    
    def get_request_context(self) -> Dict[str, Any]:
        """
        获取请求上下文
        
        Returns:
            Dict[str, Any]: 请求上下文信息
        """
        context = self.get_context()
        return {
            'request_id': context.get('request_id'),
            'method': context.get('method'),
            'path': context.get('path'),
            'ip': context.get('ip')
        }
    
    def get_operation_context(self) -> Dict[str, Any]:
        """
        获取操作上下文
        
        Returns:
            Dict[str, Any]: 操作上下文信息
        """
        context = self.get_context()
        return {
            'operation': context.get('operation'),
            'resource': context.get('resource'),
            'action': context.get('action')
        }

class LoggingContextManager:
    """日志上下文管理器（上下文管理器）"""
    
    def __init__(self, context: LoggingContext, **kwargs):
        """
        初始化日志上下文管理器
        
        Args:
            context: 日志上下文实例
            **kwargs: 上下文键值对
        """
        self.context = context
        self.kwargs = kwargs
        self.original_context = None
    
    def __enter__(self):
        """进入上下文"""
        self.original_context = self.context.get_context()
        self.context.set_context(**self.kwargs)
        return self.context
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        if self.original_context is not None:
            self.context._context.set(self.original_context)

# 全局日志上下文实例
_global_context = LoggingContext()

def get_logging_context() -> LoggingContext:
    """
    获取全局日志上下文实例
    
    Returns:
        LoggingContext: 日志上下文实例
    """
    return _global_context

def set_logging_context(**kwargs) -> None:
    """
    设置全局日志上下文
    
    Args:
        **kwargs: 上下文键值对
    """
    _global_context.set_context(**kwargs)

def get_logging_context_data() -> Dict[str, Any]:
    """
    获取全局日志上下文数据
    
    Returns:
        Dict[str, Any]: 上下文数据
    """
    return _global_context.get_context()

def clear_logging_context() -> None:
    """清空全局日志上下文"""
    _global_context.clear_context()

def with_logging_context(**kwargs):
    """
    日志上下文装饰器
    
    Args:
        **kwargs: 上下文键值对
    
    Returns:
        Callable: 装饰器函数
    """
    def decorator(func):
        def wrapper(*args, **func_kwargs):
            with LoggingContextManager(_global_context, **kwargs):
                return func(*args, **func_kwargs)
        return wrapper
    return decorator
