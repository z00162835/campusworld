"""
WebSocket 连接管理
"""

import asyncio
import json
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass
import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedError

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
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._pending_responses: Dict[str, asyncio.Future] = {}

    @property
    def uri(self) -> str:
        scheme = "wss" if self.use_ssl else "ws"
        return f"{scheme}://{self.host}:{self.port}/ws"

    @property
    def is_connected(self) -> bool:
        return self.ws is not None and self._running

    async def connect(self, user_id: str, username: str,
                     permissions: Optional[List[str]] = None) -> bool:
        """连接到服务器"""
        try:
            self.ws = await websockets.connect(self.uri, ping_interval=30)
            # 发送连接消息
            await self.ws.send(WSMessage.connect(
                user_id=user_id,
                username=username,
                permissions=permissions
            ))
            # 等待连接确认
            response = await asyncio.wait_for(self.ws.recv(), timeout=10.0)
            msg = WSMessage.parse(response)
            if msg and WSMessage.is_connected(msg):
                user_data = msg.get("user", {})
                self.user_info = UserInfo(
                    user_id=user_data.get("user_id", ""),
                    username=user_data.get("username", ""),
                    session_id=user_data.get("session_id", "")
                )
                self._running = True
                # 开始接收消息
                self._receive_task = asyncio.create_task(self._receive_loop())
                return True
            return False
        except asyncio.TimeoutError:
            print("Connection timeout")
            return False
        except ConnectionClosedError as e:
            print(f"Connection closed: {e}")
            return False
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    async def disconnect(self):
        """断开连接"""
        self._running = False
        if self._receive_task:
            self._receive_task.cancel()
            self._receive_task = None
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None

    async def reconnect(self, user_id: str, username: str,
                       permissions: Optional[List[str]] = None) -> bool:
        """重新连接"""
        await self.disconnect()
        await asyncio.sleep(1)  # 等待一下
        return await self.connect(user_id, username, permissions)

    async def send_command(self, command: str, args: Optional[List[str]] = None) -> bool:
        """发送命令"""
        if not self.is_connected:
            return False
        try:
            await self.ws.send(WSMessage.execute(command, args))
            return True
        except ConnectionClosedError:
            print("Connection closed while sending")
            return False
        except Exception as e:
            print(f"Send command failed: {e}")
            return False

    async def request_completions(self, partial: str) -> List[str]:
        """请求补全 - 使用队列等待响应"""
        if not self.is_connected:
            return []
        try:
            await self.ws.send(WSMessage.complete(partial))
            # 等待响应通过队列返回
            response = await asyncio.wait_for(self._message_queue.get(), timeout=5.0)
            if response and WSMessage.is_completions(response):
                return response.get("options", [])
            return []
        except asyncio.TimeoutError:
            return []
        except Exception as e:
            print(f"Completion request failed: {e}")
            return []

    async def receive(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """接收消息（从队列）"""
        try:
            if timeout:
                return await asyncio.wait_for(self._message_queue.get(), timeout=timeout)
            else:
                return await self._message_queue.get()
        except asyncio.TimeoutError:
            return None

    async def _receive_loop(self):
        """接收消息循环"""
        while self._running and self.ws:
            try:
                message = await self.ws.recv()
                msg = WSMessage.parse(message)
                if msg:
                    # 将消息放入队列
                    await self._message_queue.put(msg)
                    # 同时调用处理器
                    msg_type = msg.get("type", "")
                    if msg_type in self._handlers:
                        handler = self._handlers[msg_type]
                        if asyncio.iscoroutinefunction(handler):
                            await handler(msg)
                        else:
                            handler(msg)
            except ConnectionClosed:
                print("Connection closed")
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Receive error: {e}")
                await asyncio.sleep(0.1)

    def register_handler(self, msg_type: str, handler: Callable):
        """注册消息处理器"""
        self._handlers[msg_type] = handler

    async def start_receiving(self, callback: Callable[[Dict[str, Any]], None]):
        """开始接收消息（异步）"""
        self.register_handler("result", callback)

    async def stop_receiving(self):
        """停止接收消息"""
        self._handlers.clear()

    async def agent_enter(self, agent_name: str) -> bool:
        """请求进入 Agent 环境"""
        if not self.is_connected:
            return False
        try:
            await self.ws.send(WSMessage.agent_enter(agent_name))
            return True
        except Exception as e:
            print(f"Agent enter failed: {e}")
            return False

    async def agent_exit(self) -> bool:
        """请求退出 Agent 环境"""
        if not self.is_connected:
            return False
        try:
            await self.ws.send(WSMessage.agent_exit())
            return True
        except Exception as e:
            print(f"Agent exit failed: {e}")
            return False

    async def agent_execute(self, command: str) -> bool:
        """在 Agent 环境中执行命令"""
        if not self.is_connected:
            return False
        try:
            await self.ws.send(WSMessage.agent_execute(command))
            return True
        except Exception as e:
            print(f"Agent execute failed: {e}")
            return False

    async def request_agents(self) -> List[str]:
        """请求可用 Agent 列表"""
        if not self.is_connected:
            return []
        try:
            await self.ws.send(WSMessage.agent_list())
            response = await asyncio.wait_for(self._message_queue.get(), timeout=5.0)
            if response and WSMessage.is_agent_list(response):
                return response.get("agents", [])
            return []
        except asyncio.TimeoutError:
            return []
        except Exception as e:
            print(f"Agent list request failed: {e}")
            return []
