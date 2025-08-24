"""
SSH配置模块
管理SSH服务器的配置参数
"""

from typing import Dict, Any, Optional
from app.core.config import get_setting


class SSHConfig:
    """SSH服务器配置"""
    
    def __init__(self):
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        # 服务器配置
        self.host = get_setting('ssh.host', '0.0.0.0')
        self.port = get_setting('ssh.port', 2222)
        self.banner = get_setting('ssh.banner', 'Welcome to CampusWorld SSH Console')
        
        # 认证配置
        self.auth_timeout = get_setting('ssh.auth_timeout', 60)
        self.idle_timeout = get_setting('ssh.idle_timeout', 1800)  # 30分钟
        self.max_connections = get_setting('ssh.max_connections', 100)
        self.max_connections_per_user = get_setting('ssh.max_connections_per_user', 3)
        
        # 安全配置
        self.allowed_auth_methods = get_setting('ssh.allowed_auth_methods', ['password'])
        self.password_auth_enabled = get_setting('ssh.password_auth_enabled', True)
        self.public_key_auth_enabled = get_setting('ssh.public_key_auth_enabled', False)
        
        # 密钥配置
        self.host_key_path = get_setting('ssh.host_key_path', 'ssh_host_key')
        self.host_key_bits = get_setting('ssh.host_key_bits', 2048)
        
        # 日志配置
        self.log_level = get_setting('ssh.log_level', 'INFO')
        self.log_file = get_setting('ssh.log_file', 'logs/ssh.log')
        self.log_format = get_setting('ssh.log_format', 
                                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # 会话配置
        self.session_timeout = get_setting('ssh.session_timeout', 1800)  # 30分钟
        self.max_command_history = get_setting('ssh.max_command_history', 100)
        self.enable_command_logging = get_setting('ssh.enable_command_logging', True)
        
        # 性能配置
        self.worker_threads = get_setting('ssh.worker_threads', 10)
        self.connection_backlog = get_setting('ssh.connection_backlog', 100)
        self.socket_timeout = get_setting('ssh.socket_timeout', 1.0)
    
    def get_server_config(self) -> Dict[str, Any]:
        """获取服务器配置"""
        return {
            'host': self.host,
            'port': self.port,
            'banner': self.banner,
            'max_connections': self.max_connections,
            'connection_backlog': self.connection_backlog,
            'socket_timeout': self.socket_timeout
        }
    
    def get_auth_config(self) -> Dict[str, Any]:
        """获取认证配置"""
        return {
            'auth_timeout': self.auth_timeout,
            'idle_timeout': self.idle_timeout,
            'allowed_auth_methods': self.allowed_auth_methods,
            'password_auth_enabled': self.password_auth_enabled,
            'public_key_auth_enabled': self.public_key_auth_enabled,
            'max_connections_per_user': self.max_connections_per_user
        }
    
    def get_security_config(self) -> Dict[str, Any]:
        """获取安全配置"""
        return {
            'host_key_path': self.host_key_path,
            'host_key_bits': self.host_key_bits,
            'enable_command_logging': self.enable_command_logging
        }
    
    def get_session_config(self) -> Dict[str, Any]:
        """获取会话配置"""
        return {
            'session_timeout': self.session_timeout,
            'max_command_history': self.max_command_history,
            'enable_command_logging': self.enable_command_logging
        }
    
    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return {
            'log_level': self.log_level,
            'log_file': self.log_file,
            'log_format': self.log_format
        }
    
    def validate_config(self) -> bool:
        """验证配置有效性"""
        try:
            # 检查端口范围
            if not (1 <= self.port <= 65535):
                raise ValueError(f"Invalid port number: {self.port}")
            
            # 检查超时设置
            if self.auth_timeout <= 0:
                raise ValueError(f"Invalid auth timeout: {self.auth_timeout}")
            
            if self.idle_timeout <= 0:
                raise ValueError(f"Invalid idle timeout: {self.idle_timeout}")
            
            # 检查连接限制
            if self.max_connections <= 0:
                raise ValueError(f"Invalid max connections: {self.max_connections}")
            
            if self.max_connections_per_user <= 0:
                raise ValueError(f"Invalid max connections per user: {self.max_connections_per_user}")
            
            # 检查密钥位数
            if self.host_key_bits not in [1024, 2048, 4096]:
                raise ValueError(f"Invalid host key bits: {self.host_key_bits}")
            
            return True
            
        except Exception as e:
            print(f"Configuration validation failed: {e}")
            return False
    
    def get_config_summary(self) -> str:
        """获取配置摘要"""
        summary = f"""
SSH Server Configuration:
========================
Server:
  Host: {self.host}
  Port: {self.port}
  Max Connections: {self.max_connections}
  Connection Backlog: {self.connection_backlog}

Authentication:
  Auth Timeout: {self.auth_timeout}s
  Idle Timeout: {self.idle_timeout}s
  Max Connections per User: {self.max_connections_per_user}
  Password Auth: {'Enabled' if self.password_auth_enabled else 'Disabled'}
  Public Key Auth: {'Enabled' if self.public_key_auth_enabled else 'Disabled'}

Security:
  Host Key Path: {self.host_key_path}
  Host Key Bits: {self.host_key_bits}
  Command Logging: {'Enabled' if self.enable_command_logging else 'Disabled'}

Session:
  Session Timeout: {self.session_timeout}s
  Max Command History: {self.max_command_history}
  Worker Threads: {self.worker_threads}

Logging:
  Log Level: {self.log_level}
  Log File: {self.log_file}
"""
        return summary


# 全局配置实例
ssh_config = SSHConfig()


def get_ssh_config() -> SSHConfig:
    """获取SSH配置实例"""
    return ssh_config


def reload_ssh_config():
    """重新加载SSH配置"""
    global ssh_config
    ssh_config = SSHConfig()
    return ssh_config
