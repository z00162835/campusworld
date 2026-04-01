"""
WebSocket 处理器
为 CLI 客户端提供实时命令执行能力
"""

import json
import asyncio
from typing import Dict, Any, Optional, List
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.commands.registry import command_registry
from app.commands.base import CommandContext, CommandResult
from app.core.database import db_session_context
from app.core.log import get_logger, LoggerNames

logger = get_logger(LoggerNames.API)


class WSConnection:
    """WebSocket 连接封装"""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.user_id: Optional[str] = None
        self.username: Optional[str] = None
        self.session_id: Optional[str] = None
        self.permissions: List[str] = []
        self.authenticated = False

    async def send_json(self, data: Dict[str, Any]) -> bool:
        """发送 JSON 消息"""
        try:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_json(data)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
            return False

    async def send_text(self, text: str) -> bool:
        """发送文本消息"""
        try:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_text(text)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to send WebSocket text: {e}")
            return False


class WSHandler:
    """WebSocket 协议处理器"""

    def __init__(self):
        self.connections: Dict[str, WSConnection] = {}
        self.logger = logger

    async def handle_connect(self, websocket: WebSocket) -> WSConnection:
        """处理新的 WebSocket 连接"""
        await websocket.accept()
        conn = WSConnection(websocket)
        self.connections[id(websocket)] = conn
        self.logger.info(f"WebSocket client connected: {websocket.client}")
        return conn

    async def handle_disconnect(self, websocket: WebSocket):
        """处理 WebSocket 断开"""
        conn_id = id(websocket)
        if conn_id in self.connections:
            del self.connections[conn_id]
            self.logger.info(f"WebSocket client disconnected")

    async def handle_message(self, websocket: WebSocket, message: str):
        """处理接收到的消息"""
        conn = self.connections.get(id(websocket))
        if not conn:
            await websocket.send_json({"type": "error", "message": "Not connected"})
            return

        try:
            data = json.loads(message)
            msg_type = data.get("type", "")

            if msg_type == "connect":
                await self._handle_connect(conn, data)
            elif msg_type == "execute":
                await self._handle_execute(conn, data)
            elif msg_type == "complete":
                await self._handle_complete(conn, data)
            elif msg_type == "ping":
                await conn.send_json({"type": "pong"})
            else:
                await conn.send_json({"type": "error", "message": f"Unknown message type: {msg_type}"})

        except json.JSONDecodeError:
            await conn.send_json({"type": "error", "message": "Invalid JSON"})
        except Exception as e:
            self.logger.error(f"Error handling WebSocket message: {e}")
            await conn.send_json({"type": "error", "message": str(e)})

    async def _handle_connect(self, conn: WSConnection, data: Dict[str, Any]):
        """处理认证连接"""
        token = data.get("token", "")
        user_id = data.get("user_id", "")
        username = data.get("username", "")

        # TODO: 验证 token，获取用户信息
        # 目前简化处理，直接接受连接信息
        if user_id and username:
            conn.user_id = user_id
            conn.username = username
            conn.session_id = data.get("session_id", f"ws_{id(conn)}")
            conn.permissions = data.get("permissions", ["player"])
            conn.authenticated = True

            await conn.send_json({
                "type": "connected",
                "user": {
                    "user_id": conn.user_id,
                    "username": conn.username,
                    "session_id": conn.session_id
                },
                "session": {
                    "session_id": conn.session_id
                }
            })
        else:
            await conn.send_json({
                "type": "error",
                "message": "Missing user_id or username"
            })

    async def _handle_execute(self, conn: WSConnection, data: Dict[str, Any]):
        """处理命令执行"""
        if not conn.authenticated:
            await conn.send_json({"type": "error", "message": "Not authenticated"})
            return

        command_line = data.get("command", "")
        if not command_line.strip():
            await conn.send_json({"type": "result", "success": False, "message": "Empty command"})
            return

        # 解析命令
        parts = command_line.strip().split()
        command_name = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        # 创建上下文并执行
        with db_session_context() as db_session:
            context = CommandContext(
                user_id=conn.user_id or "unknown",
                username=conn.username or "unknown",
                session_id=conn.session_id or "unknown",
                permissions=conn.permissions,
                db_session=db_session,
            )

            command = command_registry.get_command(command_name)
            if not command:
                await conn.send_json({
                    "type": "result",
                    "success": False,
                    "message": f"Command '{command_name}' not found"
                })
                return

            decision = command_registry.authorize_command(command, context)
            if not decision.allowed:
                await conn.send_json({
                    "type": "result",
                    "success": False,
                    "message": f"Permission denied for command '{command_name}'"
                })
                return

            result = command.execute(context, args)

            # 发送结果
            await conn.send_json({
                "type": "result",
                "success": result.success,
                "message": result.message,
                "data": result.data,
                "should_exit": result.should_exit
            })

    async def _handle_complete(self, conn: WSConnection, data: Dict[str, Any]):
        """处理补全请求"""
        partial = data.get("partial", "")

        if not partial:
            # 返回所有可用命令
            commands = []
            for name, cmd in command_registry.commands.items():
                commands.append({
                    "name": name,
                    "description": cmd.description or ""
                })
                for alias in cmd.aliases:
                    commands.append({
                        "name": alias,
                        "description": f"alias of {name}"
                    })
        else:
            # 前缀匹配
            commands = []
            for name, cmd in command_registry.commands.items():
                if name.startswith(partial.lower()):
                    commands.append({
                        "name": name,
                        "description": cmd.description or ""
                    })
                for alias in cmd.aliases:
                    if alias.startswith(partial.lower()):
                        commands.append({
                            "name": alias,
                            "description": f"alias of {name}"
                        })

        # 去重
        seen = set()
        unique_commands = []
        for cmd in commands:
            if cmd["name"] not in seen:
                seen.add(cmd["name"])
                unique_commands.append(cmd)

        await conn.send_json({
            "type": "completions",
            "options": [c["name"] for c in unique_commands]
        })


# 全局 WebSocket 处理器实例
ws_handler = WSHandler()
