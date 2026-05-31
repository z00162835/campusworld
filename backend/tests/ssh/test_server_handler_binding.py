"""Tests for per-connection SSH handler binding and session cap."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import threading
import pytest
from paramiko.common import AUTH_FAILED, AUTH_SUCCESSFUL
from app.ssh.protocol_handler import ProtocolFactory, SSHProtocolHandler
from app.ssh.session import SessionManager, SSHSession
from app.ssh.session_config import SSHSessionSettings


@pytest.fixture
def session_manager():
    with patch.object(SessionManager, '__init__', lambda self: None):
        mgr = SessionManager.__new__(SessionManager)
        mgr.sessions = {}
        mgr.lock = threading.Lock()
        mgr.logger = MagicMock()
        mgr.add_session = SessionManager.add_session.__get__(mgr, SessionManager)
        mgr.count_active_sessions_for_user = SessionManager.count_active_sessions_for_user.__get__(mgr, SessionManager)
        return mgr


def _settings(**overrides) -> SSHSessionSettings:
    defaults = dict(
        auth_timeout_seconds=20,
        idle_timeout_minutes=5,
        idle_warning_minutes=1,
        keepalive_interval_seconds=30,
        cleanup_poll_interval_seconds=60,
        max_sessions_per_user=3,
    )
    defaults.update(overrides)
    return SSHSessionSettings(**defaults)


def test_two_handlers_share_session_manager(session_manager):
    h1 = ProtocolFactory.create_ssh_handler('10.0.0.1', session_manager=session_manager)
    h2 = ProtocolFactory.create_ssh_handler('10.0.0.2', session_manager=session_manager)
    assert h1.session_manager is h2.session_manager is session_manager


def test_authenticated_session_set_on_success(session_manager):
    handler = ProtocolFactory.create_ssh_handler('127.0.0.1', session_manager=session_manager)
    auth_result = {
        'success': True,
        'session_id': 'sess_a',
        'username': 'alice',
        'user_id': 42,
        'user_attrs': {'roles': ['player'], 'permissions': ['player']},
    }
    with patch('app.ssh.protocol_handler.game_handler.authenticate_user', return_value=auth_result), patch('app.ssh.protocol_handler.get_rate_limiter') as rl, patch('app.ssh.protocol_handler.get_ssh_session_settings', return_value=_settings(max_sessions_per_user=0)):
        rl.return_value.record_login_attempt = MagicMock()
        assert handler.check_auth_password('alice', 'secret') == AUTH_SUCCESSFUL
    assert handler.authenticated_session is not None
    assert handler.authenticated_session.session_id == 'sess_a'
    assert 'sess_a' in session_manager.sessions


def test_concurrent_handlers_get_distinct_sessions(session_manager):
    results = []

    def auth_for(session_id: str, user_id: int):
        handler = ProtocolFactory.create_ssh_handler('127.0.0.1', session_manager=session_manager)
        auth_result = {
            'success': True,
            'session_id': session_id,
            'username': 'alice',
            'user_id': user_id,
            'user_attrs': {'roles': ['player'], 'permissions': ['player']},
        }
        with patch('app.ssh.protocol_handler.game_handler.authenticate_user', return_value=auth_result), patch('app.ssh.protocol_handler.get_rate_limiter') as rl, patch('app.ssh.protocol_handler.get_ssh_session_settings', return_value=_settings(max_sessions_per_user=0)):
            rl.return_value.record_login_attempt = MagicMock()
            handler.check_auth_password('alice', 'secret')
        return handler.authenticated_session.session_id

    sid1 = auth_for('sess_1', 1)
    sid2 = auth_for('sess_2', 1)
    assert sid1 != sid2
    assert session_manager.count_active_sessions_for_user(1) == 2


def test_session_cap_rejects_new_auth(session_manager):
    for i in range(3):
        session_manager.sessions[f'sess_{i}'] = SSHSession(
            session_id=f'sess_{i}',
            username='alice',
            user_id=99,
            user_attrs={'roles': ['player'], 'permissions': ['player']},
        )
    handler = ProtocolFactory.create_ssh_handler('127.0.0.1', session_manager=session_manager)
    auth_result = {
        'success': True,
        'session_id': 'sess_new',
        'username': 'alice',
        'user_id': 99,
        'user_attrs': {'roles': ['player'], 'permissions': ['player']},
    }
    with patch('app.ssh.protocol_handler.game_handler.authenticate_user', return_value=auth_result), patch('app.ssh.protocol_handler.get_rate_limiter') as rl, patch('app.ssh.protocol_handler.get_ssh_session_settings', return_value=_settings(max_sessions_per_user=3)):
        rl.return_value.record_login_attempt = MagicMock()
        assert handler.check_auth_password('alice', 'secret') == AUTH_FAILED
    assert handler.authenticated_session is None
    assert 'sess_new' not in session_manager.sessions


def test_check_auth_uses_handler_client_ip(session_manager):
    handler = SSHProtocolHandler(client_ip='203.0.113.5', session_manager=session_manager)
    with patch('app.ssh.protocol_handler.game_handler.authenticate_user') as auth, patch('app.ssh.protocol_handler.get_rate_limiter') as rl:
        auth.return_value = {'success': False, 'error': 'bad password'}
        rl.return_value.record_login_attempt = MagicMock()
        handler.check_auth_password('bob', 'wrong')
    auth.assert_called_once_with(username='bob', password='wrong', client_ip='203.0.113.5')
