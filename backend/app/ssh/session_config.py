"""SSH session lifecycle settings (F01)."""
from __future__ import annotations
from dataclasses import dataclass
from app.core.config_manager import get_setting


@dataclass(frozen=True)
class SSHSessionSettings:
    auth_timeout_seconds: int
    idle_timeout_minutes: int
    idle_warning_minutes: int
    keepalive_interval_seconds: int
    cleanup_poll_interval_seconds: int
    max_sessions_per_user: int


def get_ssh_session_settings() -> SSHSessionSettings:
    idle_timeout = int(get_setting('ssh.session.idle_timeout_minutes', 5))
    idle_warning = int(get_setting('ssh.session.idle_warning_minutes', 1))
    if idle_timeout > 0 and idle_warning >= idle_timeout:
        idle_warning = max(0, idle_timeout - 1)
    return SSHSessionSettings(
        auth_timeout_seconds=int(get_setting('ssh.session.auth_timeout_seconds', 20)),
        idle_timeout_minutes=idle_timeout,
        idle_warning_minutes=idle_warning,
        keepalive_interval_seconds=int(get_setting('ssh.session.keepalive_interval_seconds', 30)),
        cleanup_poll_interval_seconds=int(get_setting('ssh.session.cleanup_poll_interval_seconds', 60)),
        max_sessions_per_user=int(get_setting('ssh.session.max_sessions_per_user', 3)),
    )
