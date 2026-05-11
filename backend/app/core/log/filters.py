"""
日志过滤器
提供各种日志过滤功能
"""
import logging
import re
from typing import Any, Optional, List, Dict

class SensitiveDataFilter(logging.Filter):
    """敏感数据过滤器"""

    def __init__(self, sensitive_patterns: Optional[List[str]]=None):
        """
        初始化敏感数据过滤器
        
        Args:
            sensitive_patterns: 敏感数据模式列表
        """
        super().__init__()
        default_patterns = ['password["\\\']?\\s*[:=]\\s*["\\\']?([^"\\\'\\s]+)', 'passwd["\\\']?\\s*[:=]\\s*["\\\']?([^"\\\'\\s]+)', 'token["\\\']?\\s*[:=]\\s*["\\\']?([^"\\\'\\s]+)', 'key["\\\']?\\s*[:=]\\s*["\\\']?([^"\\\'\\s]+)', 'secret["\\\']?\\s*[:=]\\s*["\\\']?([^"\\\'\\s]+)', 'api_key["\\\']?\\s*[:=]\\s*["\\\']?([^"\\\'\\s]+)', 'access_token["\\\']?\\s*[:=]\\s*["\\\']?([^"\\\'\\s]+)', 'refresh_token["\\\']?\\s*[:=]\\s*["\\\']?([^"\\\'\\s]+)']
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
        message = record.getMessage()
        for pattern in self.compiled_patterns:
            if pattern.search(message):
                message = pattern.sub('\\1=***', message)
                record.msg = message
                record.args = ()
                break
        return True

class LevelFilter(logging.Filter):
    """级别过滤器"""

    def __init__(self, level: int, above: bool=True):
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

    def __init__(self, allowed_modules: Optional[List[str]]=None, denied_modules: Optional[List[str]]=None):
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
        if self.denied_modules:
            for denied_module in self.denied_modules:
                if module_name.startswith(denied_module):
                    return False
        if self.allowed_modules:
            for allowed_module in self.allowed_modules:
                if module_name.startswith(allowed_module):
                    return True
            return False
        return True

class DuplicateFilter(logging.Filter):
    """重复日志过滤器"""

    def __init__(self, max_duplicates: int=5, timeout: float=60.0):
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
        log_key = f'{record.name}:{record.levelname}:{record.getMessage()}'
        current_time = time.time()
        if log_key in self.last_seen:
            if current_time - self.last_seen[log_key] > self.timeout:
                self.duplicate_count[log_key] = 0
                self.last_seen[log_key] = current_time
                return True
        else:
            self.duplicate_count[log_key] = 0
            self.last_seen[log_key] = current_time
            return True
        self.duplicate_count[log_key] += 1
        if self.duplicate_count[log_key] > self.max_duplicates:
            return False
        return True

class ContextFilter(logging.Filter):
    """上下文过滤器"""

    def __init__(self, context_data: Optional[Dict[str, Any]]=None):
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
        for (key, value) in self.context_data.items():
            setattr(record, key, value)
        return True

class PerformanceFilter(logging.Filter):
    """性能过滤器"""

    def __init__(self, min_duration: float=0.1):
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
        if hasattr(record, 'duration'):
            return record.duration >= self.min_duration
        return True

class RegexFilter(logging.Filter):
    """正则表达式过滤器"""

    def __init__(self, pattern: str, include: bool=True):
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
