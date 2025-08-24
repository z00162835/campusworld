"""
账号管理API
提供账号的CRUD操作和权限管理功能
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import require_permission, require_role, require_admin
from app.models.graph import Node, NodeType
from app.models.accounts import create_account, get_account_class, ACCOUNT_TYPES
from app.core.security import get_password_hash, verify_password
from app.schemas.account import (
    AccountCreate, 
    AccountUpdate, 
    AccountResponse, 
    AccountListResponse,
    AccountStatusUpdate,
    PasswordChange
)

router = APIRouter(prefix="/accounts", tags=["账号管理"])


@router.get("/", response_model=AccountListResponse)
@require_permission("user.manage")
async def list_accounts(
    skip: int = 0,
    limit: int = 100,
    account_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    获取账号列表
    支持分页、类型筛选和状态筛选
    """
    query = db.query(Node).filter(Node.type_code == "account")
    
    if account_type:
        query = query.filter(Node.attributes['type'].astext == account_type)
    
    if is_active is not None:
        query = query.filter(Node.attributes['is_active'].astext.cast(bool) == is_active)
    
    total = query.count()
    accounts = query.offset(skip).limit(limit).all()
    
    account_list = []
    for node in accounts:
        attrs = node.attributes
        account_list.append(AccountResponse(
            id=node.id,
            uuid=str(node.uuid),
            username=attrs.get("username", ""),
            email=attrs.get("email", ""),
            account_type=attrs.get("type", ""),
            roles=attrs.get("roles", []),
            is_active=attrs.get("is_active", True),
            is_verified=attrs.get("is_verified", False),
            access_level=attrs.get("access_level", "normal"),
            created_at=node.created_at,
            last_login=attrs.get("last_login"),
            last_activity=attrs.get("last_activity")
        ))
    
    return AccountListResponse(
        total=total,
        accounts=account_list,
        skip=skip,
        limit=limit
    )


@router.get("/{account_id}", response_model=AccountResponse)
@require_permission("user.view")
async def get_account(
    account_id: int,
    db: Session = Depends(get_db)
):
    """
    获取指定账号的详细信息
    """
    account = db.query(Node).filter(
        Node.id == account_id,
        Node.type_code == "account"
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在"
        )
    
    attrs = account.attributes
    return AccountResponse(
        id=account.id,
        uuid=str(account.uuid),
        username=attrs.get("username", ""),
        email=attrs.get("email", ""),
        account_type=attrs.get("type", ""),
        roles=attrs.get("roles", []),
        is_active=attrs.get("is_active", True),
        is_verified=attrs.get("is_verified", False),
        access_level=attrs.get("access_level", "normal"),
        created_at=account.created_at,
        last_login=attrs.get("last_login"),
        last_activity=attrs.get("last_activity")
    )


@router.post("/", response_model=AccountResponse)
@require_permission("user.create")
async def create_new_account(
    account_data: AccountCreate,
    db: Session = Depends(get_db)
):
    """
    创建新账号
    """
    # 检查用户名是否已存在
    existing = db.query(Node).filter(
        Node.type_code == "account",
        Node.attributes['username'].astext == account_data.username
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    # 检查邮箱是否已存在
    if account_data.email:
        existing_email = db.query(Node).filter(
            Node.type_code == "account",
            Node.attributes['email'].astext == account_data.email
        ).first()
        
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已存在"
            )
    
    try:
        # 创建账号实例
        account_class = get_account_class(account_data.account_type)
        if not account_class:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的账号类型: {account_data.account_type}"
            )
        
        # 创建账号对象
        new_account = account_class(
            username=account_data.username,
            email=account_data.email,
            password=account_data.password
        )
        
        # 同步到数据库
        new_account._schedule_node_sync()
        
        # 获取账号类型信息
        account_type = db.query(NodeType).filter(
            NodeType.type_code == "account"
        ).first()
        
        if not account_type:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="账号类型未配置"
            )
        
        # 创建节点
        node = Node(
            uuid=new_account.get_node_uuid(),
            type_id=account_type.id,
            type_code="account",
            name=account_data.username,
            description=f"用户账号: {account_data.username}",
            is_active=True,
            is_public=False,
            access_level=new_account.access_level,
            attributes=new_account._node_attributes,
            tags=new_account._node_tags
        )
        
        db.add(node)
        db.commit()
        db.refresh(node)
        
        # 返回创建的账号信息
        attrs = node.attributes
        return AccountResponse(
            id=node.id,
            uuid=str(node.uuid),
            username=attrs.get("username", ""),
            email=attrs.get("email", ""),
            account_type=attrs.get("type", ""),
            roles=attrs.get("roles", []),
            is_active=attrs.get("is_active", True),
            is_verified=attrs.get("is_verified", False),
            access_level=attrs.get("access_level", "normal"),
            created_at=node.created_at,
            last_login=attrs.get("last_login"),
            last_activity=attrs.get("last_activity")
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建账号失败: {str(e)}"
        )


@router.put("/{account_id}", response_model=AccountResponse)
@require_permission("user.edit")
async def update_account(
    account_id: int,
    account_data: AccountUpdate,
    db: Session = Depends(get_db)
):
    """
    更新账号信息
    """
    account = db.query(Node).filter(
        Node.id == account_id,
        Node.type_code == "account"
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在"
        )
    
    try:
        attrs = account.attributes
        
        # 更新基本信息
        if account_data.email is not None:
            # 检查邮箱是否已被其他账号使用
            if account_data.email != attrs.get("email"):
                existing = db.query(Node).filter(
                    Node.type_code == "account",
                    Node.attributes['email'].astext == account_data.email,
                    Node.id != account_id
                ).first()
                
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="邮箱已被其他账号使用"
                    )
            
            attrs["email"] = account_data.email
        
        if account_data.description is not None:
            account.description = account_data.description
        
        # 更新角色和权限
        if account_data.roles is not None:
            attrs["roles"] = account_data.roles
        
        if account_data.permissions is not None:
            attrs["permissions"] = account_data.permissions
        
        # 更新状态
        if account_data.is_active is not None:
            attrs["is_active"] = account_data.is_active
            account.is_active = account_data.is_active
        
        if account_data.is_verified is not None:
            attrs["is_verified"] = account_data.is_verified
        
        if account_data.access_level is not None:
            attrs["access_level"] = account_data.access_level
            account.access_level = account_data.access_level
        
        # 保存更新
        account.attributes = attrs
        db.commit()
        db.refresh(account)
        
        # 返回更新后的账号信息
        return AccountResponse(
            id=account.id,
            uuid=str(account.uuid),
            username=attrs.get("username", ""),
            email=attrs.get("email", ""),
            account_type=attrs.get("type", ""),
            roles=attrs.get("roles", []),
            is_active=attrs.get("is_active", True),
            is_verified=attrs.get("is_verified", False),
            access_level=attrs.get("access_level", "normal"),
            created_at=account.created_at,
            last_login=attrs.get("last_login"),
            last_activity=attrs.get("last_activity")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新账号失败: {str(e)}"
        )


@router.patch("/{account_id}/status", response_model=AccountResponse)
@require_permission("user.manage")
async def update_account_status(
    account_id: int,
    status_data: AccountStatusUpdate,
    db: Session = Depends(get_db)
):
    """
    更新账号状态（锁定、暂停等）
    """
    account = db.query(Node).filter(
        Node.id == account_id,
        Node.type_code == "account"
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在"
        )
    
    try:
        attrs = account.attributes
        
        # 更新状态信息
        if status_data.is_locked is not None:
            attrs["is_locked"] = status_data.is_locked
            if status_data.is_locked:
                attrs["lock_reason"] = status_data.lock_reason
            else:
                attrs["lock_reason"] = None
        
        if status_data.is_suspended is not None:
            attrs["is_suspended"] = status_data.is_suspended
            if status_data.is_suspended:
                attrs["suspension_reason"] = status_data.suspension_reason
                attrs["suspension_until"] = status_data.suspension_until
            else:
                attrs["suspension_reason"] = None
                attrs["suspension_until"] = None
        
        # 保存更新
        account.attributes = attrs
        db.commit()
        db.refresh(account)
        
        # 返回更新后的账号信息
        return AccountResponse(
            id=account.id,
            uuid=str(account.uuid),
            username=attrs.get("username", ""),
            email=attrs.get("email", ""),
            account_type=attrs.get("type", ""),
            roles=attrs.get("roles", []),
            is_active=attrs.get("is_active", True),
            is_verified=attrs.get("is_verified", False),
            access_level=attrs.get("access_level", "normal"),
            created_at=account.created_at,
            last_login=attrs.get("last_login"),
            last_activity=attrs.get("last_activity")
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新账号状态失败: {str(e)}"
        )


@router.post("/{account_id}/change-password")
@require_permission("user.manage")
async def change_account_password(
    account_id: int,
    password_data: PasswordChange,
    db: Session = Depends(get_db)
):
    """
    修改账号密码
    """
    account = db.query(Node).filter(
        Node.id == account_id,
        Node.type_code == "account"
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在"
        )
    
    try:
        attrs = account.attributes
        
        # 验证旧密码
        if password_data.old_password:
            current_hash = attrs.get("password_hash", "")
            if not verify_password(password_data.old_password, current_hash):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="旧密码不正确"
                )
        
        # 更新密码
        new_hash = get_password_hash(password_data.new_password)
        attrs["password_hash"] = new_hash
        
        # 保存更新
        account.attributes = attrs
        db.commit()
        
        return {"message": "密码修改成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"修改密码失败: {str(e)}"
        )


@router.delete("/{account_id}")
@require_admin
async def delete_account(
    account_id: int,
    db: Session = Depends(get_db)
):
    """
    删除账号（仅管理员）
    """
    account = db.query(Node).filter(
        Node.id == account_id,
        Node.type_code == "account"
    ).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在"
        )
    
    try:
        # 检查是否为系统默认账号
        attrs = account.attributes
        username = attrs.get("username", "")
        if username in ["admin", "dev", "campus"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能删除系统默认账号"
            )
        
        # 软删除：标记为非活跃
        attrs["is_active"] = False
        account.is_active = False
        account.attributes = attrs
        
        db.commit()
        
        return {"message": "账号已停用"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除账号失败: {str(e)}"
        )


@router.get("/types/list")
async def list_account_types():
    """
    获取支持的账号类型列表
    """
    return {
        "account_types": list(ACCOUNT_TYPES.keys()),
        "descriptions": {
            k: v.get("description", "") for k, v in ACCOUNT_TYPES.items()
        }
    }
