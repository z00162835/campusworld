"""
Authentication endpoints
包含注册、登录、刷新令牌、登出等功能
"""

from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Header
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.database import get_db
from app.core.config_manager import get_setting
from app.core.security import (
    create_access_token,
    get_password_hash,
    _get_token_expire_minutes,
    build_api_key_record,
)
from app.core.auth_service import AuthService
from app.models.user import User
from app.models.graph import Node, NodeType
from app.models.system import ApiKey
from app.schemas.auth import Token, UserCreate
from app.schemas.account import RefreshTokenRequest, RefreshTokenResponse
from app.ssh.game_handler import game_handler
from app.api.v1.dependencies import get_current_http_user, AuthenticatedUser

router = APIRouter()

# Rate limiter for auth endpoints - use client IP as key
limiter = Limiter(key_func=get_remote_address)

# Login rate limiting constants
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


def _is_secure_cookie() -> bool:
    """Determine if cookies should have Secure flag.

    In production, Secure should be True (requires HTTPS).
    In development, False allows HTTP for local testing.
    """
    from app.core.config_manager import get_setting
    debug = get_setting('app.debug', False)
    return not debug


class ApiKeyIssueRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    scopes: List[str] = Field(default_factory=list)
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365)


def _get_token_expire_seconds() -> int:
    """获取 access token 过期时间（秒）"""
    return _get_token_expire_minutes() * 60


def _get_api_key_ttl_days() -> int:
    return int(get_setting("security.api_key_ttl_days", 90))


@router.post("/register", response_model=Token)
@limiter.limit("5/minute")  # Rate limit: 5 registrations per minute per IP
def register(
    request: Request,
    user_data: UserCreate,
    db: Session = Depends(get_db),
    user_agent: Optional[str] = Header(None),
):
    """Register a new user (SQL legacy table; graph account required for CLI/WS)."""
    from app.core.auth_service import AuthService

    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    hashed_password = get_password_hash(user_data.password)
    # 禁止构造时写图；图账号行由下方单次 Node 写入（与 accounts API 单写语义一致）
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        disable_auto_sync=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    account_node = db.query(Node).filter(
        Node.type_code == "account",
        Node.name == user_data.username,
    ).first()

    if not account_node:
        account_type = db.query(NodeType).filter(NodeType.type_code == "account").first()
        if account_type:
            account_node = Node(
                uuid=user.get_node_uuid(),
                type_id=account_type.id,
                type_code="account",
                name=user_data.username,
                description=f"用户账号: {user_data.username}",
                is_active=True,
                is_public=False,
                access_level=user.get_node_access_level(),
                attributes=user._node_attributes,
                tags=user._node_tags,
            )
            db.add(account_node)
            db.commit()
            db.refresh(account_node)

    device = user_agent or "unknown"

    if account_node:
        # 清理过期 token
        AuthService.cleanup_expired_tokens(db, account_node.id)

        tokens = AuthService.issue_tokens(
            db=db,
            user_id=account_node.id,
            username=account_node.name,
            device=device,
        )
    else:
        access_token = create_access_token(subject=user.email)
        tokens = {
            "access_token": access_token,
            "refresh_token": "",
            "expires_in": _get_token_expire_seconds(),
        }

    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "token_type": "bearer",
        "expires_in": tokens["expires_in"],
    }


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")  # Rate limit: 10 login attempts per minute per IP
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    user_agent: Optional[str] = Header(None),
):
    """
    Login with the same graph account credentials as SSH (`Node.name` / account name).
    OAuth2 `username` field carries the campus account name, not necessarily an email.
    """
    from app.core.auth_service import AuthService

    client_ip = request.client.host if request.client else "unknown"
    device = user_agent or f"ip:{client_ip}"

    # Find account for login attempt tracking
    account = db.query(Node).filter(
        Node.type_code == "account",
        Node.name == form_data.username
    ).first()

    if account:
        # Check if account is locked
        is_locked = account.attributes.get("is_locked", False)
        if is_locked:
            locked_at = account.attributes.get("locked_at")
            locked_reason = account.attributes.get("lock_reason", "Account is locked")
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=locked_reason,
                headers={"WWW-Authenticate": "Bearer"},
            )

    result = game_handler.authenticate_user(
        username=form_data.username,
        password=form_data.password,
        client_ip=client_ip,
    )
    if not result.get("success"):
        # Track failed login attempts
        if account:
            failed_attempts = account.attributes.get("failed_login_attempts", 0) + 1
            account.attributes["failed_login_attempts"] = failed_attempts

            if failed_attempts >= MAX_LOGIN_ATTEMPTS:
                account.attributes["is_locked"] = True
                account.attributes["lock_reason"] = "Too many failed login attempts"
                account.attributes["locked_at"] = datetime.now().isoformat()
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Account locked due to too many failed login attempts",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = result["user_id"]
    username = result["username"]

    # Reset failed login attempts on successful login
    if account:
        account.attributes["failed_login_attempts"] = 0
        account.attributes.pop("is_locked", None)
        account.attributes.pop("lock_reason", None)
        account.attributes.pop("locked_at", None)

    # 清理过期 token
    AuthService.cleanup_expired_tokens(db, user_id)

    tokens = AuthService.issue_tokens(
        db=db,
        user_id=user_id,
        username=username,
        device=device,
    )

    # Set httpOnly cookie for web frontend (access token only)
    access_token = tokens["access_token"]
    cookie_max_age = tokens["expires_in"]

    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=cookie_max_age,
        httponly=True,
        samesite="lax",  # lax allows cookie on cross-origin top-level nav (works with frontend on different port)
        secure=_is_secure_cookie(),
    )

    # Also set refresh token cookie for seamless renewal
    if tokens.get("refresh_token"):
        refresh_max_age = 30 * 24 * 60 * 60  # 30 days
        response.set_cookie(
            key="refresh_token",
            value=tokens["refresh_token"],
            max_age=refresh_max_age,
            httponly=True,
            samesite="lax",
            secure=_is_secure_cookie(),
        )

    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": tokens.get("refresh_token", ""),
        "token_type": "bearer",
        "expires_in": tokens["expires_in"],
    }


@router.post("/refresh", response_model=RefreshTokenResponse)
def refresh_token(
    request: Request,
    response: Response,
    refresh_token: Optional[str] = None,
    db: Session = Depends(get_db),
    user_agent: Optional[str] = Header(None),
):
    """
    使用 refresh token 换取新的 access token 和 refresh token（带轮换）。

    - 验证 refresh token 签名和过期时间
    - 检查 token 是否已撤销或被替换（token 链检测）
    - 颁发新的 access token 和 refresh token
    - 将旧 token 标记为已撤销，设置 replaced_by 为新 JTI
    """
    from app.core.auth_service import AuthService

    # Support both body and cookie for refresh token
    if not refresh_token:
        refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    device = user_agent or "unknown"

    # 验证 refresh token（HTTP 场景不需要 expected_user_id）
    validation = AuthService.validate_refresh_token(db, refresh_token)
    if not validation["valid"]:
        error_messages = {
            "token_revoked": "Refresh token has been revoked",
            "token_reused": "Refresh token has already been used",
        }
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_messages.get(validation["error"], "Invalid refresh token"),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 执行轮换
    result = AuthService.rotate_refresh_token(
        db=db,
        user_id=validation["user_id"],
        old_jti=validation["jti"],
        old_family_id=validation["family_id"],
        device=device,
        expected_access_token=None,  # HTTP 场景不需要绑定验证
    )

    if "error" in result:
        error_messages = {
            "user_not_found": "User not found",
            "account_inactive": "Account is inactive",
            "account_locked": "Account is locked",
        }
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_messages.get(result["error"], "Token rotation failed"),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update cookies with new tokens
    access_token = result["access_token"]
    cookie_max_age = result["expires_in"]

    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=cookie_max_age,
        httponly=True,
        samesite="lax",  # lax allows cookie on cross-origin top-level nav
        secure=_is_secure_cookie(),
    )

    if result.get("refresh_token"):
        refresh_max_age = 30 * 24 * 60 * 60  # 30 days
        response.set_cookie(
            key="refresh_token",
            value=result["refresh_token"],
            max_age=refresh_max_age,
            httponly=True,
            samesite="lax",
            secure=_is_secure_cookie(),
        )

    return {
        "access_token": access_token,
        "refresh_token": result.get("refresh_token", ""),
        "token_type": "bearer",
        "expires_in": result["expires_in"],
    }


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    refresh_token: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    撤销当前的 refresh token 并清除 cookies。

    用户登出时调用，撤销指定的 refresh token 并清除客户端 cookies。
    """
    from app.core.auth_service import AuthService

    # Try to revoke refresh token if provided
    if refresh_token:
        validation = AuthService.validate_refresh_token(db, refresh_token)
        if validation["valid"]:
            AuthService.revoke_refresh_token(db, validation["user_id"], validation["jti"])

    # Clear cookies regardless of token revocation result
    response.delete_cookie(key="access_token", httponly=True, samesite="lax", secure=_is_secure_cookie())
    response.delete_cookie(key="refresh_token", httponly=True, samesite="lax", secure=_is_secure_cookie())

    return {"message": "Logged out successfully"}


@router.post("/logout-all")
def logout_all(
    current_user: AuthenticatedUser = Depends(get_current_http_user),
    db: Session = Depends(get_db),
):
    """
    撤销当前用户的所有 refresh tokens（所有设备）。

    用于用户在所有设备上登出。
    """
    from app.core.auth_service import AuthService

    AuthService.revoke_all_user_tokens(db, int(current_user.user_id))
    return {"message": "Logged out from all devices successfully"}


@router.get("/api-key")
def list_api_keys(
    current_user: AuthenticatedUser = Depends(get_current_http_user),
    db: Session = Depends(get_db),
):
    """查询当前账号 API key 元数据（不返回明文 key）。"""
    rows = (
        db.query(ApiKey)
        .filter(ApiKey.owner_account_id == int(current_user.user_id))
        .order_by(ApiKey.created_at.desc())
        .all()
    )
    return {
        "items": [
            {
                "kid": row.kid,
                "name": row.name,
                "algorithm": row.algorithm,
                "iterations": row.iterations,
                "revoked": row.revoked,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
            }
            for row in rows
        ]
    }


@router.post("/api-key")
def issue_api_key(
    payload: ApiKeyIssueRequest,
    current_user: AuthenticatedUser = Depends(get_current_http_user),
    db: Session = Depends(get_db),
):
    """签发新 API key（明文仅返回一次）。"""
    account = db.query(Node).filter(
        Node.id == int(current_user.user_id),
        Node.type_code == "account",
    ).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account node not found",
        )

    raw_key, kid, salt, iterations, key_hash = build_api_key_record()
    ttl_days = payload.expires_in_days or _get_api_key_ttl_days()
    expires_at = datetime.utcnow() + timedelta(days=ttl_days)
    row = ApiKey(
        kid=kid,
        owner_account_id=account.id,
        key_hash=key_hash,
        salt=salt,
        algorithm="pbkdf2_sha256",
        iterations=iterations,
        name=payload.name,
        scopes=payload.scopes,
        expires_at=expires_at,
        revoked=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "api_key": raw_key,
        "kid": row.kid,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else datetime.utcnow().isoformat(),
    }


@router.post("/api-key/rotate")
def rotate_api_key(
    payload: ApiKeyIssueRequest,
    current_user: AuthenticatedUser = Depends(get_current_http_user),
    db: Session = Depends(get_db),
):
    """轮换当前账号有效 key：吊销旧 key 并签发新 key。"""
    active_rows = (
        db.query(ApiKey)
        .filter(ApiKey.owner_account_id == int(current_user.user_id), ApiKey.revoked == False)
        .all()
    )
    now = datetime.utcnow()
    for row in active_rows:
        row.revoked = True
        row.revoked_at = now

    raw_key, kid, salt, iterations, key_hash = build_api_key_record()
    ttl_days = payload.expires_in_days or _get_api_key_ttl_days()
    expires_at = datetime.utcnow() + timedelta(days=ttl_days)
    new_row = ApiKey(
        kid=kid,
        owner_account_id=int(current_user.user_id),
        key_hash=key_hash,
        salt=salt,
        algorithm="pbkdf2_sha256",
        iterations=iterations,
        name=payload.name,
        scopes=payload.scopes,
        expires_at=expires_at,
        revoked=False,
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return {
        "api_key": raw_key,
        "kid": new_row.kid,
        "expires_at": new_row.expires_at.isoformat() if new_row.expires_at else None,
        "created_at": new_row.created_at.isoformat() if new_row.created_at else datetime.utcnow().isoformat(),
        "rotated_count": len(active_rows),
    }
