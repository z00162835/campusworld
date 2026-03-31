"""
日志管理器
负责统一管理日志配置和日志器创建

参考 Evennia MUD server 的日志实现:
1. 使用 QueueHandler + QueueListener 确保多线程日志顺序
2. 每次写入后立即 flush，保证日志不丢失
3. 支持日志轮转
"""

import logging
import logging.handlers
import os
import sys
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from queue import Queue
from app.core.paths import get_logs_dir, get_project_root


class FlushingRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """
    支持日志轮转的文件处理器，每次 emit 后立即刷新

    参考 Evennia 的做法：每次写入后调用 flush()，
    确保日志立即写入磁盘，防止缓冲导致日志顺序错乱或丢失。
    """

    def emit(self, record):
        """发送日志记录到文件并立即刷新"""
        super().emit(record)
        self.flush()


class FlushingTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """
    支持时间轮转的文件处理器，每次 emit 后立即刷新

    参考 Evennia 的做法：每次写入后调用 flush()，
    确保日志立即写入磁盘。
    """

    def emit(self, record):
        """发送日志记录到文件并立即刷新"""
        super().emit(record)
        self.flush()


class FlushingStreamHandler(logging.StreamHandler):
    """
    控制台处理器，每次 emit 后立即刷新

    确保 stdout 缓冲不会导致日志顺序错乱。
    """

    def emit(self, record):
        """发送日志记录到控制台并立即刷新"""
        super().emit(record)
        self.flush()


class ISOFormatter(logging.Formatter):
    """支持 ISO 8601 时间格式的格式化器"""

    def format(self, record):
        # 创建格式化时间
        dt = datetime.fromtimestamp(record.created)
        record.asctimeiso = dt.isoformat() + 'Z'
        return super().format(record)


class LoggingManager:
    """
    统一的日志管理器

    使用 QueueHandler + QueueListener 模式（参考 Evennia）：
    - 所有日志器通过 QueueHandler 发送记录到队列
    - 单一 QueueListener 线程顺序处理所有记录
    - 解决了多线程环境下日志顺序错乱的问题
    """

    _instance: Optional['LoggingManager'] = None
    _lock = threading.Lock()

    def __new__(cls, config_manager=None):
        """单例模式，确保只有一个日志管理器实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self, config_manager=None):
        """
        初始化日志管理器

        Args:
            config_manager: 配置管理器实例
        """
        if getattr(self, '_initialized', False):
            return
        self._initialized = True

        self.config_manager = config_manager
        self._configured_loggers = set()
        self._loggers: Dict[str, logging.Logger] = {}
        self._queue_handler: Optional[logging.handlers.QueueHandler] = None
        self._queue_listener: Optional[logging.handlers.QueueListener] = None
        self._handlers: List[logging.Handler] = []
        self._setup_root_logging()

    def _setup_root_logging(self):
        """设置根日志配置"""
        if self.config_manager:
            self._setup_from_config()
        else:
            self._setup_default()

    def _create_handlers(self) -> List[logging.Handler]:
        """
        创建日志处理器列表

        Returns:
            List[logging.Handler]: 处理器列表
        """
        handlers: List[logging.Handler] = []

        # 日志格式
        log_format = '%(asctimeiso)s | %(levelname)-8s | %(name)s | %(message)s'
        formatter = ISOFormatter(log_format)

        # 控制台处理器
        console_handler = FlushingStreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)

        # 文件处理器（支持轮转）
        logs_dir = get_logs_dir(self.config_manager)
        log_file = logs_dir / "campusworld.log"
        logs_dir.mkdir(parents=True, exist_ok=True)

        file_handler = FlushingRotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

        return handlers

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

            handlers: List[logging.Handler] = []

            # 控制台输出
            if log_config.get('console_output', True):
                console_handler = FlushingStreamHandler(sys.stdout)
                console_handler.setFormatter(formatter)
                handlers.append(console_handler)

            # 文件输出
            if log_config.get('file_output', False):
                file_name = log_config.get('file_name', 'campusworld.log')
                logs_dir = get_logs_dir(self.config_manager)
                full_log_path = logs_dir / file_name

                file_handler = self._create_file_handler(full_log_path, formatter, log_config)
                if file_handler:
                    handlers.append(file_handler)

            # 设置队列处理器和监听器
            self._setup_queue_logging(handlers)

            # 设置根日志级别
            root_logger.setLevel(level)

            # 设置特定模块的日志级别
            self._setup_module_log_levels(log_config)

        except Exception as e:
            print(f"从配置设置日志失败: {e}")
            self._setup_default()

    def _setup_default(self):
        """设置默认日志配置

        参考 Evennia 的日志策略：
        1. 使用 ISO 时间格式
        2. 所有处理器在单一线程中顺序处理
        3. 每次写入后立即刷新
        """
        logs_dir = get_logs_dir(self.config_manager)
        log_file = logs_dir / "campusworld.log"
        logs_dir.mkdir(parents=True, exist_ok=True)

        log_format = '%(asctimeiso)s | %(levelname)-8s | %(name)s | %(message)s'
        formatter = ISOFormatter(log_format)

        handlers: List[logging.Handler] = []

        # 控制台输出
        console_handler = FlushingStreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)

        # 文件输出（支持轮转）
        file_handler = FlushingRotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

        # 设置队列处理器和监听器
        self._setup_queue_logging(handlers)

        logger = logging.getLogger("campusworld.logging")
        logger.info(f"默认日志文件已配置: {log_file}")

    def _setup_queue_logging(self, handlers: List[logging.Handler]):
        """
        设置队列日志系统

        这是 Evennia 风格日志系统的核心：
        - QueueHandler 将日志发送到队列（非阻塞）
        - QueueListener 在单一线程中顺序处理所有日志
        - 解决了多线程日志顺序错乱的问题

        Args:
            handlers: 要注册的处理器列表
        """
        # 清除现有处理器
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # 创建队列（无界队列）
        queue: Queue = Queue(-1)

        # 创建队列处理器
        self._queue_handler = logging.handlers.QueueHandler(queue)

        # 添加队列处理器到根日志器
        root_logger.addHandler(self._queue_handler)
        root_logger.setLevel(logging.DEBUG)  # 让所有日志通过队列

        # 启动队列监听器（在独立线程中顺序处理）
        self._handlers = handlers
        self._queue_listener = logging.handlers.QueueListener(
            queue,
            *handlers,
            respect_handler_level=True
        )
        self._queue_listener.start()

    def _create_file_handler(self, file_path: Path, formatter: logging.Formatter, log_config: Dict[str, Any]) -> Optional[logging.Handler]:
        """创建文件处理器"""
        try:
            # 创建日志目录
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # 检查是否使用时间轮转
            rotate_type = log_config.get('rotate_type', 'size')  # 'size' or 'time'

            if rotate_type == 'time':
                # 时间轮转
                when = log_config.get('when', 'midnight')
                interval = log_config.get('interval', 1)
                backup_count = log_config.get('backup_count', 7)

                file_handler = FlushingTimedRotatingFileHandler(
                    file_path,
                    when=when,
                    interval=interval,
                    backupCount=backup_count,
                    encoding='utf-8'
                )
            else:
                # 大小轮转（默认）
                max_size = self._parse_size(log_config.get('max_file_size', '10MB'))
                backup_count = log_config.get('backup_count', 5)

                file_handler = FlushingRotatingFileHandler(
                    file_path,
                    maxBytes=max_size,
                    backupCount=backup_count,
                    encoding='utf-8'
                )

            file_handler.setFormatter(formatter)
            return file_handler

        except Exception as e:
            print(f"创建文件处理器失败: {e}")
            return None

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
        log_level = getattr(logging, level.upper())

        if format_str is None:
            format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

        formatter = logging.Formatter(format_str)

        # 清除现有处理器
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        handlers: List[logging.Handler] = []

        # 控制台输出
        if console_output:
            console_handler = FlushingStreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            handlers.append(console_handler)

        # 文件输出
        if file_output and file_path:
            try:
                log_dir = Path(file_path).parent
                log_dir.mkdir(parents=True, exist_ok=True)

                file_handler = FlushingRotatingFileHandler(file_path, encoding='utf-8')
                file_handler.setFormatter(formatter)
                handlers.append(file_handler)

            except Exception as e:
                print(f"设置文件输出失败: {e}")

        # 设置队列日志
        self._setup_queue_logging(handlers)

        root_logger.setLevel(log_level)

    def stop_listener(self):
        """
        停止队列监听器，确保所有日志写入完成

        在程序退出前调用，确保日志完整。
        这是参考 Evennia 的做法，确保所有日志都被 flush。
        """
        if self._queue_listener is not None:
            self._queue_listener.stop()
            self._queue_listener = None

    def reload_config(self):
        """重新加载日志配置"""
        self.stop_listener()
        if self.config_manager:
            self._setup_from_config()

    def get_logging_status(self) -> Dict[str, Any]:
        """
        获取日志系统状态

        Returns:
            Dict[str, Any]: 日志系统状态信息
        """
        root_logger = logging.getLogger()

        logs_dir = get_logs_dir(self.config_manager)

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
            'queue_listener_running': self._queue_listener is not None,
            'handlers': [
                {
                    'type': type(handler).__name__,
                    'level': logging.getLevelName(handler.level),
                    'formatter': type(handler.formatter).__name__ if handler.formatter else None
                }
                for handler in root_logger.handlers
            ]
        }


# 全局日志管理器实例获取函数
_logging_manager_instance: Optional[LoggingManager] = None


def get_logging_manager() -> LoggingManager:
    """
    获取全局日志管理器实例

    Returns:
        LoggingManager: 日志管理器实例
    """
    global _logging_manager_instance
    if _logging_manager_instance is None:
        _logging_manager_instance = LoggingManager()
    return _logging_manager_instance


# 保持向后兼容
def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    获取日志器（向后兼容）

    Args:
        name: 日志器名称
        level: 日志级别（可选）

    Returns:
        logging.Logger: 日志器实例
    """
    return get_logging_manager().get_logger(name)
