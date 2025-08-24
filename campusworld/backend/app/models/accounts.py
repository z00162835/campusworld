"""
账号类型模型定义

参考Evennia框架设计，提供不同类型的账号类
支持管理员、开发者和普通用户三种账号类型

作者：AI Assistant
创建时间：2025-08-24
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from .base import DefaultAccount
from app.core.permissions import Role, Permission


class AdminAccount(DefaultAccount):
    """
    管理员账号类
    
    拥有系统管理权限，可以管理用户、校园、世界等
    角色：admin
    权限：所有管理权限
    """
    
    def __init__(self, username: str, email: str, **kwargs):
        # 设置管理员默认属性
        admin_attrs = {
            'roles': ['admin'],
            'permissions': [
                'user.*',      # 用户管理所有权限
                'campus.*',    # 校园管理所有权限
                'world.*',     # 世界管理所有权限
                'system.*',    # 系统管理所有权限
                'admin.*',     # 管理员所有权限
            ],
            'access_level': 'admin',
            'is_verified': True,
            'max_failed_attempts': 10,  # 管理员账号更宽松的限制
            'created_by': kwargs.get('created_by', 'system'),
            **kwargs
        }
        
        super().__init__(username=username, email=email, **admin_attrs)
    
    def can_manage_user(self, target_user: 'DefaultAccount') -> bool:
        """检查是否可以管理指定用户"""
        # 管理员不能管理其他管理员或所有者
        if 'admin' in target_user.roles or 'owner' in target_user.roles:
            return False
        return True
    
    def can_manage_campus(self, campus) -> bool:
        """检查是否可以管理指定校园"""
        return True  # 管理员可以管理所有校园
    
    def can_manage_world(self, world) -> bool:
        """检查是否可以管理指定世界"""
        return True  # 管理员可以管理所有世界
    
    def get_admin_dashboard_data(self) -> Dict[str, Any]:
        """获取管理员仪表板数据"""
        return {
            'username': self.username,
            'role': 'admin',
            'permissions': self.permissions,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'system_status': 'active',
            'can_manage_users': True,
            'can_manage_campus': True,
            'can_manage_world': True,
            'can_manage_system': True,
        }


class DeveloperAccount(DefaultAccount):
    """
    开发者账号类
    
    拥有开发和调试权限，可以进行功能开发和测试
    角色：dev
    权限：开发相关权限
    """
    
    def __init__(self, username: str, email: str, **kwargs):
        # 设置开发者默认属性
        dev_attrs = {
            'roles': ['dev'],
            'permissions': [
                'user.view',           # 查看用户
                'campus.view',         # 查看校园
                'campus.edit',         # 编辑校园
                'campus.manage',       # 管理校园
                'world.view',          # 查看世界
                'world.edit',          # 编辑世界
                'world.manage',        # 管理世界
                'system.view',         # 查看系统
                'system.debug',        # 调试模式
                'system.test',         # 测试模式
                'system.develop',      # 开发功能
                'logs.view',           # 查看日志
            ],
            'access_level': 'developer',
            'is_verified': True,
            'max_failed_attempts': 8,  # 开发者账号适中的限制
            'created_by': kwargs.get('created_by', 'admin'),
            **kwargs
        }
        
        super().__init__(username=username, email=email, **dev_attrs)
    
    def can_develop_features(self) -> bool:
        """检查是否可以开发新功能"""
        return self.has_permission('system.develop')
    
    def can_access_debug_mode(self) -> bool:
        """检查是否可以访问调试模式"""
        return self.has_permission('system.debug')
    
    def can_run_tests(self) -> bool:
        """检查是否可以运行测试"""
        return self.has_permission('system.test')
    
    def can_view_logs(self) -> bool:
        """检查是否可以查看日志"""
        return self.has_permission('logs.view')
    
    def get_dev_dashboard_data(self) -> Dict[str, Any]:
        """获取开发者仪表板数据"""
        return {
            'username': self.username,
            'role': 'dev',
            'permissions': self.permissions,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'can_develop': self.can_develop_features(),
            'can_debug': self.can_access_debug_mode(),
            'can_test': self.can_run_tests(),
            'can_view_logs': self.can_view_logs(),
        }


class UserAccount(DefaultAccount):
    """
    普通用户账号类
    
    拥有基本的用户权限，可以访问校园和世界
    角色：user
    权限：基本用户权限
    """
    
    def __init__(self, username: str, email: str, **kwargs):
        # 设置普通用户默认属性
        user_attrs = {
            'roles': ['user'],
            'permissions': [
                'user.login',          # 登录
                'user.logout',         # 登出
                'user.view_profile',   # 查看个人资料
                'user.edit_profile',   # 编辑个人资料
                'campus.view',         # 查看校园
                'world.view',          # 查看世界
            ],
            'access_level': 'normal',
            'is_verified': False,      # 普通用户需要验证
            'max_failed_attempts': 5,  # 普通用户标准限制
            'created_by': kwargs.get('created_by', 'system'),
            **kwargs
        }
        
        super().__init__(username=username, email=email, **user_attrs)
    
    def can_view_campus(self, campus) -> bool:
        """检查是否可以查看指定校园"""
        return self.has_permission('campus.view')
    
    def can_view_world(self, world) -> bool:
        """检查是否可以查看指定世界"""
        return self.has_permission('world.view')
    
    def can_edit_profile(self) -> bool:
        """检查是否可以编辑个人资料"""
        return self.has_permission('user.edit_profile')
    
    def get_user_dashboard_data(self) -> Dict[str, Any]:
        """获取用户仪表板数据"""
        return {
            'username': self.username,
            'role': 'user',
            'permissions': self.permissions,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'is_verified': self.is_verified,
            'can_view_campus': self.can_view_campus(None),
            'can_view_world': self.can_view_world(None),
            'can_edit_profile': self.can_edit_profile(),
        }


class CampusUserAccount(UserAccount):
    """
    校园用户账号类
    
    继承自普通用户，专门用于校园场景
    可以加入校园、参与校园活动等
    """
    
    def __init__(self, username: str, email: str, **kwargs):
        # 设置校园用户默认属性
        campus_attrs = {
            'roles': ['user', 'campus_user'],
            'permissions': [
                'user.login',          # 登录
                'user.logout',         # 登出
                'user.view_profile',   # 查看个人资料
                'user.edit_profile',   # 编辑个人资料
                'campus.view',         # 查看校园
                'campus.join',         # 加入校园
                'campus.leave',        # 离开校园
                'campus.participate',  # 参与校园活动
                'world.view',          # 查看世界
            ],
            'campus_memberships': [],  # 校园成员关系
            'campus_activities': [],   # 校园活动参与记录
            **kwargs
        }
        
        super().__init__(username=username, email=email, **campus_attrs)
    
    def join_campus(self, campus, role: str = "member") -> bool:
        """加入校园"""
        try:
            # 创建校园成员关系
            relationship = self.create_relationship(
                target=campus,
                rel_type="campus_member",
                role=role,
                joined_at=datetime.now()
            )
            
            if relationship:
                # 更新本地成员关系列表
                memberships = self._node_attributes.get('campus_memberships', [])
                memberships.append({
                    'campus_id': campus.id if hasattr(campus, 'id') else None,
                    'campus_name': campus.name if hasattr(campus, 'name') else 'Unknown',
                    'role': role,
                    'joined_at': datetime.now().isoformat()
                })
                self._node_attributes['campus_memberships'] = memberships
                self._schedule_node_sync()
                return True
            
            return False
            
        except Exception as e:
            print(f"加入校园失败: {e}")
            return False
    
    def leave_campus(self, campus) -> bool:
        """离开校园"""
        try:
            # 移除校园成员关系
            success = self.remove_relationship(campus, "campus_member")
            
            if success:
                # 更新本地成员关系列表
                memberships = self._node_attributes.get('campus_memberships', [])
                campus_id = campus.id if hasattr(campus, 'id') else None
                memberships = [m for m in memberships if m.get('campus_id') != campus_id]
                self._node_attributes['campus_memberships'] = memberships
                self._schedule_node_sync()
                return True
            
            return False
            
        except Exception as e:
            print(f"离开校园失败: {e}")
            return False
    
    def get_campus_memberships(self) -> List[Dict[str, Any]]:
        """获取校园成员关系列表"""
        return self._node_attributes.get('campus_memberships', [])
    
    def is_campus_member(self, campus) -> bool:
        """检查是否是校园成员"""
        memberships = self.get_campus_memberships()
        campus_id = campus.id if hasattr(campus, 'id') else None
        return any(m.get('campus_id') == campus_id for m in memberships)
    
    def get_campus_role(self, campus) -> Optional[str]:
        """获取在指定校园中的角色"""
        memberships = self.get_campus_memberships()
        campus_id = campus.id if hasattr(campus, 'id') else None
        for membership in memberships:
            if membership.get('campus_id') == campus_id:
                return membership.get('role', 'guest')
        return None


# 账号类型映射
ACCOUNT_TYPES = {
    'admin': AdminAccount,
    'dev': DeveloperAccount,
    'user': UserAccount,
    'campus_user': CampusUserAccount,
}


def create_account(account_type: str, username: str, email: str, **kwargs) -> DefaultAccount:
    """
    创建指定类型的账号
    
    Args:
        account_type: 账号类型 (admin, dev, user, campus_user)
        username: 用户名
        email: 邮箱
        **kwargs: 其他参数
        
    Returns:
        创建的账号实例
    """
    if account_type not in ACCOUNT_TYPES:
        raise ValueError(f"不支持的账号类型: {account_type}")
    
    account_class = ACCOUNT_TYPES[account_type]
    return account_class(username=username, email=email, **kwargs)


def get_account_class(account_type: str):
    """获取指定类型的账号类"""
    return ACCOUNT_TYPES.get(account_type)
