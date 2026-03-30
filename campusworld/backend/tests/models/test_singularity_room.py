"""
奇点房间测试

测试 Singularity Room 的创建、用户 spawn 和基本功能
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestSingularityRoom:
    """奇点房间测试类"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """测试前设置"""
        self.mock_logger = MagicMock()

    @pytest.mark.integration
    def test_singularity_room_creation(self):
        """测试奇点房间创建"""
        from app.models.root_manager import root_manager

        # 初始化根节点
        success = root_manager.initialize_root_node(force_recreate=True)
        assert success is True, "奇点房间创建失败"

        # 获取根节点信息
        root_info = root_manager.get_root_node_info()
        assert root_info is not None, "无法获取根节点信息"

        # 验证根节点属性
        assert root_info["name"] == "Singularity Room"
        assert root_info["type"] == "room"
        assert root_info["is_root"] is True
        assert root_info["is_home"] is True

    @pytest.mark.integration
    def test_user_spawn(self):
        """测试用户 spawn 到奇点房间"""
        from app.models.root_manager import root_manager
        from app.models.user import User

        # 创建测试用户
        test_user = User(
            username="test_user_spawn",
            email="test@example.com",
            hashed_password="test_hash"
        )

        # 确保根节点存在
        assert root_manager.ensure_root_node_exists() is True, "根节点不存在"

        # 获取根节点
        root_node = root_manager.get_root_node()
        assert root_node is not None, "无法获取根节点"

        # 测试 spawn 到奇点房间
        success = test_user.spawn_to_singularity_room()
        assert success is True, "用户 spawn 失败"

        # 验证用户位置
        assert test_user.location_id == root_node.id
        assert test_user.home_id == root_node.id

    def test_room_functionality(self):
        """测试房间功能"""
        from app.models.room import SingularityRoom

        # 创建奇点房间实例
        singularity_room = SingularityRoom()

        # 测试房间基本属性
        assert singularity_room._node_type == "room", "节点类型错误"
        assert singularity_room._node_name == "Singularity Room", "节点名称错误"

        # 测试房间描述
        description = singularity_room.get_detailed_description()
        assert "CampusOS" in description
        assert "欢迎来到CampusOS的主入口" in description
        assert "奇点" in description

    @pytest.mark.integration
    def test_root_manager(self):
        """测试根节点管理器"""
        from app.models.root_manager import root_manager

        # 测试根节点存在性检查
        exists = root_manager.ensure_root_node_exists()
        assert exists is True, "根节点不存在"

        # 测试根节点获取
        root_node = root_manager.get_root_node()
        assert root_node is not None, "无法获取根节点"

        # 测试根节点信息
        root_info = root_manager.get_root_node_info()
        assert root_info is not None, "无法获取根节点信息"
        assert root_info["name"] == "Singularity Room"

    @pytest.mark.integration
    def test_user_location_management(self):
        """测试用户位置管理"""
        from app.models.root_manager import root_manager
        from app.models.user import User

        # 创建测试用户
        test_user = User(
            username="test_user_location",
            email="test_location@example.com",
            hashed_password="test_hash"
        )

        # 确保根节点存在
        root_manager.ensure_root_node_exists()
        root_node = root_manager.get_root_node()

        # 测试 spawn 到 home
        success = test_user.spawn_to_home()
        assert success is True, "spawn 到 home 失败"

        # 验证位置
        assert test_user.location_id == root_node.id
        assert test_user.home_id == root_node.id

        # 测试位置信息获取
        location_info = test_user.get_current_location_info()
        assert location_info is not None, "无法获取位置信息"
        assert location_info["name"] == "Singularity Room"
        assert location_info["is_root"] is True
