"""Tests for SSH session lifecycle (F01 idle / disconnect)."""
from __future__ import annotations
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import threading
import uuid
import pytest
from app.ssh.session import SSHSession, SessionManager
from app.ssh.session_config import SSHSessionSettings


@pytest.fixture
def session_manager():
    with patch.object(SessionManager, '__init__', lambda self: None):
        mgr = SessionManager.__new__(SessionManager)
        mgr.sessions = {}
        mgr.lock = threading.Lock()
        mgr.logger = MagicMock()
        return mgr


def _make_session(**kwargs) -> SSHSession:
    defaults = dict(
        session_id='sess_test',
        username='tester',
        user_id=1,
        user_attrs={'roles': ['player'], 'permissions': ['player']},
    )
    defaults.update(kwargs)
    return SSHSession(**defaults)


def test_touch_session_updates_last_activity(session_manager):
    sess = _make_session()
    sess.last_activity = datetime.now() - timedelta(minutes=10)
    session_manager.sessions[sess.session_id] = sess
    session_manager.touch_session(sess.session_id, user_input=True, reason='keystroke')
    assert datetime.now() - sess.last_activity < timedelta(seconds=2)
    assert sess.idle_warning_sent is False


def test_idle_zero_skips_enforcement(session_manager):
    sess = _make_session()
    sess.last_activity = datetime.now() - timedelta(hours=1)
    session_manager.sessions[sess.session_id] = sess
    settings = SSHSessionSettings(
        auth_timeout_seconds=20,
        idle_timeout_minutes=0,
        idle_warning_minutes=1,
        keepalive_interval_seconds=30,
        cleanup_poll_interval_seconds=60,
        max_sessions_per_user=3,
    )
    with patch('app.ssh.session.get_ssh_session_settings', return_value=settings):
        session_manager.enforce_idle_timeouts()
    assert sess.should_disconnect() is False
    assert sess.session_id in session_manager.sessions


def test_idle_timeout_triggers_disconnect(session_manager):
    sess = _make_session()
    sess.last_activity = datetime.now() - timedelta(minutes=10)
    ch = MagicMock()
    ch.closed = False
    sess.channel = ch
    session_manager.sessions[sess.session_id] = sess
    settings = SSHSessionSettings(
        auth_timeout_seconds=20,
        idle_timeout_minutes=5,
        idle_warning_minutes=1,
        keepalive_interval_seconds=30,
        cleanup_poll_interval_seconds=60,
        max_sessions_per_user=3,
    )
    with patch('app.ssh.session.get_ssh_session_settings', return_value=settings):
        session_manager.enforce_idle_timeouts()
    assert sess.should_disconnect() is True
    assert sess.disconnect_reason == 'idle_timeout'
    ch.send.assert_called()
    ch.close.assert_called()


def test_idle_warning_sent_before_disconnect(session_manager):
    sess = _make_session()
    sess.last_activity = datetime.now() - timedelta(minutes=4, seconds=30)
    ch = MagicMock()
    ch.closed = False
    sess.channel = ch
    session_manager.sessions[sess.session_id] = sess
    settings = SSHSessionSettings(
        auth_timeout_seconds=20,
        idle_timeout_minutes=5,
        idle_warning_minutes=1,
        keepalive_interval_seconds=30,
        cleanup_poll_interval_seconds=60,
        max_sessions_per_user=3,
    )
    with patch('app.ssh.session.get_ssh_session_settings', return_value=settings):
        session_manager.enforce_idle_timeouts()
    assert sess.idle_warning_sent is True
    assert sess.should_disconnect() is False
    sent = b''.join(call.args[0] for call in ch.send.call_args_list)
    assert b'inactivity' in sent.lower()


def test_last_activity_at_alias():
    sess = _make_session()
    now = datetime.now()
    sess.last_activity = now
    assert sess.last_activity_at == now


def test_get_ssh_session_settings_clamps_warning():
    with patch('app.ssh.session_config.get_setting') as gs:
        gs.side_effect = lambda key, default=None: {
            'ssh.session.auth_timeout_seconds': 20,
            'ssh.session.idle_timeout_minutes': 5,
            'ssh.session.idle_warning_minutes': 10,
            'ssh.session.keepalive_interval_seconds': 30,
            'ssh.session.cleanup_poll_interval_seconds': 60,
            'ssh.session.max_sessions_per_user': 3,
        }.get(key, default)
        from app.ssh.session_config import get_ssh_session_settings
        s = get_ssh_session_settings()
        assert s.idle_warning_minutes < s.idle_timeout_minutes


def test_console_ready_touch_refreshes_idle_clock(session_manager):
    sess = _make_session()
    sess.last_activity = datetime.now() - timedelta(minutes=10)
    ch = MagicMock()
    ch.closed = False
    sess.channel = ch
    session_manager.sessions[sess.session_id] = sess
    session_manager.touch_session(sess.session_id, reason='console_ready')
    settings = SSHSessionSettings(
        auth_timeout_seconds=20,
        idle_timeout_minutes=5,
        idle_warning_minutes=1,
        keepalive_interval_seconds=30,
        cleanup_poll_interval_seconds=60,
        max_sessions_per_user=3,
    )
    with patch('app.ssh.session.get_ssh_session_settings', return_value=settings):
        session_manager.enforce_idle_timeouts()
    assert sess.should_disconnect() is False


def test_pre_channel_idle_skipped(session_manager):
    sess = _make_session()
    sess.last_activity = datetime.now() - timedelta(hours=2)
    session_manager.sessions[sess.session_id] = sess
    settings = SSHSessionSettings(
        auth_timeout_seconds=20,
        idle_timeout_minutes=5,
        idle_warning_minutes=1,
        keepalive_interval_seconds=30,
        cleanup_poll_interval_seconds=60,
        max_sessions_per_user=3,
    )
    with patch('app.ssh.session.get_ssh_session_settings', return_value=settings):
        session_manager.enforce_idle_timeouts()
    assert sess.should_disconnect() is False


@patch('app.ssh.session.SessionManager.remove_session')
def test_orphan_pre_channel_cleanup(mock_remove, session_manager):
    sess = _make_session()
    sess.connected_at = datetime.now() - timedelta(seconds=60)
    session_manager.sessions[sess.session_id] = sess
    settings = SSHSessionSettings(
        auth_timeout_seconds=20,
        idle_timeout_minutes=5,
        idle_warning_minutes=1,
        keepalive_interval_seconds=30,
        cleanup_poll_interval_seconds=60,
        max_sessions_per_user=3,
    )
    with patch('app.ssh.session.get_ssh_session_settings', return_value=settings):
        session_manager.cleanup_orphan_pre_channel_sessions()
    mock_remove.assert_called_once_with(sess.session_id)
