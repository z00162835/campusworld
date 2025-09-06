"""
日志过滤器
提供各种日志过滤功能
"""

import logging
import re
from typing import Any, Optional, List, Dict

class SensitiveDataFilter(logging.Filter):
    """敏感数据过滤器"""
    
    def __init__(self, sensitive_patterns: Optional[List[str]] = None):
        """
        初始化敏感数据过滤器
        
        Args:
            sensitive_patterns: 敏感数据模式列表
        """
        super().__init__()
        
        # 默认敏感数据模式
        default_patterns = [
            r'password["\']?\s*[:=]\s*["\']?([^"\'\s]+)',
            r'passwd["\']?\s*[:=]\s*["\']?([^"\'\s]+)',
            r'token["\']?\s*[:=]\s*["\']?([^"\'\s]+)',
            r'key["\']?\s*[:=]\s*["\']?([^"\'\s]+)',
            r'secret["\']?\s*[:=]\s*["\']?([^"\'\s]+)',
            r'api_key["\']?\s*[:=]\s*["\']?([^"\'\s]+)',
            r'access_token["\']?\s*[:=]\s*["\']?([^"\'\s]+)',
            r'refresh_token["\']?\s*[:=]\s*["\']?([^"\'\s]+)'
        ]
        
        self.sensitive_patterns = sensitive_patterns or default_patterns
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.sensitive_patterns]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            bool: 是否通过过滤
        """
        # 获取日志消息
        message = record.getMessage()
        
        # 检查是否包含敏感数据
        for pattern in self.compiled_patterns:
            if pattern.search(message):
                # 替换敏感数据
                message = pattern.sub(r'\1=***', message)
                record.msg = message
                record.args = ()
                break
        
        return True

class LevelFilter(logging.Filter):
    """级别过滤器"""
    
    def __init__(self, level: int, above: bool = True):
        """
        初始化级别过滤器
        
        Args:
            level: 日志级别
            above: 是否过滤高于指定级别的日志
        """
        super().__init__()
        self.level = level
        self.above = above
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            bool: 是否通过过滤
        """
        if self.above:
            return record.levelno >= self.level
        else:
            return record.levelno <= self.level

class ModuleFilter(logging.Filter):
    """模块过滤器"""
    
    def __init__(self, allowed_modules: Optional[List[str]] = None, denied_modules: Optional[List[str]] = None):
        """
        初始化模块过滤器
        
        Args:
            allowed_modules: 允许的模块列表
            denied_modules: 拒绝的模块列表
        """
        super().__init__()
        self.allowed_modules = allowed_modules or []
        self.denied_modules = denied_modules or []
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            bool: 是否通过过滤
        """
        module_name = record.name
        
        # 检查拒绝列表
        if self.denied_modules:
            for denied_module in self.denied_modules:
                if module_name.startswith(denied_module):
                    return False
        
        # 检查允许列表
        if self.allowed_modules:
            for allowed_module in self.allowed_modules:
                if module_name.startswith(allowed_module):
                    return True
            return False
        
        return True

class DuplicateFilter(logging.Filter):
    """重复日志过滤器"""
    
    def __init__(self, max_duplicates: int = 5, timeout: float = 60.0):
        """
        初始化重复日志过滤器
        
        Args:
            max_duplicates: 最大重复次数
            timeout: 超时时间（秒）
        """
        super().__init__()
        self.max_duplicates = max_duplicates
        self.timeout = timeout
        self.duplicate_count = {}
        self.last_seen = {}
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤重复日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            bool: 是否通过过滤
        """
        import time
        
        # 创建日志键
        log_key = f"{record.name}:{record.levelname}:{record.getMessage()}"
        current_time = time.time()
        
        # 检查是否超时
        if log_key in self.last_seen:
            if current_time - self.last_seen[log_key] > self.timeout:
                # 超时，重置计数
                self.duplicate_count[log_key] = 0
                self.last_seen[log_key] = current_time
                return True
        else:
            # 新日志
            self.duplicate_count[log_key] = 0
            self.last_seen[log_key] = current_time
            return True
        
        # 增加重复计数
        self.duplicate_count[log_key] += 1
        
        # 检查是否超过最大重复次数
        if self.duplicate_count[log_key] > self.max_duplicates:
            return False
        
        return True

class ContextFilter(logging.Filter):
    """上下文过滤器"""
    
    def __init__(self, context_data: Optional[Dict[str, Any]] = None):
        """
        初始化上下文过滤器
        
        Args:
            context_data: 上下文数据
        """
        super().__init__()
        self.context_data = context_data or {}
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        添加上下文信息到日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            bool: 是否通过过滤
        """
        # 添加上下文信息
        for key, value in self.context_data.items():
            setattr(record, key, value)
        
        return True

class PerformanceFilter(logging.Filter):
    """性能过滤器"""
    
    def __init__(self, min_duration: float = 0.1):
        """
        初始化性能过滤器
        
        Args:
            min_duration: 最小持续时间（秒）
        """
        super().__init__()
        self.min_duration = min_duration
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤性能日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            bool: 是否通过过滤
        """
        # 检查是否有持续时间信息
        if hasattr(record, 'duration'):
            return record.duration >= self.min_duration
        
        return True

class RegexFilter(logging.Filter):
    """正则表达式过滤器"""
    
    def __init__(self, pattern: str, include: bool = True):
        """
        初始化正则表达式过滤器
        
        Args:
            pattern: 正则表达式模式
            include: 是否包含匹配的日志
        """
        super().__init__()
        self.pattern = re.compile(pattern)
        self.include = include
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            bool: 是否通过过滤
        """
        message = record.getMessage()
        matches = bool(self.pattern.search(message))
        
        return matches if self.include else not matches
