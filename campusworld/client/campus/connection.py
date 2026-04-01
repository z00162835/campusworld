"""
WebSocket 连接管理
"""

import asyncio
import json
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass

import websockets

from .protocol import WSMessage


@dataclass
class UserInfo:
    """用户信息"""
    user_id: str
    username: str
    session_id: str


class WSConnection:
    """WebSocket 连接"""

    def __init__(self, host: str, port: int, use_ssl: bool = False):
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.user_info: Optional[UserInfo] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._handlers: Dict[str, Callable] = {}

    @property
    def uri(self) -> str:
        scheme = "wss" if self.use_ssl else "ws"
        return f"{scheme}://{self.host}:{self.port}/ws"

    async def connect(self, user_id: str, username: str,
                     permissions: Optional[List[str]] = None) -> bool:
        """连接到服务器"""
        try:
            self.ws = await websockets.connect(self.uri)
            # 发送连接消息
            await self.ws.send(WSMessage.connect(
                user_id=user_id,
                username=username,
                permissions=permissions
            ))
            # 等待连接确认
            response = await self.ws.recv()
            msg = WSMessage.parse(response)
            if msg and WSMessage.is_connected(msg):
                user_data = msg.get("user", {})
                self.user_info = UserInfo(
                    user_id=user_data.get("user_id", ""),
                    username=user_data.get("username", ""),
                    session_id=user_data.get("session_id", "")
                )
                return True
            return False
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    async def disconnect(self):
        """断开连接"""
        if self.ws:
            await self.ws.close()
            self.ws = None

    async def send_command(self, command: str, args: Optional[List[str]] = None) -> bool:
        """发送命令"""
        if not self.ws:
            return False
        try:
            await self.ws.send(WSMessage.execute(command, args))
            return True
        except Exception as e:
            print(f"Send command failed: {e}")
            return False

    async def request_completions(self, partial: str) -> List[str]:
        """请求补全"""
        if not self.ws:
            return []
        try:
            await self.ws.send(WSMessage.complete(partial))
            response = await asyncio.wait_for(self.ws.recv(), timeout=5.0)
            msg = WSMessage.parse(response)
            if msg and WSMessage.is_completions(msg):
                return msg.get("options", [])
            return []
        except asyncio.TimeoutError:
            return []
        except Exception as e:
            print(f"Completion request failed: {e}")
            return []

    async def receive(self) -> Optional[Dict[str, Any]]:
        """接收消息"""
        if not self.ws:
            return None
        try:
            message = await self.ws.recv()
            return WSMessage.parse(message)
        except Exception:
            return None

    def register_handler(self, msg_type: str, handler: Callable):
        """注册消息处理器"""
        self._handlers[msg_type] = handler

    async def start_receiving(self, callback: Callable[[Dict[str, Any]], None]):
        """开始接收消息（异步）"""
        async def _receive_loop():
            while self.ws:
                try:
                    msg = await self.receive()
                    if msg:
                        callback(msg)
                except websockets.exceptions.ConnectionClosed:
                    break
                except Exception as e:
                    print(f"Receive error: {e}")
                    break

        self._receive_task = asyncio.create_task(_receive_loop())

    async def stop_receiving(self):
        """停止接收消息"""
        if self._receive_task:
            self._receive_task.cancel()
            self._receive_task = None
