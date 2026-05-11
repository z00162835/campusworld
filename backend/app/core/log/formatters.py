"""
日志格式化器
提供各种日志格式化功能
"""
import logging
import json
from typing import Any, Dict, Optional
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """JSON格式日志格式化器"""

    def __init__(self, include_extra: bool=True):
        """
        初始化JSON格式化器

        Args:
            include_extra: 是否包含额外字段
        """
        super().__init__()
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        """
        格式化日志记录

        Args:
            record: 日志记录

        Returns:
            str: 格式化后的日志字符串
        """
        import os
        log_data = {'timestamp': datetime.fromtimestamp(record.created).isoformat() + 'Z', 'level': record.levelname, 'logger': record.name, 'message': record.getMessage(), 'module': record.module, 'function': record.funcName, 'line': record.lineno, 'process_id': record.process, 'thread_id': record.thread}
        context_fields = ['user_id', 'session_id', 'request_id', 'correlation_id', 'trace_id']
        if self.include_extra and hasattr(record, 'extra'):
            for field in context_fields:
                if field in record.extra:
                    log_data[field] = record.extra[field]
            for (key, value) in record.extra.items():
                if key not in context_fields:
                    log_data[key] = value
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        if record.stack_info:
            log_data['stack_info'] = record.stack_info
        return json.dumps(log_data, ensure_ascii=False)

class ColoredFormatter(logging.Formatter):
    """彩色控制台日志格式化器"""
    COLORS = {'DEBUG': '\x1b[36m', 'INFO': '\x1b[32m', 'WARNING': '\x1b[33m', 'ERROR': '\x1b[31m', 'CRITICAL': '\x1b[35m', 'RESET': '\x1b[0m'}

    def __init__(self, use_colors: bool=True):
        """
        初始化彩色格式化器
        
        Args:
            use_colors: 是否使用颜色
        """
        super().__init__()
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        """
        格式化日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            str: 格式化后的日志字符串
        """
        formatted = super().format(record)
        if self.use_colors and record.levelname in self.COLORS:
            color = self.COLORS[record.levelname]
            reset = self.COLORS['RESET']
            formatted = f'{color}{formatted}{reset}'
        return formatted

class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""

    def __init__(self, fields: Optional[list]=None):
        """
        初始化结构化格式化器
        
        Args:
            fields: 要包含的字段列表
        """
        super().__init__()
        self.fields = fields or ['timestamp', 'level', 'logger', 'message', 'module', 'function', 'line']

    def format(self, record: logging.LogRecord) -> str:
        """
        格式化日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            str: 格式化后的日志字符串
        """
        log_parts = []
        for field in self.fields:
            if field == 'timestamp':
                value = datetime.fromtimestamp(record.created).isoformat()
            elif field == 'level':
                value = record.levelname
            elif field == 'logger':
                value = record.name
            elif field == 'message':
                value = record.getMessage()
            elif field == 'module':
                value = record.module
            elif field == 'function':
                value = record.funcName
            elif field == 'line':
                value = record.lineno
            else:
                value = getattr(record, field, 'N/A')
            log_parts.append(f'{field}={value}')
        if record.exc_info:
            log_parts.append(f'exception={self.formatException(record.exc_info)}')
        return ' | '.join(log_parts)

class AuditFormatter(logging.Formatter):
    """审计日志格式化器"""

    def __init__(self):
        """初始化审计格式化器"""
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        """
        格式化审计日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            str: 格式化后的审计日志字符串
        """
        timestamp = datetime.fromtimestamp(record.created).isoformat()
        level = record.levelname
        message = record.getMessage()
        audit_log = f'[AUDIT] {timestamp} | {level} | {message}'
        if hasattr(record, 'user_id'):
            audit_log += f' | user_id={record.user_id}'
        if hasattr(record, 'action'):
            audit_log += f' | action={record.action}'
        if hasattr(record, 'resource'):
            audit_log += f' | resource={record.resource}'
        if hasattr(record, 'ip_address'):
            audit_log += f' | ip={record.ip_address}'
        if record.exc_info:
            audit_log += f' | exception={self.formatException(record.exc_info)}'
        return audit_log

class CompactFormatter(logging.Formatter):
    """紧凑型日志格式化器"""

    def __init__(self):
        """初始化紧凑格式化器"""
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        """
        格式化紧凑日志记录
        
        Args:
            record: 日志记录
        
        Returns:
            str: 格式化后的紧凑日志字符串
        """
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        level = record.levelname[0]
        logger_name = record.name.split('.')[-1]
        message = record.getMessage()
        return f'{timestamp} {level} {logger_name}: {message}'
