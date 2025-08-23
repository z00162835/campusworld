"""
Authentication schemas
"""

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    username: str


class UserCreate(UserBase):
    """User creation schema"""
    password: str
    full_name: str = None


class UserLogin(BaseModel):
    """User login schema"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """Token response schema"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token data schema"""
    email: str = None
