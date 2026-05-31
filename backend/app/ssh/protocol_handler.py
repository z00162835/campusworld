"""
协议处理器 - Protocol Layer

负责处理SSH协议相关的操作，与逻辑解耦。
参考Evenia的Portal层设计。
"""
import threading
from typing import Optional
from datetime import datetime
import paramiko
from paramiko import ServerInterface
from paramiko.common import AUTH_SUCCESSFUL, AUTH_FAILED, OPEN_SUCCEEDED
from app.core.config_manager import get_setting
from app.core.log import get_logger, LoggerNames
from app.ssh.session import SSHSession, SessionManager
from app.ssh.session_config import get_ssh_session_settings
from app.ssh.game_handler import game_handler
from app.ssh.rate_limiter import get_rate_limiter

class SSHProtocolHandler(ServerInterface):
    """
    SSH协议处理器（每连接 Portal）

    负责：
    - SSH连接管理
    - 用户认证（委托给GameHandler）
    - 本会话 transport 上下文（client_ip, authenticated_session）
    """

    def __init__(self, client_ip: str = 'unknown', *, session_manager: SessionManager):
        self.event = threading.Event()
        self.session_manager = session_manager
        self.client_ip = client_ip
        self._authenticated_session: Optional[SSHSession] = None
        self.logger = get_logger(LoggerNames.SSH)
        self.audit_logger = get_logger(LoggerNames.AUDIT)
        self.security_logger = get_logger(LoggerNames.SECURITY)
        self.auth_timeout = int(get_setting('ssh.session.auth_timeout_seconds', 20))

    @property
    def authenticated_session(self) -> Optional[SSHSession]:
        return self._authenticated_session

    def check_auth_password(self, username: str, password: str) -> int:
        """
        验证用户名和密码

        委托给GameHandler处理逻辑
        """
        self.security_logger.info(f'SSH authentication attempt', extra={'username': username, 'client_ip': self.client_ip, 'timestamp': datetime.now().isoformat()})
        try:
            result = game_handler.authenticate_user(username=username, password=password, client_ip=self.client_ip)
            rate_limiter = get_rate_limiter()
            rate_limiter.record_login_attempt(self.client_ip, result['success'])
            if result['success']:
                settings = get_ssh_session_settings()
                if settings.max_sessions_per_user > 0:
                    active_count = self.session_manager.count_active_sessions_for_user(result['user_id'])
                    if active_count >= settings.max_sessions_per_user:
                        self.security_logger.warning(
                            'ssh_session_limit_exceeded',
                            extra={
                                'username': username,
                                'user_id': result['user_id'],
                                'client_ip': self.client_ip,
                                'active_count': active_count,
                                'max_sessions_per_user': settings.max_sessions_per_user,
                                'event_type': 'ssh_session_limit_exceeded',
                            },
                        )
                        return AUTH_FAILED
                ssh_session = SSHSession(session_id=result['session_id'], username=result['username'], user_id=result['user_id'], user_attrs=result['user_attrs'])
                self._authenticated_session = ssh_session
                self.session_manager.add_session(ssh_session)
                self.audit_logger.info(f'SSH login succeeded', extra={'username': username, 'session_id': result['session_id'], 'client_ip': self.client_ip, 'login_time': datetime.now().isoformat(), 'event_type': 'ssh_login'})
                return AUTH_SUCCESSFUL
            else:
                self.security_logger.warning(f"SSH authentication failed: {result.get('error')}", extra={'username': username, 'client_ip': self.client_ip, 'event_type': 'auth_failed'})
                return AUTH_FAILED
        except Exception as e:
            self.security_logger.error(f'Authentication exception: {e}')
            return AUTH_FAILED

    def check_auth_publickey(self, username: str, key: paramiko.PKey) -> int:
        """验证公钥认证（暂不支持）"""
        self.logger.info(f'Public key authentication not supported for user: {username}')
        return AUTH_FAILED

    def check_channel_request(self, kind: str, chanid: int) -> int:
        """检查通道请求"""
        if kind == 'session':
            return OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_shell_request(self, channel: paramiko.Channel) -> bool:
        """检查shell请求"""
        return True

    def check_channel_pty_request(self, channel: paramiko.Channel, term: str, width: int, height: int, pixelwidth: int, pixelheight: int, modes: bytes) -> bool:
        """检查PTY请求"""
        return True

    def get_allowed_auths(self, username: str) -> str:
        """获取允许的认证方法"""
        return 'password'

    def check_channel_window_change_request(self, channel: paramiko.Channel, width: int, height: int, pixelwidth: int, pixelheight: int) -> bool:
        """检查窗口大小改变请求"""
        return True

class ProtocolFactory:
    """
    协议工厂

    用于创建不同类型的协议处理器
    """

    @staticmethod
    def create_ssh_handler(client_ip: str = 'unknown', *, session_manager: SessionManager) -> SSHProtocolHandler:
        """Create a per-connection SSH protocol handler (Portal)."""
        return SSHProtocolHandler(client_ip=client_ip, session_manager=session_manager)

    @staticmethod
    def load_host_key() -> paramiko.RSAKey:
        """加载或生成主机密钥"""
        from app.core.config_manager import get_setting
        from app.core.log import get_logger, LoggerNames
        logger = get_logger(LoggerNames.SSH)
        try:
            host_key_path = get_setting('ssh.host_key_path', 'ssh_host_key')
            return paramiko.RSAKey(filename=host_key_path)
        except (FileNotFoundError, paramiko.SSHException):
            logger.info('Generating new host key...')
            host_key = paramiko.RSAKey.generate(bits=4096)
            try:
                host_key_path = get_setting('ssh.host_key_path', 'ssh_host_key')
                host_key.write_private_key_file(host_key_path)
                logger.info(f'Host key saved to {host_key_path}')
            except Exception as e:
                logger.warning(f'Failed to save host key: {e}')
            return host_key
