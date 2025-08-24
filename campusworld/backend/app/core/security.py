"""
Security utilities for authentication and authorization
"""

from datetime import datetime, timedelta
from typing import Any, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import get_security_config

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None) -> str:
    """Create JWT access token"""
    security_config = get_security_config()
    
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=security_config['access_token_expire_minutes'])
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, 
        security_config['secret_key'], 
        algorithm=security_config['algorithm']
    )
    return encoded_jwt


def verify_token(token: str) -> Union[dict, None]:
    """Verify JWT token"""
    security_config = get_security_config()
    
    try:
        payload = jwt.decode(
            token, 
            security_config['secret_key'], 
            algorithms=[security_config['algorithm']]
        )
        return payload
    except JWTError:
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    security_config = get_security_config()
    return pwd_context.hash(password, rounds=security_config['bcrypt_rounds'])
