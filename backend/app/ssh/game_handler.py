"""
逻辑处理器 - Game Layer

负责处理相关的业务逻辑，与协议层解耦。
参考Evenia的Server层设计。
"""
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm.attributes import flag_modified
from app.core.database import db_session_context
from app.core.log import get_logger, LoggerNames
from app.game_engine.manager import game_engine_manager
from app.game_engine.world_room_resolve import find_world_room_node
from app.models.graph import Node
from app.models.root_manager import root_manager
from app.ssh.entry_router import EntryRouter

def teleport_account_to_root(session, user_node: Node, root_node: Node) -> None:
    """Clear world session attributes and anchor the account at the singularity (root) room."""
    attrs = dict(user_node.attributes or {})
    attrs['active_world'] = None
    attrs['world_location'] = None
    user_node.location_id = root_node.id
    user_node.home_id = root_node.id
    user_node.attributes = attrs
    flag_modified(user_node, 'attributes')

class GameHandler:
    """
    逻辑处理器

    负责：
    - 用户认证
    - 用户spawn/位置管理
    - 会话状态管理
    - 事件处理
    """

    def __init__(self):
        self.logger = get_logger(LoggerNames.GAME)
        self.audit_logger = get_logger(LoggerNames.AUDIT)
        self.security_logger = get_logger(LoggerNames.SECURITY)
        self.entry_router = EntryRouter()

    def authenticate_user(self, username: str, password: str, client_ip: str='unknown') -> Dict[str, Any]:
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
                user_node = session.query(Node).filter(Node.type_code == 'account', Node.name == username).first()
                if not user_node:
                    self.security_logger.warning(f'User does not exist', extra={'username': username, 'client_ip': client_ip, 'event_type': 'auth_failed_user_not_found'})
                    return {'success': False, 'error': '用户不存在'}
                attrs = user_node.attributes
                if not attrs.get('is_active', True):
                    self.security_logger.warning(f'Account disabled', extra={'username': username, 'client_ip': client_ip, 'event_type': 'auth_failed_account_inactive'})
                    return {'success': False, 'error': '账号已被禁用'}
                if attrs.get('is_locked', False):
                    self.security_logger.warning(f'Account locked', extra={'username': username, 'client_ip': client_ip, 'event_type': 'auth_failed_account_locked', 'lock_reason': attrs.get('lock_reason', 'unknown')})
                    return {'success': False, 'error': '账号已被锁定'}
                if attrs.get('is_suspended', False):
                    suspension_until = attrs.get('suspension_until')
                    if suspension_until and datetime.fromisoformat(suspension_until) > datetime.now():
                        self.security_logger.warning(f'Account suspended', extra={'username': username, 'client_ip': client_ip, 'event_type': 'auth_failed_account_suspended', 'suspension_until': suspension_until})
                        return {'success': False, 'error': f'账号已暂停，暂停至 {suspension_until}'}
                stored_hash = attrs.get('hashed_password', '')
                if not stored_hash:
                    self.security_logger.warning(f'User has no password hash', extra={'username': username, 'client_ip': client_ip, 'event_type': 'auth_failed_no_password_hash'})
                    return {'success': False, 'error': '用户密码未设置'}
                if verify_password(password, stored_hash):
                    session_id = f'{username}_{int(time.time())}'
                    attrs['last_login'] = datetime.now().isoformat()
                    if not str(attrs.get('access_level') or '').strip():
                        attrs['access_level'] = str(user_node.access_level or 'normal')
                    user_node.attributes = attrs
                    session.commit()
                    auth_duration = time.time() - start_time
                    self.security_logger.info(f'Authentication succeeded', extra={'username': username, 'client_ip': client_ip, 'session_id': session_id, 'auth_duration': auth_duration, 'event_type': 'auth_success'})
                    return {'success': True, 'session_id': session_id, 'user_id': user_node.id, 'username': username, 'user_attrs': attrs}
                else:
                    failed_attempts = attrs.get('failed_login_attempts', 0) + 1
                    attrs['failed_login_attempts'] = failed_attempts
                    max_attempts = attrs.get('max_failed_attempts', 5)
                    if failed_attempts >= max_attempts:
                        attrs['is_locked'] = True
                        attrs['lock_reason'] = 'Too many failed login attempts'
                        attrs['locked_at'] = datetime.now().isoformat()
                        self.security_logger.warning(f'Account locked after repeated failed logins', extra={'username': username, 'client_ip': client_ip, 'failed_attempts': failed_attempts, 'max_attempts': max_attempts, 'event_type': 'account_locked'})
                    user_node.attributes = attrs
                    session.commit()
                    self.security_logger.warning(f'Authentication failed - wrong password', extra={'username': username, 'client_ip': client_ip, 'failed_attempts': failed_attempts, 'event_type': 'auth_failed_wrong_password'})
                    return {'success': False, 'error': '密码错误'}
        except Exception as e:
            self.security_logger.error(f'Error during authentication: {e}')
            return {'success': False, 'error': f'认证失败: {str(e)}'}

    def spawn_user(self, user_id, username: str='Unknown') -> bool:
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
                if not root_manager.ensure_root_node_exists():
                    self.security_logger.warning(f'Unable to ensure root node exists for user {username} spawn failed')
                    return False
                root_node = root_manager.get_root_node(session)
                if not root_node:
                    self.security_logger.warning(f'Unable to get root node for user {username} spawn failed')
                    return False
                user_node = session.query(Node).filter(Node.id == user_id).first()
                if not user_node:
                    self.security_logger.warning(f'User node does not exist: {user_id}')
                    return False
                route = self.entry_router.resolve_post_auth_destination(user_node)
                fallback_used = False
                if route.target_kind == 'world' and route.world_name:
                    (entered, _) = self._enter_world_in_session(session=session, user_node=user_node, username=username, world_name=route.world_name, spawn_key=route.world_spawn_key or 'campus', root_node_id=root_node.id)
                    if not entered:
                        fallback_used = True
                        teleport_account_to_root(session, user_node, root_node)
                        attrs = dict(user_node.attributes or {})
                        attrs['entry_fallback_reason'] = 'enter_world_failed'
                        user_node.attributes = attrs
                        flag_modified(user_node, 'attributes')
                else:
                    user_node.location_id = root_node.id
                    user_node.home_id = root_node.id
                attrs = dict(user_node.attributes or {})
                attrs['last_activity'] = datetime.now().isoformat()
                attrs['last_entry_route'] = route.target_kind
                attrs['last_entry_reason'] = route.reason
                user_node.attributes = attrs
                flag_modified(user_node, 'attributes')
                session.commit()
                self.logger.info(f'User {username} login entry routing complete', extra={'username': username, 'route_target': route.target_kind, 'route_reason': route.reason, 'world_name': route.world_name, 'fallback_used': fallback_used, 'event_type': 'user_post_auth_routed'})
                return True
        except Exception as e:
            self.security_logger.error(f'User spawn failed: {e}', extra={'username': username, 'user_id': user_id, 'error': str(e), 'event_type': 'user_spawn_error'})
            return False

    def enter_world(self, user_id, username: str, world_name: str, spawn_key: str='campus') -> Dict[str, Any]:
        """由命令层调用：从奇点屋进入指定世界。"""
        try:
            with db_session_context() as session:
                user_node = session.query(Node).filter(Node.id == user_id).first()
                if not user_node:
                    return {'success': False, 'message': '用户不存在'}
                if not root_manager.ensure_root_node_exists():
                    return {'success': False, 'message': '系统入口不可用'}
                root_node = root_manager.get_root_node(session)
                if not root_node:
                    return {'success': False, 'message': '系统入口不可用'}
                if user_node.location_id != root_node.id:
                    return {'success': False, 'message': '请先回到奇点屋再进入世界'}
                (success, message) = self._enter_world_in_session(session=session, user_node=user_node, username=username, world_name=world_name, spawn_key=spawn_key, root_node_id=root_node.id)
                if not success:
                    return {'success': False, 'message': message}
                attrs = dict(user_node.attributes or {})
                attrs['last_activity'] = datetime.now().isoformat()
                user_node.attributes = attrs
                flag_modified(user_node, 'attributes')
                session.commit()
                return {'success': True, 'message': message}
        except Exception as e:
            self.logger.error(f'Failed to enter world: {e}')
            return {'success': False, 'message': f'进入世界失败: {e}'}

    def leave_world(self, user_id, username: str='Unknown') -> Dict[str, Any]:
        """Leave the current world and return the account to the singularity room."""
        try:
            with db_session_context() as session:
                user_node = session.query(Node).filter(Node.id == user_id).first()
                if not user_node:
                    return {'success': False, 'message': '用户不存在'}
                if not root_manager.ensure_root_node_exists():
                    return {'success': False, 'message': '系统入口不可用'}
                root_node = root_manager.get_root_node(session)
                if not root_node:
                    return {'success': False, 'message': '系统入口不可用'}
                if user_node.location_id == root_node.id:
                    return {'success': False, 'message': '你当前已在奇点屋'}
                teleport_account_to_root(session, user_node, root_node)
                attrs = dict(user_node.attributes or {})
                attrs['last_activity'] = datetime.now().isoformat()
                user_node.attributes = attrs
                flag_modified(user_node, 'attributes')
                session.commit()
                return {'success': True, 'message': '已离开世界，回到奇点屋'}
        except Exception as e:
            self.logger.error(f'Failed to leave world: {e}')
            return {'success': False, 'message': f'离开世界失败: {e}'}

    def _enter_world_in_session(self, session, user_node: Node, username: str, world_name: str, spawn_key: str, root_node_id: int):
        """在当前数据库会话内执行世界进入和状态写回。"""
        engine = game_engine_manager.get_engine()
        if not engine:
            return (False, '引擎未启动')
        game = engine.get_game(world_name)
        if not game:
            load_out = game_engine_manager.load_game(world_name)
            if load_out.get('ok'):
                game = engine.get_game(world_name)
            else:
                err_msg = str(load_out.get('message') or 'load failed')
                err_code = str(load_out.get('error_code') or '')
                if err_code == 'WORLD_STATE_CONFLICT' or 'already loaded' in err_msg.lower():
                    game = engine.get_game(world_name)
                else:
                    return (False, f'世界未加载: {world_name}。{err_msg} （进程内未加载世界包；请确认已 world install，且 game_engine.load_installed_worlds_on_start=true，或先执行: world load {world_name}）')
        if not game:
            return (False, f'世界未加载: {world_name}（load 后仍未注册到引擎，请查看日志或执行 world load {world_name}）')
        spawn_room = find_world_room_node(session, world_name, spawn_key)
        if not spawn_room:
            return (False, f'出生点房间不在图中: {world_name}/{spawn_key}（请确认已 world install 且 graph_seed 已写入）')
        attrs = dict(user_node.attributes or {})
        player_payload = {'username': username, 'world_name': world_name}
        if hasattr(game, 'add_player'):
            ok = game.add_player(str(user_node.id), player_payload, initial_location=spawn_key)
            if not ok:
                return (False, f'无法进入世界: {world_name}')
        attrs['active_world'] = world_name
        attrs['world_location'] = spawn_key
        attrs['last_world_location'] = spawn_key
        user_node.attributes = attrs
        flag_modified(user_node, 'attributes')
        user_node.location_id = spawn_room.id
        user_node.home_id = root_node_id
        return (True, f'已进入世界 {world_name}（出生点: {spawn_key}）')

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
                location_node = session.query(Node).filter(Node.id == user_node.location_id).first()
                if not location_node:
                    return None
                return {'id': location_node.id, 'name': location_node.name, 'description': location_node.attributes.get('description', ''), 'type_code': location_node.type_code}
        except Exception as e:
            self.logger.error(f'Failed to get user location: {e}')
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
                    attrs = dict(user_node.attributes or {})
                    attrs['last_activity'] = datetime.now().isoformat()
                    user_node.attributes = attrs
                    flag_modified(user_node, 'attributes')
                    session.commit()
                    return True
                return False
        except Exception as e:
            self.logger.error(f'Failed to update user activity time: {e}')
            return False
game_handler = GameHandler()
