"""
日志处理器
提供各种日志处理器功能
"""

import logging
import logging.handlers
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List
from pathlib import Path

class RotatingFileHandler(logging.handlers.RotatingFileHandler):
    """轮转文件处理器（继承自标准库）"""
    
    def __init__(
        self,
        filename: str,
        mode: str = 'a',
        maxBytes: int = 0,
        backupCount: int = 0,
        encoding: Optional[str] = None,
        delay: bool = False
    ):
        """
        初始化轮转文件处理器
        
        Args:
            filename: 文件名
            mode: 文件模式
            maxBytes: 最大字节数
            backupCount: 备份文件数量
            encoding: 文件编码
            delay: 是否延迟打开文件
        """
        # 确保日志目录存在
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        
        super().__init__(
            filename=filename,
            mode=mode,
            maxBytes=maxBytes,
            backupCount=backupCount,
            encoding=encoding,
            delay=delay
        )

class TimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """时间轮转文件处理器（继承自标准库）"""
    
    def __init__(
        self,
        filename: str,
        when: str = 'h',
        interval: int = 1,
        backupCount: int = 0,
        encoding: Optional[str] = None,
        delay: bool = False,
        utc: bool = False,
        atTime: Optional[Any] = None
    ):
        """
        初始化时间轮转文件处理器
        
        Args:
            filename: 文件名
            when: 轮转时间单位
            interval: 轮转间隔
            backupCount: 备份文件数量
            encoding: 文件编码
            delay: 是否延迟打开文件
            utc: 是否使用UTC时间
            atTime: 轮转时间
        """
        # 确保日志目录存在
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        
        super().__init__(
            filename=filename,
            when=when,
            interval=interval,
            backupCount=backupCount,
            encoding=encoding,
            delay=delay,
            utc=utc,
            atTime=atTime
        )

class DatabaseHandler(logging.Handler):
    """数据库日志处理器"""
    
    def __init__(self, connection, table_name: str = 'logs'):
        """
        初始化数据库处理器
        
        Args:
            connection: 数据库连接
            table_name: 日志表名
        """
        super().__init__()
        self.connection = connection
        self.table_name = table_name
    
    def emit(self, record: logging.LogRecord):
        """
        发送日志记录到数据库
        
        Args:
            record: 日志记录
        """
        try:
            # 构建SQL插入语句
            sql = f"""
            INSERT INTO {self.table_name} 
            (timestamp, level, logger, message, module, function, line, exception)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # 准备数据
            data = (
                record.created,
                record.levelname,
                record.name,
                record.getMessage(),
                record.module,
                record.funcName,
                record.lineno,
                self.formatException(record.exc_info) if record.exc_info else None
            )
            
            # 执行插入
            cursor = self.connection.cursor()
            cursor.execute(sql, data)
            self.connection.commit()
            cursor.close()
            
        except Exception:
            # 避免日志处理器中的异常影响主程序
            self.handleError(record)

class EmailHandler(logging.Handler):
    """邮件日志处理器"""
    
    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
        to_emails: List[str],
        subject: str = "Log Alert",
        level: int = logging.ERROR
    ):
        """
        初始化邮件处理器
        
        Args:
            smtp_server: SMTP服务器
            smtp_port: SMTP端口
            username: 用户名
            password: 密码
            from_email: 发件人邮箱
            to_emails: 收件人邮箱列表
            subject: 邮件主题
            level: 日志级别
        """
        super().__init__(level)
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.to_emails = to_emails
        self.subject = subject
    
    def emit(self, record: logging.LogRecord):
        """
        发送日志记录到邮件
        
        Args:
            record: 日志记录
        """
        try:
            # 构建邮件内容
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)
            msg['Subject'] = f"{self.subject} - {record.levelname}"
            
            # 邮件正文
            body = f"""
日志级别: {record.levelname}
日志器: {record.name}
时间: {record.created}
模块: {record.module}
函数: {record.funcName}
行号: {record.lineno}
消息: {record.getMessage()}
"""
            
            if record.exc_info:
                body += f"\n异常信息:\n{self.formatException(record.exc_info)}"
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # 发送邮件
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            
        except Exception:
            # 避免邮件发送失败影响主程序
            self.handleError(record)

class MemoryHandler(logging.Handler):
    """内存日志处理器"""
    
    def __init__(self, capacity: int = 1000):
        """
        初始化内存处理器
        
        Args:
            capacity: 内存容量
        """
        super().__init__()
        self.capacity = capacity
        self.logs = []
    
    def emit(self, record: logging.LogRecord):
        """
        将日志记录存储到内存
        
        Args:
            record: 日志记录
        """
        # 格式化日志记录
        formatted_record = {
            'timestamp': record.created,
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # 添加到内存
        self.logs.append(formatted_record)
        
        # 保持容量限制
        if len(self.logs) > self.capacity:
            self.logs.pop(0)
    
    def get_logs(self, level: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取日志记录
        
        Args:
            level: 日志级别过滤
            limit: 限制数量
        
        Returns:
            List[Dict[str, Any]]: 日志记录列表
        """
        logs = self.logs
        
        # 按级别过滤
        if level:
            logs = [log for log in logs if log['level'] == level]
        
        # 限制数量
        if limit:
            logs = logs[-limit:]
        
        return logs
    
    def clear_logs(self):
        """清空日志记录"""
        self.logs.clear()
