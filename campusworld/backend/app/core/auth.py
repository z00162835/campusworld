"""
权限验证和认证系统

参考Evennia框架设计，提供权限验证装饰器
集成到命令系统和API接口

作者：AI Assistant
创建时间：2025-08-24
"""

from typing import List, Optional, Callable, Any, Union
from functools import wraps
import logging
from datetime import datetime

from .permissions import permission_checker, Role, Permission

logger = logging.getLogger(__name__)


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
            # 获取调用者（通常是self或第一个参数）
            caller = args[0] if args else None
            
            if not caller:
                logger.error("权限检查失败: 无法获取调用者")
                return False
            
            # 检查权限
            if hasattr(caller, 'check_permission'):
                if not caller.check_permission(permission):
                    logger.warning(f"权限不足: {caller.username} 尝试执行 {permission}")
                    return False
            else:
                logger.error("权限检查失败: 调用者没有check_permission方法")
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
            # 获取调用者
            caller = args[0] if args else None
            
            if not caller:
                logger.error("角色检查失败: 无法获取调用者")
                return False
            
            # 检查角色
            if hasattr(caller, 'check_role'):
                if not caller.check_role(role):
                    logger.warning(f"角色不足: {caller.username} 尝试执行需要 {role} 角色的操作")
                    return False
            else:
                logger.error("角色检查失败: 调用者没有check_role方法")
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
            # 获取调用者
            caller = args[0] if args else None
            
            if not caller:
                logger.error("访问级别检查失败: 无法获取调用者")
                return False
            
            # 检查访问级别
            if hasattr(caller, 'check_access_level'):
                if not caller.check_access_level(level):
                    logger.warning(f"访问级别不足: {caller.username} 尝试执行需要 {level} 级别的操作")
                    return False
            else:
                logger.error("访问级别检查失败: 调用者没有check_access_level方法")
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
            # 获取调用者
            caller = args[0] if args else None
            
            if not caller:
                logger.error("权限检查失败: 无法获取调用者")
                return False
            
            # 检查是否有任意一个权限
            if hasattr(caller, 'check_permission'):
                for permission in permissions:
                    if caller.check_permission(permission):
                        return func(*args, **kwargs)
                
                logger.warning(f"权限不足: {caller.username} 尝试执行需要以下权限之一的操作: {permissions}")
                return False
            else:
                logger.error("权限检查失败: 调用者没有check_permission方法")
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
            # 获取调用者
            caller = args[0] if args else None
            
            if not caller:
                logger.error("权限检查失败: 无法获取调用者")
                return False
            
            # 检查是否满足所有权限
            if hasattr(caller, 'check_permission'):
                for permission in permissions:
                    if not caller.check_permission(permission):
                        logger.warning(f"权限不足: {caller.username} 缺少权限 {permission}")
                        return False
                
                return func(*args, **kwargs)
            else:
                logger.error("权限检查失败: 调用者没有check_permission方法")
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
            raise PermissionError(f"权限不足: 需要权限 {permission}")
        return True
    
    def require_role(self, role: str) -> bool:
        """要求角色（抛出异常）"""
        if not self.check_role(role):
            raise PermissionError(f"角色不足: 需要角色 {role}")
        return True
    
    def require_access_level(self, level: str) -> bool:
        """要求访问级别（抛出异常）"""
        if not self.check_access_level(level):
            raise PermissionError(f"访问级别不足: 需要级别 {level}")
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


# 常用权限组合装饰器
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
    """要求校园管理权限"""
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
