"""
SSH会话管理模块
管理用户SSH连接会话，包括状态跟踪和清理
"""

import time
import threading
import logging
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from app.core.database import SessionLocal
from app.models.graph import Node
from app.models.user import User
from app.core.log import get_logger, LoggerNames
logger = get_logger(LoggerNames.SSH)
@dataclass
class SSHSession:
    """SSH会话信息"""
    session_id: str
    username: str
    user_id: int
    user_attrs: Dict[str, Any]
    
    # 会话状态
    connected_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    
    # 用户信息
    roles: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    access_level: str = "normal"
    _user_object: Optional[Any] = field(default=None, init=False, repr=False)
    
    # 控制台信息
    terminal_size: Optional[tuple] = None
    command_history: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """初始化后处理"""
        # 从用户属性中提取信息
        self.roles = self.user_attrs.get("roles", [])
        self.permissions = self.user_attrs.get("permissions", [])
        self.access_level = self.user_attrs.get("access_level", "normal")
    
    def update_activity(self):
        """更新最后活动时间"""
        self.last_activity = datetime.now()
    
    def add_command(self, command: str):
        """添加命令到历史记录"""
        self.command_history.append(command)
        # 限制历史记录长度
        if len(self.command_history) > 100:
            self.command_history = self.command_history[-100:]
        self.update_activity()
    
    def get_session_info(self) -> Dict[str, Any]:
        """获取会话信息摘要"""
        return {
            "session_id": self.session_id,
            "username": self.username,
            "user_id": self.user_id,
            "connected_at": self.connected_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "duration": str(datetime.now() - self.connected_at),
            "roles": self.roles,
            "access_level": self.access_level,
            "command_count": len(self.command_history)
        }
    
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """检查会话是否过期"""
        if not self.is_active:
            return True
        
        timeout = timedelta(minutes=timeout_minutes)
        return datetime.now() - self.last_activity > timeout
    
    def cleanup(self):
        """清理会话资源"""
        self.is_active = False
        # 保存会话状态到数据库
        self._save_session_state()
        # 这里可以添加其他清理逻辑，如保存会话日志等
    
    def _save_session_state(self):
        """保存会话状态到数据库"""
        try:
            with SessionLocal() as session:
                # 查找用户节点
                user_node = session.query(Node).filter(
                    Node.id == self.user_id,
                    Node.type_code == 'account',
                    Node.is_active == True
                ).first()
                
                if user_node:
                    # 更新会话状态
                    attrs = user_node.attributes
                    attrs["last_session_info"] = {
                        "session_id": self.session_id,
                        "last_activity": self.last_activity.isoformat(),
                        "command_count": len(self.command_history),
                        "terminal_size": self.terminal_size
                    }
                    user_node.attributes = attrs
                    session.commit()
                    
        except Exception as e:
            logger.error(f"Failed to save session state: {e}")
    
    def restore_from_state(self, session_state: Dict[str, Any]):
        """从保存的状态恢复会话"""
        if session_state:
            # 恢复终端大小
            if "terminal_size" in session_state:
                self.terminal_size = session_state["terminal_size"]
            
            # 恢复命令历史（限制数量）
            if "command_count" in session_state:
                # 这里可以从数据库加载历史命令
                pass
    @property
    def user_object(self) -> Optional[Any]:
        """获取用户对象"""
        if self._user_object is None:
            self._user_object = self._load_user_object()
        return self._user_object
    def _load_user_object(self) -> Optional[Any]:
        """加载用户对象"""
        try:
            with SessionLocal() as session:
                user_node = session.query(Node).filter(
                    Node.id == self.user_id,
                    Node.type_code == 'account',
                    Node.is_active == True
                ).first()
                if user_node:
                    attrs = user_node.attributes
                    return User(
                        username=attrs.get('username', ''),
                        **attrs
                    )
                return None
        except Exception as e:
            logger.error(f"Failed to load user object: {e}")
            return None

class SessionManager:
    """会话管理器"""
    
    def __init__(self):
        self.sessions: Dict[str, SSHSession] = {}
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
        # 启动清理线程
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_thread.start()
    
    def add_session(self, session: SSHSession):
        """添加新会话"""
        with self.lock:
            self.sessions[session.session_id] = session
            self.logger.info(f"Session added: {session.session_id} for user {session.username}")
    
    def remove_session(self, session_id: str):
        """移除会话"""
        with self.lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.cleanup()
                del self.sessions[session_id]
                self.logger.info(f"Session removed: {session_id}")
    
    def get_session(self, session_id: str) -> Optional[SSHSession]:
        """获取指定会话"""
        with self.lock:
            return self.sessions.get(session_id)
    
    def get_user_sessions(self, username: str) -> List[SSHSession]:
        """获取指定用户的所有会话"""
        with self.lock:
            return [s for s in self.sessions.values() if s.username == username]
    
    def get_active_sessions(self) -> List[SSHSession]:
        """获取所有活跃会话"""
        with self.lock:
            return [s for s in self.sessions.values() if s.is_active]
    
    def get_session_count(self) -> int:
        """获取当前会话数量"""
        with self.lock:
            return len(self.sessions)
    
    def get_user_session_count(self, username: str) -> int:
        """获取指定用户的会话数量"""
        with self.lock:
            return len([s for s in self.sessions.values() if s.username == username])
    
    def update_session_activity(self, session_id: str):
        """更新会话活动时间"""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id].update_activity()
    
    def add_command_to_session(self, session_id: str, command: str):
        """向指定会话添加命令"""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id].add_command(command)
    
    def get_session_stats(self) -> Dict[str, Any]:
        """获取会话统计信息"""
        with self.lock:
            active_sessions = [s for s in self.sessions.values() if s.is_active]
            total_sessions = len(self.sessions)
            
            # 按用户统计
            user_stats = {}
            for session in active_sessions:
                if session.username not in user_stats:
                    user_stats[session.username] = {
                        "session_count": 0,
                        "total_commands": 0,
                        "roles": session.roles,
                        "access_level": session.access_level
                    }
                user_stats[session.username]["session_count"] += 1
                user_stats[session.username]["total_commands"] += len(session.command_history)
            
            return {
                "total_sessions": total_sessions,
                "active_sessions": len(active_sessions),
                "user_stats": user_stats,
                "timestamp": datetime.now().isoformat()
            }
    
    def cleanup_expired_sessions(self, timeout_minutes: int = 30):
        """清理过期会话"""
        with self.lock:
            expired_sessions = []
            for session_id, session in self.sessions.items():
                if session.is_expired(timeout_minutes):
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                self.remove_session(session_id)
            
            if expired_sessions:
                self.logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
    
    def cleanup_all(self):
        """清理所有会话"""
        with self.lock:
            for session in self.sessions.values():
                session.cleanup()
            self.sessions.clear()
            self.logger.info("All sessions cleaned up")
    
    def _cleanup_worker(self):
        """清理工作线程"""
        while True:
            try:
                time.sleep(300)  # 每5分钟检查一次
                self.cleanup_expired_sessions()
            except Exception as e:
                self.logger.error(f"Cleanup worker error: {e}")
    
    def save_session_logs(self):
        """保存会话日志到数据库"""
        try:
            session = SessionLocal()
            try:
                # 这里可以实现会话日志的持久化存储
                # 暂时只是记录日志
                for session_obj in self.sessions.values():
                    if session_obj.is_active:
                        self.logger.info(f"Active session: {session_obj.get_session_info()}")
            finally:
                session.close()
        except Exception as e:
            self.logger.error(f"Failed to save session logs: {e}")


class SessionMonitor:
    """会话监控器"""
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.logger = logging.getLogger(__name__)
    
    def get_connection_summary(self) -> Dict[str, Any]:
        """获取连接摘要"""
        stats = self.session_manager.get_session_stats()
        
        # 添加连接趋势信息
        active_sessions = self.session_manager.get_active_sessions()
        if active_sessions:
            avg_session_duration = sum(
                (datetime.now() - s.connected_at).total_seconds() 
                for s in active_sessions
            ) / len(active_sessions)
            
            stats["avg_session_duration_seconds"] = avg_session_duration
            stats["avg_commands_per_session"] = sum(
                len(s.command_history) for s in active_sessions
            ) / len(active_sessions)
        
        return stats
    
    def check_security_issues(self) -> List[Dict[str, Any]]:
        """检查安全相关问题"""
        issues = []
        active_sessions = self.session_manager.get_active_sessions()
        
        for session in active_sessions:
            # 检查长时间空闲的会话
            if session.is_expired(10):  # 10分钟无活动
                issues.append({
                    "type": "idle_session",
                    "session_id": session.session_id,
                    "username": session.username,
                    "idle_time": str(datetime.now() - session.last_activity),
                    "severity": "warning"
                })
            
            # 检查异常命令模式
            if len(session.command_history) > 50:
                issues.append({
                    "type": "high_command_volume",
                    "session_id": session.session_id,
                    "username": session.username,
                    "command_count": len(session.command_history),
                    "severity": "info"
                })
        
        return issues
    
    def generate_report(self) -> str:
        """生成监控报告"""
        summary = self.get_connection_summary()
        issues = self.check_security_issues()
        
        report = f"""
=== CampusWorld SSH Session Report ===
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Session Statistics:
- Total Sessions: {summary['total_sessions']}
- Active Sessions: {summary['active_sessions']}
- Users Connected: {len(summary['user_stats'])}

User Details:
"""
        
        for username, user_info in summary['user_stats'].items():
            report += f"- {username}: {user_info['session_count']} sessions, {user_info['total_commands']} commands\n"
        
        if issues:
            report += "\nSecurity Issues:\n"
            for issue in issues:
                report += f"- {issue['type']}: {issue['username']} ({issue['severity']})\n"
        else:
            report += "\nNo security issues detected.\n"
        
        return report
