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
from app.core.database import db_session_context
from app.models.graph import Node
from app.models.user import User
from app.core.log import get_logger, LoggerNames
from app.ssh.session_config import get_ssh_session_settings
logger = get_logger(LoggerNames.SSH)
audit_logger = get_logger(LoggerNames.AUDIT)


def _send_terminal_line(session: 'SSHSession', line: str) -> None:
    ch = getattr(session, 'channel', None)
    if ch is None or getattr(ch, 'closed', True):
        return
    try:
        ch.send((line + '\r\n').encode('utf-8'))
    except Exception:
        pass


@dataclass
class SSHSession:
    """SSH会话信息"""
    session_id: str
    username: str
    user_id: int
    user_attrs: Dict[str, Any]
    connected_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    last_user_input_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    is_closing: bool = False
    idle_warning_sent: bool = False
    disconnect_reason: Optional[str] = None
    roles: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    access_level: str = 'normal'
    _user_object: Optional[Any] = field(default=None, init=False, repr=False)
    terminal_size: Optional[tuple] = None
    command_history: List[str] = field(default_factory=list)
    output_buffer: List[str] = field(default_factory=list)
    command_ephemeral: Dict[str, Any] = field(default_factory=dict)
    nested_repl: Optional[Any] = field(default=None, init=False, repr=False)
    channel: Optional[Any] = field(default=None, init=False, repr=False)
    disconnect_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)

    def __post_init__(self):
        """初始化后处理"""
        self.roles = list(self.user_attrs.get('roles') or [])
        raw_p = self.user_attrs.get('permissions')
        if isinstance(raw_p, list):
            self.permissions = [str(x) for x in raw_p]
        elif raw_p is not None and str(raw_p).strip():
            self.permissions = [str(raw_p).strip()]
        else:
            self.permissions = []
        self.access_level = str(self.user_attrs.get('access_level') or 'normal')
        if not self.permissions:
            al = self.access_level.lower()
            if al in ('admin', 'developer', 'dev', 'development'):
                self.permissions = ['admin.*']
            elif al in ('normal', 'user', 'campus'):
                self.permissions = ['player']
            logger.warning('ssh_session_permission_fallback', extra={'username': self.username, 'user_id': self.user_id, 'access_level': self.access_level, 'fallback_permissions': list(self.permissions)})

    @property
    def last_activity_at(self) -> datetime:
        return self.last_activity

    def update_activity(self, *, user_input: bool = False) -> None:
        """Update idle clock (last_activity)."""
        now = datetime.now()
        self.last_activity = now
        if user_input:
            self.last_user_input_at = now

    def add_command(self, command: str):
        """添加命令到历史记录"""
        self.command_history.append(command)
        if len(self.command_history) > 100:
            self.command_history = self.command_history[-100:]
        self.update_activity(user_input=True)

    def add_output(self, text: str):
        """追加待下发/回显的输出行（测试与控制台缓冲）。"""
        self.output_buffer.append(text)
        self.update_activity()

    def clear_output(self):
        """清空输出缓冲。"""
        self.output_buffer.clear()

    def should_disconnect(self) -> bool:
        return self.disconnect_event.is_set()

    def get_session_info(self) -> Dict[str, Any]:
        """获取会话信息摘要"""
        return {'session_id': self.session_id, 'username': self.username, 'user_id': self.user_id, 'connected_at': self.connected_at.isoformat(), 'last_activity': self.last_activity.isoformat(), 'duration': str(datetime.now() - self.connected_at), 'roles': self.roles, 'access_level': self.access_level, 'command_count': len(self.command_history)}

    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """检查会话是否过期"""
        if not self.is_active:
            return True
        timeout = timedelta(minutes=timeout_minutes)
        return datetime.now() - self.last_activity > timeout

    def cleanup(self):
        """清理会话资源"""
        self.is_active = False
        self.is_closing = True
        self.nested_repl = None
        if not self.disconnect_event.is_set():
            self.disconnect_event.set()
        self._close_channel()
        self._save_session_state()

    def _close_channel(self):
        """关闭SSH channel"""
        if self.channel and (not self.channel.closed):
            try:
                self.channel.close()
            except Exception:
                pass
        self.channel = None

    def set_channel(self, channel):
        """设置SSH channel引用"""
        self.channel = channel

    def _save_session_state(self):
        """保存会话状态到数据库"""
        try:
            with db_session_context() as session:
                user_node = session.query(Node).filter(Node.id == self.user_id, Node.type_code == 'account', Node.is_active == True).first()
                if user_node:
                    attrs = user_node.attributes
                    attrs['last_session_info'] = {'session_id': self.session_id, 'last_activity': self.last_activity.isoformat(), 'command_count': len(self.command_history), 'terminal_size': self.terminal_size}
                    user_node.attributes = attrs
                    session.commit()
        except Exception as e:
            logger.error(f'Failed to save session state: {e}')

    def restore_from_state(self, session_state: Dict[str, Any]):
        """从保存的状态恢复会话"""
        if session_state:
            if 'terminal_size' in session_state:
                self.terminal_size = session_state['terminal_size']
            if 'command_count' in session_state:
                pass

    @property
    def user_object(self) -> Optional[Any]:
        """获取用户对象"""
        if self._user_object is None:
            self._user_object = self._load_user_object()
        return self._user_object

    def _load_user_object(self) -> Optional[Any]:
        """从图库加载账号到内存（单向 hydrate，不写新 ``nodes`` 行）。"""
        try:
            from app.models.graph_sync import GraphSynchronizer
            with db_session_context() as session:
                user_node = session.query(Node).filter(Node.id == self.user_id, Node.type_code == 'account', Node.is_active == True).first()
                if not user_node:
                    return None
                return GraphSynchronizer().sync_node_to_object(user_node, User)
        except Exception as e:
            logger.error(f'Failed to load user object: {e}')
            return None


class SessionManager:
    """会话管理器"""

    def __init__(self):
        self.sessions: Dict[str, SSHSession] = {}
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_thread.start()

    def add_session(self, session: SSHSession):
        """添加新会话"""
        with self.lock:
            self.sessions[session.session_id] = session
            self.logger.info(f'Session added: {session.session_id} for user {session.username}')

    def touch_session(self, session_id: str, *, user_input: bool = False, reason: str = '') -> None:
        """Refresh session activity clock (F01 idle enforcement)."""
        with self.lock:
            sess = self.sessions.get(session_id)
            if sess is None or not sess.is_active:
                return
            sess.update_activity(user_input=user_input)
            if user_input:
                sess.idle_warning_sent = False

    def maybe_send_idle_warning(self, session: SSHSession, settings) -> None:
        if settings.idle_timeout_minutes <= 0 or settings.idle_warning_minutes <= 0:
            return
        if session.idle_warning_sent or not session.is_active:
            return
        idle_limit = timedelta(minutes=settings.idle_timeout_minutes)
        warn_at = idle_limit - timedelta(minutes=settings.idle_warning_minutes)
        idle_elapsed = datetime.now() - session.last_activity
        if idle_elapsed < warn_at:
            return
        remaining = max(1, settings.idle_warning_minutes)
        _send_terminal_line(session, f'Session will disconnect in {remaining} minute(s) due to inactivity.')
        session.idle_warning_sent = True
        logger.info('ssh_session_idle_warning', extra={'session_id': session.session_id, 'username': session.username, 'idle_seconds': int(idle_elapsed.total_seconds()), 'reason': 'idle_warning'})
        audit_logger.info('ssh_session_idle_warning', extra={'session_id': session.session_id, 'username': session.username, 'event_type': 'ssh_session_idle_warning'})

    def request_disconnect(self, session_id: str, reason: str = 'idle_timeout') -> None:
        """Signal console to exit and close channel (full session teardown)."""
        with self.lock:
            sess = self.sessions.get(session_id)
            if sess is None or not sess.is_active or sess.is_closing:
                return
            sess.is_closing = True
            sess.disconnect_reason = reason
        idle_seconds = int((datetime.now() - sess.last_activity).total_seconds())
        if reason == 'idle_timeout':
            _send_terminal_line(sess, 'Session idle timeout. Disconnecting.')
        audit_logger.info('ssh_session_idle_disconnect', extra={'session_id': session_id, 'username': sess.username, 'idle_seconds': idle_seconds, 'reason': reason, 'event_type': 'ssh_session_idle_disconnect'})
        logger.info('ssh_session_idle_disconnect', extra={'session_id': session_id, 'username': sess.username, 'idle_seconds': idle_seconds, 'reason': reason})
        sess.disconnect_event.set()
        sess._close_channel()

    def remove_session(self, session_id: str):
        """移除会话"""
        sess_obj = None
        with self.lock:
            if session_id in self.sessions:
                sess_obj = self.sessions.pop(session_id)
        if sess_obj is None:
            return
        try:
            from app.game_engine.agent_runtime.conversation_stm_service import release_daemon_possession_for_transport_session_if_configured
            with db_session_context() as db:
                release_daemon_possession_for_transport_session_if_configured(db, session_id)
                db.commit()
        except Exception as e:
            self.logger.warning('daemon_possession_transport_release_failed session_id=%s error=%s', session_id, e)
        try:
            sess_obj.cleanup()
        except Exception as e:
            self.logger.warning('session.cleanup failed session_id=%s error=%s', session_id, e)
        self.logger.info(f'Session removed: {session_id}')

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

    def list_all_sessions(self) -> List[SSHSession]:
        """返回当前管理的所有会话（含非活跃）。"""
        with self.lock:
            return list(self.sessions.values())

    def get_user_session_count(self, username: str) -> int:
        """获取指定用户的会话数量"""
        with self.lock:
            return len([s for s in self.sessions.values() if s.username == username])

    def count_active_sessions_for_user(self, user_id: int) -> int:
        """Count active sessions for an account (session cap enforcement)."""
        with self.lock:
            return len([s for s in self.sessions.values() if s.is_active and s.user_id == user_id])

    def update_session_activity(self, session_id: str):
        """更新会话活动时间"""
        self.touch_session(session_id)

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
            user_stats = {}
            for session in active_sessions:
                if session.username not in user_stats:
                    user_stats[session.username] = {'session_count': 0, 'total_commands': 0, 'roles': session.roles, 'access_level': session.access_level}
                user_stats[session.username]['session_count'] += 1
                user_stats[session.username]['total_commands'] += len(session.command_history)
            return {'total_sessions': total_sessions, 'active_sessions': len(active_sessions), 'user_stats': user_stats, 'timestamp': datetime.now().isoformat()}

    def enforce_idle_timeouts(self) -> None:
        """Apply configured app-layer idle disconnect (F01)."""
        settings = get_ssh_session_settings()
        if settings.idle_timeout_minutes <= 0:
            return
        idle_limit = timedelta(minutes=settings.idle_timeout_minutes)
        with self.lock:
            active = [s for s in self.sessions.values() if s.is_active and not s.is_closing and s.channel is not None]
        for sess in active:
            idle_elapsed = datetime.now() - sess.last_activity
            self.maybe_send_idle_warning(sess, settings)
            if idle_elapsed >= idle_limit:
                self.request_disconnect(sess.session_id, reason='idle_timeout')

    def cleanup_orphan_pre_channel_sessions(self) -> None:
        """Remove sessions that authenticated but never bound a channel (orphan TTL)."""
        settings = get_ssh_session_settings()
        ttl = timedelta(seconds=max(1, settings.auth_timeout_seconds) * 2)
        now = datetime.now()
        with self.lock:
            orphan_ids = [
                sid for sid, sess in self.sessions.items()
                if sess.is_active and sess.channel is None and (now - sess.connected_at) > ttl
            ]
        for session_id in orphan_ids:
            sess = self.get_session(session_id)
            username = sess.username if sess else 'unknown'
            logger.info(
                'ssh_session_orphan_removed',
                extra={
                    'session_id': session_id,
                    'username': username,
                    'reason': 'orphan_pre_channel',
                    'event_type': 'ssh_session_orphan_removed',
                },
            )
            self.remove_session(session_id)

    def cleanup_expired_sessions(self, timeout_minutes: int = 30):
        """Legacy helper; delegates to enforce_idle_timeouts when using default config."""
        settings = get_ssh_session_settings()
        if settings.idle_timeout_minutes > 0:
            self.enforce_idle_timeouts()
            return
        with self.lock:
            expired_sessions = [session_id for (session_id, session) in self.sessions.items() if session.is_expired(timeout_minutes)]
        for session_id in expired_sessions:
            self.remove_session(session_id)
        if expired_sessions:
            self.logger.info(f'Cleaned up {len(expired_sessions)} expired sessions')

    def cleanup_all(self):
        """清理所有会话"""
        with self.lock:
            ids = [sid for sid in self.sessions.keys()]
            sessions = list(self.sessions.values())
            self.sessions.clear()
        for sid in ids:
            try:
                from app.game_engine.agent_runtime.conversation_stm_service import release_daemon_possession_for_transport_session_if_configured
                with db_session_context() as db:
                    release_daemon_possession_for_transport_session_if_configured(db, sid)
                    db.commit()
            except Exception as e:
                self.logger.warning('daemon_possession_transport_release_failed session_id=%s error=%s', sid, e)
        for session in sessions:
            try:
                session.cleanup()
            except Exception as e:
                self.logger.warning('session.cleanup failed error=%s', e)
        self.logger.info('All sessions cleaned up')

    def force_close_all(self):
        """强制关闭所有会话（参照 Evennia shutdown）"""
        with self.lock:
            ids = [s.session_id for s in self.sessions.values()]
            sessions = list(self.sessions.values())
            self.sessions.clear()
        for sid in ids:
            try:
                from app.game_engine.agent_runtime.conversation_stm_service import release_daemon_possession_for_transport_session_if_configured
                with db_session_context() as db:
                    release_daemon_possession_for_transport_session_if_configured(db, sid)
                    db.commit()
            except Exception as e:
                self.logger.warning('daemon_possession_transport_release_failed session_id=%s error=%s', sid, e)
        for session in sessions:
            session.is_closing = True
            session.disconnect_event.set()
            session._close_channel()
            session.is_active = False
        self.logger.warning('All sessions force closed')

    def _cleanup_worker(self):
        """Idle enforcement worker (F01)."""
        while True:
            try:
                settings = get_ssh_session_settings()
                poll = max(1, settings.cleanup_poll_interval_seconds)
                time.sleep(poll)
                self.cleanup_orphan_pre_channel_sessions()
                self.enforce_idle_timeouts()
            except Exception as e:
                self.logger.error(f'Cleanup worker error: {e}')

    def save_session_logs(self):
        """保存会话日志到数据库"""
        try:
            for session_obj in self.sessions.values():
                if session_obj.is_active:
                    self.logger.info(f'Active session: {session_obj.get_session_info()}')
        except Exception as e:
            self.logger.error(f'Failed to save session logs: {e}')


class SessionMonitor:
    """会话监控器"""

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.logger = logging.getLogger(__name__)

    def get_connection_summary(self) -> Dict[str, Any]:
        """获取连接摘要"""
        stats = self.session_manager.get_session_stats()
        active_sessions = self.session_manager.get_active_sessions()
        if active_sessions:
            avg_session_duration = sum(((datetime.now() - s.connected_at).total_seconds() for s in active_sessions)) / len(active_sessions)
            stats['avg_session_duration_seconds'] = avg_session_duration
            stats['avg_commands_per_session'] = sum((len(s.command_history) for s in active_sessions)) / len(active_sessions)
        return stats

    def check_security_issues(self) -> List[Dict[str, Any]]:
        """检查安全相关问题"""
        issues = []
        settings = get_ssh_session_settings()
        warn_minutes = settings.idle_timeout_minutes if settings.idle_timeout_minutes > 0 else 10
        active_sessions = self.session_manager.get_active_sessions()
        for session in active_sessions:
            if session.is_expired(warn_minutes):
                issues.append({'type': 'idle_session', 'session_id': session.session_id, 'username': session.username, 'idle_time': str(datetime.now() - session.last_activity), 'severity': 'warning'})
            if len(session.command_history) > 50:
                issues.append({'type': 'high_command_volume', 'session_id': session.session_id, 'username': session.username, 'command_count': len(session.command_history), 'severity': 'info'})
        return issues

    def generate_report(self) -> str:
        """生成监控报告"""
        summary = self.get_connection_summary()
        issues = self.check_security_issues()
        report = f"\n=== CampusWorld SSH Session Report ===\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nSession Statistics:\n- Total Sessions: {summary['total_sessions']}\n- Active Sessions: {summary['active_sessions']}\n- Users Connected: {len(summary['user_stats'])}\n\nUser Details:\n"
        for (username, user_info) in summary['user_stats'].items():
            report += f"- {username}: {user_info['session_count']} sessions, {user_info['total_commands']} commands\n"
        if issues:
            report += '\nSecurity Issues:\n'
            for issue in issues:
                report += f"- {issue['type']}: {issue['username']} ({issue['severity']})\n"
        else:
            report += '\nNo security issues detected.\n'
        return report
