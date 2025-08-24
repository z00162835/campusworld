"""
权限管理系统

参考Evennia框架设计，提供完整的权限控制功能
支持角色、权限、访问级别等多层次权限控制

作者：AI Assistant
创建时间：2025-08-24
"""

from typing import List, Dict, Set, Optional, Union
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """权限级别枚举"""
    GUEST = 0      # 访客权限
    USER = 1       # 普通用户权限
    MODERATOR = 2  # 版主权限
    DEVELOPER = 3  # 开发者权限
    ADMIN = 4      # 管理员权限
    OWNER = 5      # 所有者权限


class Role(Enum):
    """角色枚举"""
    GUEST = "guest"
    USER = "user"
    MODERATOR = "moderator"
    DEVELOPER = "dev"
    ADMIN = "admin"
    OWNER = "owner"


class Permission(Enum):
    """权限枚举"""
    # 基础权限
    LOGIN = "login"
    LOGOUT = "logout"
    VIEW_PROFILE = "view_profile"
    EDIT_PROFILE = "edit_profile"
    
    # 用户管理权限
    CREATE_USER = "create_user"
    EDIT_USER = "edit_user"
    DELETE_USER = "delete_user"
    VIEW_USERS = "view_users"
    MANAGE_USERS = "manage_users"
    
    # 校园管理权限
    VIEW_CAMPUS = "view_campus"
    CREATE_CAMPUS = "create_campus"
    EDIT_CAMPUS = "edit_campus"
    DELETE_CAMPUS = "delete_campus"
    MANAGE_CAMPUS = "manage_campus"
    
    # 世界管理权限
    VIEW_WORLD = "view_world"
    CREATE_WORLD = "create_world"
    EDIT_WORLD = "edit_world"
    DELETE_WORLD = "delete_world"
    MANAGE_WORLD = "manage_world"
    
    # 系统管理权限
    VIEW_SYSTEM = "view_system"
    MANAGE_SYSTEM = "manage_system"
    VIEW_LOGS = "view_logs"
    MANAGE_LOGS = "manage_logs"
    SYSTEM_CONFIG = "system_config"
    
    # 开发权限
    DEBUG_MODE = "debug_mode"
    TEST_MODE = "test_mode"
    DEVELOP_FEATURES = "develop_features"
    DEPLOY_CHANGES = "deploy_changes"


class PermissionManager:
    """
    权限管理器
    
    负责权限的分配、检查和验证
    """
    
    def __init__(self):
        # 角色权限映射
        self._role_permissions: Dict[Role, Set[Permission]] = {
            Role.GUEST: {
                Permission.LOGIN,
                Permission.VIEW_PROFILE,
            },
            Role.USER: {
                Permission.LOGIN,
                Permission.LOGOUT,
                Permission.VIEW_PROFILE,
                Permission.EDIT_PROFILE,
                Permission.VIEW_CAMPUS,
                Permission.VIEW_WORLD,
            },
            Role.MODERATOR: {
                Permission.LOGIN,
                Permission.LOGOUT,
                Permission.VIEW_PROFILE,
                Permission.EDIT_PROFILE,
                Permission.VIEW_USERS,
                Permission.VIEW_CAMPUS,
                Permission.EDIT_CAMPUS,
                Permission.MANAGE_CAMPUS,
                Permission.VIEW_WORLD,
                Permission.EDIT_WORLD,
                Permission.MANAGE_WORLD,
            },
            Role.DEVELOPER: {
                Permission.LOGIN,
                Permission.LOGOUT,
                Permission.VIEW_PROFILE,
                Permission.EDIT_PROFILE,
                Permission.VIEW_USERS,
                Permission.VIEW_CAMPUS,
                Permission.EDIT_CAMPUS,
                Permission.MANAGE_CAMPUS,
                Permission.VIEW_WORLD,
                Permission.EDIT_WORLD,
                Permission.MANAGE_WORLD,
                Permission.DEBUG_MODE,
                Permission.TEST_MODE,
                Permission.DEVELOP_FEATURES,
                Permission.VIEW_SYSTEM,
                Permission.VIEW_LOGS,
            },
            Role.ADMIN: {
                Permission.LOGIN,
                Permission.LOGOUT,
                Permission.VIEW_PROFILE,
                Permission.EDIT_PROFILE,
                Permission.CREATE_USER,
                Permission.EDIT_USER,
                Permission.DELETE_USER,
                Permission.VIEW_USERS,
                Permission.MANAGE_USERS,
                Permission.CREATE_CAMPUS,
                Permission.EDIT_CAMPUS,
                Permission.DELETE_CAMPUS,
                Permission.VIEW_CAMPUS,
                Permission.MANAGE_CAMPUS,
                Permission.CREATE_WORLD,
                Permission.EDIT_WORLD,
                Permission.DELETE_WORLD,
                Permission.VIEW_WORLD,
                Permission.MANAGE_WORLD,
                Permission.VIEW_SYSTEM,
                Permission.MANAGE_SYSTEM,
                Permission.VIEW_LOGS,
                Permission.MANAGE_LOGS,
                Permission.SYSTEM_CONFIG,
            },
            Role.OWNER: {
                # 拥有所有权限
                *[perm for perm in Permission],
            }
        }
        
        # 权限级别映射
        self._permission_levels: Dict[Permission, PermissionLevel] = {
            # 基础权限
            Permission.LOGIN: PermissionLevel.GUEST,
            Permission.LOGOUT: PermissionLevel.USER,
            Permission.VIEW_PROFILE: PermissionLevel.GUEST,
            Permission.EDIT_PROFILE: PermissionLevel.USER,
            
            # 用户管理权限
            Permission.CREATE_USER: PermissionLevel.ADMIN,
            Permission.EDIT_USER: PermissionLevel.ADMIN,
            Permission.DELETE_USER: PermissionLevel.ADMIN,
            Permission.VIEW_USERS: PermissionLevel.MODERATOR,
            Permission.MANAGE_USERS: PermissionLevel.ADMIN,
            
            # 校园管理权限
            Permission.VIEW_CAMPUS: PermissionLevel.USER,
            Permission.CREATE_CAMPUS: PermissionLevel.ADMIN,
            Permission.EDIT_CAMPUS: PermissionLevel.MODERATOR,
            Permission.DELETE_CAMPUS: PermissionLevel.ADMIN,
            Permission.MANAGE_CAMPUS: PermissionLevel.MODERATOR,
            
            # 世界管理权限
            Permission.VIEW_WORLD: PermissionLevel.USER,
            Permission.CREATE_WORLD: PermissionLevel.ADMIN,
            Permission.EDIT_WORLD: PermissionLevel.MODERATOR,
            Permission.DELETE_WORLD: PermissionLevel.ADMIN,
            Permission.MANAGE_WORLD: PermissionLevel.MODERATOR,
            
            # 系统管理权限
            Permission.VIEW_SYSTEM: PermissionLevel.DEVELOPER,
            Permission.MANAGE_SYSTEM: PermissionLevel.ADMIN,
            Permission.VIEW_LOGS: PermissionLevel.DEVELOPER,
            Permission.MANAGE_LOGS: PermissionLevel.ADMIN,
            Permission.SYSTEM_CONFIG: PermissionLevel.ADMIN,
            
            # 开发权限
            Permission.DEBUG_MODE: PermissionLevel.DEVELOPER,
            Permission.TEST_MODE: PermissionLevel.DEVELOPER,
            Permission.DEVELOP_FEATURES: PermissionLevel.DEVELOPER,
            Permission.DEPLOY_CHANGES: PermissionLevel.ADMIN,
        }
    
    def get_role_permissions(self, role: Role) -> Set[Permission]:
        """获取角色的权限集合"""
        return self._role_permissions.get(role, set())
    
    def get_permission_level(self, permission: Permission) -> PermissionLevel:
        """获取权限的级别"""
        return self._permission_levels.get(permission, PermissionLevel.USER)
    
    def get_all_permissions(self) -> Set[Permission]:
        """获取所有权限"""
        return set(Permission)
    
    def get_all_roles(self) -> Set[Role]:
        """获取所有角色"""
        return set(Role)
    
    def check_role_permission(self, role: Role, permission: Permission) -> bool:
        """检查角色是否有指定权限"""
        role_perms = self.get_role_permissions(role)
        return permission in role_perms
    
    def check_permission_level(self, user_level: PermissionLevel, required_level: PermissionLevel) -> bool:
        """检查用户级别是否满足要求"""
        return user_level.value >= required_level.value
    
    def get_roles_by_permission(self, permission: Permission) -> Set[Role]:
        """获取拥有指定权限的所有角色"""
        roles = set()
        for role, perms in self._role_permissions.items():
            if permission in perms:
                roles.add(role)
        return roles
    
    def add_role_permission(self, role: Role, permission: Permission) -> bool:
        """为角色添加权限"""
        if role not in self._role_permissions:
            self._role_permissions[role] = set()
        
        self._role_permissions[role].add(permission)
        logger.info(f"为角色 {role.value} 添加权限 {permission.value}")
        return True
    
    def remove_role_permission(self, role: Role, permission: Permission) -> bool:
        """从角色移除权限"""
        if role in self._role_permissions:
            self._role_permissions[role].discard(permission)
            logger.info(f"从角色 {role.value} 移除权限 {permission.value}")
            return True
        return False
    
    def create_custom_role(self, role_name: str, permissions: Set[Permission]) -> Role:
        """创建自定义角色"""
        try:
            # 创建新的角色枚举值
            custom_role = Role(role_name)
            self._role_permissions[custom_role] = permissions
            logger.info(f"创建自定义角色 {role_name}，权限: {[p.value for p in permissions]}")
            return custom_role
        except ValueError:
            logger.error(f"创建自定义角色失败: {role_name}")
            return None


# 全局权限管理器实例
permission_manager = PermissionManager()


class PermissionChecker:
    """
    权限检查器
    
    提供便捷的权限检查方法
    """
    
    @staticmethod
    def check_permission(user_permissions: List[str], required_permission: str) -> bool:
        """
        检查用户是否有指定权限
        
        Args:
            user_permissions: 用户权限列表
            required_permission: 需要的权限
            
        Returns:
            是否有权限
        """
        if not user_permissions:
            return False
        
        # 直接权限检查
        if required_permission in user_permissions:
            return True
        
        # 通配符权限检查
        for perm in user_permissions:
            if perm == "*" or perm == "all":  # 超级权限
                return True
            if perm.endswith(".*") and required_permission.startswith(perm[:-1]):
                return True
        
        return False
    
    @staticmethod
    def check_role(user_roles: List[str], required_role: str) -> bool:
        """
        检查用户是否有指定角色
        
        Args:
            user_roles: 用户角色列表
            required_role: 需要的角色
            
        Returns:
            是否有角色
        """
        if not user_roles:
            return False
        
        # 角色层级检查
        role_hierarchy = {
            "guest": 0,
            "user": 1,
            "moderator": 2,
            "dev": 3,
            "admin": 4,
            "owner": 5
        }
        
        user_max_level = max(role_hierarchy.get(role.lower(), 0) for role in user_roles)
        required_level = role_hierarchy.get(required_role.lower(), 0)
        
        return user_max_level >= required_level
    
    @staticmethod
    def check_access_level(user_level: str, required_level: str) -> bool:
        """
        检查用户访问级别是否满足要求
        
        Args:
            user_level: 用户访问级别
            required_level: 需要的访问级别
            
        Returns:
            是否满足要求
        """
        level_hierarchy = {
            "guest": 0,
            "normal": 1,
            "moderator": 2,
            "developer": 3,
            "admin": 4,
            "owner": 5
        }
        
        user_level_value = level_hierarchy.get(user_level.lower(), 0)
        required_level_value = level_hierarchy.get(required_level.lower(), 0)
        
        return user_level_value >= required_level_value


# 全局权限检查器实例
permission_checker = PermissionChecker()
