"""
协议处理
WebSocket 消息的编码和解码
"""

import json
from typing import Dict, Any, Optional, List


class WSMessage:
    """WebSocket 消息"""

    @staticmethod
    def connect(token: str) -> str:
        """创建连接消息（JWT token 认证）"""
        return json.dumps({
            "type": "connect",
            "token": token
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

    # Agent 消息
    @staticmethod
    def agent_enter(agent_name: str) -> str:
        """创建进入 Agent 环境消息"""
        return json.dumps({"type": "agent_enter", "agent_name": agent_name})

    @staticmethod
    def agent_exit() -> str:
        """创建退出 Agent 环境消息"""
        return json.dumps({"type": "agent_exit"})

    @staticmethod
    def agent_execute(command: str) -> str:
        """创建 Agent 执行命令消息"""
        return json.dumps({"type": "agent_execute", "command": command})

    @staticmethod
    def agent_list() -> str:
        """创建列出 Agent 实例消息"""
        return json.dumps({"type": "agent_list"})

    @staticmethod
    def is_agent_entered(msg: Dict[str, Any]) -> bool:
        """是否是进入 Agent 环境响应"""
        return msg.get("type") == "agent_entered"

    @staticmethod
    def is_agent_exited(msg: Dict[str, Any]) -> bool:
        """是否是退出 Agent 环境响应"""
        return msg.get("type") == "agent_exited"

    @staticmethod
    def is_agent_result(msg: Dict[str, Any]) -> bool:
        """是否是 Agent 执行结果"""
        return msg.get("type") == "agent_result"

    @staticmethod
    def is_agent_list(msg: Dict[str, Any]) -> bool:
        """是否是 Agent 列表响应"""
        return msg.get("type") == "agent_list"
