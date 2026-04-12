"""
安全相关功能模块
提供密码哈希、JWT令牌生成和验证等功能
"""

import os
import hashlib
import uuid
import secrets
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any, Callable, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# 使用延迟导入避免循环依赖
from app.core.log import get_logger

# 获取日志器
logger = get_logger("campusworld.security")

# 密码加密上下文
# 使用 Argon2id（通过 passlib 的 "argon2" scheme）替代 bcrypt，避免 bcrypt 72-byte 限制/后端兼容问题影响 seed。
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# JWT令牌配置
ALGORITHM = "HS256"
REFRESH_TOKEN_EXPIRE_DAYS = 30  # 默认30天

# HTTP Bearer认证
security = HTTPBearer()

# ==================================================
# 延迟加载配置（避免模块导入时的循环依赖）
# ==================================================

def _get_config_manager():
    """延迟获取配置管理器"""
    from app.core.config_manager import get_config
    return get_config()

def _get_secret_key() -> str:
    """获取 JWT 签名密钥（延迟加载）

    Raises:
        ValueError: 当未配置密钥时抛出，明确禁止使用不安全的默认值或占位符
    """
    from app.core.config_manager import get_setting
    secret_key = get_setting('security.secret_key', None)
    if not secret_key:
        logger.critical("JWT secret key is not configured. Set 'security.secret_key' in config.")
        raise ValueError(
            "CRITICAL: JWT secret key is not configured. "
            "Please set 'security.secret_key' in your config/settings.yaml or environment variable."
        )
    # Detect common placeholder patterns that should not be used in production
    placeholder_patterns = ('${SECRET_KEY}', 'your-secret-key-here', 'changeme', 'secret')
    if secret_key.startswith('${') and secret_key.endswith('}'):
        logger.critical(f"JWT secret key appears to be an unexpanded environment variable placeholder: {secret_key}")
        raise ValueError(
            f"CRITICAL: JWT secret key is a placeholder '{secret_key}' that was not expanded. "
            "Please set the SECRET_KEY environment variable or update 'security.secret_key' in config/settings.yaml."
        )
    # 验证密钥长度（JWT HS256 推荐至少 32 字节）
    if len(secret_key) < 32:
        logger.warning(f"JWT secret key is too short ({len(secret_key)} bytes). Recommended: 32+ bytes.")
    return secret_key

def _get_token_expire_minutes() -> int:
    """获取 token 过期时间（延迟加载）"""
    from app.core.config_manager import get_setting
    return get_setting('security.access_token_expire_minutes', 11520)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希密码
        
    Returns:
        bool: 验证结果
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    获取密码哈希值
    
    Args:
        password: 明文密码
        
    Returns:
        str: 哈希密码
    """
    return pwd_context.hash(password)


def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    **kwargs
) -> str:
    """
    创建访问令牌

    Args:
        subject: 令牌主题（通常是用户ID）
        expires_delta: 过期时间增量
        **kwargs: 其他要编码到令牌中的数据

    Returns:
        str: JWT令牌
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=_get_token_expire_minutes())

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.utcnow(),
        **kwargs
    }

    encoded_jwt = jwt.encode(to_encode, _get_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    jti: Optional[str] = None,
    family_id: Optional[str] = None,
) -> str:
    """
    创建刷新令牌

    Args:
        subject: 令牌主题（通常是用户ID）
        expires_delta: 过期时间增量
        jti: JWT ID（唯一标识），如果不提供则自动生成
        family_id: Token 家族 ID，同一登录会话的所有 token 共享

    Returns:
        str: JWT刷新令牌
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.utcnow(),
        "type": "refresh",
        "jti": jti or str(uuid.uuid4()),
        "family_id": family_id,
    }

    encoded_jwt = jwt.encode(to_encode, _get_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """
    验证JWT令牌
    
    Args:
        token: JWT令牌
        
    Returns:
        dict: 解码后的令牌数据
        
    Raises:
        HTTPException: 令牌无效或过期
    """
    try:
        payload = jwt.decode(token, _get_secret_key(), algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_id(token: str) -> str:
    """
    从令牌中获取当前用户ID
    
    Args:
        token: JWT令牌
        
    Returns:
        str: 用户ID
    """
    payload = verify_token(token)
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌中缺少用户信息",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


def get_token_expiration(token: str) -> datetime:
    """
    获取令牌过期时间
    
    Args:
        token: JWT令牌
        
    Returns:
        datetime: 过期时间
    """
    payload = verify_token(token)
    exp_timestamp = payload.get("exp")
    if exp_timestamp is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌中缺少过期时间",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return datetime.fromtimestamp(exp_timestamp)


def is_token_expired(token: str) -> bool:
    """
    检查令牌是否已过期
    
    Args:
        token: JWT令牌
        
    Returns:
        bool: 是否已过期
    """
    try:
        exp_time = get_token_expiration(token)
        return datetime.utcnow() > exp_time
    except Exception as e:
        logger.warning(f"Failed to check token expiration: {e}")
        return True


def extract_token_from_header(credentials: HTTPAuthorizationCredentials) -> str:
    """
    从HTTP认证头中提取令牌
    
    Args:
        credentials: HTTP认证凭据
        
    Returns:
        str: JWT令牌
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌为空",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token


def generate_password_reset_token(email: str) -> str:
    """
    生成密码重置令牌
    
    Args:
        email: 用户邮箱
        
    Returns:
        str: 密码重置令牌
    """
    delta = timedelta(hours=24)  # 默认24小时
    now = datetime.utcnow()
    expires = now + delta
    
    to_encode = {
        "exp": expires,
        "sub": email,
        "iat": now,
        "type": "password_reset"
    }
    
    encoded_jwt = jwt.encode(to_encode, _get_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt


def verify_password_reset_token(token: str) -> Optional[str]:
    """
    验证密码重置令牌
    
    Args:
        token: 密码重置令牌
        
    Returns:
        Optional[str]: 邮箱地址，如果令牌无效则返回None
    """
    try:
        payload = jwt.decode(token, _get_secret_key(), algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if email is None or token_type != "password_reset":
            return None
            
        return email
    except JWTError:
        return None


def generate_email_verification_token(email: str) -> str:
    """
    生成邮箱验证令牌
    
    Args:
        email: 用户邮箱
        
    Returns:
        str: 邮箱验证令牌
    """
    delta = timedelta(hours=48)  # 默认48小时
    now = datetime.utcnow()
    expires = now + delta
    
    to_encode = {
        "exp": expires,
        "sub": email,
        "iat": now,
        "type": "email_verification"
    }
    
    encoded_jwt = jwt.encode(to_encode, _get_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt


def verify_email_verification_token(token: str) -> Optional[str]:
    """
    验证邮箱验证令牌
    
    Args:
        token: 邮箱验证令牌
        
    Returns:
        Optional[str]: 邮箱地址，如果令牌无效则返回None
    """
    try:
        payload = jwt.decode(token, _get_secret_key(), algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if email is None or token_type != "email_verification":
            return None
            
        return email
    except JWTError:
        return None


def generate_api_key(user_id: str, permissions: list = None) -> str:
    """
    生成API密钥
    
    Args:
        user_id: 用户ID
        permissions: 权限列表
        
    Returns:
        str: API密钥
    """
    _ = user_id
    _ = permissions
    kid = secrets.token_hex(8)
    secret = secrets.token_hex(24)
    return f"cwk_{kid}_{secret}"


def hash_api_key(api_key: str) -> str:
    """
    使用 PBKDF2-SHA256 生成 API key 哈希。

    注意：为了兼容旧调用，salt 缺省时会使用固定占位 salt；
    生产校验请始终显式传入每条 key 记录的 salt 与 iterations。
    """
    return hash_api_key_pbkdf2(api_key, "default_salt", 210000)


def parse_api_key(api_key: str) -> Optional[tuple[str, str]]:
    """解析 cwk_<kid>_<secret>。"""
    if not api_key or not api_key.startswith("cwk_"):
        return None
    parts = api_key.split("_", 2)
    if len(parts) != 3:
        return None
    _, kid, secret = parts
    if not kid or not secret:
        return None
    return kid, secret


def hash_api_key_pbkdf2(api_key: str, salt: str, iterations: int = 210000) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        api_key.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations),
    )
    return dk.hex()


def build_api_key_record() -> tuple[str, str, str, int, str]:
    """返回 (raw_key, kid, salt, iterations, key_hash)。"""
    kid = secrets.token_hex(8)
    secret = secrets.token_hex(24)
    raw_key = f"cwk_{kid}_{secret}"
    salt = secrets.token_hex(16)
    iterations = 210000
    key_hash = hash_api_key_pbkdf2(raw_key, salt=salt, iterations=iterations)
    return raw_key, kid, salt, iterations, key_hash


def resolve_api_key_principal(api_key: str) -> Optional[Dict[str, Any]]:
    """解析并校验 API key，返回主体信息。"""
    parsed = parse_api_key(api_key)
    if not parsed:
        return None

    try:
        from app.core.database import db_session_context
        from app.models.system import ApiKey

        kid, _secret = parsed
        with db_session_context() as db_session:
            key_row = (
                db_session.query(ApiKey)
                .filter(ApiKey.kid == kid, ApiKey.revoked == False)
                .first()
            )
            if not key_row:
                return None
            # expires_at 为 TIMESTAMPTZ（timezone-aware），须与 aware UTC 比较；用 utcnow() 会引发 TypeError 并被下方 except 吞掉，表现为「Invalid API key」。
            now_utc = datetime.now(timezone.utc)
            if key_row.expires_at and key_row.expires_at < now_utc:
                return None

            computed = hash_api_key_pbkdf2(api_key, salt=key_row.salt, iterations=key_row.iterations)
            if not hmac.compare_digest(computed, key_row.key_hash):
                return None

            key_row.last_used_at = now_utc
            db_session.commit()
            return {
                "user_id": str(key_row.owner_account_id),
                "kid": key_row.kid,
                "scopes": list(key_row.scopes or []),
            }
    except Exception as e:
        logger.warning(f"API key verification failed: {e}")
        return None


def verify_api_key(api_key: str) -> Optional[str]:
    """
    验证API密钥
    
    Args:
        api_key: API密钥
        
    Returns:
        Optional[str]: 用户ID，如果密钥无效则返回None
    """
    principal = resolve_api_key_principal(api_key)
    if not principal:
        return None
    return principal["user_id"]


def hash_sensitive_data(data: str) -> str:
    """
    哈希敏感数据
    
    Args:
        data: 敏感数据
        
    Returns:
        str: 哈希值
    """
    return pwd_context.hash(data)


def generate_secure_random_string(length: int = 32) -> str:
    """
    生成安全的随机字符串
    
    Args:
        length: 字符串长度
        
    Returns:
        str: 随机字符串
    """
    return os.urandom(length).hex()[:length]


def validate_password_strength(password: str) -> dict:
    """
    验证密码强度
    
    Args:
        password: 密码
        
    Returns:
        dict: 强度评估结果
    """
    result = {
        "is_strong": True,
        "score": 0,
        "issues": [],
        "suggestions": []
    }
    
    # 长度检查
    if len(password) < 8:
        result["is_strong"] = False
        result["issues"].append("密码长度至少8位")
        result["suggestions"].append("增加密码长度")
    elif len(password) >= 12:
        result["score"] += 2
    else:
        result["score"] += 1
    
    # 包含数字
    if any(c.isdigit() for c in password):
        result["score"] += 1
    else:
        result["is_strong"] = False
        result["issues"].append("应包含数字")
        result["suggestions"].append("添加数字")
    
    # 包含小写字母
    if any(c.islower() for c in password):
        result["score"] += 1
    else:
        result["is_strong"] = False
        result["issues"].append("应包含小写字母")
        result["suggestions"].append("添加小写字母")
    
    # 包含大写字母
    if any(c.isupper() for c in password):
        result["score"] += 1
    else:
        result["suggestions"].append("添加大写字母")
    
    # 包含特殊字符
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if any(c in special_chars for c in password):
        result["score"] += 1
    else:
        result["suggestions"].append("添加特殊字符")
    
    # 检查常见弱密码
    weak_passwords = [
        "password", "123456", "qwerty", "admin", "letmein",
        "welcome", "monkey", "dragon", "master", "football"
    ]
    if password.lower() in weak_passwords:
        result["is_strong"] = False
        result["issues"].append("使用了常见弱密码")
        result["suggestions"].append("避免使用常见密码")
    
    # 最终强度评估
    if result["score"] >= 4:
        result["is_strong"] = True
    
    return result
