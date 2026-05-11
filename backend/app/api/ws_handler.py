"""
WebSocket 处理器
为 CLI 客户端提供实时命令执行能力

安全设计:
- 所有连接必须通过 JWT token 认证
- 权限由服务端从数据库查询，禁止客户端提供
- 所有消息类型都需要认证
- 支持连接数和消息速率限制
"""
import json
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import defaultdict
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from jose import JWTError
from app.commands.registry import command_registry
from app.commands.base import CommandContext, CommandResult
from app.commands.shell_words import split_command_line
from app.core.database import db_session_context
from app.core.log import get_logger, LoggerNames
from app.core.security import ALGORITHM
from app.models.graph import Node
logger = get_logger(LoggerNames.API)
audit_logger = get_logger(LoggerNames.AUDIT)

def _release_daemon_possession_for_transport_sync(transport_session_id: Optional[str]) -> None:
    """Release daemon STM locks bound to this WebSocket transport session id when configured."""
    sid = str(transport_session_id or '').strip()
    if not sid:
        return
    try:
        from app.game_engine.agent_runtime.conversation_stm_service import release_daemon_possession_for_transport_session_if_configured
        with db_session_context() as db:
            release_daemon_possession_for_transport_session_if_configured(db, sid)
            db.commit()
    except Exception as e:
        logger.warning('websocket daemon_possession_transport_release_failed session_id=%s err=%s', sid, e)

def _ensure_command_registry_loaded() -> None:
    """SSH 控制台未连接时 registry 可能未初始化；WS 路径兜底。"""
    from app.commands.init_commands import ensure_commands_initialized
    ensure_commands_initialized()
MAX_CONNECTIONS = 1000
MAX_CONNECTIONS_PER_IP = 10
MAX_MESSAGES_PER_SECOND = 100
RATE_LIMIT_WINDOW = 1.0
MAX_MESSAGE_SIZE = 64 * 1024

@dataclass
class RateLimitEntry:
    """单连接速率限制条目"""
    timestamps: List[float] = field(default_factory=list)

class ConnectionRateLimiter:
    """WebSocket 连接和消息速率限制器"""

    def __init__(self):
        self._connections: Dict[int, WSConnection] = {}
        self._ip_connections: Dict[str, int] = defaultdict(int)
        self._message_rates: Dict[int, RateLimitEntry] = {}
        self._lock = asyncio.Lock()

    async def try_add_connection(self, websocket: WebSocket, conn: 'WSConnection') -> tuple[bool, str]:
        """
        尝试添加新连接。

        Returns:
            (allowed, error_message)
        """
        async with self._lock:
            client_ip = self._get_client_ip(websocket)
            if len(self._connections) >= MAX_CONNECTIONS:
                return (False, 'Server at maximum connection capacity')
            if self._ip_connections.get(client_ip, 0) >= MAX_CONNECTIONS_PER_IP:
                return (False, f'Too many connections from IP: {client_ip}')
            conn_id = id(websocket)
            self._connections[conn_id] = conn
            self._ip_connections[client_ip] += 1
            self._message_rates[conn_id] = RateLimitEntry()
            return (True, '')

    async def remove_connection(self, websocket: WebSocket, conn: 'WSConnection'):
        """移除连接"""
        async with self._lock:
            conn_id = id(websocket)
            client_ip = self._get_client_ip(websocket)
            if conn_id in self._connections:
                del self._connections[conn_id]
            if client_ip in self._ip_connections:
                self._ip_connections[client_ip] = max(0, self._ip_connections[client_ip] - 1)
            if conn_id in self._message_rates:
                del self._message_rates[conn_id]

    async def check_message_rate(self, websocket: WebSocket) -> tuple[bool, str]:
        """
        检查消息速率是否超限。

        Returns:
            (allowed, error_message)
        """
        conn_id = id(websocket)
        async with self._lock:
            if conn_id not in self._message_rates:
                return (False, 'Connection not registered')
            now = time.time()
            entry = self._message_rates[conn_id]
            entry.timestamps = [ts for ts in entry.timestamps if now - ts < RATE_LIMIT_WINDOW]
            if len(entry.timestamps) >= MAX_MESSAGES_PER_SECOND:
                return (False, f'Message rate limit exceeded ({MAX_MESSAGES_PER_SECOND}/s)')
            entry.timestamps.append(now)
            return (True, '')

    def _get_client_ip(self, websocket: WebSocket) -> str:
        """获取客户端 IP 地址"""
        headers = dict(websocket.headers)
        forwarded = headers.get('x-forwarded-for', '')
        if forwarded:
            return forwarded.split(',')[0].strip()
        if websocket.client:
            return websocket.client.host
        return 'unknown'

    def try_add_connection_sync(self, websocket: WebSocket, conn: 'WSConnection') -> tuple[bool, str]:
        """同步版本：尝试添加新连接（用于测试）"""
        client_ip = self._get_client_ip(websocket)
        if len(self._connections) >= MAX_CONNECTIONS:
            return (False, 'Server at maximum connection capacity')
        if self._ip_connections.get(client_ip, 0) >= MAX_CONNECTIONS_PER_IP:
            return (False, f'Too many connections from IP: {client_ip}')
        conn_id = id(websocket)
        self._connections[conn_id] = conn
        self._ip_connections[client_ip] += 1
        self._message_rates[conn_id] = RateLimitEntry()
        return (True, '')

    def check_message_rate_sync(self, conn_id: int) -> tuple[bool, str]:
        """同步版本：检查消息速率（用于测试）"""
        if conn_id not in self._message_rates:
            return (False, 'Connection not registered')
        now = time.time()
        entry = self._message_rates[conn_id]
        entry.timestamps = [ts for ts in entry.timestamps if now - ts < RATE_LIMIT_WINDOW]
        if len(entry.timestamps) >= MAX_MESSAGES_PER_SECOND:
            return (False, f'Message rate limit exceeded ({MAX_MESSAGES_PER_SECOND}/s)')
        entry.timestamps.append(now)
        return (True, '')
_rate_limiter = ConnectionRateLimiter()

class WSConnection:
    """WebSocket 连接封装"""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.user_id: Optional[str] = None
        self.username: Optional[str] = None
        self.session_id: Optional[str] = None
        self.permissions: List[str] = []
        self.roles: List[str] = []
        self.authenticated = False
        self.authenticated_at: Optional[float] = None
        self.command_ephemeral: Dict[str, Any] = {}

    async def send_json(self, data: Dict[str, Any]) -> bool:
        """发送 JSON 消息"""
        try:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_json(data)
                return True
            return False
        except Exception as e:
            logger.error(f'Failed to send WebSocket message: {e}')
            return False

    async def send_text(self, text: str) -> bool:
        """发送文本消息"""
        try:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_text(text)
                return True
            return False
        except Exception as e:
            logger.error(f'Failed to send WebSocket text: {e}')
            return False

class WSHandler:
    """WebSocket 协议处理器"""

    def __init__(self):
        self.logger = logger

    async def handle_connect(self, websocket: WebSocket) -> WSConnection:
        """处理新的 WebSocket 连接（限流检查）"""
        conn = WSConnection(websocket)
        (allowed, error) = await _rate_limiter.try_add_connection(websocket, conn)
        if not allowed:
            await websocket.accept()
            await websocket.close(code=1011, reason=error)
            raise WebSocketDisconnect()
        await websocket.accept()
        self.logger.info(f'WebSocket connection accepted: {websocket.client}')
        return conn

    async def handle_disconnect(self, websocket: WebSocket):
        """处理 WebSocket 断开"""
        conn = _rate_limiter._connections.get(id(websocket))
        if conn:
            sid = conn.session_id
            await _rate_limiter.remove_connection(websocket, conn)
            if sid:
                await asyncio.to_thread(_release_daemon_possession_for_transport_sync, sid)
            if conn.authenticated:
                audit_logger.info(f'websocket_disconnect user_id={conn.user_id} username={conn.username} session_id={conn.session_id}')
        self.logger.info(f'WebSocket client disconnected')

    async def handle_message(self, websocket: WebSocket, message: str):
        """处理接收到的消息"""
        conn = _rate_limiter._connections.get(id(websocket))
        if not conn:
            await websocket.send_json({'type': 'error', 'message': 'Connection not registered'})
            return
        if len(message) > MAX_MESSAGE_SIZE:
            await websocket.send_json({'type': 'error', 'message': f'Message too large (max {MAX_MESSAGE_SIZE} bytes)'})
            return
        (allowed, error) = await _rate_limiter.check_message_rate(websocket)
        if not allowed:
            await websocket.send_json({'type': 'error', 'message': error})
            return
        try:
            data = json.loads(message)
            msg_type = data.get('type', '')
            if msg_type == 'connect':
                await self._handle_connect(conn, data)
            elif msg_type == 'execute':
                await self._handle_execute(conn, data)
            elif msg_type == 'complete':
                await self._handle_complete(conn, data)
            elif msg_type == 'ping':
                await conn.send_json({'type': 'pong'})
            elif msg_type == 'agent_enter':
                await self._handle_agent_enter(conn, data)
            elif msg_type == 'agent_exit':
                await self._handle_agent_exit(conn, data)
            elif msg_type == 'agent_execute':
                await self._handle_agent_execute(conn, data)
            elif msg_type == 'agent_list':
                await self._handle_agent_list(conn, data)
            elif msg_type == 'refresh':
                await self._handle_refresh(conn, data)
            else:
                await conn.send_json({'type': 'error', 'message': 'Unknown message type'})
        except json.JSONDecodeError:
            await conn.send_json({'type': 'error', 'message': 'Invalid JSON'})
        except Exception as e:
            self.logger.error(f'Error handling WebSocket message: {e}')
            await conn.send_json({'type': 'error', 'message': 'Internal error'})

    async def _handle_connect(self, conn: WSConnection, data: Dict[str, Any]):
        """
        处理认证连接 - JWT token 验证

        安全要求:
        - 必须提供有效的 JWT token
        - 禁止客户端提供 user_id, username, permissions
        - 权限由服务端从数据库查询
        """
        token = data.get('token', '')
        if not token:
            await conn.send_json({'type': 'error', 'message': 'Authentication required (missing token)'})
            audit_logger.warning(f'ws_auth_failed_no_token ip={conn.websocket.client}')
            return
        try:
            from app.core.security import _get_secret_key
            from jose import jwt
            payload = jwt.decode(token, _get_secret_key(), algorithms=[ALGORITHM])
        except JWTError:
            await conn.send_json({'type': 'error', 'message': 'Invalid or expired token'})
            audit_logger.warning('ws_auth_failed_invalid_token')
            return
        email = payload.get('sub')
        if not email:
            await conn.send_json({'type': 'error', 'message': 'Token missing subject'})
            return
        try:
            with db_session_context() as db_session:
                user_node = db_session.query(Node).filter(Node.type_code == 'account', (Node.attributes['email'].astext == email) | (Node.id == int(email) if email.isdigit() else False)).first()
                if not user_node:
                    await conn.send_json({'type': 'error', 'message': 'User not found'})
                    audit_logger.warning(f'ws_auth_failed_user_not_found email={email}')
                    return
                attrs = dict(user_node.attributes or {})
                if not attrs.get('is_active', True):
                    await conn.send_json({'type': 'error', 'message': 'Account is inactive'})
                    return
                if attrs.get('is_locked', False):
                    await conn.send_json({'type': 'error', 'message': 'Account is locked'})
                    return
                roles = list(attrs.get('roles', []))
                permissions = list(attrs.get('permissions', []))
                if user_node.location_id is None:
                    from app.ssh.game_handler import game_handler
                    spawned = game_handler.spawn_user(user_node.id, user_node.name or 'unknown')
                    if not spawned:
                        self.logger.warning('ws_auth_spawn_user_failed', extra={'user_id': user_node.id, 'username': user_node.name})
                conn.user_id = str(user_node.id)
                conn.username = user_node.name
                conn.session_id = f'ws_{user_node.id}_{int(time.time())}'
                conn.roles = roles
                conn.permissions = permissions
                conn.authenticated = True
                conn.authenticated_at = time.time()
                await conn.send_json({'type': 'connected', 'user': {'user_id': conn.user_id, 'username': conn.username, 'session_id': conn.session_id}, 'session': {'session_id': conn.session_id}})
                audit_logger.info(f'ws_auth_success user_id={conn.user_id} username={conn.username} ip={conn.websocket.client}')
        except Exception as e:
            self.logger.error(f'Database error during auth: {e}')
            await conn.send_json({'type': 'error', 'message': 'Authentication failed'})

    async def _handle_execute(self, conn: WSConnection, data: Dict[str, Any]):
        """处理命令执行"""
        if not conn.authenticated:
            await conn.send_json({'type': 'error', 'message': 'Not authenticated'})
            return
        command_line = data.get('command', '')
        if not command_line.strip():
            await conn.send_json({'type': 'result', 'success': False, 'message': 'Empty command'})
            return
        if len(command_line) > 4096:
            await conn.send_json({'type': 'result', 'success': False, 'message': 'Command too long'})
            return
        _ensure_command_registry_loaded()
        parts = split_command_line(command_line)
        command_name = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        with db_session_context() as db_session:
            context = CommandContext(user_id=conn.user_id or 'unknown', username=conn.username or 'unknown', session_id=conn.session_id or 'unknown', permissions=conn.permissions, roles=conn.roles, session=conn, db_session=db_session)
            command = command_registry.get_command(command_name)
            if not command:
                await conn.send_json({'type': 'result', 'success': False, 'message': f"Command '{command_name}' not found"})
                return
            decision = command_registry.authorize_command(command, context)
            if not decision.allowed:
                await conn.send_json({'type': 'result', 'success': False, 'message': f"Permission denied for command '{command_name}'"})
                return
            result = command.execute(context, args)
            await conn.send_json({'type': 'result', 'success': result.success, 'message': result.message, 'data': result.data, 'should_exit': result.should_exit})

    async def _handle_complete(self, conn: WSConnection, data: Dict[str, Any]):
        """处理补全请求（需要认证）"""
        if not conn.authenticated:
            await conn.send_json({'type': 'error', 'message': 'Not authenticated'})
            return
        _ensure_command_registry_loaded()
        partial = data.get('partial', '')
        if not partial:
            commands = []
            for (name, cmd) in command_registry.commands.items():
                commands.append({'name': name, 'description': cmd.description or ''})
                for alias in cmd.aliases:
                    commands.append({'name': alias, 'description': f'alias of {name}'})
        else:
            commands = []
            partial_lower = partial.lower()
            for (name, cmd) in command_registry.commands.items():
                if name.lower().startswith(partial_lower):
                    commands.append({'name': name, 'description': cmd.description or ''})
                for alias in cmd.aliases:
                    if alias.lower().startswith(partial_lower):
                        commands.append({'name': alias, 'description': f'alias of {name}'})
        seen = set()
        unique_commands = []
        for cmd in commands:
            if cmd['name'] not in seen:
                seen.add(cmd['name'])
                unique_commands.append(cmd)
        await conn.send_json({'type': 'completions', 'options': [c['name'] for c in unique_commands]})

    async def _handle_agent_list(self, conn: WSConnection, data: Dict[str, Any]):
        """返回可用 Agent 列表（需要认证）"""
        if not conn.authenticated:
            await conn.send_json({'type': 'error', 'message': 'Not authenticated'})
            return
        agents = []
        await conn.send_json({'type': 'agent_list', 'agents': agents})

    async def _handle_agent_enter(self, conn: WSConnection, data: Dict[str, Any]):
        """进入 Agent 环境（需要认证）"""
        if not conn.authenticated:
            await conn.send_json({'type': 'error', 'message': 'Not authenticated'})
            return
        agent_name = data.get('agent_name', '')
        await conn.send_json({'type': 'agent_entered', 'agent_name': agent_name})

    async def _handle_agent_exit(self, conn: WSConnection, data: Dict[str, Any]):
        """退出 Agent 环境（需要认证）"""
        if not conn.authenticated:
            await conn.send_json({'type': 'error', 'message': 'Not authenticated'})
            return
        await conn.send_json({'type': 'agent_exited'})

    async def _handle_agent_execute(self, conn: WSConnection, data: Dict[str, Any]):
        """在 Agent 环境中执行命令（需要认证）"""
        if not conn.authenticated:
            await conn.send_json({'type': 'error', 'message': 'Not authenticated'})
            return
        command = data.get('command', '')
        await conn.send_json({'type': 'agent_result', 'result': '', 'success': True})

    async def _handle_refresh(self, conn: WSConnection, data: Dict[str, Any]):
        """
        处理 refresh token 刷新请求。

        安全要求:
        - 连接必须已认证（conn.authenticated == True）
        - 客户端必须提供 access_token 和 refresh_token
        - 验证 access_token 与 refresh_token 属于同一用户

        消息格式: {"type": "refresh", "access_token": "<token>", "refresh_token": "<token>"}
        响应格式: {"type": "refreshed", "access_token": "...", "refresh_token": "...", "expires_in": 11520}
        """
        from app.core.auth_service import AuthService
        if not conn.authenticated:
            await conn.send_json({'type': 'error', 'message': 'Not authenticated'})
            return
        access_token = data.get('access_token', '')
        refresh_token = data.get('refresh_token', '')
        if not access_token:
            await conn.send_json({'type': 'error', 'message': 'Missing access_token'})
            return
        if not refresh_token:
            await conn.send_json({'type': 'error', 'message': 'Missing refresh_token'})
            return
        device = f'websocket:{conn.websocket.client}'
        with db_session_context() as db:
            validation = AuthService.validate_refresh_token(db, refresh_token, expected_user_id=None)
            if not validation['valid']:
                await conn.send_json({'type': 'error', 'message': f"Invalid refresh token: {validation['error']}"})
                return
            result = AuthService.rotate_refresh_token(db=db, user_id=validation['user_id'], old_jti=validation['jti'], old_family_id=validation['family_id'], device=device, expected_access_token=access_token)
            if 'error' in result:
                error_messages = {'token_binding_mismatch': 'Access token does not match refresh token', 'invalid_access_token': 'Invalid access token', 'user_not_found': 'User not found', 'account_inactive': 'Account is inactive', 'account_locked': 'Account is locked'}
                await conn.send_json({'type': 'error', 'message': error_messages.get(result['error'], 'Token rotation failed')})
                return
            await conn.send_json({'type': 'refreshed', 'access_token': result['access_token'], 'refresh_token': result['refresh_token'], 'token_type': 'bearer', 'expires_in': result['expires_in']})
ws_handler = WSHandler()
