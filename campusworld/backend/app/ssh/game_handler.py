"""
游戏逻辑处理器 - Game Layer

负责处理游戏相关的业务逻辑，与协议层解耦。
参考Evenia的Server层设计。
"""

import time
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.core.database import db_session_context
from app.core.log import get_logger, LoggerNames
from app.models.graph import Node
from app.models.root_manager import root_manager
from app.models.user import User


class GameHandler:
    """
    游戏逻辑处理器

    负责：
    - 用户认证
    - 用户spawn/位置管理
    - 会话状态管理
    - 游戏事件处理
    """

    def __init__(self):
        self.logger = get_logger(LoggerNames.GAME)
        self.audit_logger = get_logger(LoggerNames.AUDIT)
        self.security_logger = get_logger(LoggerNames.SECURITY)

    def authenticate_user(self, username: str, password: str,
                         client_ip: str = 'unknown') -> Dict[str, Any]:
        """
        验证用户凭证

        Args:
            username: 用户名
            password: 密码
            client_ip: 客户端IP

        Returns:
            认证结果字典:
            {
                'success': bool,
                'session_id': str,
                'user_id': UUID,
                'username': str,
                'user_attrs': dict,
                'error': str (可选)
            }
        """
        from app.core.security import verify_password

        start_time = time.time()
        try:
            with db_session_context() as session:
                # 查找用户账号
                user_node = session.query(Node).filter(
                    Node.type_code == "account",
                    Node.name == username
                ).first()

                if not user_node:
                    self.security_logger.warning(f"用户不存在", extra={
                        'username': username,
                        'client_ip': client_ip,
                        'event_type': 'auth_failed_user_not_found'
                    })
                    return {
                        'success': False,
                        'error': '用户不存在'
                    }

                # 检查账号状态
                attrs = user_node.attributes
                if not attrs.get("is_active", True):
                    self.security_logger.warning(f"账号已禁用", extra={
                        'username': username,
                        'client_ip': client_ip,
                        'event_type': 'auth_failed_account_inactive'
                    })
                    return {
                        'success': False,
                        'error': '账号已被禁用'
                    }

                if attrs.get("is_locked", False):
                    self.security_logger.warning(f"账号已锁定", extra={
                        'username': username,
                        'client_ip': client_ip,
                        'event_type': 'auth_failed_account_locked',
                        'lock_reason': attrs.get("lock_reason", "unknown")
                    })
                    return {
                        'success': False,
                        'error': '账号已被锁定'
                    }

                if attrs.get("is_suspended", False):
                    suspension_until = attrs.get("suspension_until")
                    if suspension_until and datetime.fromisoformat(suspension_until) > datetime.now():
                        self.security_logger.warning(f"账号已暂停", extra={
                            'username': username,
                            'client_ip': client_ip,
                            'event_type': 'auth_failed_account_suspended',
                            'suspension_until': suspension_until
                        })
                        return {
                            'success': False,
                            'error': f'账号已暂停，暂停至 {suspension_until}'
                        }

                # 验证密码
                stored_hash = attrs.get("hashed_password", "")
                if not stored_hash:
                    self.security_logger.warning(f"用户无密码哈希", extra={
                        'username': username,
                        'client_ip': client_ip,
                        'event_type': 'auth_failed_no_password_hash'
                    })
                    return {
                        'success': False,
                        'error': '用户密码未设置'
                    }

                if verify_password(password, stored_hash):
                    # 生成会话ID
                    session_id = f"{username}_{int(time.time())}"

                    # 更新最后登录时间
                    attrs["last_login"] = datetime.now().isoformat()
                    user_node.attributes = attrs
                    session.commit()

                    # 认证成功日志
                    auth_duration = time.time() - start_time
                    self.security_logger.info(f"认证成功", extra={
                        'username': username,
                        'client_ip': client_ip,
                        'session_id': session_id,
                        'auth_duration': auth_duration,
                        'event_type': 'auth_success'
                    })

                    return {
                        'success': True,
                        'session_id': session_id,
                        'user_id': user_node.id,
                        'username': username,
                        'user_attrs': attrs
                    }
                else:
                    # 处理失败登录
                    failed_attempts = attrs.get("failed_login_attempts", 0) + 1
                    attrs["failed_login_attempts"] = failed_attempts

                    # 检查是否需要锁定账号
                    max_attempts = attrs.get("max_failed_attempts", 5)
                    if failed_attempts >= max_attempts:
                        attrs["is_locked"] = True
                        attrs["lock_reason"] = "Too many failed login attempts"
                        attrs["locked_at"] = datetime.now().isoformat()

                        self.security_logger.warning(f"账号因多次失败登录被锁定", extra={
                            'username': username,
                            'client_ip': client_ip,
                            'failed_attempts': failed_attempts,
                            'max_attempts': max_attempts,
                            'event_type': 'account_locked'
                        })

                    user_node.attributes = attrs
                    session.commit()

                    self.security_logger.warning(f"认证失败 - 密码错误", extra={
                        'username': username,
                        'client_ip': client_ip,
                        'failed_attempts': failed_attempts,
                        'event_type': 'auth_failed_wrong_password'
                    })

                    return {
                        'success': False,
                        'error': '密码错误'
                    }

        except Exception as e:
            self.security_logger.error(f"认证过程出错: {e}")
            return {
                'success': False,
                'error': f'认证失败: {str(e)}'
            }

    def spawn_user(self, user_id, username: str = 'Unknown') -> bool:
        """
        将用户spawn到初始位置

        参考Evenia的DefaultHome设计，确保用户登录后出现在正确的位置。

        Args:
            user_id: 用户ID
            username: 用户名（用于日志）

        Returns:
            是否成功
        """
        try:
            with db_session_context() as session:
                # 确保根节点存在
                if not root_manager.ensure_root_node_exists():
                    self.security_logger.warning(
                        f"无法确保根节点存在，用户 {username} spawn失败"
                    )
                    return False

                # 获取根节点
                root_node = root_manager.get_root_node(session)
                if not root_node:
                    self.security_logger.warning(
                        f"无法获取根节点，用户 {username} spawn失败"
                    )
                    return False

                # 获取用户节点
                user_node = session.query(Node).filter(Node.id == user_id).first()
                if not user_node:
                    self.security_logger.warning(f"用户节点不存在: {user_id}")
                    return False

                # 设置用户位置到根节点
                user_node.location_id = root_node.id
                user_node.home_id = root_node.id

                # 更新最后活动时间
                attrs = user_node.attributes
                attrs["last_activity"] = datetime.now().isoformat()
                user_node.attributes = attrs

                # 提交更改
                session.commit()

                self.logger.info(f"用户 {username} 已spawn到根节点")
                return True

        except Exception as e:
            self.security_logger.error(f"用户spawn失败: {e}", extra={
                'username': username,
                'user_id': user_id,
                'error': str(e),
                'event_type': 'user_spawn_error'
            })
            return False

    def get_user_location(self, user_id) -> Optional[Dict[str, Any]]:
        """
        获取用户当前位置信息

        Args:
            user_id: 用户ID

        Returns:
            位置信息字典或None
        """
        try:
            with db_session_context() as session:
                user_node = session.query(Node).filter(Node.id == user_id).first()
                if not user_node or not user_node.location_id:
                    return None

                location_node = session.query(Node).filter(
                    Node.id == user_node.location_id
                ).first()

                if not location_node:
                    return None

                return {
                    'id': location_node.id,
                    'name': location_node.name,
                    'description': location_node.attributes.get('description', ''),
                    'type_code': location_node.type_code
                }
        except Exception as e:
            self.logger.error(f"获取用户位置失败: {e}")
            return None

    def update_user_activity(self, user_id: str) -> bool:
        """
        更新用户最后活动时间

        Args:
            user_id: 用户ID

        Returns:
            是否成功
        """
        try:
            with db_session_context() as session:
                user_node = session.query(Node).filter(Node.id == user_id).first()
                if user_node:
                    attrs = user_node.attributes
                    attrs["last_activity"] = datetime.now().isoformat()
                    user_node.attributes = attrs
                    session.commit()
                    return True
                return False
        except Exception as e:
            self.logger.error(f"更新用户活动时间失败: {e}")
            return False


# 全局游戏处理器实例
game_handler = GameHandler()
