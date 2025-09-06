"""
安全相关功能模块
提供密码哈希、JWT令牌生成和验证等功能
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Union, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# 修改导入
from app.core.config_manager import get_config, get_setting
from app.core.log import get_logger

# 获取日志器
logger = get_logger("campusworld.security")

# 获取配置管理器
config_manager = get_config()

# 从配置管理器获取配置
SECRET_KEY = get_setting('security.secret_key', 'your-secret-key-here')
ACCESS_TOKEN_EXPIRE_MINUTES = get_setting('security.access_token_expire_minutes', 11520)

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT令牌配置
ALGORITHM = "HS256"
REFRESH_TOKEN_EXPIRE_DAYS = 30  # 默认30天

# HTTP Bearer认证
security = HTTPBearer()


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
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.utcnow(),
        **kwargs
    }
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建刷新令牌
    
    Args:
        subject: 令牌主题（通常是用户ID）
        expires_delta: 过期时间增量
        
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
        "type": "refresh"
    }
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
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
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
    except:
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
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
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
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
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
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
    # 生成随机密钥
    api_key = os.urandom(32).hex()
    
    # 创建API密钥记录（这里可以存储到数据库）
    # 实际应用中应该将API密钥存储到数据库并关联用户
    
    return api_key


def verify_api_key(api_key: str) -> Optional[str]:
    """
    验证API密钥
    
    Args:
        api_key: API密钥
        
    Returns:
        Optional[str]: 用户ID，如果密钥无效则返回None
    """
    # 实际应用中应该从数据库查询API密钥
    # 这里只是示例实现
    
    # 检查密钥格式
    if len(api_key) != 64:  # 32字节的十六进制字符串
        return None
    
    try:
        # 这里应该查询数据库验证API密钥
        # 暂时返回None表示需要实现
        return None
    except:
        return None


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
