"""
权限验证系统

提供权限验证装饰器和便捷的权限检查接口
集成到命令系统和API接口

作者：AI Assistant
创建时间：2025-08-24
"""
from typing import List, Optional, Callable, Any, Union
from functools import wraps
import logging
from datetime import datetime
from .permissions import PermissionChecker, permission_checker, Role, Permission, ROLE_STRING_PERMISSIONS
logger = logging.getLogger(__name__)

def check_permission(user_permissions: List[str], required_permission: str) -> bool:
    """检查用户是否有指定权限"""
    return PermissionChecker.check_permission(user_permissions, required_permission)

def check_role(user_roles: List[str], required_role: str) -> bool:
    """检查用户是否有指定角色"""
    return PermissionChecker.check_role(user_roles, required_role)

def require_permission(permission: str):
    """
    权限验证装饰器
    
    Args:
        permission: 需要的权限
        
    Usage:
        @require_permission('user.create')
        def create_user(self):
            pass
    """

    def decorator(func: Callable) -> Callable:

        @wraps(func)
        def wrapper(*args, **kwargs):
            caller = args[0] if args else None
            if not caller:
                logger.error('Permission check failed: unable to resolve caller')
                return False
            if hasattr(caller, 'check_permission'):
                if not caller.check_permission(permission):
                    logger.warning(f'Insufficient permission: {caller.username} Attempted execute {permission}')
                    return False
            else:
                logger.error('Permission check failed: caller has no check_permission method')
                return False
            return func(*args, **kwargs)
        return wrapper
    return decorator

def require_role(role: str):
    """
    角色验证装饰器
    
    Args:
        role: 需要的角色
        
    Usage:
        @require_role('admin')
        def admin_only_function(self):
            pass
    """

    def decorator(func: Callable) -> Callable:

        @wraps(func)
        def wrapper(*args, **kwargs):
            caller = args[0] if args else None
            if not caller:
                logger.error('Role check failed: unable to resolve caller')
                return False
            if hasattr(caller, 'check_role'):
                if not caller.check_role(role):
                    logger.warning(f'Insufficient role: {caller.username} Attempted operation requires {role} role operation')
                    return False
            else:
                logger.error('Role check failed: caller has no check_role method')
                return False
            return func(*args, **kwargs)
        return wrapper
    return decorator

def require_access_level(level: str):
    """
    访问级别验证装饰器
    
    Args:
        level: 需要的访问级别
        
    Usage:
        @require_access_level('admin')
        def admin_level_function(self):
            pass
    """

    def decorator(func: Callable) -> Callable:

        @wraps(func)
        def wrapper(*args, **kwargs):
            caller = args[0] if args else None
            if not caller:
                logger.error('Access level check failed: unable to resolve caller')
                return False
            if hasattr(caller, 'check_access_level'):
                if not caller.check_access_level(level):
                    logger.warning(f'Insufficient access level: {caller.username} Attempted operation requires {level}-level operation')
                    return False
            else:
                logger.error('Access level check failed: caller has no check_access_level method')
                return False
            return func(*args, **kwargs)
        return wrapper
    return decorator

def require_any_permission(permissions: List[str]):
    """
    任意权限验证装饰器（满足其中一个即可）
    
    Args:
        permissions: 权限列表，满足其中一个即可
        
    Usage:
        @require_any_permission(['user.create', 'user.edit'])
        def user_management_function(self):
            pass
    """

    def decorator(func: Callable) -> Callable:

        @wraps(func)
        def wrapper(*args, **kwargs):
            caller = args[0] if args else None
            if not caller:
                logger.error('Permission check failed: unable to resolve caller')
                return False
            if hasattr(caller, 'check_permission'):
                for permission in permissions:
                    if caller.check_permission(permission):
                        return func(*args, **kwargs)
                logger.warning(f'Insufficient permission: {caller.username} Attempted operation requiring one of the following permissions: {permissions}')
                return False
            else:
                logger.error('Permission check failed: caller has no check_permission method')
                return False
        return wrapper
    return decorator

def require_all_permissions(permissions: List[str]):
    """
    所有权限验证装饰器（必须满足所有权限）
    
    Args:
        permissions: 权限列表，必须满足所有权限
        
    Usage:
        @require_all_permissions(['user.create', 'user.edit'])
        def full_user_management_function(self):
            pass
    """

    def decorator(func: Callable) -> Callable:

        @wraps(func)
        def wrapper(*args, **kwargs):
            caller = args[0] if args else None
            if not caller:
                logger.error('Permission check failed: unable to resolve caller')
                return False
            if hasattr(caller, 'check_permission'):
                for permission in permissions:
                    if not caller.check_permission(permission):
                        logger.warning(f'Insufficient permission: {caller.username} missing permission {permission}')
                        return False
                return func(*args, **kwargs)
            else:
                logger.error('Permission check failed: caller has no check_permission method')
                return False
        return wrapper
    return decorator

class PermissionGuard:
    """
    权限守卫类
    
    用于在运行时动态检查权限
    """

    def __init__(self, caller):
        self.caller = caller

    def check_permission(self, permission: str) -> bool:
        """检查权限"""
        if not self.caller:
            return False
        if hasattr(self.caller, 'check_permission'):
            return self.caller.check_permission(permission)
        return False

    def check_role(self, role: str) -> bool:
        """检查角色"""
        if not self.caller:
            return False
        if hasattr(self.caller, 'check_role'):
            return self.caller.check_role(role)
        return False

    def check_access_level(self, level: str) -> bool:
        """检查访问级别"""
        if not self.caller:
            return False
        if hasattr(self.caller, 'check_access_level'):
            return self.caller.check_access_level(level)
        return False

    def require_permission(self, permission: str) -> bool:
        """要求权限（抛出异常）"""
        if not self.check_permission(permission):
            self.logger.warning(f'Permission denied: requires permission {permission}')
            raise PermissionError(f'Permission denied: requires permission {permission}')
        return True

    def require_role(self, role: str) -> bool:
        """要求角色（抛出异常）"""
        if not self.check_role(role):
            self.logger.warning(f'Role denied: requires role {role}')
            raise PermissionError(f'Role denied: requires role {role}')
        return True

    def require_access_level(self, level: str) -> bool:
        """要求访问级别（抛出异常）"""
        if not self.check_access_level(level):
            self.logger.warning(f'Access level denied: requires level {level}')
            raise PermissionError(f'Access level denied: requires level {level}')
        return True

def create_permission_guard(caller) -> PermissionGuard:
    """
    创建权限守卫实例
    
    Args:
        caller: 调用者对象
        
    Returns:
        PermissionGuard实例
    """
    return PermissionGuard(caller)

def require_admin(func: Callable) -> Callable:
    """要求管理员权限"""
    return require_role('admin')(func)

def require_developer(func: Callable) -> Callable:
    """要求开发者权限"""
    return require_role('dev')(func)

def require_moderator(func: Callable) -> Callable:
    """要求版主权限"""
    return require_role('moderator')(func)

def require_user(func: Callable) -> Callable:
    """要求用户权限"""
    return require_role('user')(func)

def require_system_management(func: Callable) -> Callable:
    """要求系统管理权限"""
    return require_permission('system.manage')(func)

def require_user_management(func: Callable) -> Callable:
    """要求用户管理权限"""
    return require_permission('user.manage')(func)

def require_campus_management(func: Callable) -> Callable:
    """要求园区管理权限"""
    return require_permission('campus.manage')(func)

def require_world_management(func: Callable) -> Callable:
    """要求世界管理权限"""
    return require_permission('world.manage')(func)

def require_debug_mode(func: Callable) -> Callable:
    """要求调试模式权限"""
    return require_permission('system.debug')(func)

def require_test_mode(func: Callable) -> Callable:
    """要求测试模式权限"""
    return require_permission('system.test')(func)

def require_development(func: Callable) -> Callable:
    """要求开发权限"""
    return require_permission('system.develop')(func)

def require_logs_view(func: Callable) -> Callable:
    """要求日志查看权限"""
    return require_permission('logs.view')(func)

def require_logs_management(func: Callable) -> Callable:
    """要求日志管理权限"""
    return require_permission('logs.manage')(func)
