"""
日志装饰器
提供函数调用、执行时间、命令执行等日志记录功能
"""
import logging
import functools
import time
from typing import Any, Callable, Optional

def log_function_call(logger: Optional[logging.Logger]=None):
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
                logger.debug(f'Calling function: {func.__name__} with args={args}, kwargs={kwargs}')
            try:
                result = func(*args, **kwargs)
                if logger:
                    logger.debug(f'Function {func.__name__} executed successfully')
                return result
            except Exception as e:
                if logger:
                    logger.error(f'Function {func.__name__} execution failed: {e}')
                raise
        return wrapper
    return decorator

def log_execution_time(logger: Optional[logging.Logger]=None):
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
                    logger.debug(f'Function {func.__name__} execution time: {execution_time:.4f}s')
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                if logger:
                    logger.error(f'Function {func.__name__} execution failed, elapsed: {execution_time:.4f}s, error: {e}')
                raise
        return wrapper
    return decorator

def log_ssh_command(logger: Optional[logging.Logger]=None):
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
            command_name = getattr(self, 'name', func.__name__)
            user = 'unknown'
            if hasattr(self, 'current_session') and self.current_session:
                user = getattr(self.current_session, 'username', 'unknown')
            elif hasattr(self, 'session') and self.session:
                user = getattr(self.session, 'username', 'unknown')
            if logger:
                logger.info(f'SSH command execution: {command_name} by user: {user}')
            try:
                result = func(self, *args, **kwargs)
                if logger:
                    logger.info(f'SSH command {command_name} executed successfully')
                return result
            except Exception as e:
                if logger:
                    logger.error(f'SSH command {command_name} execution failed: {e}')
                raise
        return wrapper
    return decorator

def log_database_operation(logger: Optional[logging.Logger]=None):
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
                logger.debug(f'Database operation: {operation}')
            try:
                result = func(*args, **kwargs)
                if logger:
                    logger.debug(f'Database operation {operation} executed successfully')
                return result
            except Exception as e:
                if logger:
                    logger.error(f'Database operation {operation} execution failed: {e}')
                raise
        return wrapper
    return decorator

def log_api_request(logger: Optional[logging.Logger]=None):
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
            request_info = {'method': getattr(self, 'method', 'UNKNOWN'), 'path': getattr(self, 'path', 'UNKNOWN'), 'user': getattr(self, 'user', 'unknown')}
            if logger:
                logger.info(f'API request: {request_info}')
            try:
                result = func(self, *args, **kwargs)
                if logger:
                    logger.info(f'API request succeeded: {request_info}')
                return result
            except Exception as e:
                if logger:
                    logger.error(f'API request failed: {request_info}, error: {e}')
                raise
        return wrapper
    return decorator

def log_performance(logger: Optional[logging.Logger]=None):
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
                    logger.info(f'Performance monitoring - function {func.__name__} execution time: {execution_time:.4f}s')
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                if logger:
                    logger.error(f'Performance monitoring - function {func.__name__} execution failed, elapsed: {execution_time:.4f}s, error: {e}')
                raise
        return wrapper
    return decorator
