"""
SSH服务器实现
基于Paramiko库，提供SSH控制台访问功能
"""

import socket
import threading
import time
from typing import Dict
from datetime import datetime

import paramiko
from paramiko import ServerInterface
from paramiko.common import AUTH_SUCCESSFUL, AUTH_FAILED, OPEN_SUCCEEDED
# Paramiko 4.0+ 不再需要 py3compat

from app.core.config_manager import get_setting
from app.core.database import SessionLocal
from app.models.graph import Node
from app.core.security import verify_password
from app.ssh.console import SSHConsole
from app.ssh.session import SSHSession, SessionManager
from app.core.log import get_logger, LoggerNames
from app.models.root_manager import root_manager
from app.models.user import User

class CampusWorldSSHServerInterface(ServerInterface):
    """CampusWorld SSH服务器实现"""
    
    def __init__(self):
        self.event = threading.Event()
        self.sessions: Dict[str, SSHSession] = {}
        self.session_manager = SessionManager()
        
        # 使用统一的日志系统
        self.logger = get_logger(LoggerNames.SSH)
        self.audit_logger = get_logger(LoggerNames.AUDIT)
        self.security_logger = get_logger(LoggerNames.SECURITY)
        
        # 服务器配置
        self.host_key = self._load_host_key()
        self.auth_timeout = get_setting('ssh.auth_timeout', 60)
        self.banner = get_setting('ssh.banner', 'Welcome to CampusWorld SSH Console')
        
    def _load_host_key(self) -> paramiko.RSAKey:
        """加载或生成主机密钥"""
        try:
            # 尝试从文件加载现有密钥
            host_key_path = get_setting('ssh.host_key_path', 'ssh_host_key')
            return paramiko.RSAKey(filename=host_key_path)
        except (FileNotFoundError, paramiko.SSHException):
            # 生成新的主机密钥
            self.logger.info("Generating new host key...")
            host_key = paramiko.RSAKey.generate(2048)
            
            # 保存密钥到文件
            try:
                host_key.write_private_key_file(host_key_path)
                self.logger.info(f"Host key saved to {host_key_path}")
            except Exception as e:
                self.logger.warning(f"Failed to save host key: {e}")
            
            return host_key
    
    def check_auth_password(self, username: str, password: str) -> int:
        """验证用户名和密码"""
        start_time = time.time()
        try:
            # 记录认证尝试
            self.security_logger.info(f"SSH认证尝试", extra={
                'username': username,
                'client_ip': getattr(self, 'client_ip', 'unknown'),
                'timestamp': datetime.now().isoformat()
            })
            
            # 查询数据库验证用户
            with SessionLocal() as session: 
                # 查找用户账号
                user_node = session.query(Node).filter(
                    Node.type_code == "account",
                    Node.name == username
                ).first()
                
                if not user_node:
                    self.security_logger.warning(f"用户不存在", extra={
                        'username': username,
                        'client_ip': getattr(self, 'client_ip', 'unknown'),
                        'event_type': 'auth_failed_user_not_found'
                    })
                    return AUTH_FAILED
                
                # 检查账号状态
                attrs = user_node.attributes
                if not attrs.get("is_active", True):
                    self.security_logger.warning(f"账号已禁用", extra={
                        'username': username,
                        'client_ip': getattr(self, 'client_ip', 'unknown'),
                        'event_type': 'auth_failed_account_inactive'
                    })
                    return AUTH_FAILED
                
                if attrs.get("is_locked", False):
                    self.security_logger.warning(f"账号已锁定", extra={
                        'username': username,
                        'client_ip': getattr(self, 'client_ip', 'unknown'),
                        'event_type': 'auth_failed_account_locked',
                        'lock_reason': attrs.get("lock_reason", "unknown")
                    })
                    return AUTH_FAILED
                
                if attrs.get("is_suspended", False):
                    suspension_until = attrs.get("suspension_until")
                    if suspension_until and datetime.fromisoformat(suspension_until) > datetime.now():
                        self.security_logger.warning(f"账号已暂停", extra={
                            'username': username,
                            'client_ip': getattr(self, 'client_ip', 'unknown'),
                            'event_type': 'auth_failed_account_suspended',
                            'suspension_until': suspension_until
                        })
                        return AUTH_FAILED
                
                # 验证密码
                stored_hash = attrs.get("hashed_password", "")
                if not stored_hash:
                    self.security_logger.warning(f"用户无密码哈希", extra={
                        'username': username,
                        'client_ip': getattr(self, 'client_ip', 'unknown'),
                        'event_type': 'auth_failed_no_password_hash'
                    })
                    return AUTH_FAILED
                
                if verify_password(password, stored_hash):
                    # 认证成功
                    session_id = f"{username}_{int(time.time())}"
                    ssh_session = SSHSession(
                        session_id=session_id,
                        username=username,
                        user_id=user_node.id,
                        user_attrs=attrs
                    )
                    
                    # 存储会话信息
                    self.sessions[session_id] = ssh_session
                    self.session_manager.add_session(ssh_session)
                    
                    if not hasattr(self, 'user_sessions'):
                        self.user_sessions = {}
                    self.user_sessions[username] = session_id
                    
                    # 更新最后登录时间
                    attrs["last_login"] = datetime.now().isoformat()
                    user_node.attributes = attrs
                    session.commit()
                    
                    # 确保用户spawn到奇点房间
                    self.spawn_user_to_singularity_room(user_node, session)
                    
                    # 记录成功认证
                    auth_duration = time.time() - start_time
                    self.security_logger.info(f"SSH认证成功", extra={
                        'username': username,
                        'client_ip': getattr(self, 'client_ip', 'unknown'),
                        'session_id': session_id,
                        'auth_duration': auth_duration,
                        'event_type': 'auth_success'
                    })
                    
                    # 记录审计日志
                    self.audit_logger.info(f"SSH登录成功", extra={
                        'username': username,
                        'session_id': session_id,
                        'client_ip': getattr(self, 'client_ip', 'unknown'),
                        'login_time': datetime.now().isoformat(),
                        'event_type': 'ssh_login'
                    })
                    
                    return AUTH_SUCCESSFUL
                else:
                    # 记录失败登录
                    failed_attempts = attrs.get("failed_login_attempts", 0) + 1
                    attrs["failed_login_attempts"] = failed_attempts
                    
                    # 检查是否需要锁定账号
                    max_attempts = attrs.get("max_failed_attempts", 5)
                    if failed_attempts >= max_attempts:
                        attrs["is_locked"] = True
                        attrs["lock_reason"] = "Too many failed login attempts"
                        attrs["locked_at"] = datetime.now().isoformat()
                        
                        self.security_logger.warning(f"账号因多次失败登录被锁定", extra={
                            'username': username,
                            'client_ip': getattr(self, 'client_ip', 'unknown'),
                            'failed_attempts': failed_attempts,
                            'max_attempts': max_attempts,
                            'event_type': 'account_locked'
                        })
                    
                    user_node.attributes = attrs
                    session.commit()
                    
                    self.security_logger.warning(f"SSH认证失败", extra={
                        'username': username,
                        'client_ip': getattr(self, 'client_ip', 'unknown'),
                        'failed_attempts': failed_attempts,
                        'event_type': 'auth_failed_wrong_password'
                    })
                    
            self.security_logger.warning(f"Failed to authenticate user: {e}")
            return AUTH_FAILED
                    
        except Exception as e:
            self.security_logger.error(f"Failed to authenticate user: {e}")
            return AUTH_FAILED
    
    def check_auth_publickey(self, username: str, key: paramiko.PKey) -> int:
        """验证公钥认证（暂不支持）"""
        self.logger.info(f"Public key authentication not supported for user: {username}")
        return AUTH_FAILED
    
    def check_channel_request(self, kind: str, chanid: int) -> int:
        """检查通道请求"""
        if kind == 'session':
            return OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
    
    def check_channel_shell_request(self, channel: paramiko.Channel) -> bool:
        """检查shell请求"""
        return True
    
    def check_channel_pty_request(self, channel: paramiko.Channel, term: str, width: int, height: int, 
                                 pixelwidth: int, pixelheight: int, modes: bytes) -> bool:
        """检查PTY请求"""
        return True
    
    def get_allowed_auths(self, username: str) -> str:
        """获取允许的认证方法"""
        return "password"
    
    def check_channel_window_change_request(self, channel: paramiko.Channel, width: int, height: int, 
                                          pixelwidth: int, pixelheight: int) -> bool:
        """检查窗口大小改变请求"""
        return True
    
    def spawn_user_to_singularity_room(self, user_node, session):
        """
        将用户spawn到奇点房间
        
        参考Evennia的DefaultHome设计，确保用户登录后出现在Singularity Room
        """
        try:
            
            # 确保根节点存在
            if not root_manager.ensure_root_node_exists():
                self.security_logger.warning(f"无法确保根节点存在，用户 {user_node.attributes.get('username', 'Unknown')} spawn失败")
                return False
            
            # 获取根节点
            root_node = root_manager.get_root_node(session)
            if not root_node:
                self.security_logger.warning(f"无法获取根节点，用户 {user_node.attributes.get('username', 'Unknown')} spawn失败")
                return False
            
            # 设置用户位置到根节点
            user_node.location_id = root_node.id
            user_node.home_id = root_node.id  # 同时设置为home
            
            # 更新最后活动时间
            attrs = user_node.attributes
            attrs["last_activity"] = datetime.now().isoformat()
            user_node.attributes = attrs
            
            # 提交更改
            session.commit()
            
            return True
            
        except Exception as e:
            self.security_logger.error(f"用户spawn到奇点房间失败: {e}", extra={
                'username': user_node.attributes.get('username', 'Unknown') if user_node else 'Unknown',
                'user_id': user_node.id if user_node else None,
                'error': str(e),
                'event_type': 'user_spawn_error'
            })
            return False



class CampusWorldSSHServer:
    """CampusWorld SSH服务器主类"""
    
    def __init__(self, host: str = None, port: int = None):
        self.host = host
        self.port = port
        self.server_socket = None
        self.server = None
        self.running = False
        
        # 使用统一的日志系统
        self.logger = get_logger(LoggerNames.SSH)
        self.audit_logger = get_logger(LoggerNames.AUDIT)
        
        # 创建SSH服务器接口
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
    
    # 启动服务器
    start_ssh_server()
