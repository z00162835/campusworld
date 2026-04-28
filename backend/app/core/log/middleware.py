"""
日志中间件
提供结构化的日志记录功能
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

class LoggingMiddleware:
    """日志中间件"""
    
    def __init__(self, logger: logging.Logger):
        """
        初始化日志中间件
        
        Args:
            logger: 日志器实例
        """
        self.logger = logger
    
    def log_request(self, request_data: Dict[str, Any]):
        """
        记录请求日志
        
        Args:
            request_data: 请求数据
        """
        log_data = {
            'type': 'request',
            'timestamp': datetime.now().isoformat(),
            'data': request_data
        }
        self.logger.info(f"请求: {json.dumps(log_data, ensure_ascii=False)}")
    
    def log_response(self, response_data: Dict[str, Any]):
        """
        记录响应日志
        
        Args:
            response_data: 响应数据
        """
        log_data = {
            'type': 'response',
            'timestamp': datetime.now().isoformat(),
            'data': response_data
        }
        self.logger.info(f"响应: {json.dumps(log_data, ensure_ascii=False)}")
    
    def log_error(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """
        记录错误日志
        
        Args:
            error: 异常实例
            context: 上下文信息
        """
        error_data = {
            'type': 'error',
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.now().isoformat(),
            'context': context or {}
        }
        self.logger.error(f"错误: {json.dumps(error_data, ensure_ascii=False)}")
    
    def log_performance(self, operation: str, duration: float, metadata: Optional[Dict[str, Any]] = None):
        """
        记录性能日志
        
        Args:
            operation: 操作名称
            duration: 执行时间（秒）
            metadata: 元数据
        """
        perf_data = {
            'type': 'performance',
            'operation': operation,
            'duration': duration,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        self.logger.info(f"性能: {json.dumps(perf_data, ensure_ascii=False)}")
    
    def log_ssh_session(self, session_data: Dict[str, Any]):
        """
        记录SSH会话日志
        
        Args:
            session_data: 会话数据
        """
        log_data = {
            'type': 'ssh_session',
            'timestamp': datetime.now().isoformat(),
            'data': session_data
        }
        self.logger.info(f"SSH会话: {json.dumps(log_data, ensure_ascii=False)}")
    
    def log_command_execution(self, command_data: Dict[str, Any]):
        """
        记录命令执行日志
        
        Args:
            command_data: 命令数据
        """
        log_data = {
            'type': 'command_execution',
            'timestamp': datetime.now().isoformat(),
            'data': command_data
        }
        self.logger.info(f"命令执行: {json.dumps(log_data, ensure_ascii=False)}")
    
    def log_security_event(self, event_data: Dict[str, Any]):
        """
        记录安全事件日志
        
        Args:
            event_data: 事件数据
        """
        log_data = {
            'type': 'security_event',
            'timestamp': datetime.now().isoformat(),
            'data': event_data
        }
        self.logger.warning(f"安全事件: {json.dumps(log_data, ensure_ascii=False)}")
    
    def log_audit_event(self, audit_data: Dict[str, Any]):
        """
        记录审计事件日志
        
        Args:
            audit_data: 审计数据
        """
        log_data = {
            'type': 'audit_event',
            'timestamp': datetime.now().isoformat(),
            'data': audit_data
        }
        self.logger.info(f"审计事件: {json.dumps(log_data, ensure_ascii=False)}")
    
    def log_system_event(self, event_data: Dict[str, Any]):
        """
        记录系统事件日志
        
        Args:
            event_data: 事件数据
        """
        log_data = {
            'type': 'system_event',
            'timestamp': datetime.now().isoformat(),
            'data': event_data
        }
        self.logger.info(f"系统事件: {json.dumps(log_data, ensure_ascii=False)}")
