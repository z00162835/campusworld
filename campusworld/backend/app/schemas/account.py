"""
账号相关的Pydantic模型
定义API请求和响应的数据结构
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator


class AccountBase(BaseModel):
    """账号基础模型"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: Optional[EmailStr] = Field(None, description="邮箱地址")
    description: Optional[str] = Field(None, max_length=500, description="账号描述")


class AccountCreate(AccountBase):
    """创建账号请求模型"""
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    account_type: str = Field(..., description="账号类型")
    roles: Optional[List[str]] = Field(default_factory=list, description="角色列表")
    permissions: Optional[List[str]] = Field(default_factory=list, description="权限列表")
    
    @validator('username')
    def validate_username(cls, v):
        """验证用户名格式"""
        if not v.isalnum() and '_' not in v:
            raise ValueError('用户名只能包含字母、数字和下划线')
        return v.lower()
    
    @validator('password')
    def validate_password(cls, v):
        """验证密码强度"""
        if len(v) < 6:
            raise ValueError('密码长度至少6位')
        return v


class AccountUpdate(BaseModel):
    """更新账号请求模型"""
    email: Optional[EmailStr] = Field(None, description="邮箱地址")
    description: Optional[str] = Field(None, max_length=500, description="账号描述")
    roles: Optional[List[str]] = Field(None, description="角色列表")
    permissions: Optional[List[str]] = Field(None, description="权限列表")
    is_active: Optional[bool] = Field(None, description="是否活跃")
    is_verified: Optional[bool] = Field(None, description="是否已验证")
    access_level: Optional[str] = Field(None, description="访问级别")


class AccountStatusUpdate(BaseModel):
    """更新账号状态请求模型"""
    is_locked: Optional[bool] = Field(None, description="是否锁定")
    lock_reason: Optional[str] = Field(None, max_length=200, description="锁定原因")
    is_suspended: Optional[bool] = Field(None, description="是否暂停")
    suspension_reason: Optional[str] = Field(None, max_length=200, description="暂停原因")
    suspension_until: Optional[datetime] = Field(None, description="暂停截止时间")


class PasswordChange(BaseModel):
    """修改密码请求模型"""
    old_password: Optional[str] = Field(None, description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")
    
    @validator('new_password')
    def validate_new_password(cls, v):
        """验证新密码强度"""
        if len(v) < 6:
            raise ValueError('密码长度至少6位')
        return v


class AccountResponse(AccountBase):
    """账号响应模型"""
    id: int = Field(..., description="账号ID")
    uuid: str = Field(..., description="账号UUID")
    account_type: str = Field(..., description="账号类型")
    roles: List[str] = Field(default_factory=list, description="角色列表")
    is_active: bool = Field(..., description="是否活跃")
    is_verified: bool = Field(..., description="是否已验证")
    access_level: str = Field(..., description="访问级别")
    created_at: datetime = Field(..., description="创建时间")
    last_login: Optional[datetime] = Field(None, description="最后登录时间")
    last_activity: Optional[datetime] = Field(None, description="最后活动时间")
    
    class Config:
        from_attributes = True


class AccountListResponse(BaseModel):
    """账号列表响应模型"""
    total: int = Field(..., description="总数量")
    accounts: List[AccountResponse] = Field(..., description="账号列表")
    skip: int = Field(..., description="跳过数量")
    limit: int = Field(..., description="限制数量")


class AccountSummary(BaseModel):
    """账号摘要模型"""
    id: int = Field(..., description="账号ID")
    username: str = Field(..., description="用户名")
    account_type: str = Field(..., description="账号类型")
    roles: List[str] = Field(default_factory=list, description="角色列表")
    is_active: bool = Field(..., description="是否活跃")
    access_level: str = Field(..., description="访问级别")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True


class AccountStats(BaseModel):
    """账号统计模型"""
    total_accounts: int = Field(..., description="总账号数")
    active_accounts: int = Field(..., description="活跃账号数")
    suspended_accounts: int = Field(..., description="暂停账号数")
    locked_accounts: int = Field(..., description="锁定账号数")
    accounts_by_type: dict = Field(..., description="按类型统计")
    accounts_by_role: dict = Field(..., description="按角色统计")
    accounts_by_access_level: dict = Field(..., description="按访问级别统计")


class LoginRequest(BaseModel):
    """登录请求模型"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class LoginResponse(BaseModel):
    """登录响应模型"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(..., description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")
    user: AccountResponse = Field(..., description="用户信息")


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求模型"""
    refresh_token: str = Field(..., description="刷新令牌")


class RefreshTokenResponse(BaseModel):
    """刷新令牌响应模型"""
    access_token: str = Field(..., description="新的访问令牌")
    token_type: str = Field(..., description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")


class AccountSearchRequest(BaseModel):
    """账号搜索请求模型"""
    query: str = Field(..., min_length=1, max_length=100, description="搜索查询")
    account_type: Optional[str] = Field(None, description="账号类型筛选")
    role: Optional[str] = Field(None, description="角色筛选")
    access_level: Optional[str] = Field(None, description="访问级别筛选")
    is_active: Optional[bool] = Field(None, description="活跃状态筛选")
    skip: int = Field(0, ge=0, description="跳过数量")
    limit: int = Field(100, ge=1, le=1000, description="限制数量")


class AccountBulkUpdateRequest(BaseModel):
    """账号批量更新请求模型"""
    account_ids: List[int] = Field(..., description="账号ID列表")
    updates: AccountUpdate = Field(..., description="更新内容")
    reason: Optional[str] = Field(None, max_length=200, description="更新原因")


class AccountBulkUpdateResponse(BaseModel):
    """账号批量更新响应模型"""
    success_count: int = Field(..., description="成功更新数量")
    failed_count: int = Field(..., description="失败数量")
    failed_accounts: List[dict] = Field(..., description="失败的账号信息")
    message: str = Field(..., description="操作结果消息")
