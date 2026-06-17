"""
Authentication endpoints
包含注册、登录、刷新令牌、登出等功能
"""
import logging
import secrets
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Header
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.core.database import get_db, db_session_context
from app.core.config_manager import get_setting
from app.core.security import get_password_hash, _get_refresh_token_expire_days, build_api_key_record
from app.core.auth_service import AuthService
from app.models.user import User
from app.models.graph import Node, NodeType
from app.models.system import ApiKey
from app.schemas.auth import Token, UserCreate, RegisterResponse
from app.schemas.account import RefreshTokenResponse
from app.ssh.game_handler import game_handler
from app.api.v1.dependencies import bearer_scheme, get_current_http_user, AuthenticatedUser

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

def _is_secure_cookie(request: Request = None) -> bool:
    """Determine if cookies should have Secure flag.

    In production, Secure should be True (requires HTTPS).
    In development, False allows HTTP for local testing.

    Also checks the actual request scheme (or X-Forwarded-Proto header)
    so that __Host- prefixed cookies are not silently rejected by the
    browser when running on HTTP even if app.debug=false.
    """
    from app.core.config_manager import get_setting
    debug = get_setting('app.debug', False)
    if debug:
        return False
    # Check the actual request scheme to avoid setting __Host- cookies
    # on non-HTTPS connections (browsers reject them silently).
    if request is not None:
        scheme = request.headers.get('X-Forwarded-Proto') or request.url.scheme
        if scheme.lower() != 'https':
            return False
    return True

def _refresh_cookie_name(request: Request = None) -> str:
    if _is_secure_cookie(request):
        return '__Host-refresh_token'
    return 'refresh_token'

def _csrf_cookie_name() -> str:
    return 'csrf_token'

def _refresh_cookie_max_age_seconds() -> int:
    return _get_refresh_token_expire_days() * 24 * 60 * 60

def _get_session_idle_timeout_seconds() -> int:
    return int(get_setting('security.session_idle_timeout_minutes', 30)) * 60

def _set_no_store(response: Response) -> None:
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'

def _set_session_termination_headers(response: Response) -> None:
    _set_no_store(response)
    response.headers['Clear-Site-Data'] = '"cache", "storage"'

def _clear_auth_cookies(response: Response, request: Request = None) -> None:
    # Always try to delete both cookie names regardless of secure flag,
    # since we may not know which variant was set.
    response.delete_cookie(key='access_token', httponly=True, samesite='lax', secure=_is_secure_cookie(request), path='/')
    for cookie_name in ('refresh_token', '__Host-refresh_token'):
        response.delete_cookie(key=cookie_name, httponly=True, samesite='lax', secure=_is_secure_cookie(request), path='/')
    response.delete_cookie(key=_csrf_cookie_name(), httponly=False, samesite='lax', secure=_is_secure_cookie(request), path='/')

def _set_csrf_cookie(response: Response, csrf_token: str, request: Request = None, max_age: Optional[int] = None) -> None:
    response.set_cookie(key=_csrf_cookie_name(), value=csrf_token, max_age=max_age or _refresh_cookie_max_age_seconds(), httponly=False, samesite='lax', secure=_is_secure_cookie(request), path='/')

def _refresh_unauthorized_response(detail: str, request: Request = None) -> JSONResponse:
    response = JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={'detail': detail}, headers={'WWW-Authenticate': 'Bearer'})
    _clear_auth_cookies(response, request)
    _set_session_termination_headers(response)
    return response

def _log_refresh_rejected(
    request: Request,
    *,
    reason: str,
    has_cookie: bool,
    validation: Optional[dict] = None,
    user_agent: Optional[str] = None,
) -> None:
    validation = validation or {}
    client = request.client.host if request and request.client else 'unknown'
    agent = user_agent or (request.headers.get('user-agent') if request else None) or 'unknown'
    log = logger.debug if reason == 'missing_cookie' else logger.info
    log(
        'Refresh token rejected reason=%s has_cookie=%s user_id=%s jti=%s family_id=%s stored_tokens=%s client=%s user_agent=%s',
        reason,
        has_cookie,
        validation.get('user_id'),
        validation.get('jti'),
        validation.get('family_id'),
        validation.get('token_count'),
        client,
        agent,
    )

def _get_refresh_token_from_request(request: Request) -> Optional[str]:
    return request.cookies.get('__Host-refresh_token') or request.cookies.get('refresh_token')

def _validate_auth_ajax_header(x_requested_with: Optional[str]) -> None:
    if x_requested_with != 'XMLHttpRequest':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Missing required auth request header')

def _validate_auth_csrf_token(request: Request, expected_token: Optional[str]) -> None:
    supplied_token = request.headers.get('X-CSRF-Token')
    if not expected_token or not supplied_token or not secrets.compare_digest(supplied_token, expected_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Invalid CSRF token')

def _allowed_auth_origins() -> List[str]:
    origins = get_setting('cors.allowed_origins', [])
    return [origin.rstrip('/') for origin in origins if origin and origin != '*']

def _validate_auth_request_origin(request: Request) -> None:
    allowed_origins = _allowed_auth_origins()
    if not allowed_origins:
        return
    origin = request.headers.get('origin')
    referer = request.headers.get('referer')
    source = origin or referer
    if not source:
        return
    normalized_source = source.rstrip('/')
    if origin:
        allowed = normalized_source in allowed_origins
    else:
        allowed = any((normalized_source == allowed or normalized_source.startswith(f'{allowed}/') for allowed in allowed_origins))
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Invalid request origin')

class ApiKeyIssueRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    scopes: List[str] = Field(default_factory=list)
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365)

def _get_api_key_ttl_days() -> int:
    return int(get_setting('security.api_key_ttl_days', 90))

@router.post('/register', response_model=RegisterResponse)
@limiter.limit('5/minute')
def register(request: Request, response: Response, user_data: UserCreate, db: Session=Depends(get_db)):
    """Register a new user (SQL legacy table; graph account required for CLI/WS)."""
    _validate_auth_request_origin(request)
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Email already registered')
    hashed_password = get_password_hash(user_data.password)
    user = User(email=user_data.email, username=user_data.username, hashed_password=hashed_password, disable_auto_sync=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    account_node = db.query(Node).filter(Node.type_code == 'account', Node.name == user_data.username).first()
    if not account_node:
        account_type = db.query(NodeType).filter(NodeType.type_code == 'account').first()
        if account_type:
            account_node = Node(uuid=user.get_node_uuid(), type_id=account_type.id, type_code='account', name=user_data.username, description=f'用户账号: {user_data.username}', is_active=True, is_public=False, access_level=user.get_node_access_level(), attributes=user._node_attributes, tags=user._node_tags)
            db.add(account_node)
            db.commit()
            db.refresh(account_node)
    _set_no_store(response)
    return {'message': 'Registered successfully'}

@router.post('/login', response_model=Token)
@limiter.limit('10/minute')
def login(request: Request, response: Response, form_data: OAuth2PasswordRequestForm=Depends(), db: Session=Depends(get_db), user_agent: Optional[str]=Header(None)):
    """
    Login with the same graph account credentials as SSH (`Node.name` / account name).
    OAuth2 `username` field carries the campus account name, not necessarily an email.
    """
    _validate_auth_request_origin(request)
    client_ip = request.client.host if request.client else 'unknown'
    device = user_agent or f'ip:{client_ip}'
    account = db.query(Node).filter(Node.type_code == 'account', Node.name == form_data.username).first()
    if account:
        is_locked = account.attributes.get('is_locked', False)
        if is_locked:
            locked_at = account.attributes.get('locked_at')
            locked_reason = account.attributes.get('lock_reason', 'Account is locked')
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=locked_reason, headers={'WWW-Authenticate': 'Bearer'})
    result = game_handler.authenticate_user(username=form_data.username, password=form_data.password, client_ip=client_ip)
    if not result.get('success'):
        if account:
            failed_attempts = account.attributes.get('failed_login_attempts', 0) + 1
            account.attributes['failed_login_attempts'] = failed_attempts
            if failed_attempts >= MAX_LOGIN_ATTEMPTS:
                account.attributes['is_locked'] = True
                account.attributes['lock_reason'] = 'Too many failed login attempts'
                account.attributes['locked_at'] = datetime.now().isoformat()
                db.commit()
                raise HTTPException(status_code=status.HTTP_423_LOCKED, detail='Account locked due to too many failed login attempts', headers={'WWW-Authenticate': 'Bearer'})
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid username or password', headers={'WWW-Authenticate': 'Bearer'})
    user_id = result['user_id']
    username = result['username']
    if account:
        account.attributes['failed_login_attempts'] = 0
        account.attributes.pop('is_locked', None)
        account.attributes.pop('lock_reason', None)
        account.attributes.pop('locked_at', None)
    AuthService.cleanup_expired_tokens(db, user_id)
    tokens = AuthService.issue_tokens(db=db, user_id=user_id, username=username, device=device)
    if 'error' in tokens:
        logger.error('Failed to issue auth session user_id=%s reason=%s', user_id, tokens['error'])
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Unable to issue auth session')
    access_token = tokens['access_token']
    _set_no_store(response)
    if tokens.get('refresh_token'):
        response.set_cookie(key=_refresh_cookie_name(request), value=tokens['refresh_token'], max_age=tokens.get('refresh_max_age', _refresh_cookie_max_age_seconds()), httponly=True, samesite='lax', secure=_is_secure_cookie(request), path='/')
    if tokens.get('csrf_token'):
        _set_csrf_cookie(response, tokens['csrf_token'], request, tokens.get('refresh_max_age', _refresh_cookie_max_age_seconds()))
    db.commit()
    logger.info(
        'Auth session issued user_id=%s jti=%s family_id=%s refresh_cookie=%s csrf_cookie=%s client=%s',
        user_id,
        tokens.get('jti'),
        tokens.get('family_id'),
        bool(tokens.get('refresh_token')),
        bool(tokens.get('csrf_token')),
        client_ip,
    )
    return {'access_token': access_token, 'token_type': 'bearer', 'expires_in': tokens['expires_in'], 'idle_expires_in': tokens['idle_expires_in']}

@router.post('/refresh', response_model=RefreshTokenResponse)
def refresh_token(request: Request, response: Response, db: Session=Depends(get_db), user_agent: Optional[str]=Header(None), x_requested_with: Optional[str]=Header(None, alias='X-Requested-With')):
    """
    使用 refresh token 换取新的 access token 和 refresh token（带轮换）。

    - 验证 refresh token 签名和过期时间
    - 检查 token 是否已撤销或被替换（token 链检测）
    - 颁发新的 access token 和 refresh token
    - 将旧 token 标记为已撤销，设置 replaced_by 为新 JTI
    """
    _validate_auth_request_origin(request)
    _validate_auth_ajax_header(x_requested_with)
    _set_no_store(response)
    refresh_token = _get_refresh_token_from_request(request)
    if not refresh_token:
        _log_refresh_rejected(request, reason='missing_cookie', has_cookie=False, user_agent=user_agent)
        return _refresh_unauthorized_response('Refresh token required', request)
    device = user_agent or 'unknown'
    validation = AuthService.validate_refresh_token(db, refresh_token)
    if not validation['valid']:
        error_messages = {'token_revoked': 'Refresh token has been revoked', 'token_reused': 'Refresh token has already been used', 'token_expired': 'Refresh token has expired', 'idle_timeout': 'Session idle timeout'}
        _log_refresh_rejected(
            request,
            reason=validation.get('error') or 'invalid_refresh_token',
            has_cookie=True,
            validation=validation,
            user_agent=user_agent,
        )
        return _refresh_unauthorized_response(error_messages.get(validation['error'], 'Invalid refresh token'), request)
    _validate_auth_csrf_token(request, validation.get('csrf_token'))
    result = AuthService.rotate_refresh_token(db=db, user_id=validation['user_id'], old_jti=validation['jti'], old_family_id=validation['family_id'], device=device, expected_access_token=None)
    if 'error' in result:
        error_messages = {'user_not_found': 'User not found', 'account_inactive': 'Account is inactive', 'account_locked': 'Account is locked'}
        _log_refresh_rejected(
            request,
            reason=f"rotate:{result['error']}",
            has_cookie=True,
            validation=validation,
            user_agent=user_agent,
        )
        return _refresh_unauthorized_response(error_messages.get(result['error'], 'Token rotation failed'), request)
    access_token = result['access_token']
    if result.get('refresh_token'):
        response.set_cookie(key=_refresh_cookie_name(request), value=result['refresh_token'], max_age=result.get('refresh_max_age', _refresh_cookie_max_age_seconds()), httponly=True, samesite='lax', secure=_is_secure_cookie(request), path='/')
    if result.get('csrf_token'):
        _set_csrf_cookie(response, result['csrf_token'], request, result.get('refresh_max_age', _refresh_cookie_max_age_seconds()))
    logger.debug(
        'Refresh token rotated user_id=%s old_jti=%s new_jti=%s family_id=%s client=%s',
        validation['user_id'],
        validation['jti'],
        result.get('jti'),
        result.get('family_id', validation['family_id']),
        request.client.host if request and request.client else 'unknown',
    )
    return {'access_token': access_token, 'token_type': 'bearer', 'expires_in': result['expires_in'], 'idle_expires_in': result.get('idle_expires_in', validation.get('idle_expires_in'))}

@router.post('/logout')
def logout(request: Request, response: Response, db: Session=Depends(get_db), x_requested_with: Optional[str]=Header(None, alias='X-Requested-With')):
    """
    撤销当前的 refresh token 并清除 cookies。

    用户登出时调用，撤销指定的 refresh token 并清除客户端 cookies。
    """
    _validate_auth_request_origin(request)
    _validate_auth_ajax_header(x_requested_with)
    refresh_token = _get_refresh_token_from_request(request)
    if refresh_token:
        validation = AuthService.validate_refresh_token(db, refresh_token)
        if validation['valid']:
            _validate_auth_csrf_token(request, validation.get('csrf_token'))
            AuthService.revoke_refresh_token(db, validation['user_id'], validation['jti'])
    _clear_auth_cookies(response, request)
    _set_session_termination_headers(response)
    return {'message': 'Logged out successfully'}

@router.post('/activity')
async def record_activity(request: Request, response: Response, credentials: Optional[HTTPAuthorizationCredentials]=Depends(bearer_scheme), x_requested_with: Optional[str]=Header(None, alias='X-Requested-With')):
    _validate_auth_request_origin(request)
    _validate_auth_ajax_header(x_requested_with)
    _set_no_store(response)
    refresh_token = _get_refresh_token_from_request(request)
    if not refresh_token:
        return _refresh_unauthorized_response('Refresh token required', request)
    with db_session_context() as db:
        validation = AuthService.validate_refresh_token(db, refresh_token)
        if not validation['valid']:
            return _refresh_unauthorized_response('Invalid refresh token', request)
        _validate_auth_csrf_token(request, validation.get('csrf_token'))
    current_user = await get_current_http_user(credentials)
    return {'message': 'Activity recorded', 'idle_expires_in': _get_session_idle_timeout_seconds(), 'user_id': current_user.user_id}

@router.post('/logout-all')
def logout_all(current_user: AuthenticatedUser=Depends(get_current_http_user), db: Session=Depends(get_db)):
    """
    撤销当前用户的所有 refresh tokens（所有设备）。

    用于用户在所有设备上登出。
    """
    from app.core.auth_service import AuthService
    AuthService.revoke_all_user_tokens(db, int(current_user.user_id))
    return {'message': 'Logged out from all devices successfully'}

@router.get('/api-key')
def list_api_keys(current_user: AuthenticatedUser=Depends(get_current_http_user), db: Session=Depends(get_db)):
    """查询当前账号 API key 元数据（不返回明文 key）。"""
    rows = db.query(ApiKey).filter(ApiKey.owner_account_id == int(current_user.user_id)).order_by(ApiKey.created_at.desc()).all()
    return {'items': [{'kid': row.kid, 'name': row.name, 'algorithm': row.algorithm, 'iterations': row.iterations, 'revoked': row.revoked, 'created_at': row.created_at.isoformat() if row.created_at else None, 'expires_at': row.expires_at.isoformat() if row.expires_at else None, 'last_used_at': row.last_used_at.isoformat() if row.last_used_at else None} for row in rows]}

@router.post('/api-key')
def issue_api_key(payload: ApiKeyIssueRequest, current_user: AuthenticatedUser=Depends(get_current_http_user), db: Session=Depends(get_db)):
    """签发新 API key（明文仅返回一次）。"""
    account = db.query(Node).filter(Node.id == int(current_user.user_id), Node.type_code == 'account').first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Account node not found')
    (raw_key, kid, salt, iterations, key_hash) = build_api_key_record()
    ttl_days = payload.expires_in_days or _get_api_key_ttl_days()
    expires_at = datetime.utcnow() + timedelta(days=ttl_days)
    row = ApiKey(kid=kid, owner_account_id=account.id, key_hash=key_hash, salt=salt, algorithm='pbkdf2_sha256', iterations=iterations, name=payload.name, scopes=payload.scopes, expires_at=expires_at, revoked=False)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'api_key': raw_key, 'kid': row.kid, 'expires_at': row.expires_at.isoformat() if row.expires_at else None, 'created_at': row.created_at.isoformat() if row.created_at else datetime.utcnow().isoformat()}

@router.post('/api-key/rotate')
def rotate_api_key(payload: ApiKeyIssueRequest, current_user: AuthenticatedUser=Depends(get_current_http_user), db: Session=Depends(get_db)):
    """轮换当前账号有效 key：吊销旧 key 并签发新 key。"""
    active_rows = db.query(ApiKey).filter(ApiKey.owner_account_id == int(current_user.user_id), ApiKey.revoked == False).all()
    now = datetime.utcnow()
    for row in active_rows:
        row.revoked = True
        row.revoked_at = now
    (raw_key, kid, salt, iterations, key_hash) = build_api_key_record()
    ttl_days = payload.expires_in_days or _get_api_key_ttl_days()
    expires_at = datetime.utcnow() + timedelta(days=ttl_days)
    new_row = ApiKey(kid=kid, owner_account_id=int(current_user.user_id), key_hash=key_hash, salt=salt, algorithm='pbkdf2_sha256', iterations=iterations, name=payload.name, scopes=payload.scopes, expires_at=expires_at, revoked=False)
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return {'api_key': raw_key, 'kid': new_row.kid, 'expires_at': new_row.expires_at.isoformat() if new_row.expires_at else None, 'created_at': new_row.created_at.isoformat() if new_row.created_at else datetime.utcnow().isoformat(), 'rotated_count': len(active_rows)}
