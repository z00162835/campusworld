"""
SSH 连接速率限制器
防止SSH暴力破解和DDoS攻击
"""

import time
import threading
from typing import Dict, Optional
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.core.config_manager import get_setting
from app.core.log import get_logger, LoggerNames


@dataclass
class ConnectionRecord:
    """连接记录"""
    timestamp: float
    ip: str
    success: bool


class IPConnectionTracker:
    """IP连接追踪器"""

    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self.connections: Dict[str, list] = defaultdict(list)
        self.lock = threading.Lock()

    def record_connection(self, ip: str, success: bool = True):
        """记录连接"""
        now = time.time()
        with self.lock:
            # 清理过期记录
            self.connections[ip] = [
                t for t in self.connections[ip]
                if now - t['timestamp'] < self.window_seconds
            ]
            # 添加新记录
            self.connections[ip].append({
                'timestamp': now,
                'success': success
            })

    def get_connection_count(self, ip: str) -> int:
        """获取连接次数"""
        now = time.time()
        with self.lock:
            # 清理过期记录
            self.connections[ip] = [
                t for t in self.connections[ip]
                if now - t['timestamp'] < self.window_seconds
            ]
            return len(self.connections[ip])

    def get_failed_count(self, ip: str) -> int:
        """获取失败次数"""
        now = time.time()
        with self.lock:
            self.connections[ip] = [
                t for t in self.connections[ip]
                if now - t['timestamp'] < self.window_seconds
            ]
            return sum(1 for t in self.connections[ip] if not t['success'])


class LoginAttemptTracker:
    """登录尝试追踪器 - 防止暴力破解"""

    def __init__(
        self,
        max_attempts: int = 5,
        lockout_duration: int = 300,
        window_seconds: int = 300
    ):
        self.max_attempts = max_attempts  # 最大尝试次数
        self.lockout_duration = lockout_duration  # 锁定时长（秒）
        self.window_seconds = window_seconds  # 时间窗口（秒）

        self.attempts: Dict[str, list] = defaultdict(list)
        self.locked_ips: Dict[str, float] = {}  # IP锁定过期时间
        self.lock = threading.Lock()

    def record_attempt(self, ip: str, success: bool = False):
        """记录登录尝试"""
        now = time.time()

        with self.lock:
            # 如果IP已被锁定，检查是否过期
            if ip in self.locked_ips:
                if now >= self.locked_ips[ip]:
                    # 锁定已过期，清除记录
                    del self.locked_ips[ip]
                    self.attempts.pop(ip, None)
                else:
                    # IP仍被锁定
                    remaining = int(self.locked_ips[ip] - now)
                    return {
                        'blocked': True,
                        'remaining_seconds': remaining
                    }

            # 清理过期记录
            self.attempts[ip] = [
                t for t in self.attempts[ip]
                if now - t < self.window_seconds
            ]

            if success:
                # 成功登录，清除记录
                self.attempts[ip] = []
            else:
                # 失败尝试
                self.attempts[ip].append(now)

                # 检查是否达到锁定阈值
                if len(self.attempts[ip]) >= self.max_attempts:
                    # 锁定IP
                    self.locked_ips[ip] = now + self.lockout_duration
                    return {
                        'blocked': True,
                        'reason': 'too_many_failed_attempts',
                        'lockout_duration': self.lockout_duration
                    }

        return {'blocked': False}

    def is_blocked(self, ip: str) -> bool:
        """检查IP是否被锁定"""
        now = time.time()
        with self.lock:
            if ip in self.locked_ips:
                if now >= self.locked_ips[ip]:
                    # 锁定已过期
                    del self.locked_ips[ip]
                    self.attempts.pop(ip, None)
                    return False
                return True
            return False

    def get_remaining_lockout(self, ip: str) -> Optional[int]:
        """获取剩余锁定时间"""
        now = time.time()
        with self.lock:
            if ip in self.locked_ips:
                remaining = int(self.locked_ips[ip] - now)
                return remaining if remaining > 0 else None
            return None

    def clear_lock(self, ip: str):
        """清除IP锁定（管理员操作）"""
        with self.lock:
            self.locked_ips.pop(ip, None)
            self.attempts.pop(ip, None)


class ConnectionRateLimiter:
    """
    连接速率限制器

    功能：
    - 基于IP的连接速率限制
    - 登录失败追踪和自动锁定
    - 实时威胁检测
    """

    def __init__(self):
        # 从配置加载参数
        self.max_connections_per_minute = get_setting(
            'ssh.rate_limit.max_connections_per_minute', 10
        )
        self.max_failed_attempts = get_setting(
            'ssh.rate_limit.max_failed_attempts', 5
        )
        self.lockout_duration = get_setting(
            'ssh.rate_limit.lockout_duration', 300
        )
        self.attempt_window = get_setting(
            'ssh.rate_limit.attempt_window', 300
        )
        self.connection_window = get_setting(
            'ssh.rate_limit.connection_window', 60
        )

        # 初始化组件
        self.connection_tracker = IPConnectionTracker(self.connection_window)
        self.login_tracker = LoginAttemptTracker(
            max_attempts=self.max_failed_attempts,
            lockout_duration=self.lockout_duration,
            window_seconds=self.attempt_window
        )

        # 日志
        self.logger = get_logger(LoggerNames.SECURITY)
        self.audit_logger = get_logger(LoggerNames.AUDIT)

        # 白名单（不受限制的IP）
        self.whitelist: set = set()

        # 统计信息
        self.stats = {
            'total_connections': 0,
            'blocked_connections': 0,
            'blocked_ips': set()
        }

        # 启动清理线程
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_worker,
            daemon=True
        )
        self._cleanup_thread.start()

        self.logger.info(
            f"连接速率限制器初始化: "
            f"max_conn={self.max_connections_per_minute}/min, "
            f"max_failed={self.max_failed_attempts}, "
            f"lockout={self.lockout_duration}s"
        )

    def check_connection(self, ip: str) -> Dict:
        """
        检查连接是否允许

        Args:
            ip: 客户端IP地址

        Returns:
            {
                'allowed': bool,
                'reason': str (可选),
                'remaining_seconds': int (可选)
            }
        """
        # 检查白名单
        if ip in self.whitelist:
            return {'allowed': True, 'reason': 'whitelisted'}

        # 检查IP锁定状态
        if self.login_tracker.is_blocked(ip):
            remaining = self.login_tracker.get_remaining_lockout(ip)
            self.stats['blocked_connections'] += 1

            self.logger.warning(
                f"连接被拒绝（IP锁定）",
                extra={
                    'ip': ip,
                    'remaining_seconds': remaining,
                    'event_type': 'connection_blocked_locked'
                }
            )

            return {
                'allowed': False,
                'reason': 'ip_locked',
                'remaining_seconds': remaining
            }

        # 检查连接速率
        connection_count = self.connection_tracker.get_connection_count(ip)
        if connection_count >= self.max_connections_per_minute:
            self.stats['blocked_connections'] += 1
            self.stats['blocked_ips'].add(ip)

            self.logger.warning(
                f"连接被拒绝（超过速率限制）",
                extra={
                    'ip': ip,
                    'connection_count': connection_count,
                    'limit': self.max_connections_per_minute,
                    'event_type': 'connection_blocked_rate_limit'
                }
            )

            return {
                'allowed': False,
                'reason': 'rate_limit_exceeded',
                'connection_count': connection_count,
                'limit': self.max_connections_per_minute
            }

        # 允许连接
        self.stats['total_connections'] += 1
        return {'allowed': True}

    def record_login_attempt(self, ip: str, success: bool):
        """
        记录登录尝试

        Args:
            ip: 客户端IP地址
            success: 是否成功
        """
        # 检查白名单
        if ip in self.whitelist:
            return

        # 记录连接
        self.connection_tracker.record_connection(ip, success)

        # 记录登录尝试
        result = self.login_tracker.record_attempt(ip, success)

        if success:
            self.logger.info(
                f"登录成功",
                extra={
                    'ip': ip,
                    'event_type': 'login_success'
                }
            )
        else:
            if result.get('blocked'):
                self.stats['blocked_ips'].add(ip)
                self.logger.warning(
                    f"登录失败 - IP已锁定",
                    extra={
                        'ip': ip,
                        'reason': result.get('reason'),
                        'lockout_duration': result.get('lockout_duration'),
                        'event_type': 'login_blocked'
                    }
                )
            else:
                failed_count = self.login_tracker.get_failed_count(ip)
                self.logger.warning(
                    f"登录失败",
                    extra={
                        'ip': ip,
                        'failed_attempts': failed_count,
                        'max_attempts': self.max_failed_attempts,
                        'event_type': 'login_failed'
                    }
                )

    def add_to_whitelist(self, ip: str):
        """添加IP到白名单"""
        self.whitelist.add(ip)
        self.logger.info(f"IP添加到白名单: {ip}")

    def remove_from_whitelist(self, ip: str):
        """从白名单移除IP"""
        self.whitelist.discard(ip)
        self.logger.info(f"IP从白名单移除: {ip}")

    def clear_ip_lock(self, ip: str):
        """清除IP锁定"""
        self.login_tracker.clear_lock(ip)
        self.logger.info(f"IP锁定已清除: {ip}")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'total_connections': self.stats['total_connections'],
            'blocked_connections': self.stats['blocked_connections'],
            'blocked_ips_count': len(self.stats['blocked_ips']),
            'whitelist_count': len(self.whitelist),
            'active_locks': len(self.login_tracker.locked_ips),
            'settings': {
                'max_connections_per_minute': self.max_connections_per_minute,
                'max_failed_attempts': self.max_failed_attempts,
                'lockout_duration': self.lockout_duration
            }
        }

    def get_blocked_ips(self) -> Dict[str, int]:
        """获取被锁定的IP及剩余时间"""
        result = {}
        for ip, expiry in self.login_tracker.locked_ips.items():
            remaining = int(expiry - time.time())
            if remaining > 0:
                result[ip] = remaining
        return result

    def _cleanup_worker(self):
        """清理过期数据的工作线程"""
        while True:
            try:
                time.sleep(60)  # 每分钟清理一次
                self._cleanup_expired_data()
            except Exception as e:
                self.logger.error(f"清理线程错误: {e}")

    def _cleanup_expired_data(self):
        """清理过期数据"""
        now = time.time()

        # 清理过期的连接记录
        with self.connection_tracker.lock:
            expired_ips = []
            for ip, records in self.connection_tracker.connections.items():
                records = [
                    r for r in records
                    if now - r['timestamp'] < self.connection_window
                ]
                if not records:
                    expired_ips.append(ip)
                else:
                    self.connection_tracker.connections[ip] = records

            for ip in expired_ips:
                del self.connection_tracker.connections[ip]

        # 清理统计中的过期IP
        self.stats['blocked_ips'] = {
            ip for ip in self.stats['blocked_ips']
            if self.login_tracker.is_blocked(ip)
        }


# 全局速率限制器实例
_rate_limiter: Optional[ConnectionRateLimiter] = None


def get_rate_limiter() -> ConnectionRateLimiter:
    """获取速率限制器实例（延迟初始化）"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = ConnectionRateLimiter()
    return _rate_limiter