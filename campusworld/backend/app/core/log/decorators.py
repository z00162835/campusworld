"""
日志装饰器
提供函数调用、执行时间、命令执行等日志记录功能
"""

import logging
import functools
import time
from typing import Any, Callable, Optional

def log_function_call(logger: Optional[logging.Logger] = None):
    """
    记录函数调用的装饰器
    
    Args:
        logger: 日志器实例，如果为None则使用默认日志器
    
    Returns:
        Callable: 装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            if logger:
                logger.debug(f"调用函数: {func.__name__} with args={args}, kwargs={kwargs}")
            
            try:
                result = func(*args, **kwargs)
                if logger:
                    logger.debug(f"函数 {func.__name__} 执行成功")
                return result
            except Exception as e:
                if logger:
                    logger.error(f"函数 {func.__name__} 执行失败: {e}")
                raise
        
        return wrapper
    return decorator

def log_execution_time(logger: Optional[logging.Logger] = None):
    """
    记录函数执行时间的装饰器
    
    Args:
        logger: 日志器实例，如果为None则使用默认日志器
    
    Returns:
        Callable: 装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                if logger:
                    logger.debug(f"函数 {func.__name__} 执行时间: {execution_time:.4f}秒")
                
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                
                if logger:
                    logger.error(f"函数 {func.__name__} 执行失败，耗时: {execution_time:.4f}秒, 错误: {e}")
                
                raise
        
        return wrapper
    return decorator

def log_ssh_command(logger: Optional[logging.Logger] = None):
    """
    记录SSH命令执行的装饰器
    
    Args:
        logger: 日志器实例，如果为None则使用默认日志器
    
    Returns:
        Callable: 装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs) -> Any:
            # 获取命令信息
            command_name = getattr(self, 'name', func.__name__)
            user = 'unknown'
            
            # 尝试获取用户信息
            if hasattr(self, 'current_session') and self.current_session:
                user = getattr(self.current_session, 'username', 'unknown')
            elif hasattr(self, 'session') and self.session:
                user = getattr(self.session, 'username', 'unknown')
            
            if logger:
                logger.info(f"SSH命令执行: {command_name} by user: {user}")
            
            try:
                result = func(self, *args, **kwargs)
                
                if logger:
                    logger.info(f"SSH命令 {command_name} 执行成功")
                
                return result
            except Exception as e:
                if logger:
                    logger.error(f"SSH命令 {command_name} 执行失败: {e}")
                
                raise
        
        return wrapper
    return decorator

def log_database_operation(logger: Optional[logging.Logger] = None):
    """
    记录数据库操作的装饰器
    
    Args:
        logger: 日志器实例，如果为None则使用默认日志器
    
    Returns:
        Callable: 装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            operation = func.__name__
            
            if logger:
                logger.debug(f"数据库操作: {operation}")
            
            try:
                result = func(*args, **kwargs)
                
                if logger:
                    logger.debug(f"数据库操作 {operation} 执行成功")
                
                return result
            except Exception as e:
                if logger:
                    logger.error(f"数据库操作 {operation} 执行失败: {e}")
                
                raise
        
        return wrapper
    return decorator

def log_api_request(logger: Optional[logging.Logger] = None):
    """
    记录API请求的装饰器
    
    Args:
        logger: 日志器实例，如果为None则使用默认日志器
    
    Returns:
        Callable: 装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs) -> Any:
            # 获取请求信息
            request_info = {
                'method': getattr(self, 'method', 'UNKNOWN'),
                'path': getattr(self, 'path', 'UNKNOWN'),
                'user': getattr(self, 'user', 'unknown')
            }
            
            if logger:
                logger.info(f"API请求: {request_info}")
            
            try:
                result = func(self, *args, **kwargs)
                
                if logger:
                    logger.info(f"API请求成功: {request_info}")
                
                return result
            except Exception as e:
                if logger:
                    logger.error(f"API请求失败: {request_info}, 错误: {e}")
                
                raise
        
        return wrapper
    return decorator

def log_performance(logger: Optional[logging.Logger] = None):
    """
    记录性能的装饰器
    
    Args:
        logger: 日志器实例，如果为None则使用默认日志器
    
    Returns:
        Callable: 装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                if logger:
                    logger.info(f"性能监控 - 函数 {func.__name__} 执行时间: {execution_time:.4f}秒")
                
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                
                if logger:
                    logger.error(f"性能监控 - 函数 {func.__name__} 执行失败，耗时: {execution_time:.4f}秒, 错误: {e}")
                
                raise
        
        return wrapper
    return decorator
