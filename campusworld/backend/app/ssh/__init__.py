"""
CampusWorld SSH模块

提供SSH终端服务，采用双层架构设计:
- Protocol Layer: protocol_handler.py, server.py - 处理SSH协议
- Game Layer: game_handler.py - 处理游戏逻辑
"""

from .server import CampusWorldSSHServer, start_ssh_server
from .session import SSHSession, SessionManager
from .console import SSHConsole
from .protocol_handler import SSHProtocolHandler, ProtocolFactory
from .game_handler import GameHandler, game_handler
from .input_handler import InputHandler

__all__ = [
    # Server
    "CampusWorldSSHServer",
    "start_ssh_server",

    # Session
    "SSHSession",
    "SessionManager",

    # Console
    "SSHConsole",

    # Protocol Layer
    "SSHProtocolHandler",
    "ProtocolFactory",

    # Game Layer
    "GameHandler",
    "game_handler",

    # Input
    "InputHandler",
]
