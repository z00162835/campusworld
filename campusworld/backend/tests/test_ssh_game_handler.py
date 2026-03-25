"""
SSH模块测试 - GameHandler

测试游戏逻辑处理器的功能
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import uuid

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestGameHandler:
    """测试GameHandler类"""

    def setup_method(self):
        """每个测试方法前的设置"""
        # 导入需要测试的模块
        from app.ssh.game_handler import GameHandler
        self.handler = GameHandler()

    def test_handler_initialization(self):
        """测试Handler初始化"""
        assert self.handler is not None
        assert self.handler.logger is not None
        assert self.handler.audit_logger is not None
        assert self.handler.security_logger is not None

    @patch('app.ssh.game_handler.SessionLocal')
    def test_authenticate_user_not_found(self, mock_session_local):
        """测试用户不存在的情况"""
        # 设置mock
        mock_session = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_session

        # 查询返回None
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = self.handler.authenticate_user(
            username="nonexistent",
            password="password",
            client_ip="127.0.0.1"
        )

        assert result['success'] is False
        assert '用户不存在' in result['error']

    @patch('app.ssh.game_handler.SessionLocal')
    @patch('app.ssh.game_handler.verify_password')
    def test_authenticate_user_success(self, mock_verify, mock_session_local):
        """测试用户认证成功"""
        # 设置mock
        mock_session = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_session

        # 创建模拟用户节点
        mock_user_node = MagicMock()
        mock_user_node.id = uuid.uuid4()
        mock_user_node.attributes = {
            'is_active': True,
            'is_locked': False,
            'hashed_password': 'hashed_password',
            'last_login': None
        }

        mock_session.query.return_value.filter.return_value.first.return_value = mock_user_node

        # 密码验证成功
        mock_verify.return_value = True

        result = self.handler.authenticate_user(
            username="testuser",
            password="correct_password",
            client_ip="127.0.0.1"
        )

        assert result['success'] is True
        assert result['username'] == "testuser"
        assert 'session_id' in result
        assert 'user_id' in result

    @patch('app.ssh.game_handler.SessionLocal')
    @patch('app.ssh.game_handler.verify_password')
    def test_authenticate_user_wrong_password(self, mock_verify, mock_session_local):
        """测试密码错误的情况"""
        # 设置mock
        mock_session = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_session

        # 创建模拟用户节点
        mock_user_node = MagicMock()
        mock_user_node.attributes = {
            'is_active': True,
            'is_locked': False,
            'hashed_password': 'hashed_password',
            'failed_login_attempts': 0
        }

        mock_session.query.return_value.filter.return_value.first.return_value = mock_user_node

        # 密码验证失败
        mock_verify.return_value = False

        result = self.handler.authenticate_user(
            username="testuser",
            password="wrong_password",
            client_ip="127.0.0.1"
        )

        assert result['success'] is False
        assert '密码错误' in result['error']

    @patch('app.ssh.game_handler.SessionLocal')
    def test_authenticate_user_inactive(self, mock_session_local):
        """测试账号被禁用的情況"""
        # 设置mock
        mock_session = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_session

        # 创建模拟用户节点（账号被禁用）
        mock_user_node = MagicMock()
        mock_user_node.attributes = {
            'is_active': False
        }

        mock_session.query.return_value.filter.return_value.first.return_value = mock_user_node

        result = self.handler.authenticate_user(
            username="inactive_user",
            password="password",
            client_ip="127.0.0.1"
        )

        assert result['success'] is False
        assert '已被禁用' in result['error']

    @patch('app.ssh.game_handler.SessionLocal')
    def test_authenticate_user_locked(self, mock_session_local):
        """测试账号被锁定的情況"""
        # 设置mock
        mock_session = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_session

        # 创建模拟用户节点（账号被锁定）
        mock_user_node = MagicMock()
        mock_user_node.attributes = {
            'is_active': True,
            'is_locked': True,
            'lock_reason': 'Too many failed attempts'
        }

        mock_session.query.return_value.filter.return_value.first.return_value = mock_user_node

        result = self.handler.authenticate_user(
            username="locked_user",
            password="password",
            client_ip="127.0.0.1"
        )

        assert result['success'] is False
        assert '已被锁定' in result['error']

    @patch('app.ssh.game_handler.SessionLocal')
    def test_authenticate_user_suspended(self, mock_session_local):
        """测试账号被暂停的情況"""
        # 设置mock
        mock_session = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_session

        future_date = (datetime.now() + datetime.timedelta(days=1)).isoformat()

        # 创建模拟用户节点（账号被暂停）
        mock_user_node = MagicMock()
        mock_user_node.attributes = {
            'is_active': True,
            'is_locked': False,
            'is_suspended': True,
            'suspension_until': future_date
        }

        mock_session.query.return_value.filter.return_value.first.return_value = mock_user_node

        result = self.handler.authenticate_user(
            username="suspended_user",
            password="password",
            client_ip="127.0.0.1"
        )

        assert result['success'] is False
        assert '已暂停' in result['error']

    @patch('app.ssh.game_handler.root_manager')
    @patch('app.ssh.game_handler.SessionLocal')
    def test_spawn_user_success(self, mock_session_local, mock_root_manager):
        """测试用户spawn成功"""
        # 设置mock
        mock_session = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_session

        # Mock root_manager
        mock_root_manager.ensure_root_node_exists.return_value = True
        mock_root_node = MagicMock()
        mock_root_node.id = uuid.uuid4()
        mock_root_manager.get_root_node.return_value = mock_root_node

        # 创建模拟用户节点
        mock_user_node = MagicMock()
        mock_user_node.id = uuid.uuid4()
        mock_user_node.attributes = {}

        mock_session.query.return_value.filter.return_value.first.return_value = mock_user_node

        user_id = mock_user_node.id
        result = self.handler.spawn_user(user_id, "testuser")

        assert result is True

    @patch('app.ssh.game_handler.root_manager')
    @patch('app.ssh.game_handler.SessionLocal')
    def test_spawn_user_root_not_exists(self, mock_session_local, mock_root_manager):
        """测试根节点不存在时spawn失败"""
        # 设置mock
        mock_session = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_session

        # Mock root_manager返回False
        mock_root_manager.ensure_root_node_exists.return_value = False

        user_id = uuid.uuid4()
        result = self.handler.spawn_user(user_id, "testuser")

        assert result is False


class TestGameHandlerIntegration:
    """集成测试 - 测试GameHandler与数据库的交互"""

    @patch('app.ssh.game_handler.verify_password')
    def test_authenticate_flow(self, mock_verify):
        """测试完整的认证流程"""
        from app.ssh.game_handler import GameHandler

        handler = GameHandler()

        with patch('app.ssh.game_handler.SessionLocal') as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value.__enter__.return_value = mock_session

            # 创建模拟用户
            mock_user_node = MagicMock()
            mock_user_node.id = uuid.uuid4()
            mock_user_node.attributes = {
                'is_active': True,
                'is_locked': False,
                'hashed_password': 'hashed_pwd',
                'failed_login_attempts': 0
            }

            mock_session.query.return_value.filter.return_value.first.return_value = mock_user_node
            mock_verify.return_value = True

            result = handler.authenticate_user(
                username="testuser",
                password="password",
                client_ip="127.0.0.1"
            )

            # 验证
            assert result['success'] is True
            assert result['username'] == "testuser"
            mock_session.commit.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
