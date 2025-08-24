"""
SSH服务器实现
基于Paramiko库，提供SSH控制台访问功能
"""

import socket
import threading
import logging
import time
from typing import Dict, Optional, Any
from datetime import datetime

import paramiko
from paramiko import ServerInterface, SFTPServerInterface
from paramiko.common import AUTH_SUCCESSFUL, AUTH_FAILED, OPEN_SUCCEEDED
# Paramiko 4.0+ 不再需要 py3compat

from app.core.config import get_setting
from app.core.database import SessionLocal
from app.models.graph import Node
from app.core.security import verify_password
from app.ssh.console import SSHConsole
from app.ssh.session import SSHSession, SessionManager


class CampusWorldSSHServerInterface(ServerInterface):
    """CampusWorld SSH服务器实现"""
    
    def __init__(self):
        self.event = threading.Event()
        self.sessions: Dict[str, SSHSession] = {}
        self.session_manager = SessionManager()
        
        # 配置日志
        self.logger = logging.getLogger(__name__)
        
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
        try:
            self.logger.info(f"Authentication attempt for user: {username}")
            
            # 查询数据库验证用户
            session = SessionLocal()
            try:
                # 查找用户账号
                user_node = session.query(Node).filter(
                    Node.type_code == "account",
                    Node.attributes['username'].astext == username
                ).first()
                
                if not user_node:
                    self.logger.warning(f"User not found: {username}")
                    return AUTH_FAILED
                
                # 检查账号状态
                attrs = user_node.attributes
                if not attrs.get("is_active", True):
                    self.logger.warning(f"Account inactive: {username}")
                    return AUTH_FAILED
                
                if attrs.get("is_locked", False):
                    self.logger.warning(f"Account locked: {username}")
                    return AUTH_FAILED
                
                if attrs.get("is_suspended", False):
                    suspension_until = attrs.get("suspension_until")
                    if suspension_until and datetime.fromisoformat(suspension_until) > datetime.now():
                        self.logger.warning(f"Account suspended: {username}")
                        return AUTH_FAILED
                
                # 验证密码
                stored_hash = attrs.get("password_hash", "")
                if not stored_hash:
                    self.logger.warning(f"No password hash for user: {username}")
                    return AUTH_FAILED
                
                if verify_password(password, stored_hash):
                    # 认证成功，创建会话
                    session_id = f"{username}_{int(time.time())}"
                    ssh_session = SSHSession(
                        session_id=session_id,
                        username=username,
                        user_id=user_node.id,
                        user_attrs=attrs
                    )
                    
                    # 存储会话信息，供后续使用
                    self.sessions[session_id] = ssh_session
                    self.session_manager.add_session(ssh_session)
                    
                    # 存储用户名到会话ID的映射
                    if not hasattr(self, 'user_sessions'):
                        self.user_sessions = {}
                    self.user_sessions[username] = session_id
                    
                    # 更新最后登录时间
                    attrs["last_login"] = datetime.now().isoformat()
                    user_node.attributes = attrs
                    session.commit()
                    
                    self.logger.info(f"Authentication successful for user: {username}")
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
                        self.logger.warning(f"Account locked due to failed attempts: {username}")
                    
                    user_node.attributes = attrs
                    session.commit()
                    
                    self.logger.warning(f"Authentication failed for user: {username}")
                    return AUTH_FAILED
                    
            finally:
                session.close()
                
        except Exception as e:
            self.logger.error(f"Authentication error for user {username}: {e}")
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


class CampusWorldSSHServer:
    """CampusWorld SSH服务器主类"""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 2222):
        self.host = host
        self.port = port
        self.server_socket = None
        self.server = None
        self.running = False
        
        # 配置日志
        self.logger = logging.getLogger(__name__)
        
        # 创建SSH服务器接口
        self.ssh_interface = CampusWorldSSHServerInterface()
        
    def start(self):
        """启动SSH服务器"""
        try:
            # 创建服务器socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(100)
            
            self.logger.info(f"SSH server started on {self.host}:{self.port}")
            self.running = True
            
            # 主服务器循环
            while self.running:
                try:
                    client, addr = self.server_socket.accept()
                    self.logger.info(f"Connection from {addr[0]}:{addr[1]}")
                    
                    # 为每个连接创建新线程
                    t = threading.Thread(target=self._handle_client, args=(client, addr))
                    t.daemon = True
                    t.start()
                    
                except Exception as e:
                    if self.running:
                        self.logger.error(f"Error accepting connection: {e}")
                        
        except Exception as e:
            self.logger.error(f"Failed to start SSH server: {e}")
            raise
            
    def _handle_client(self, client: socket.socket, addr: tuple):
        """处理客户端连接"""
        try:
            # 创建传输
            t = paramiko.Transport(client)
            t.add_server_key(self.ssh_interface.host_key)
            t.start_server(server=self.ssh_interface)
            
            # 等待认证
            channel = t.accept(20)
            if channel is None:
                self.logger.warning(f"Authentication timeout for {addr[0]}:{addr[1]}")
                return
                
            # 等待shell请求
            channel.send(self.ssh_interface.banner + '\n')
            channel.send('Type "help" for available commands.\n\n')
            
            # 创建控制台实例
            console = SSHConsole(channel, self.ssh_interface)
            
            # 设置会话（从认证成功的会话中获取）
            # 这里需要根据用户名找到对应的会话
            # 由于认证成功后，我们需要知道是哪个用户
            # 暂时创建一个匿名会话，后续可以通过其他方式识别用户
            
            # 尝试从传输中获取认证信息
            try:
                # 获取认证的用户名
                transport = channel.get_transport()
                if hasattr(transport, 'get_username'):
                    username = transport.get_username()
                    # 查找对应的会话
                    for session_id, session in self.sessions.items():
                        if session.username == username:
                            console.set_session(session)
                            break
            except Exception as e:
                self.logger.debug(f"Could not get username from transport: {e}")
            
            console.run()
            
        except Exception as e:
            self.logger.error(f"Error handling client {addr[0]}:{addr[1]}: {e}")
        finally:
            try:
                client.close()
            except:
                pass
                
    def stop(self):
        """停止SSH服务器"""
        self.logger.info("Stopping SSH server...")
        self.running = False
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
                
        # 清理所有会话
        self.ssh_interface.session_manager.cleanup_all()
        
        self.logger.info("SSH server stopped")


def start_ssh_server(host: str = '0.0.0.0', port: int = 2222):
    """启动SSH服务器的便捷函数"""
    server = CampusWorldSSHServer(host, port)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
    except Exception as e:
        logging.error(f"SSH server error: {e}")
        server.stop()


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 启动服务器
    start_ssh_server()
