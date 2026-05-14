"""
日志模块入口
提供统一的日志接口和便捷的日志功能

使用示例:
    from app.core.log import get_logger, log_function_call
    
    # 获取日志器
    logger = get_logger("my_module")
    logger.info("这是一条日志消息")
    
    # 使用装饰器
    @log_function_call
    def my_function():
        pass
"""
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
import os
_logging_manager: Optional['object'] = None

class LoggerNames:
    """预定义的日志器名称"""
    ROOT = 'root'
    APP = 'app'
    SSH = 'app.ssh'
    GAME = 'app.games'
    DATABASE = 'app.database'
    API = 'app.api'
    AUTH = 'app.auth'
    CORE = 'app.core'
    UTILS = 'app.utils'
    TESTS = 'tests'
    PERFORMANCE = 'performance'
    AUDIT = 'audit'
    SECURITY = 'security'
    COMMAND = 'command'
    PROTOCOL = 'protocol'
    SESSION = 'session'
    AICO_AGENT = 'app.agent.aico'

def get_logging_manager() -> object:
    """
    获取全局日志管理器实例（延迟加载）
    
    Returns:
        LoggingManager: 日志管理器实例
    """
    global _logging_manager
    if _logging_manager is None:
        from .manager import LoggingManager
        _logging_manager = LoggingManager()
    return _logging_manager

def get_logger(name: str, level: Optional[str]=None) -> logging.Logger:
    """
    获取日志器（延迟加载）
    
    Args:
        name: 日志器名称
        level: 日志级别（可选）
    
    Returns:
        logging.Logger: 日志器实例
    """
    manager = get_logging_manager()
    logger = manager.get_logger(name)
    if level:
        logger.setLevel(getattr(logging, level.upper()))
    return logger

def setup_logging(level: str='INFO', format_str: Optional[str]=None, file_path: Optional[str]=None, console_output: bool=True, file_output: bool=False, date_format: Optional[str]=None) -> object:
    """
    设置日志系统（延迟加载）
    
    Args:
        level: 日志级别
        format_str: 日志格式
        file_path: 日志文件路径
        console_output: 是否输出到控制台
        file_output: 是否输出到文件
        date_format: ``%(asctime)s`` 的日期时间格式（传给 ``logging.Formatter`` 的 ``datefmt``）
    
    Returns:
        LoggingManager: 配置后的日志管理器
    """
    manager = get_logging_manager()
    manager.setup_custom(level, format_str, file_path, console_output, file_output, date_format=date_format)
    return manager

def create_logging_middleware(module_name: str) -> object:
    """
    创建日志中间件（延迟加载）
    
    Args:
        module_name: 模块名称
    
    Returns:
        LoggingMiddleware: 日志中间件实例
    """
    from .middleware import LoggingMiddleware
    logger = get_logger(module_name)
    return LoggingMiddleware(logger)

def get_app_logger() -> logging.Logger:
    """获取应用日志器"""
    return get_logger(LoggerNames.APP)

def get_ssh_logger() -> logging.Logger:
    """获取SSH日志器"""
    return get_logger(LoggerNames.SSH)

def get_game_logger() -> logging.Logger:
    """获取场景日志器"""
    return get_logger(LoggerNames.GAME)

def get_database_logger() -> logging.Logger:
    """获取数据库日志器"""
    return get_logger(LoggerNames.DATABASE)

def get_audit_logger() -> logging.Logger:
    """获取审计日志器"""
    return get_logger(LoggerNames.AUDIT)

def get_security_logger() -> logging.Logger:
    """获取安全日志器"""
    return get_logger(LoggerNames.SECURITY)

def log_function_call(func):
    """函数调用日志装饰器（延迟加载）"""
    from .decorators import log_function_call as _log_function_call
    return _log_function_call(func)

def log_execution_time(func):
    """执行时间日志装饰器（延迟加载）"""
    from .decorators import log_execution_time as _log_execution_time
    return _log_execution_time(func)

def log_ssh_command(func):
    """SSH命令日志装饰器（延迟加载）"""
    from .decorators import log_ssh_command as _log_ssh_command
    return _log_ssh_command(func)

def log_database_operation(func):
    """数据库操作日志装饰器（延迟加载）"""
    from .decorators import log_database_operation as _log_database_operation
    return _log_database_operation(func)

def get_logging_context():
    """获取全局日志上下文"""
    from .context import get_logging_context as _get_logging_context
    return _get_logging_context()

def set_logging_context(**kwargs):
    """设置全局日志上下文"""
    from .context import set_logging_context as _set_logging_context
    return _set_logging_context(**kwargs)

def get_logging_context_data():
    """获取全局日志上下文数据"""
    from .context import get_logging_context_data as _get_logging_context_data
    return _get_logging_context_data()

def clear_logging_context():
    """清空全局日志上下文"""
    from .context import clear_logging_context as _clear_logging_context
    return _clear_logging_context()

def with_logging_context(**kwargs):
    """日志上下文装饰器"""
    from .context import with_logging_context as _with_logging_context
    return _with_logging_context(**kwargs)

class JSONFormatter:
    """JSON格式化器（延迟加载）"""

    def __new__(cls, *args, **kwargs):
        from .formatters import JSONFormatter as _JSONFormatter
        return _JSONFormatter(*args, **kwargs)

class ColoredFormatter:
    """彩色格式化器（延迟加载）"""

    def __new__(cls, *args, **kwargs):
        from .formatters import ColoredFormatter as _ColoredFormatter
        return _ColoredFormatter(*args, **kwargs)

class LoggingContext:
    """日志上下文（延迟加载）"""

    def __new__(cls, *args, **kwargs):
        from .context import LoggingContext as _LoggingContext
        return _LoggingContext(*args, **kwargs)

class LoggingContextManager:
    """日志上下文管理器（延迟加载）"""

    def __new__(cls, *args, **kwargs):
        from .context import LoggingContextManager as _LoggingContextManager
        return _LoggingContextManager(*args, **kwargs)
__all__ = ['LoggingManager', 'LoggingMiddleware', 'log_function_call', 'log_execution_time', 'log_ssh_command', 'log_database_operation', 'JSONFormatter', 'ColoredFormatter', 'LoggingContext', 'LoggingContextManager', 'get_logging_context', 'set_logging_context', 'get_logging_context_data', 'clear_logging_context', 'with_logging_context', 'LoggerNames', 'get_logging_manager', 'get_logger', 'setup_logging', 'create_logging_middleware', 'get_app_logger', 'get_ssh_logger', 'get_game_logger', 'get_database_logger', 'get_audit_logger', 'get_security_logger']

def _init_module():
    """模块初始化"""
    try:
        pass
    except Exception:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_init_module()
