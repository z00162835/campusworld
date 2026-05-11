"""
认证服务 - 核心认证逻辑的共享实现

提供 Refresh Token 轮换、撤销、验证等核心功能，
被 HTTP API endpoints 和 WebSocket handler 共用。
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.core.security import create_access_token, create_refresh_token, verify_token, _get_token_expire_minutes, _get_refresh_token_expire_days

def _get_refresh_token_jti() -> str:
    """生成 refresh token 的 JTI"""
    return str(uuid.uuid4())

def _get_token_family_id() -> str:
    """生成 token family ID，同一登录会话的所有 token 共享"""
    return str(uuid.uuid4())

def _get_token_expire_seconds() -> int:
    """获取 access token 过期时间（秒）"""
    return _get_token_expire_minutes() * 60

def _get_session_idle_timeout_minutes() -> int:
    """获取 Web 会话空闲超时时间（分钟）"""
    from app.core.config_manager import get_setting
    return get_setting('security.session_idle_timeout_minutes', 30)

def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None

def _seconds_until(value: datetime) -> int:
    return max(0, int((value - datetime.utcnow()).total_seconds()))

def _idle_expires_in(last_activity_at: datetime) -> int:
    expires_at = last_activity_at + timedelta(minutes=_get_session_idle_timeout_minutes())
    return _seconds_until(expires_at)

class AuthService:
    """认证服务类，提供 token 管理核心功能"""

    @staticmethod
    def validate_refresh_token(db: Session, refresh_token: str, expected_user_id: Optional[int]=None) -> dict:
        """
        验证 refresh token 并返回 token 信息。

        Args:
            db: 数据库会话
            refresh_token: 待验证的 refresh token
            expected_user_id: 如果提供，验证 token 属于指定用户（用于 WS 绑定验证）

        Returns:
            dict: {
                "valid": bool,
                "user_id": int,
                "jti": str,
                "family_id": str,
                "error": str or None
            }
        """
        from app.models.graph import Node
        try:
            payload = verify_token(refresh_token)
        except HTTPException:
            return {'valid': False, 'user_id': None, 'jti': None, 'family_id': None, 'error': 'invalid_token'}
        if payload.get('type') != 'refresh':
            return {'valid': False, 'user_id': None, 'jti': None, 'family_id': None, 'error': 'invalid_token_type'}
        user_id_str = payload.get('sub')
        if not user_id_str or not user_id_str.isdigit():
            return {'valid': False, 'user_id': None, 'jti': None, 'family_id': None, 'error': 'invalid_subject'}
        user_id = int(user_id_str)
        if expected_user_id is not None and user_id != expected_user_id:
            return {'valid': False, 'user_id': user_id, 'jti': None, 'family_id': None, 'error': 'user_mismatch'}
        jti = payload.get('jti', user_id_str)
        family_id = payload.get('family_id')
        user_node = db.query(Node).filter(Node.type_code == 'account', Node.id == user_id).first()
        if not user_node:
            return {'valid': False, 'user_id': None, 'jti': None, 'family_id': None, 'error': 'user_not_found'}
        attrs = dict(user_node.attributes or {})
        refresh_tokens = attrs.get('refresh_tokens', {})
        token_info = refresh_tokens.get(jti, {})
        if not token_info:
            return {'valid': False, 'user_id': user_id, 'jti': jti, 'family_id': family_id, 'error': 'invalid_token'}
        if token_info.get('revoked'):
            return {'valid': False, 'user_id': user_id, 'jti': jti, 'family_id': family_id, 'error': 'token_revoked'}
        if token_info.get('replaced_by'):
            return {'valid': False, 'user_id': user_id, 'jti': jti, 'family_id': family_id, 'error': 'token_reused'}
        now = datetime.utcnow()
        expires_at = _parse_iso_datetime(token_info.get('expires_at'))
        family_expires_at = _parse_iso_datetime(token_info.get('family_expires_at')) or expires_at
        if expires_at and expires_at < now:
            return {'valid': False, 'user_id': user_id, 'jti': jti, 'family_id': family_id, 'error': 'token_expired'}
        if family_expires_at and family_expires_at < now:
            return {'valid': False, 'user_id': user_id, 'jti': jti, 'family_id': family_id, 'error': 'token_expired'}
        last_activity_at = _parse_iso_datetime(token_info.get('last_activity_at')) or _parse_iso_datetime(token_info.get('issued_at'))
        idle_timeout = timedelta(minutes=_get_session_idle_timeout_minutes())
        if last_activity_at and last_activity_at + idle_timeout < now:
            return {'valid': False, 'user_id': user_id, 'jti': jti, 'family_id': family_id, 'error': 'idle_timeout'}
        stored_family_id = token_info.get('family_id', family_id)
        return {'valid': True, 'user_id': user_id, 'jti': jti, 'family_id': stored_family_id, 'idle_expires_in': _idle_expires_in(last_activity_at or now), 'error': None}

    @staticmethod
    def issue_tokens(db: Session, user_id: int, username: str, device: str, family_id: Optional[str]=None, family_issued_at: Optional[datetime]=None, family_expires_at: Optional[datetime]=None, last_activity_at: Optional[datetime]=None) -> dict:
        """
        颁发新的 access token 和 refresh token。

        Args:
            db: 数据库会话
            user_id: 用户 ID
            username: 用户名
            device: 设备标识
            family_id: 如果提供，复用此 family_id（用于同一登录会话）

        Returns:
            dict: {access_token, refresh_token, expires_in, jti, family_id}
        """
        from app.models.graph import Node
        now = datetime.utcnow()
        session_family_issued_at = family_issued_at or now
        session_family_expires_at = family_expires_at or now + timedelta(days=_get_refresh_token_expire_days())
        session_last_activity_at = last_activity_at or now
        refresh_expires_delta = session_family_expires_at - now
        if refresh_expires_delta.total_seconds() <= 0:
            return {'error': 'token_expired'}
        jti = _get_refresh_token_jti()
        new_family_id = family_id or _get_token_family_id()
        access_token = create_access_token(subject=str(user_id), username=username, family_id=new_family_id, session_jti=jti)
        expires_in = _get_token_expire_seconds()
        refresh_token = create_refresh_token(subject=str(user_id), expires_delta=refresh_expires_delta, jti=jti, family_id=new_family_id)
        user_node = db.query(Node).filter(Node.type_code == 'account', Node.id == user_id).first()
        if user_node:
            attrs = dict(user_node.attributes or {})
            refresh_tokens = attrs.get('refresh_tokens', {})
            refresh_tokens[jti] = {'jti': jti, 'family_id': new_family_id, 'device': device, 'issued_at': now.isoformat(), 'family_issued_at': session_family_issued_at.isoformat(), 'family_expires_at': session_family_expires_at.isoformat(), 'last_activity_at': session_last_activity_at.isoformat(), 'expires_at': session_family_expires_at.isoformat(), 'revoked': False, 'replaced_by': None}
            attrs['refresh_tokens'] = refresh_tokens
            user_node.attributes = attrs
            db.commit()
        return {'access_token': access_token, 'refresh_token': refresh_token, 'expires_in': expires_in, 'jti': jti, 'family_id': new_family_id, 'refresh_expires_at': session_family_expires_at, 'refresh_max_age': _seconds_until(session_family_expires_at), 'idle_expires_in': _idle_expires_in(session_last_activity_at)}

    @staticmethod
    def rotate_refresh_token(db: Session, user_id: int, old_jti: str, old_family_id: str, device: str, expected_access_token: Optional[str]=None) -> dict:
        """
        执行 refresh token 轮换：撤销旧 token，颁发新 token。

        Args:
            db: 数据库会话
            user_id: 用户 ID
            old_jti: 旧 refresh token 的 JTI
            old_family_id: 旧 token 的 family_id
            device: 设备标识
            expected_access_token: 如果提供，验证与 refresh token 属于同一用户（WS 场景）

        Returns:
            dict: {access_token, refresh_token, expires_in} 或 {"error": ...}
        """
        from app.models.graph import Node
        if expected_access_token is not None:
            try:
                payload = verify_token(expected_access_token)
                token_user_id = payload.get('sub')
                if not token_user_id or int(token_user_id) != user_id:
                    return {'error': 'token_binding_mismatch'}
            except HTTPException:
                return {'error': 'invalid_access_token'}
        user_node = db.query(Node).filter(Node.type_code == 'account', Node.id == user_id).first()
        if not user_node:
            return {'error': 'user_not_found'}
        attrs = dict(user_node.attributes or {})
        if not attrs.get('is_active', True):
            return {'error': 'account_inactive'}
        if attrs.get('is_locked', False):
            return {'error': 'account_locked'}
        username = user_node.name
        refresh_tokens = attrs.get('refresh_tokens', {})
        old_token_info = refresh_tokens.get(old_jti, {})
        now = datetime.utcnow()
        old_expires_at = _parse_iso_datetime(old_token_info.get('expires_at'))
        family_issued_at = _parse_iso_datetime(old_token_info.get('family_issued_at')) or _parse_iso_datetime(old_token_info.get('issued_at')) or now
        family_expires_at = _parse_iso_datetime(old_token_info.get('family_expires_at')) or old_expires_at
        last_activity_at = _parse_iso_datetime(old_token_info.get('last_activity_at')) or _parse_iso_datetime(old_token_info.get('issued_at')) or now
        if family_expires_at is None:
            family_expires_at = now + timedelta(days=_get_refresh_token_expire_days())
        if family_expires_at <= now:
            return {'error': 'token_expired'}
        new_tokens = AuthService.issue_tokens(db=db, user_id=user_id, username=username, device=device, family_id=old_family_id, family_issued_at=family_issued_at, family_expires_at=family_expires_at, last_activity_at=last_activity_at)
        if 'error' in new_tokens:
            return new_tokens
        db.refresh(user_node)
        attrs = dict(user_node.attributes or {})
        refresh_tokens = attrs.get('refresh_tokens', {})
        for (existing_jti, token_data) in list(refresh_tokens.items()):
            if token_data.get('family_id') == old_family_id and existing_jti != new_tokens['jti']:
                token_data['revoked'] = True
                token_data['replaced_by'] = new_tokens['jti']
        attrs['refresh_tokens'] = refresh_tokens
        user_node.attributes = attrs
        db.commit()
        return {'access_token': new_tokens['access_token'], 'refresh_token': new_tokens['refresh_token'], 'expires_in': new_tokens['expires_in'], 'refresh_expires_at': new_tokens['refresh_expires_at'], 'refresh_max_age': new_tokens['refresh_max_age'], 'idle_expires_in': new_tokens['idle_expires_in']}

    @staticmethod
    def revoke_refresh_token(db: Session, user_id: int, jti: str) -> None:
        """
        撤销指定的 refresh token。

        Args:
            db: 数据库会话
            user_id: 用户节点 ID
            jti: 要撤销的 token 的 JTI
        """
        from app.models.graph import Node
        user_node = db.query(Node).filter(Node.type_code == 'account', Node.id == user_id).first()
        if not user_node:
            return
        attrs = dict(user_node.attributes or {})
        refresh_tokens = attrs.get('refresh_tokens', {})
        if jti in refresh_tokens:
            refresh_tokens[jti]['revoked'] = True
            attrs['refresh_tokens'] = refresh_tokens
            user_node.attributes = attrs
            db.commit()

    @staticmethod
    def revoke_all_user_tokens(db: Session, user_id: int) -> None:
        """
        撤销用户的所有 refresh tokens。

        Args:
            db: 数据库会话
            user_id: 用户节点 ID
        """
        from app.models.graph import Node
        user_node = db.query(Node).filter(Node.type_code == 'account', Node.id == user_id).first()
        if not user_node:
            return
        attrs = dict(user_node.attributes or {})
        refresh_tokens = attrs.get('refresh_tokens', {})
        for token_key in refresh_tokens:
            refresh_tokens[token_key]['revoked'] = True
        attrs['refresh_tokens'] = refresh_tokens
        user_node.attributes = attrs
        db.commit()

    @staticmethod
    def cleanup_expired_tokens(db: Session, user_id: int) -> int:
        """
        清理用户所有已过期的 refresh token 记录。

        删除条件：expires_at < now 的记录（无论 revoked 状态如何）。

        Args:
            db: 数据库会话
            user_id: 用户节点 ID

        Returns:
            int: 清理的 token 数量
        """
        from app.models.graph import Node
        user_node = db.query(Node).filter(Node.type_code == 'account', Node.id == user_id).first()
        if not user_node:
            return 0
        attrs = dict(user_node.attributes or {})
        refresh_tokens = attrs.get('refresh_tokens', {})
        now = datetime.utcnow()
        keys_to_remove = [jti for (jti, info) in refresh_tokens.items() if info.get('expires_at') and _parse_iso_datetime(info['expires_at']) and (_parse_iso_datetime(info['expires_at']) < now)]
        for key in keys_to_remove:
            del refresh_tokens[key]
        attrs['refresh_tokens'] = refresh_tokens
        user_node.attributes = attrs
        db.commit()
        return len(keys_to_remove)
