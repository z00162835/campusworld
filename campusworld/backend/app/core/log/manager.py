"""
日志管理器
负责统一管理日志配置和日志器创建
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from app.core.paths import get_logs_dir, get_project_root

class LoggingManager:
    """统一的日志管理器"""
    
    def __init__(self, config_manager=None):
        """
        初始化日志管理器
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self._configured_loggers = set()
        self._loggers = {}
        self._setup_root_logging()
    
    def _setup_root_logging(self):
        """设置根日志配置"""
        if self.config_manager:
            self._setup_from_config()
        else:
            self._setup_default()
    
    def _setup_from_config(self):
        """从配置文件设置日志"""
        try:
            log_config = self.config_manager.get('logging', {})
            
            # 获取日志级别
            level = getattr(logging, log_config.get('level', 'INFO').upper())
            
            # 获取日志格式
            format_str = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            date_format = log_config.get('date_format', '%Y-%m-%d %H:%M:%S')
            
            # 创建格式化器
            formatter = logging.Formatter(format_str, date_format)
            
            # 清除现有处理器
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            
            # 控制台输出
            if log_config.get('console_output', True):
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(formatter)
                root_logger.addHandler(console_handler)
            
            # 文件输出
            if log_config.get('file_output', False):
                # 从配置获取日志文件名
                file_name = log_config.get('file_name', 'campusworld.log')
                
                # 使用统一的路径管理获取日志目录
                logs_dir = get_logs_dir(self.config_manager)
                full_log_path = logs_dir / file_name
                
                self._setup_file_handler(full_log_path, formatter, log_config)
            
            # 设置根日志级别
            root_logger.setLevel(level)
            
            # 设置特定模块的日志级别
            self._setup_module_log_levels(log_config)
            
        except Exception as e:
            print(f"从配置设置日志失败: {e}")
            self._setup_default()
    
    def _setup_default(self):
        """设置默认日志配置"""
        # 使用统一的路径管理
        logs_dir = get_logs_dir(self.config_manager)
        log_file = logs_dir / "campusworld.log"
        
        # 创建日志目录
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_file, encoding='utf-8')
            ]
        )
        
        logger = logging.getLogger("campusworld.logging")
        logger.info(f"默认日志文件已配置: {log_file}")
    
    def _setup_file_handler(self, file_path: Path, formatter: logging.Formatter, log_config: Dict[str, Any]):
        """设置文件处理器"""
        try:
            # 创建日志目录
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 获取文件大小限制
            max_size = self._parse_size(log_config.get('max_file_size', '10MB'))
            backup_count = log_config.get('backup_count', 5)
            
            # 创建轮转文件处理器
            file_handler = logging.handlers.RotatingFileHandler(
                file_path,
                maxBytes=max_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            
            # 添加文件处理器到根日志器
            root_logger = logging.getLogger()
            root_logger.addHandler(file_handler)
            
            print(f"日志文件已配置: {file_path}")
            
        except Exception as e:
            print(f"设置文件处理器失败: {e}")
    
    def _setup_module_log_levels(self, log_config: Dict[str, Any]):
        """设置特定模块的日志级别"""
        module_levels = log_config.get('module_levels', {})
        
        # 默认模块级别
        default_module_levels = {
            'paramiko': 'WARNING',
            'asyncio': 'WARNING',
            'urllib3': 'WARNING',
            'requests': 'WARNING',
            'sqlalchemy': 'WARNING',
        }
        
        # 合并配置
        all_module_levels = {**default_module_levels, **module_levels}
        
        for module, level in all_module_levels.items():
            try:
                logging.getLogger(module).setLevel(getattr(logging, level.upper()))
            except (ValueError, AttributeError):
                print(f"无效的日志级别: {module}={level}")
    
    def _parse_size(self, size_str: str) -> int:
        """解析文件大小字符串"""
        size_str = size_str.upper().strip()
        
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            try:
                return int(size_str)
            except ValueError:
                return 10 * 1024 * 1024  # 默认10MB
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        获取日志器
        
        Args:
            name: 日志器名称
        
        Returns:
            logging.Logger: 日志器实例
        """
        if name not in self._loggers:
            self._loggers[name] = logging.getLogger(name)
            self._configured_loggers.add(name)
        
        return self._loggers[name]
    
    def setup_module_logging(self, module_name: str, level: str = "INFO") -> logging.Logger:
        """
        为特定模块设置日志
        
        Args:
            module_name: 模块名称
            level: 日志级别
        
        Returns:
            logging.Logger: 配置后的日志器
        """
        logger = self.get_logger(module_name)
        logger.setLevel(getattr(logging, level.upper()))
        return logger
    
    def setup_custom(
        self,
        level: str = "INFO",
        format_str: Optional[str] = None,
        file_path: Optional[str] = None,
        console_output: bool = True,
        file_output: bool = False
    ):
        """
        设置自定义日志配置
        
        Args:
            level: 日志级别
            format_str: 日志格式
            file_path: 日志文件路径
            console_output: 是否输出到控制台
            file_output: 是否输出到文件
        """
        # 获取日志级别
        log_level = getattr(logging, level.upper())
        
        # 获取日志格式
        if format_str is None:
            format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # 创建格式化器
        formatter = logging.Formatter(format_str)
        
        # 清除现有处理器
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 控制台输出
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
        
        # 文件输出
        if file_output and file_path:
            try:
                # 创建日志目录
                log_dir = Path(file_path).parent
                log_dir.mkdir(parents=True, exist_ok=True)
                
                # 创建文件处理器
                file_handler = logging.FileHandler(file_path, encoding='utf-8')
                file_handler.setFormatter(formatter)
                root_logger.addHandler(file_handler)
                
            except Exception as e:
                print(f"设置文件输出失败: {e}")
        
        # 设置根日志级别
        root_logger.setLevel(log_level)
    
    def reload_config(self):
        """重新加载日志配置"""
        if self.config_manager:
            self._setup_from_config()
    
    def get_logging_status(self) -> Dict[str, Any]:
        """
        获取日志系统状态
        
        Returns:
            Dict[str, Any]: 日志系统状态信息
        """
        root_logger = logging.getLogger()
        
        # 使用统一的路径管理获取日志目录
        logs_dir = get_logs_dir(self.config_manager)
        
        # 获取当前配置的日志路径
        log_config = {}
        if self.config_manager:
            log_config = self.config_manager.get('logging', {})
        
        file_name = log_config.get('file_name', 'campusworld.log')
        full_log_path = logs_dir / file_name
        
        return {
            'level': logging.getLevelName(root_logger.level),
            'handlers_count': len(root_logger.handlers),
            'configured_loggers': list(self._configured_loggers),
            'project_root': str(get_project_root(self.config_manager)),
            'logs_dir': str(logs_dir),
            'file_name': file_name,
            'full_log_path': str(full_log_path),
            'handlers': [
                {
                    'type': type(handler).__name__,
                    'level': logging.getLevelName(handler.level),
                    'formatter': type(handler.formatter).__name__ if handler.formatter else None
                }
                for handler in root_logger.handlers
            ]
        }
