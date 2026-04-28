"""
WebSocket Handler 安全测试

测试 WebSocket 认证和限流机制：
1. 无 token 拒绝连接
2. 无效 token 拒绝连接
3. 有效 token 接受连接
4. complete 需要认证
5. agent_* 需要认证
6. 消息速率限制
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
import time

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
from fastapi import WebSocket
from jose import jwt

from app.core.security import create_access_token, ALGORITHM


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_token():
    """生成有效的 JWT token（sub 为图账号 id，与 HTTP/CLI 登录一致）"""
    token = create_access_token(subject="1", username="testuser")
    return token


@pytest.fixture
def invalid_token():
    """生成无效的 JWT token"""
    return "invalid.token.here"


# ---------------------------------------------------------------------------
# Test: Rate Limiter
# ---------------------------------------------------------------------------

def test_rate_limiter_connection_limit():
    """测试连接数限制"""
    from app.api.ws_handler import ConnectionRateLimiter, MAX_CONNECTIONS, WSConnection

    limiter = ConnectionRateLimiter()

    added_ids = set()
    for i in range(MAX_CONNECTIONS):
        ws = MagicMock()
        ws.client.host = f"192.168.1.{i}"
        ws.headers = {}
        conn = WSConnection(ws)
        conn_id = id(ws)
        while conn_id in added_ids:
            ws = MagicMock()
            ws.client.host = f"192.168.1.{i}"
            ws.headers = {}
            conn_id = id(ws)
        added_ids.add(conn_id)
        allowed, _ = limiter.try_add_connection_sync(ws, conn)
        assert allowed is True, f"Connection {i} should be allowed"

    ws_over = MagicMock()
    ws_over.client.host = "192.168.2.1"
    ws_over.headers = {}
    conn_over = WSConnection(ws_over)

    allowed, error = limiter.try_add_connection_sync(ws_over, conn_over)
    assert allowed is False
    assert "maximum connection capacity" in error.lower()


def test_rate_limiter_per_ip_limit():
    """测试每 IP 连接数限制"""
    from app.api.ws_handler import ConnectionRateLimiter, MAX_CONNECTIONS_PER_IP, WSConnection

    limiter = ConnectionRateLimiter()

    ws = MagicMock()
    ws.client.host = "10.0.0.1"
    ws.headers = {}

    added_ids = set()
    for i in range(MAX_CONNECTIONS_PER_IP):
        conn = WSConnection(ws)
        conn_id = id(ws) + i
        while conn_id in added_ids:
            conn_id += 1000
        added_ids.add(conn_id)
        allowed, _ = limiter.try_add_connection_sync(ws, conn)
        assert allowed is True

    conn_over = WSConnection(ws)
    allowed, error = limiter.try_add_connection_sync(ws, conn_over)
    assert allowed is False
    assert "too many connections from ip" in error.lower()


def test_rate_limiter_message_rate():
    """测试消息速率限制"""
    from app.api.ws_handler import ConnectionRateLimiter, MAX_MESSAGES_PER_SECOND, WSConnection

    limiter = ConnectionRateLimiter()

    ws = MagicMock()
    ws.client.host = "10.0.0.1"
    ws.headers = {}
    conn = WSConnection(ws)

    limiter.try_add_connection_sync(ws, conn)
    conn_id = id(ws)

    for i in range(MAX_MESSAGES_PER_SECOND):
        allowed, _ = limiter.check_message_rate_sync(conn_id)
        assert allowed is True, f"Message {i} should be allowed"

    allowed, error = limiter.check_message_rate_sync(conn_id)
    assert allowed is False
    assert "rate limit exceeded" in error.lower()


# ---------------------------------------------------------------------------
# Test: _handle_connect logic (token validation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_connect_requires_token():
    """connect 消息必须提供 token"""
    from app.api.ws_handler import WSHandler, WSConnection

    handler = WSHandler()

    ws = MagicMock()
    ws.client = MagicMock()
    ws.client.host = "127.0.0.1"
    ws.headers = {}

    conn = WSConnection(ws)

    # 模拟 send_json
    sent_messages = []
    async def mock_send_json(data):
        sent_messages.append(data)
    conn.send_json = mock_send_json

    await handler._handle_connect(conn, {"type": "connect"})

    assert len(sent_messages) == 1
    assert sent_messages[0]["type"] == "error"
    assert "token" in sent_messages[0]["message"].lower()


@pytest.mark.asyncio
async def test_handle_connect_rejects_invalid_token():
    """无效 token 应被拒绝"""
    from app.api.ws_handler import WSHandler, WSConnection

    handler = WSHandler()

    ws = MagicMock()
    ws.client = MagicMock()
    ws.client.host = "127.0.0.1"
    ws.headers = {}

    conn = WSConnection(ws)

    sent_messages = []
    async def mock_send_json(data):
        sent_messages.append(data)
    conn.send_json = mock_send_json

    await handler._handle_connect(conn, {"type": "connect", "token": "invalid.token.here"})

    assert len(sent_messages) == 1
    assert sent_messages[0]["type"] == "error"
    assert "invalid" in sent_messages[0]["message"].lower() or "token" in sent_messages[0]["message"].lower()


@pytest.mark.asyncio
async def test_handle_connect_uses_server_permissions():
    """服务端权限必须覆盖客户端提供的权限"""
    from app.api.ws_handler import WSHandler, WSConnection

    handler = WSHandler()

    ws = MagicMock()
    ws.client = MagicMock()
    ws.client.host = "127.0.0.1"
    ws.headers = {}
    ws.client_state = MagicMock()

    conn = WSConnection(ws)

    token = create_access_token(subject="1", username="admin")

    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.name = "admin"
    mock_user.location_id = 999
    mock_user.attributes = {
        "email": "admin@example.com",
        "roles": ["player"],
        "permissions": ["player.*"],
        "is_active": True,
        "is_locked": False,
    }

    sent_messages = []
    async def mock_send_json(data):
        sent_messages.append(data)
    conn.send_json = mock_send_json

    with patch("app.api.ws_handler.db_session_context") as mock_db_ctx:
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db_ctx.return_value.__enter__.return_value = mock_session

        # 客户端尝试提供 admin 权限
        await handler._handle_connect(conn, {
            "type": "connect",
            "token": token,
            "permissions": ["admin.*"]
        })

    # 验证服务端权限被使用
    assert conn.permissions == ["player.*"]
    assert conn.permissions != ["admin.*"]


@pytest.mark.asyncio
async def test_handle_connect_spawns_user_when_location_missing():
    """仅 WS 登录且 account 尚无 location_id 时，应调用与 SSH 相同的 spawn_user 落点"""
    from app.api.ws_handler import WSHandler, WSConnection

    handler = WSHandler()
    ws = MagicMock()
    ws.client = MagicMock()
    ws.client.host = "127.0.0.1"
    ws.headers = {}
    conn = WSConnection(ws)

    token = create_access_token(subject="42", username="cliuser")

    mock_user = MagicMock()
    mock_user.id = 42
    mock_user.name = "cliuser"
    mock_user.location_id = None
    mock_user.attributes = {
        "email": "cli@example.com",
        "roles": ["player"],
        "permissions": ["player.*"],
        "is_active": True,
        "is_locked": False,
    }

    sent_messages = []

    async def mock_send_json(data):
        sent_messages.append(data)

    conn.send_json = mock_send_json

    with patch("app.api.ws_handler.db_session_context") as mock_db_ctx:
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user
        mock_db_ctx.return_value.__enter__.return_value = mock_session
        with patch("app.ssh.game_handler.game_handler.spawn_user", return_value=True) as mock_spawn:
            await handler._handle_connect(conn, {"type": "connect", "token": token})

    mock_spawn.assert_called_once_with(42, "cliuser")
    assert conn.authenticated is True
    assert any(m.get("type") == "connected" for m in sent_messages)


# ---------------------------------------------------------------------------
# Test: Auth required for message types
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_requires_auth():
    """complete 消息需要认证"""
    from app.api.ws_handler import WSHandler, WSConnection

    handler = WSHandler()
    conn = WSConnection(MagicMock())
    conn.authenticated = False

    sent_messages = []
    async def mock_send_json(data):
        sent_messages.append(data)
    conn.send_json = mock_send_json

    await handler._handle_complete(conn, {"type": "complete", "partial": ""})

    assert len(sent_messages) == 1
    assert sent_messages[0]["type"] == "error"
    assert "authenticated" in sent_messages[0]["message"].lower()


@pytest.mark.asyncio
async def test_agent_list_requires_auth():
    """agent_list 消息需要认证"""
    from app.api.ws_handler import WSHandler, WSConnection

    handler = WSHandler()
    conn = WSConnection(MagicMock())
    conn.authenticated = False

    sent_messages = []
    async def mock_send_json(data):
        sent_messages.append(data)
    conn.send_json = mock_send_json

    await handler._handle_agent_list(conn, {"type": "agent_list"})

    assert len(sent_messages) == 1
    assert sent_messages[0]["type"] == "error"
    assert "authenticated" in sent_messages[0]["message"].lower()


@pytest.mark.asyncio
async def test_agent_enter_requires_auth():
    """agent_enter 消息需要认证"""
    from app.api.ws_handler import WSHandler, WSConnection

    handler = WSHandler()
    conn = WSConnection(MagicMock())
    conn.authenticated = False

    sent_messages = []
    async def mock_send_json(data):
        sent_messages.append(data)
    conn.send_json = mock_send_json

    await handler._handle_agent_enter(conn, {"type": "agent_enter", "agent_name": "test"})

    assert len(sent_messages) == 1
    assert sent_messages[0]["type"] == "error"
    assert "authenticated" in sent_messages[0]["message"].lower()


@pytest.mark.asyncio
async def test_agent_exit_requires_auth():
    """agent_exit 消息需要认证"""
    from app.api.ws_handler import WSHandler, WSConnection

    handler = WSHandler()
    conn = WSConnection(MagicMock())
    conn.authenticated = False

    sent_messages = []
    async def mock_send_json(data):
        sent_messages.append(data)
    conn.send_json = mock_send_json

    await handler._handle_agent_exit(conn, {"type": "agent_exit"})

    assert len(sent_messages) == 1
    assert sent_messages[0]["type"] == "error"
    assert "authenticated" in sent_messages[0]["message"].lower()


@pytest.mark.asyncio
async def test_agent_execute_requires_auth():
    """agent_execute 消息需要认证"""
    from app.api.ws_handler import WSHandler, WSConnection

    handler = WSHandler()
    conn = WSConnection(MagicMock())
    conn.authenticated = False

    sent_messages = []
    async def mock_send_json(data):
        sent_messages.append(data)
    conn.send_json = mock_send_json

    await handler._handle_agent_execute(conn, {"type": "agent_execute", "command": "test"})

    assert len(sent_messages) == 1
    assert sent_messages[0]["type"] == "error"
    assert "authenticated" in sent_messages[0]["message"].lower()


# ---------------------------------------------------------------------------
# Test: execute requires auth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_requires_auth():
    """execute 消息需要认证"""
    from app.api.ws_handler import WSHandler, WSConnection

    handler = WSHandler()
    conn = WSConnection(MagicMock())
    conn.authenticated = False

    sent_messages = []
    async def mock_send_json(data):
        sent_messages.append(data)
    conn.send_json = mock_send_json

    await handler._handle_execute(conn, {"type": "execute", "command": "look"})

    assert len(sent_messages) == 1
    assert sent_messages[0]["type"] == "error"
    assert "authenticated" in sent_messages[0]["message"].lower()
