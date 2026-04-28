"""
API 依赖注入
提供 FastAPI 依赖项，包括认证和用户上下文解析
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from app.core.security import verify_token, verify_api_key, resolve_api_key_principal, ALGORITHM
from app.core.database import db_session_context
from app.models.graph import Node


# HTTP Bearer 认证方案
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedUser:
    """认证用户上下文"""
    user_id: str
    username: str
    email: str
    roles: List[str]
    permissions: List[str]
    user_attrs: Dict[str, Any]


@dataclass
class APIPrincipal:
    """统一身份主体（JWT 或 API Key）。"""

    subject: str
    auth_type: str
    roles: List[str]
    permissions: List[str]
    user_attrs: Dict[str, Any]
    scopes: List[str]
    api_key_kid: Optional[str] = None

    def has_permission(self, permission_code: str) -> bool:
        if self.auth_type == "api_key" and self.scopes:
            return permission_code in self.scopes or "*" in self.scopes
        if "admin" in self.roles:
            return True
        return permission_code in self.permissions


def _get_secret_key() -> str:
    """获取 JWT 密钥"""
    from app.core.config_manager import get_setting
    return get_setting('security.secret_key', 'your-secret-key-here')


async def get_current_http_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthenticatedUser:
    """
    FastAPI 依赖：从 HTTP Authorization Header 提取并验证 JWT，
    查询数据库获取用户完整信息（roles、permissions）。

    失败时抛出 401未授权异常。

    用法:
        @router.post("/execute")
        async def execute_command(
            current_user: AuthenticatedUser = Depends(get_current_http_user),
            ...
        )
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # 1. 验证 JWT 令牌
    try:
        from app.core.security import _get_secret_key
        from jose import jwt
        payload = jwt.decode(token, _get_secret_key(), algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. 从 token payload 提取用户标识
    #兼容两种格式：email (旧) 或 user_id (新)
    email = payload.get("sub") or payload.get("user_id")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. 查询数据库获取用户属性
    with db_session_context() as db_session:
        # 支持通过 email 或 user_id 查找
        user_node = db_session.query(Node).filter(
            Node.type_code == "account",
            (Node.attributes["email"].astext == email) | (Node.id == int(email) if email.isdigit() else False)
        ).first()

        if not user_node:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        attrs = dict(user_node.attributes or {})

        # 检查账号状态
        if not attrs.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive",
            )

        if attrs.get("is_locked", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is locked",
            )

        # 4. 提取 roles 和 permissions
        roles = list(attrs.get("roles", []))
        permissions = list(attrs.get("permissions", []))

        return AuthenticatedUser(
            user_id=str(user_node.id),
            username=user_node.name,
            email=attrs.get("email", email),
            roles=roles,
            permissions=permissions,
            user_attrs=attrs,
        )


async def get_optional_http_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[AuthenticatedUser]:
    """
    可选的认证用户依赖 - 如果没有 token 返回 None 而不是抛出异常。
    用于公开端点仍需识别已登录用户的场景。
    """
    if credentials is None:
        return None

    try:
        return await get_current_http_user(credentials)
    except HTTPException:
        return None


async def get_api_principal(
    optional_user: Optional[AuthenticatedUser] = Depends(get_optional_http_user),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> APIPrincipal:
    """
    HTTP API 统一鉴权主体（图读等端点复用）。

    支持二选一：
    - Bearer JWT（复用 HTTP 用户上下文）
    - X-API-Key（当前为占位实现，可由配置静态 Key 放行）
    """
    if optional_user and x_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use either Bearer token or X-API-Key, not both.",
        )

    if optional_user:
        return APIPrincipal(
            subject=optional_user.user_id,
            auth_type="jwt",
            roles=optional_user.roles,
            permissions=optional_user.permissions,
            user_attrs=optional_user.user_attrs,
            scopes=[],
            api_key_kid=None,
        )

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials. Provide Bearer token or X-API-Key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    key_principal = resolve_api_key_principal(x_api_key)
    if key_principal:
        verified_user_id = key_principal["user_id"]
        key_scopes = list(key_principal.get("scopes", []))
        with db_session_context() as db_session:
            user_node = db_session.query(Node).filter(
                Node.id == int(verified_user_id),
                Node.type_code == "account",
            ).first()
            attrs = dict(user_node.attributes or {}) if user_node else {}
            base_permissions = list(attrs.get("permissions", []))
            if key_scopes:
                effective_permissions = sorted(set(base_permissions).intersection(set(key_scopes)))
            else:
                effective_permissions = base_permissions
        return APIPrincipal(
            subject=verified_user_id,
            auth_type="api_key",
            roles=list(attrs.get("roles", [])),
            permissions=effective_permissions,
            user_attrs=attrs,
            scopes=key_scopes,
            api_key_kid=key_principal.get("kid"),
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key.",
    )


def require_api_permission(permission_code: str):
    """返回可注入依赖：校验 APIPrincipal 权限。"""

    async def _dependency(principal: APIPrincipal = Depends(get_api_principal)) -> APIPrincipal:
        if not principal.has_permission(permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission_code}",
            )
        return principal

    return _dependency
