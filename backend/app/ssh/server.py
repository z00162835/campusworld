"""
SSH服务器实现
基于Paramiko库，提供SSH控制台访问功能

架构说明:
- Protocol Layer (本文件 + protocol_handler.py): 处理SSH协议
- Game Layer (game_handler.py): 处理逻辑

参考Evenia的Portal-Server双层架构设计
"""
import socket
import threading
import time
from typing import Dict, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future
import paramiko
from app.core.config_manager import get_setting
from app.core.log import get_logger, LoggerNames
from app.ssh.console import SSHConsole
from app.ssh.session import SessionManager
from app.ssh.protocol_handler import ProtocolFactory
from app.ssh.game_handler import game_handler
from app.ssh.rate_limiter import get_rate_limiter
from app.ssh.session_config import get_ssh_session_settings

class CampusWorldSSHServer:
    """
    CampusWorld SSH服务器主类

    负责SSH服务器的生命周期管理
    """

    def __init__(self, host: str=None, port: int=None):
        self.host = host
        self.port = port
        self.server_socket = None
        self.server = None
        self.running = False
        self.logger = get_logger(LoggerNames.SSH)
        self.audit_logger = get_logger(LoggerNames.AUDIT)
        self.host_key = ProtocolFactory.load_host_key()
        self.banner = get_setting('ssh.banner', 'Welcome to CampusWorld SSH Console')
        self.session_manager = SessionManager()
        max_workers = get_setting('ssh.worker_pool_size', 50)
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='ssh_client')
        self.active_connections: Dict[str, Future] = {}
        self.connections_lock = threading.Lock()
        self.logger.info(f'SSH server initialization', extra={'host': self.host, 'port': self.port, 'max_workers': max_workers, 'event_type': 'ssh_server_init'})

    def start(self):
        """启动SSH服务器"""
        start_time = time.time()
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(100)
            self.running = True
            startup_duration = time.time() - start_time
            self.logger.info(f'SSH server started successfully', extra={'host': self.host, 'port': self.port, 'startup_duration': startup_duration, 'event_type': 'ssh_server_start'})
            self.audit_logger.info(f'SSH server start', extra={'host': self.host, 'port': self.port, 'startup_time': datetime.now().isoformat(), 'event_type': 'ssh_server_startup'})
            while self.running:
                try:
                    (client, addr) = self.server_socket.accept()
                    self.logger.info(f'Accepting new SSH connection', extra={'client_ip': addr[0], 'client_port': addr[1], 'event_type': 'ssh_connection_accepted'})
                    future = self.executor.submit(self._handle_client, client, addr)
                    with self.connections_lock:
                        connection_id = f'{addr[0]}:{addr[1]}'
                        self.active_connections[connection_id] = future
                    self._cleanup_completed_connections()
                except Exception as e:
                    if self.running:
                        self.logger.error(f'Error accepting SSH connection', extra={'error': str(e), 'error_type': type(e).__name__, 'event_type': 'ssh_accept_error'})
        except Exception as e:
            self.logger.error(f'Failed to start SSH server', extra={'host': self.host, 'port': self.port, 'error': str(e), 'error_type': type(e).__name__, 'event_type': 'ssh_server_start_failed'})
            raise

    def _handle_client(self, client: socket.socket, addr: tuple):
        """处理客户端连接"""
        client_ip = addr[0]
        client_port = addr[1]
        connection_id = f'{client_ip}:{client_port}_{int(time.time())}'
        console = None
        channel = None
        transport = None
        handler = None
        rate_limiter = get_rate_limiter()
        check_result = rate_limiter.check_connection(client_ip)
        if not check_result['allowed']:
            self.logger.warning(f'SSH connection rejected by rate limiter', extra={'client_ip': client_ip, 'client_port': client_port, 'reason': check_result.get('reason'), 'connection_id': connection_id, 'event_type': 'ssh_connection_rate_limited'})
            try:
                reject_msg = b'Connection rate limit exceeded. Please try again later.\r\n'
                client.send(reject_msg)
            except Exception as e:
                self.logger.warning(f'Failed to send rate limit rejection message: {e}')
            try:
                client.close()
            except Exception as e:
                self.logger.warning(f'Failed to close client connection after rate limit: {e}')
            return
        self.logger.info(f'New SSH connection', extra={'client_ip': client_ip, 'client_port': client_port, 'connection_id': connection_id, 'event_type': 'ssh_connection_start'})
        try:
            handler = ProtocolFactory.create_ssh_handler(client_ip, session_manager=self.session_manager)
            t = paramiko.Transport(client)
            transport = t
            session_settings = get_ssh_session_settings()
            if session_settings.keepalive_interval_seconds > 0:
                t.set_keepalive(session_settings.keepalive_interval_seconds)
                self.logger.debug('SSH transport keepalive enabled', extra={'interval_seconds': session_settings.keepalive_interval_seconds, 'event_type': 'ssh_session_keepalive_enabled'})
            t.add_server_key(self.host_key)
            t.start_server(server=handler)
            auth_timeout = max(1, session_settings.auth_timeout_seconds)
            channel = t.accept(auth_timeout)
            if channel is None:
                self.logger.warning(f'SSH authentication timed out', extra={'client_ip': client_ip, 'client_port': client_port, 'connection_id': connection_id, 'event_type': 'ssh_auth_timeout'})
                return
            ssh_session = handler.authenticated_session
            if ssh_session is None:
                self.logger.warning(f'No matching SSH session found', extra={'client_ip': client_ip, 'connection_id': connection_id, 'event_type': 'ssh_session_not_found'})
                return
            try:
                ssh_session.set_channel(channel)
                game_handler.spawn_user(user_id=ssh_session.user_id, username=ssh_session.username)
                self.session_manager.touch_session(ssh_session.session_id, reason='console_ready')
                self.logger.info(
                    f'SSH session set',
                    extra={
                        'username': ssh_session.username,
                        'session_id': ssh_session.session_id,
                        'client_ip': client_ip,
                        'connection_id': connection_id,
                        'event_type': 'ssh_session_established',
                    },
                )
            except Exception as e:
                self.logger.error(f'Error setting SSH console session', extra={'client_ip': client_ip, 'connection_id': connection_id, 'error': str(e), 'error_type': type(e).__name__, 'event_type': 'ssh_console_setup_error'})
                return
            console = SSHConsole(channel, ssh_session, session_manager=self.session_manager, game_handler=game_handler)
            console.run()
        except Exception as e:
            self.logger.error(f'Error handling SSH client connection', extra={'client_ip': client_ip, 'client_port': client_port, 'connection_id': connection_id, 'error': str(e), 'error_type': type(e).__name__, 'event_type': 'ssh_connection_error'})
        finally:
            self.logger.info(f'SSH connection ended', extra={'client_ip': client_ip, 'client_port': client_port, 'connection_id': connection_id, 'event_type': 'ssh_connection_end'})
        try:
            if console:
                console._cleanup()
            if channel and (not channel.closed):
                try:
                    channel.close()
                except Exception as e:
                    self.logger.warning(f'Error closing SSH channel: {e}')
            if transport and transport.is_active():
                try:
                    transport.close()
                except Exception as e:
                    self.logger.warning(f'Error closing SSH transport: {e}')
            if client:
                try:
                    client.close()
                except Exception as e:
                    self.logger.warning(f'Error closing client socket: {e}')
        except Exception as e:
            self.logger.error(f'Error cleaning up SSH connection resources: {e}')

    def stop(self, force: bool=True):
        """停止SSH服务器

        Args:
            force: 是否强制关闭。True时立即关闭所有连接，False时优雅关闭（超时后强制）
        """
        stop_start_time = time.time()
        if hasattr(self, '_stopInitiated') and self._stopInitiated:
            return
        self._stopInitiated = True
        self.logger.info(f'Stopping SSH server', extra={'host': self.host, 'port': self.port, 'force': force, 'event_type': 'ssh_server_stop_start'})
        self.running = False
        self.logger.warning('Force closing SSH server...')
        try:
            self.session_manager.force_close_all()
        except Exception as e:
            self.logger.error(f'Force close sessions failed: {e}')
        if self.executor:
            self.executor.shutdown(wait=False)
            self.logger.info(f'SSH thread pool shut down', extra={'event_type': 'ssh_executor_shutdown'})
        if self.server_socket:
            try:
                self.server_socket.close()
                self.logger.info(f'SSH server socket closed', extra={'event_type': 'ssh_socket_closed'})
            except Exception as e:
                self.logger.error(f'Error closing SSH server socket', extra={'error': str(e), 'error_type': type(e).__name__, 'event_type': 'ssh_socket_close_error'})
        try:
            self.session_manager.cleanup_all()
            self.logger.info(f'SSH session cleaned up', extra={'event_type': 'ssh_sessions_cleaned'})
        except Exception as e:
            self.logger.error(f'Error cleaning up SSH session', extra={'error': str(e), 'error_type': type(e).__name__, 'event_type': 'ssh_sessions_cleanup_error'})
        stop_duration = time.time() - stop_start_time
        self.logger.info(f'SSH server stopped', extra={'host': self.host, 'port': self.port, 'stop_duration': stop_duration, 'event_type': 'ssh_server_stopped'})
        self.audit_logger.info(f'SSH server stop', extra={'host': self.host, 'port': self.port, 'stop_time': datetime.now().isoformat(), 'event_type': 'ssh_server_shutdown'})

    def _cleanup_completed_connections(self):
        """清理已完成的连接"""
        with self.connections_lock:
            completed = []
            for (conn_id, future) in self.active_connections.items():
                if future.done():
                    completed.append(conn_id)
            for conn_id in completed:
                del self.active_connections[conn_id]
            if completed:
                self.logger.debug(f'Cleaned up {len(completed)} completed connections')

def start_ssh_server(host: str=None, port: int=None):
    """启动SSH服务器的便捷函数"""
    logger = get_logger(LoggerNames.SSH)
    audit_logger = get_logger(LoggerNames.AUDIT)
    logger.info(f'Starting SSH server convenience entry', extra={'host': host, 'port': port, 'event_type': 'ssh_server_convenience_start'})
    server = CampusWorldSSHServer(host, port)
    try:
        server.start()
    except KeyboardInterrupt:
        logger.info(f'Interrupt received, stopping SSH server', extra={'event_type': 'ssh_server_interrupted'})
        server.stop()
    except Exception as e:
        logger.error(f'SSH server runtime error', extra={'error': str(e), 'error_type': type(e).__name__, 'event_type': 'ssh_server_runtime_error'})
        server.stop()
if __name__ == '__main__':
    logger = get_logger(LoggerNames.SSH)
    logger.info(f'SSH server main program started', extra={'event_type': 'ssh_server_main_start'})
