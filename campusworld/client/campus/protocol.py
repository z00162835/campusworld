"""
协议处理
WebSocket 消息的编码和解码
"""

import json
from typing import Dict, Any, Optional, List


class WSMessage:
    """WebSocket 消息"""

    @staticmethod
    def connect(user_id: str, username: str, session_id: str = "",
                permissions: Optional[List[str]] = None) -> str:
        """创建连接消息"""
        return json.dumps({
            "type": "connect",
            "user_id": user_id,
            "username": username,
            "session_id": session_id,
            "permissions": permissions or ["player"]
        })

    @staticmethod
    def execute(command: str, args: Optional[List[str]] = None) -> str:
        """创建执行命令消息"""
        return json.dumps({
            "type": "execute",
            "command": command,
            "args": args or []
        })

    @staticmethod
    def complete(partial: str) -> str:
        """创建补全请求消息"""
        return json.dumps({
            "type": "complete",
            "partial": partial
        })

    @staticmethod
    def ping() -> str:
        """创建心跳消息"""
        return json.dumps({"type": "ping"})

    @staticmethod
    def parse(message: str) -> Optional[Dict[str, Any]]:
        """解析消息"""
        try:
            return json.loads(message)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def is_result(msg: Dict[str, Any]) -> bool:
        """是否是命令结果"""
        return msg.get("type") == "result"

    @staticmethod
    def is_connected(msg: Dict[str, Any]) -> bool:
        """是否是连接成功"""
        return msg.get("type") == "connected"

    @staticmethod
    def is_completions(msg: Dict[str, Any]) -> bool:
        """是否是补全结果"""
        return msg.get("type") == "completions"

    @staticmethod
    def is_error(msg: Dict[str, Any]) -> bool:
        """是否是错误消息"""
        return msg.get("type") == "error"

    @staticmethod
    def is_pong(msg: Dict[str, Any]) -> bool:
        """是否是心跳响应"""
        return msg.get("type") == "pong"
