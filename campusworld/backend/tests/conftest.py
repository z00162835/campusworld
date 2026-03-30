"""
Shared pytest fixtures for CampusWorld backend tests

Architecture Role: 本 conftest 定义测试工程化标准 fixtures，
为所有后端测试提供统一的模拟对象和数据生成能力。
"""

import sys
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch
from typing import Any, Dict

import pytest

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ---------------------------------------------------------------------------
# Database Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db_session():
    """
    模拟 SQLAlchemy 数据库会话
    用于不需要真实数据库的单元测试
    """
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.filter.return_value.all.return_value = []
    session.query.return_value.count.return_value = 0
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    return session


@pytest.fixture
def mock_db_engine():
    """模拟数据库引擎"""
    engine = MagicMock()
    engine.connect.return_value.__enter__ = MagicMock()
    engine.connect.return_value.__exit__ = MagicMock()
    return engine


# ---------------------------------------------------------------------------
# User / Account Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_user_node():
    """
    模拟用户节点（GraphNode）
    用于 EntryRouter / GameHandler 测试
    """
    user = MagicMock()
    user.id = 1
    user.uuid = uuid.uuid4()
    user.name = "testuser"
    user.attributes = {
        "email": "test@example.com",
        "roles": ["player"],
        "active_world": None,
        "last_world_location": None,
    }
    user.is_active = True
    return user


@pytest.fixture
def mock_user_node_with_world():
    """
    模拟有世界恢复状态的用户节点
    用于 Last Location Resume 测试
    """
    user = MagicMock()
    user.id = 2
    user.uuid = uuid.uuid4()
    user.name = "returning_user"
    user.attributes = {
        "email": "return@example.com",
        "roles": ["player"],
        "active_world": "campus_life",
        "last_world_location": "library",
    }
    user.is_active = True
    return user


@pytest.fixture
def mock_admin_node():
    """模拟管理员用户节点"""
    admin = MagicMock()
    admin.id = 99
    admin.uuid = uuid.uuid4()
    admin.name = "admin"
    admin.attributes = {
        "email": "admin@example.com",
        "roles": ["admin", "player"],
        "is_superuser": True,
    }
    admin.is_active = True
    return admin


# ---------------------------------------------------------------------------
# SSH Session Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_ssh_session():
    """
    模拟 SSH 会话
    用于 SSH 模块测试
    """
    session = MagicMock()
    session.session_id = f"session_{uuid.uuid4().hex[:8]}"
    session.username = "testuser"
    session.user_id = uuid.uuid4()
    session.user_attrs = {"roles": ["player"]}
    session.is_active = True
    session.last_activity = datetime.now()
    session.output_buffer = []
    session.command_history = []
    return session


@pytest.fixture
def mock_ssh_client():
    """模拟 Paramiko SSH 客户端"""
    transport = MagicMock()
    transport.open_session.return_value = MagicMock()
    transport.getpeername.return_value = ("127.0.0.1", 12345)

    client = MagicMock()
    client.get_transport.return_value = transport
    return client


# ---------------------------------------------------------------------------
# Model Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_room():
    """示例空间 fixture"""
    room = MagicMock()
    room.id = 1
    room.uuid = uuid.uuid4()
    room.name = "测试空间"
    room.description = "这是一个用于测试的空间"
    room.type_code = "room"
    room.attributes = {
        "exits": ["north", "south"],
        "items": [],
        "capacity": 10,
        "is_public": True,
    }
    room.is_active = True
    return room


@pytest.fixture
def sample_character():
    """示例角色 fixture"""
    character = MagicMock()
    character.id = 1
    character.uuid = uuid.uuid4()
    character.name = "TestCharacter"
    character.user_id = 1
    character.location_id = 1
    character.attributes = {
        "energy": 100,
        "hunger": 0,
        "knowledge": 0,
        "social": 0,
        "inventory": [],
    }
    character.is_active = True
    return character


@pytest.fixture
def sample_world():
    """示例世界 fixture"""
    world = MagicMock()
    world.id = 1
    world.uuid = uuid.uuid4()
    world.name = "campus_life"
    world.description = "校园生活世界"
    world.type_code = "world"
    world.attributes = {
        "is_public": True,
        "max_players": 100,
    }
    world.is_active = True
    return world


# ---------------------------------------------------------------------------
# Command Context Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_command_context():
    """模拟命令执行上下文"""
    from app.commands.base import CommandContext

    context = CommandContext(
        user_id=str(uuid.uuid4()),
        username="testuser",
        session_id="test_session",
        permissions=["player"],
        session=None,
        caller=None,
        game_state={"is_running": True},
        metadata={}
    )
    return context


# ---------------------------------------------------------------------------
# Game Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_game_handler():
    """模拟游戏处理器"""
    handler = MagicMock()
    handler.authenticate_user.return_value = (True, "user123")
    handler.spawn_user.return_value = {"location": "singularity", "success": True}
    handler.get_user_location.return_value = "singularity"
    return handler


@pytest.fixture
def mock_entry_router():
    """模拟入口路由器"""
    from app.ssh.entry_router import EntryRouter

    router = EntryRouter()
    # 默认世界可用
    router._is_world_available = lambda _name: True
    return router


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_sys_path():
    """确保测试环境路径正确"""
    yield
    # 测试后清理（如果需要）


@pytest.fixture
def freeze_time():
    """时间冻结 fixture（配合 freezegun 使用）"""
    from freezegun import freeze_time

    return freeze_time