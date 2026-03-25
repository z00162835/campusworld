"""
SSH服务器实现
基于Paramiko库，提供SSH控制台访问功能

架构说明:
- Protocol Layer (本文件 + protocol_handler.py): 处理SSH协议
- Game Layer (game_handler.py): 处理游戏逻辑

参考Evenia的Portal-Server双层架构设计
"""

import socket
import threading
import time
from typing import Dict, Optional
from datetime import datetime

import paramiko
from paramiko import ServerInterface
from paramiko.common import AUTH_SUCCESSFUL, AUTH_FAILED, OPEN_SUCCEEDED
# Paramiko 4.0+ 不再需要 py3compat

from app.core.config_manager import get_setting
from app.core.log import get_logger, LoggerNames
from app.ssh.console import SSHConsole
from app.ssh.session import SSHSession, SessionManager
from app.ssh.protocol_handler import SSHProtocolHandler, ProtocolFactory
from app.ssh.game_handler import game_handler


class CampusWorldSSHServerInterface(SSHProtocolHandler):
    """
    CampusWorld SSH服务器接口

    继承自SSHProtocolHandler，处理SSH协议相关操作
    游戏逻辑已委托给GameHandler
    """

    def __init__(self):
        # 初始化父类（Protocol Layer）
        super().__init__()

        # 服务器配置
        self.host_key = self._load_host_key()
        self.banner = get_setting('ssh.banner', 'Welcome to CampusWorld SSH Console')

    def _load_host_key(self) -> paramiko.RSAKey:
        """加载或生成主机密钥"""
        return ProtocolFactory.load_host_key()

    def check_auth_password(self, username: str, password: str) -> int:
        """
        验证用户名和密码

        委托给父类SSHProtocolHandler处理，父类会调用GameHandler
        """
        return super().check_auth_password(username, password)


class CampusWorldSSHServer:
    """
    CampusWorld SSH服务器主类

    负责SSH服务器的生命周期管理
    """

    def __init__(self, host: str = None, port: int = None):
        self.host = host
        self.port = port
        self.server_socket = None
        self.server = None
        self.running = False

        # 使用统一的日志系统
        self.logger = get_logger(LoggerNames.SSH)
        self.audit_logger = get_logger(LoggerNames.AUDIT)

        # 创建SSH服务器接口（Protocol Layer）
        self.ssh_interface = CampusWorldSSHServerInterface()

        # 记录服务器初始化
        self.logger.info(f"SSH服务器初始化", extra={
            'host': self.host,
            'port': self.port,
            'event_type': 'ssh_server_init'
        })

    def start(self):
        """启动SSH服务器"""
        start_time = time.time()

        try:
            # 创建服务器socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(100)

            self.running = True

            # 记录服务器启动成功
            startup_duration = time.time() - start_time
            self.logger.info(f"SSH服务器启动成功", extra={
                'host': self.host,
                'port': self.port,
                'startup_duration': startup_duration,
                'event_type': 'ssh_server_start'
            })

            # 记录审计日志
            self.audit_logger.info(f"SSH服务器启动", extra={
                'host': self.host,
                'port': self.port,
                'startup_time': datetime.now().isoformat(),
                'event_type': 'ssh_server_startup'
            })

            # 主服务器循环
            while self.running:
                try:
                    client, addr = self.server_socket.accept()

                    # 记录新连接
                    self.logger.info(f"接受新SSH连接", extra={
                        'client_ip': addr[0],
                        'client_port': addr[1],
                        'event_type': 'ssh_connection_accepted'
                    })

                    # 为每个连接创建新线程
                    t = threading.Thread(target=self._handle_client, args=(client, addr))
                    t.daemon = True
                    t.start()

                except Exception as e:
                    if self.running:
                        self.logger.error(f"接受SSH连接时出错", extra={
                            'error': str(e),
                            'error_type': type(e).__name__,
                            'event_type': 'ssh_accept_error'
                        })

        except Exception as e:
            self.logger.error(f"启动SSH服务器失败", extra={
                'host': self.host,
                'port': self.port,
                'error': str(e),
                'error_type': type(e).__name__,
                'event_type': 'ssh_server_start_failed'
            })
            raise

    def _handle_client(self, client: socket.socket, addr: tuple):
        """处理客户端连接"""
        client_ip = addr[0]
        client_port = addr[1]
        connection_id = f"{client_ip}:{client_port}_{int(time.time())}"
        console = None
        channel = None
        transport = None

        # 记录连接开始
        self.logger.info(f"新SSH连接", extra={
            'client_ip': client_ip,
            'client_port': client_port,
            'connection_id': connection_id,
            'event_type': 'ssh_connection_start'
        })

        try:
            # 创建传输
            t = paramiko.Transport(client)
            t.add_server_key(self.ssh_interface.host_key)
            t.start_server(server=self.ssh_interface)

            # 等待认证
            channel = t.accept(20)
            if channel is None:
                self.logger.warning(f"SSH认证超时", extra={
                    'client_ip': client_ip,
                    'client_port': client_port,
                    'connection_id': connection_id,
                    'event_type': 'ssh_auth_timeout'
                })
                return

            # 创建控制台实例
            console = SSHConsole(channel, None)

            # 设置会话
            try:
                transport = channel.get_transport()
                if hasattr(transport, 'get_username'):
                    username = transport.get_username()
                    self.logger.info(f"设置SSH控制台", extra={
                        'username': username,
                        'client_ip': client_ip,
                        'connection_id': connection_id,
                        'event_type': 'ssh_console_setup'
                    })

                    # 查找对应的会话
                    for session_id, session in self.ssh_interface.sessions.items():
                        if session.username == username:
                            console.current_session = session

                            # 触发用户spawn到初始位置（Game Layer）
                            game_handler.spawn_user(
                                user_id=session.user_id,
                                username=username
                            )

                            self.logger.info(f"SSH会话已设置", extra={
                                'username': username,
                                'session_id': session_id,
                                'client_ip': client_ip,
                                'connection_id': connection_id,
                                'event_type': 'ssh_session_established'
                            })
                            break
                    else:
                        self.logger.warning(f"未找到对应的SSH会话", extra={
                            'username': username,
                            'client_ip': client_ip,
                            'connection_id': connection_id,
                            'event_type': 'ssh_session_not_found'
                        })
                else:
                    self.logger.warning(f"无法从传输层获取用户名", extra={
                        'client_ip': client_ip,
                        'connection_id': connection_id,
                        'event_type': 'ssh_username_not_available'
                    })
            except Exception as e:
                self.logger.error(f"设置SSH控制台会话时出错", extra={
                    'client_ip': client_ip,
                    'connection_id': connection_id,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'event_type': 'ssh_console_setup_error'
                })

            # 运行控制台
            console.run()

        except Exception as e:
            self.logger.error(f"处理SSH客户端连接时出错", extra={
                'client_ip': client_ip,
                'client_port': client_port,
                'connection_id': connection_id,
                'error': str(e),
                'error_type': type(e).__name__,
                'event_type': 'ssh_connection_error'
            })
        finally:
            # 记录连接结束
            self.logger.info(f"SSH连接结束", extra={
                'client_ip': client_ip,
                'client_port': client_port,
                'connection_id': connection_id,
                'event_type': 'ssh_connection_end'
            })

        # 清理资源 - 按正确顺序关闭
        try:
            # 1. 清理控制台
            if console:
                console._cleanup()

            # 2. 关闭SSH通道
            if channel and not channel.closed:
                try:
                    channel.close()
                except Exception as e:
                    self.logger.warning(f"关闭SSH通道时出错: {e}")

            # 3. 关闭SSH传输层
            if transport and transport.is_active():
                try:
                    transport.close()
                except Exception as e:
                    self.logger.warning(f"关闭SSH传输层时出错: {e}")

            # 4. 关闭客户端socket
            if client:
                try:
                    client.close()
                except Exception as e:
                    self.logger.warning(f"关闭客户端socket时出错: {e}")

        except Exception as e:
            self.logger.error(f"清理SSH连接资源时出错: {e}")

    def stop(self):
        """停止SSH服务器"""
        stop_start_time = time.time()

        self.logger.info(f"开始停止SSH服务器", extra={
            'host': self.host,
            'port': self.port,
            'event_type': 'ssh_server_stop_start'
        })

        self.running = False

        if self.server_socket:
            try:
                self.server_socket.close()
                self.logger.info(f"SSH服务器socket已关闭", extra={
                    'event_type': 'ssh_socket_closed'
                })
            except Exception as e:
                self.logger.error(f"关闭SSH服务器socket时出错", extra={
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'event_type': 'ssh_socket_close_error'
                })

        # 清理所有会话
        try:
            self.ssh_interface.session_manager.cleanup_all()
            self.logger.info(f"SSH会话已清理", extra={
                'event_type': 'ssh_sessions_cleaned'
            })
        except Exception as e:
            self.logger.error(f"清理SSH会话时出错", extra={
                'error': str(e),
                'error_type': type(e).__name__,
                'event_type': 'ssh_sessions_cleanup_error'
            })

        stop_duration = time.time() - stop_start_time
        self.logger.info(f"SSH服务器已停止", extra={
            'host': self.host,
            'port': self.port,
            'stop_duration': stop_duration,
            'event_type': 'ssh_server_stopped'
        })

        # 记录审计日志
        self.audit_logger.info(f"SSH服务器停止", extra={
            'host': self.host,
            'port': self.port,
            'stop_time': datetime.now().isoformat(),
            'event_type': 'ssh_server_shutdown'
        })


def start_ssh_server(host: str = None, port: int = None):
    """启动SSH服务器的便捷函数"""
    # 使用统一的日志系统
    logger = get_logger(LoggerNames.SSH)
    audit_logger = get_logger(LoggerNames.AUDIT)

    logger.info(f"启动SSH服务器便捷函数", extra={
        'host': host,
        'port': port,
        'event_type': 'ssh_server_convenience_start'
    })

    server = CampusWorldSSHServer(host, port)
    try:
        server.start()
    except KeyboardInterrupt:
        logger.info(f"收到中断信号，停止SSH服务器", extra={
            'event_type': 'ssh_server_interrupted'
        })
        server.stop()
    except Exception as e:
        logger.error(f"SSH服务器运行时出错", extra={
            'error': str(e),
            'error_type': type(e).__name__,
            'event_type': 'ssh_server_runtime_error'
        })
        server.stop()


if __name__ == "__main__":
    # 获取日志器
    logger = get_logger(LoggerNames.SSH)
    logger.info(f"SSH服务器主程序启动", extra={
        'event_type': 'ssh_server_main_start'
    })
