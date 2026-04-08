"""
Authentication endpoints
包含注册、登录、刷新令牌、登出等功能
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, _get_token_expire_minutes
from app.core.auth_service import AuthService
from app.models.user import User
from app.models.graph import Node
from app.schemas.auth import Token, UserCreate
from app.schemas.account import RefreshTokenRequest, RefreshTokenResponse
from app.ssh.game_handler import game_handler
from app.api.v1.dependencies import get_current_http_user, AuthenticatedUser

router = APIRouter()


def _get_token_expire_seconds() -> int:
    """获取 access token 过期时间（秒）"""
    return _get_token_expire_minutes() * 60


@router.post("/register", response_model=Token)
def register(
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
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    account_node = db.query(Node).filter(
        Node.type_code == "account",
        Node.name == user_data.username
    ).first()

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
def login(
    request: Request,
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

    result = game_handler.authenticate_user(
        username=form_data.username,
        password=form_data.password,
        client_ip=client_ip,
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = result["user_id"]
    username = result["username"]

    # 清理过期 token
    AuthService.cleanup_expired_tokens(db, user_id)

    tokens = AuthService.issue_tokens(
        db=db,
        user_id=user_id,
        username=username,
        device=device,
    )

    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
        "expires_in": tokens["expires_in"],
    }


@router.post("/refresh", response_model=RefreshTokenResponse)
def refresh_token(
    request: RefreshTokenRequest,
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

    device = user_agent or "unknown"

    # 验证 refresh token（HTTP 场景不需要 expected_user_id）
    validation = AuthService.validate_refresh_token(db, request.refresh_token)
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

    return {
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
        "token_type": "bearer",
        "expires_in": result["expires_in"],
    }


@router.post("/logout")
def logout(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """
    撤销当前的 refresh token。

    用户登出时调用，撤销指定的 refresh token。
    """
    from app.core.auth_service import AuthService

    validation = AuthService.validate_refresh_token(db, request.refresh_token)
    if not validation["valid"]:
        return {"message": "Logged out successfully"}

    AuthService.revoke_refresh_token(db, validation["user_id"], validation["jti"])
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
