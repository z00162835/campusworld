"""
基础模型定义 - 纯图数据设计

采用纯图数据设计方式，所有对象都存储在Node中
通过type和typeclass来区分不同的对象类型
"""

from typing import Dict, Any, List, Optional, Type, Union
from abc import ABC, abstractmethod
import uuid
import time
from datetime import datetime


# ==================== 图节点接口定义 ====================

class GraphNodeInterface(ABC):
    """
    图节点接口
    
    定义所有图节点必须实现的方法
    """
    
    @abstractmethod
    def get_node_uuid(self) -> str:
        """获取节点UUID"""
        pass
    
    @abstractmethod
    def get_node_type(self) -> str:
        """获取节点类型"""
        pass
    
    @abstractmethod
    def get_node_typeclass(self) -> str:
        """获取节点类型类"""
        pass
    
    @abstractmethod
    def get_node_attributes(self) -> Dict[str, Any]:
        """获取节点属性"""
        pass
    
    @abstractmethod
    def set_node_attribute(self, key: str, value: Any) -> None:
        """设置节点属性"""
        pass
    
    @abstractmethod
    def get_node_tags(self) -> List[str]:
        """获取节点标签"""
        pass
    
    @abstractmethod
    def add_node_tag(self, tag: str) -> None:
        """添加节点标签"""
        pass
    
    @abstractmethod
    def remove_node_tag(self, tag: str) -> None:
        """移除节点标签"""
        pass
    
    @abstractmethod
    def sync_to_node(self) -> None:
        """同步到图节点系统"""
        pass


# ==================== 图关系接口定义 ====================

class GraphRelationshipInterface(ABC):
    """
    图关系接口
    
    定义所有图关系必须实现的方法
    """
    
    @abstractmethod
    def get_relationship_type(self) -> str:
        """获取关系类型"""
        pass
    
    @abstractmethod
    def get_relationship_attributes(self) -> Dict[str, Any]:
        """获取关系属性"""
        pass
    
    @abstractmethod
    def set_relationship_attribute(self, key: str, value: Any) -> None:
        """设置关系属性"""
        pass


# ==================== 基础对象类 ====================

class DefaultObject(GraphNodeInterface):
    """
    默认对象基类 - 纯图数据设计
    
    所有对象都存储在Node中，通过type和typeclass区分
    不再有独立的数据库表，完全依赖图节点系统
    集成命令系统，支持命令执行和管理
    """
    
    def __init__(self, name: str, **kwargs):
        # 设置节点类型和类型类
        self._node_type = self.__class__.__name__.lower()  # 如: 'campus', 'user'
        self._node_typeclass = f"{self.__class__.__module__}.{self.__class__.__name__}"
        
        # 设置独立的name字段（对应数据库nodes表的name字段）
        self._node_name = name
        
        # 所有其他属性都存储在Node的attributes中（不包含name）
        self._node_attributes = {
            'type': self._node_type,
            'typeclass': self._node_typeclass,
            'is_active': True,
            'is_public': True,
            'access_level': 'normal',
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            **kwargs
        }
        
        # 自动生成UUID
        self._node_uuid = str(uuid.uuid4())
        
        # 命令系统相关属性
        self._cmdset = None
        self._command_history = []
        self._max_command_history = 100
        
        # 自动同步到Node表
        self._schedule_node_sync()
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(uuid='{self._node_uuid}', name='{self._node_name}', type='{self._node_type}')>"
    
    # ==================== 图节点接口实现 ====================
    
    def get_node_uuid(self) -> str:
        """获取节点UUID"""
        return self._node_uuid
    
    def get_node_type(self) -> str:
        """获取节点类型"""
        return self._node_type
    
    def get_node_typeclass(self) -> str:
        """获取节点类型类"""
        return self._node_typeclass
    
    def get_node_name(self) -> str:
        """获取节点名称"""
        return self._node_name
    
    def set_node_name(self, name: str) -> None:
        """设置节点名称"""
        self._node_name = name
        self._schedule_node_sync()
    
    def get_node_attributes(self) -> Dict[str, Any]:
        """获取节点属性"""
        return self._node_attributes.copy()
    
    def get_node_attribute(self, key: str, default: Any = None) -> Any:
        """获取节点属性值"""
        return self._node_attributes.get(key, default)
    
    def set_node_attribute(self, key: str, value: Any) -> None:
        """设置节点属性"""
        # 不允许设置name属性，name应该通过set_node_name方法设置
        if key == 'name':
            raise ValueError("不能直接设置name属性，请使用set_node_name方法")
        
        self._node_attributes[key] = value
        self._node_attributes['updated_at'] = datetime.now()
        self._schedule_node_sync()
    
    def get_node_tags(self) -> List[str]:
        """获取节点标签"""
        return self._node_attributes.get('tags', [])
    
    def add_node_tag(self, tag: str) -> None:
        """添加节点标签"""
        tags = self._node_attributes.get('tags', [])
        if tag not in tags:
            tags.append(tag)
            self._node_attributes['tags'] = tags
            self._schedule_node_sync()
    
    def remove_node_tag(self, tag: str) -> None:
        """移除节点标签"""
        tags = self._node_attributes.get('tags', [])
        if tag in tags:
            tags.remove(tag)
            self._node_attributes['tags'] = tags
            self._schedule_node_sync()
    
    def sync_to_node(self) -> None:
        """同步到图节点系统"""
        try:
            from app.models.graph_sync import GraphSynchronizer
            synchronizer = GraphSynchronizer()
            synchronizer.sync_object_to_node(self)
        except Exception as e:
            # 记录同步错误，但不中断对象操作
            print(f"图节点同步失败: {e}")
    
    # ==================== 图节点管理方法 ====================
    
    def _schedule_node_sync(self) -> None:
        """调度图节点同步"""
        # 在实际应用中，这里可以使用异步任务队列
        # 目前使用简单的延迟同步
        import threading
        def delayed_sync():
            time.sleep(0.1)  # 延迟100ms
            self.sync_to_node()
        
        thread = threading.Thread(target=delayed_sync)
        thread.daemon = True
        thread.start()
    
    @classmethod
    def get_node_type(cls) -> str:
        """获取类的节点类型"""
        return cls.__name__.lower()
    
    @classmethod
    def get_node_typeclass(cls) -> str:
        """获取类的节点类型类"""
        return f"{cls.__module__}.{cls.__name__}"
    
    # ==================== 命令系统集成 ====================
    
    def get_cmdset(self):
        """获取命令集合"""
        if self._cmdset is None:
            # 延迟初始化命令集合
            self._init_default_cmdset()
        return self._cmdset
    
    def set_cmdset(self, cmdset):
        """设置命令集合"""
        self._cmdset = cmdset
    
    def _init_default_cmdset(self):
        """初始化默认命令集合"""
        try:
            from app.commands.base import CmdSet
            # 创建空的命令集合，子类可以重写此方法添加特定命令
            self._cmdset = CmdSet()
        except ImportError:
            # 如果命令系统不可用，创建空的命令集合
            self._cmdset = None
    
    def execute_command(self, command_string: str, caller=None, **kwargs) -> Dict[str, Any]:
        """
        执行命令
        
        Args:
            command_string: 命令字符串
            caller: 命令调用者
            **kwargs: 其他参数
            
        Returns:
            执行结果字典
        """
        try:
            from app.commands.base import CommandExecutor
            
            # 获取命令集合
            cmdset = self.get_cmdset()
            if not cmdset:
                return {
                    'success': False,
                    'error': '命令集合未初始化',
                    'command': command_string
                }
            
            # 创建命令执行器
            executor = CommandExecutor(default_cmdset=cmdset)
            
            # 执行命令
            results = executor.execute_command_string(command_string, caller=caller, **kwargs)
            
            # 处理执行结果（可能包含多个命令）
            if not results:
                error_result = {
                    'success': False,
                    'error': '命令执行失败，无结果返回',
                    'command': command_string
                }
                self._add_command_to_history(command_string, error_result)
                return error_result
            
            # 如果只有一个结果，直接返回
            if len(results) == 1:
                result = results[0]
                self._add_command_to_history(command_string, result)
                return result
            
            # 如果有多个结果，合并为一个
            combined_result = {
                'success': all(r.get('success', False) for r in results),
                'command': command_string,
                'results': results,
                'result_count': len(results)
            }
            
            # 检查是否有错误
            errors = [r.get('error') for r in results if r.get('error')]
            if errors:
                combined_result['error'] = f"多个错误: {'; '.join(errors)}"
            
            self._add_command_to_history(command_string, combined_result)
            return combined_result
            
        except Exception as e:
            error_result = {
                'success': False,
                'error': str(e),
                'command': command_string
            }
            self._add_command_to_history(command_string, error_result)
            return error_result
    
    def _add_command_to_history(self, command: str, result: Dict[str, Any]):
        """添加命令到历史记录"""
        history_entry = {
            'command': command,
            'timestamp': datetime.now(),
            'result': result,
            'success': result.get('success', False)
        }
        
        self._command_history.append(history_entry)
        
        # 限制历史记录数量
        if len(self._command_history) > self._max_command_history:
            self._command_history.pop(0)
    
    def get_command_history(self, limit: int = None) -> List[Dict[str, Any]]:
        """获取命令历史记录"""
        if limit is None:
            return self._command_history.copy()
        else:
            return self._command_history[-limit:]
    
    def clear_command_history(self):
        """清除命令历史记录"""
        self._command_history.clear()
    
    def has_command(self, command_key: str) -> bool:
        """检查是否有指定命令"""
        cmdset = self.get_cmdset()
        if not cmdset:
            return False
        return cmdset.has_command(command_key)
    
    def get_available_commands(self) -> List[str]:
        """获取可用命令列表"""
        cmdset = self.get_cmdset()
        if not cmdset:
            return []
        return list(cmdset.get_commands().keys())
    
    def get_commands_by_category(self, category: str) -> List[str]:
        """根据分类获取命令"""
        cmdset = self.get_cmdset()
        if not cmdset:
            return []
        return cmdset.get_commands_by_category(category)
    
    # ==================== 权限管理方法 ====================
    
    def has_role(self, role: str) -> bool:
        """检查是否有指定角色"""
        roles = self._node_attributes.get('roles', [])
        return role in roles
    
    def has_permission(self, permission: str) -> bool:
        """检查是否有指定权限"""
        permissions = self._node_attributes.get('permissions', [])
        return permission in permissions
    
    def add_role(self, role: str) -> None:
        """添加角色"""
        roles = self._node_attributes.get('roles', [])
        if role not in roles:
            roles.append(role)
            self._node_attributes['roles'] = roles
            self._schedule_node_sync()
    
    def remove_role(self, role: str) -> None:
        """移除角色"""
        roles = self._node_attributes.get('roles', [])
        if role in roles:
            roles.remove(role)
            self._node_attributes['roles'] = roles
            self._schedule_node_sync()
    
    def add_permission(self, permission: str) -> None:
        """添加权限"""
        permissions = self._node_attributes.get('permissions', [])
        if permission not in permissions:
            permissions.append(permission)
            self._node_attributes['permissions'] = permissions
            self._schedule_node_sync()
    
    def remove_permission(self, permission: str) -> None:
        """移除权限"""
        permissions = self._node_attributes.get('permissions', [])
        if permission in permissions:
            permissions.remove(permission)
            self._node_attributes['permissions'] = permissions
            self._schedule_node_sync()
    
    def check_permission(self, required_permission: str) -> bool:
        """检查权限（支持层级权限）"""
        if not self.has_permission(required_permission):
            return False
        
        # 层级权限检查（例如：admin 包含 user 权限）
        permission_hierarchy = {
            "user": 1,
            "moderator": 2,
            "admin": 3,
            "owner": 4
        }
        
        user_level = max(permission_hierarchy.get(perm, 0) for perm in self._node_attributes.get('permissions', []))
        required_level = permission_hierarchy.get(required_permission, 0)
        
        return user_level >= required_level
    
    # ==================== 属性访问器 ====================
    
    @property
    def id(self) -> Optional[int]:
        """获取节点ID（从Node中获取）"""
        try:
            from app.models.graph_sync import GraphSynchronizer
            synchronizer = GraphSynchronizer()
            node = synchronizer.get_node_by_uuid(self._node_uuid)
            return node.id if node else None
        except:
            return None
    
    @property
    def name(self) -> str:
        """获取名称"""
        return self._node_name
    
    @name.setter
    def name(self, value: str):
        """设置名称"""
        self.set_node_name(value)
    
    @property
    def description(self) -> str:
        """获取描述"""
        return self._node_attributes.get('description', '')
    
    @description.setter
    def description(self, value: str):
        """设置描述"""
        self.set_node_attribute('description', value)
    
    @property
    def is_active(self) -> bool:
        """获取是否活跃"""
        return self._node_attributes.get('is_active', True)
    
    @is_active.setter
    def is_active(self, value: bool):
        """设置是否活跃"""
        self.set_node_attribute('is_active', value)
    
    @property
    def is_public(self) -> bool:
        """获取是否公开"""
        return self._node_attributes.get('is_public', True)
    
    @is_public.setter
    def is_public(self, value: bool):
        """设置是否公开"""
        self.set_node_attribute('is_public', value)
    
    @property
    def access_level(self) -> str:
        """获取访问级别"""
        return self._node_attributes.get('access_level', 'normal')
    
    @access_level.setter
    def access_level(self, value: str):
        """设置访问级别"""
        self.set_node_attribute('access_level', value)
    
    @property
    def created_at(self):
        """获取创建时间"""
        return self._node_attributes.get('created_at')
    
    @property
    def updated_at(self):
        """获取更新时间"""
        return self._node_attributes.get('updated_at')
    
    # ==================== 位置管理 ====================
    
    @property
    def location_id(self) -> Optional[int]:
        """获取位置ID"""
        return self._node_attributes.get('location_id')
    
    @location_id.setter
    def location_id(self, value: Optional[int]):
        """设置位置ID"""
        self.set_node_attribute('location_id', value)
    
    @property
    def home_id(self) -> Optional[int]:
        """获取默认位置ID"""
        return self._node_attributes.get('home_id')
    
    @home_id.setter
    def home_id(self, value: Optional[int]):
        """设置默认位置ID"""
        self.set_node_attribute('home_id', value)
    
    def move_to(self, new_location: 'DefaultObject') -> bool:
        """移动到新位置"""
        if new_location and new_location.is_active:
            self.location_id = new_location.id
            return True
        return False
    
    def go_home(self) -> bool:
        """回到默认位置"""
        if self.home_id:
            self.location_id = self.home_id
            return True
        return False
    
    # ==================== 属性管理 ====================
    
    def get_attribute(self, key: str, default: Any = None) -> Any:
        """获取属性（从图节点属性获取）"""
        return self._node_attributes.get(key, default)
    
    def set_attribute(self, key: str, value: Any) -> None:
        """设置属性（设置到图节点属性）"""
        self.set_node_attribute(key, value)
    
    def has_attribute(self, key: str) -> bool:
        """检查是否有指定属性"""
        return key in self._node_attributes
    
    def remove_attribute(self, key: str) -> bool:
        """移除属性"""
        if key in self._node_attributes:
            del self._node_attributes[key]
            self._schedule_node_sync()
            return True
        return False
    
    # ==================== 标签管理 ====================
    
    def has_tag(self, tag: str) -> bool:
        """检查是否有指定标签"""
        tags = self._node_attributes.get('tags', [])
        return tag in tags
    
    def get_all_tags(self) -> List[str]:
        """获取所有标签"""
        return self._node_attributes.get('tags', []).copy()
    
    def clear_tags(self) -> None:
        """清除所有标签"""
        self._node_attributes['tags'] = []
        self._schedule_node_sync()
    
    # ==================== 关系管理 ====================
    
    def create_relationship(self, target: 'DefaultObject', rel_type: str, **attributes) -> 'GraphRelationship':
        """创建关系"""
        try:
            from app.models.graph_sync import GraphSynchronizer
            synchronizer = GraphSynchronizer()
            return synchronizer.create_relationship(self, target, rel_type, **attributes)
        except Exception as e:
            print(f"创建关系失败: {e}")
            return None
    
    def get_relationships(self, rel_type: str = None) -> List['GraphRelationship']:
        """获取关系"""
        try:
            from app.models.graph_sync import GraphSynchronizer
            synchronizer = GraphSynchronizer()
            return synchronizer.get_object_relationships(self, rel_type)
        except Exception as e:
            print(f"获取关系失败: {e}")
            return []
    
    def remove_relationship(self, target: 'DefaultObject', rel_type: str) -> bool:
        """移除关系"""
        try:
            from app.models.graph_sync import GraphSynchronizer
            synchronizer = GraphSynchronizer()
            return synchronizer.remove_relationship(self, target, rel_type)
        except Exception as e:
            print(f"移除关系失败: {e}")
            return False


class DefaultAccount(DefaultObject):
    """
    默认账户基类 - 纯图数据设计
    
    继承自DefaultObject，提供用户账户相关功能
    所有数据都存储在Node中，type为'account'
    集成命令系统，支持用户命令执行
    集成权限系统，支持角色和权限管理
    """
    
    def __init__(self, username: str, email: str, **kwargs):
        # 设置账户特定的节点类型
        self._node_type = 'account'
        
        # 设置账户默认属性
        account_attrs = {
            'username': username,
            'email': email,
            'is_verified': False,
            'is_locked': False,
            'is_suspended': False,
            'login_count': 0,
            'failed_login_attempts': 0,
            'max_failed_attempts': 5,
            'roles': ['user'],
            'permissions': [],
            'hashed_password': kwargs.get('hashed_password', ''),
            'last_login': None,
            'last_activity': None,
            'lock_reason': None,
            'suspension_reason': None,
            'suspension_until': None,
            'created_by': kwargs.get('created_by', 'system'),
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            **kwargs
        }
        
        super().__init__(name=username, **account_attrs)
    
    def _init_default_cmdset(self):
        """初始化账户默认命令集合"""
        try:
            from app.commands.base import CmdSet
            from app.commands.system.cmdset import SystemCmdSet
            
            # 账户默认包含系统命令
            self._cmdset = SystemCmdSet()
            
        except ImportError:
            # 如果命令系统不可用，创建空的命令集合
            self._cmdset = None
    
    # ==================== 账户属性访问器 ====================
    
    @property
    def username(self) -> str:
        """获取用户名"""
        return self._node_attributes.get('username', '')
    
    @username.setter
    def username(self, value: str):
        """设置用户名"""
        self.set_node_attribute('username', value)
    
    @property
    def email(self) -> str:
        """获取邮箱"""
        return self._node_attributes.get('email', '')
    
    @email.setter
    def email(self, value: str):
        """设置邮箱"""
        self.set_node_attribute('email', value)
    
    @property
    def hashed_password(self) -> str:
        """获取哈希密码"""
        return self._node_attributes.get('hashed_password', '')
    
    @hashed_password.setter
    def hashed_password(self, value: str):
        """设置哈希密码"""
        self.set_node_attribute('hashed_password', value)
    
    @property
    def is_verified(self) -> bool:
        """获取是否已验证"""
        return self._node_attributes.get('is_verified', False)
    
    @is_verified.setter
    def is_verified(self, value: bool):
        """设置是否已验证"""
        self.set_node_attribute('is_verified', value)
    
    @property
    def is_locked(self) -> bool:
        """获取是否已锁定"""
        return self._node_attributes.get('is_locked', False)
    
    @is_locked.setter
    def is_locked(self, value: bool):
        """设置是否已锁定"""
        self.set_node_attribute('is_locked', value)
    
    @property
    def is_suspended(self) -> bool:
        """获取是否已暂停"""
        return self._node_attributes.get('is_suspended', False)
    
    @is_suspended.setter
    def is_suspended(self, value: bool):
        """设置是否已暂停"""
        self.set_node_attribute('is_suspended', value)
    
    @property
    def login_count(self) -> int:
        """获取登录次数"""
        return self._node_attributes.get('login_count', 0)
    
    @login_count.setter
    def login_count(self, value: int):
        """设置登录次数"""
        self.set_node_attribute('login_count', value)
    
    @property
    def failed_login_attempts(self) -> int:
        """获取失败登录次数"""
        return self._node_attributes.get('failed_login_attempts', 0)
    
    @failed_login_attempts.setter
    def failed_login_attempts(self, value: int):
        """设置失败登录次数"""
        self.set_node_attribute('failed_login_attempts', value)
    
    @property
    def max_failed_attempts(self) -> int:
        """获取最大失败登录次数"""
        return self._node_attributes.get('max_failed_attempts', 5)
    
    @max_failed_attempts.setter
    def max_failed_attempts(self, value: int):
        """设置最大失败登录次数"""
        self.set_node_attribute('max_failed_attempts', value)
    
    @property
    def roles(self) -> List[str]:
        """获取角色列表"""
        return self._node_attributes.get('roles', ['user'])
    
    @roles.setter
    def roles(self, value: List[str]):
        """设置角色列表"""
        self.set_node_attribute('roles', value)
    
    @property
    def permissions(self) -> List[str]:
        """获取权限列表"""
        return self._node_attributes.get('permissions', [])
    
    @permissions.setter
    def permissions(self, value: List[str]):
        """设置权限列表"""
        self.set_node_attribute('permissions', value)
    
    @property
    def last_login(self) -> Optional[datetime]:
        """获取最后登录时间"""
        last_login = self._node_attributes.get('last_login')
        if isinstance(last_login, str):
            try:
                return datetime.fromisoformat(last_login)
            except ValueError:
                return None
        return last_login
    
    @last_login.setter
    def last_login(self, value: Optional[datetime]):
        """设置最后登录时间"""
        if value is None:
            self.set_node_attribute('last_login', None)
        else:
            self.set_node_attribute('last_login', value.isoformat())
    
    @property
    def last_activity(self) -> Optional[datetime]:
        """获取最后活动时间"""
        last_activity = self._node_attributes.get('last_activity')
        if isinstance(last_activity, str):
            try:
                return datetime.fromisoformat(last_activity)
            except ValueError:
                return None
        return last_activity
    
    @last_activity.setter
    def last_activity(self, value: Optional[datetime]):
        """设置最后活动时间"""
        if value is None:
            self.set_node_attribute('last_activity', None)
        else:
            self.set_node_attribute('last_activity', value.isoformat())
    
    @property
    def lock_reason(self) -> Optional[str]:
        """获取锁定原因"""
        return self._node_attributes.get('lock_reason')
    
    @lock_reason.setter
    def lock_reason(self, value: Optional[str]):
        """设置锁定原因"""
        self.set_node_attribute('lock_reason', value)
    
    @property
    def suspension_reason(self) -> Optional[str]:
        """获取暂停原因"""
        return self._node_attributes.get('suspension_reason')
    
    @suspension_reason.setter
    def suspension_reason(self, value: Optional[str]):
        """设置暂停原因"""
        self.set_node_attribute('suspension_reason', value)
    
    @property
    def suspension_until(self) -> Optional[datetime]:
        """获取暂停截止时间"""
        suspension_until = self._node_attributes.get('suspension_until')
        if isinstance(suspension_until, str):
            try:
                return datetime.fromisoformat(suspension_until)
            except ValueError:
                return None
        return suspension_until
    
    @suspension_until.setter
    def suspension_until(self, value: Optional[datetime]):
        """设置暂停截止时间"""
        if value is None:
            self.set_node_attribute('suspension_until', None)
        else:
            self.set_node_attribute('suspension_until', value.isoformat())
    
    # ==================== 账户管理方法 ====================
    
    def add_role(self, role: str) -> None:
        """添加角色"""
        roles = self.roles.copy()
        if role not in roles:
            roles.append(role)
            self.roles = roles
            self._schedule_node_sync()
    
    def remove_role(self, role: str) -> None:
        """移除角色"""
        roles = self.roles.copy()
        if role in roles:
            roles.remove(role)
            self.roles = roles
            self._schedule_node_sync()
    
    def has_role(self, role: str) -> bool:
        """检查是否有指定角色"""
        return role in self.roles
    
    def add_permission(self, permission: str) -> None:
        """添加权限"""
        permissions = self.permissions.copy()
        if permission not in permissions:
            permissions.append(permission)
            self.permissions = permissions
            self._schedule_node_sync()
    
    def remove_permission(self, permission: str) -> None:
        """移除权限"""
        permissions = self.permissions.copy()
        if permission in permissions:
            permissions.remove(permission)
            self.permissions = permissions
            self._schedule_node_sync()
    
    def has_permission(self, permission: str) -> bool:
        """检查是否有指定权限"""
        return permission in self.permissions
    
    def check_permission(self, required_permission: str) -> bool:
        """检查权限（支持层级权限）"""
        if not self.permissions:
            return False
        
        # 直接权限检查
        if required_permission in self.permissions:
            return True
        
        # 通配符权限检查
        for perm in self.permissions:
            if perm == "*" or perm == "all":  # 超级权限
                return True
            if perm.endswith(".*") and required_permission.startswith(perm[:-1]):
                return True
        
        # 角色权限检查
        from app.core.permissions import permission_manager, Role
        for role_name in self.roles:
            try:
                role = Role(role_name)
                if permission_manager.check_role_permission(role, required_permission):
                    return True
            except ValueError:
                continue
        
        return False
    
    def check_role(self, required_role: str) -> bool:
        """检查角色（支持层级角色）"""
        if not self.roles:
            return False
        
        # 直接角色检查
        if required_role in self.roles:
            return True
        
        # 角色层级检查
        from app.core.permissions import permission_checker
        return permission_checker.check_role(self.roles, required_role)
    
    def check_access_level(self, required_level: str) -> bool:
        """检查访问级别"""
        from app.core.permissions import permission_checker
        user_level = self._node_attributes.get('access_level', 'normal')
        return permission_checker.check_access_level(user_level, required_level)
    
    def update_last_login(self) -> None:
        """更新最后登录时间"""
        self.last_login = datetime.now()
        self.login_count += 1
        self.failed_login_attempts = 0  # 重置失败次数
        self._schedule_node_sync()
    
    def update_last_activity(self) -> None:
        """更新最后活动时间"""
        self.last_activity = datetime.now()
        self._schedule_node_sync()
    
    def record_failed_login(self) -> None:
        """记录失败登录"""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= self.max_failed_attempts:
            self.lock_account("登录失败次数过多")
        self._schedule_node_sync()
    
    def lock_account(self, reason: str = None) -> None:
        """锁定账户"""
        self.is_locked = True
        self.lock_reason = reason
        self._schedule_node_sync()
    
    def unlock_account(self) -> None:
        """解锁账户"""
        self.is_locked = False
        self.lock_reason = None
        self.failed_login_attempts = 0
        self._schedule_node_sync()
    
    def suspend_account(self, reason: str, until: datetime = None) -> None:
        """暂停账户"""
        self.is_suspended = True
        self.suspension_reason = reason
        self.suspension_until = until
        self._schedule_node_sync()
    
    def unsuspend_account(self) -> None:
        """恢复账户"""
        self.is_suspended = False
        self.suspension_reason = None
        self.suspension_until = None
        self._schedule_node_sync()
    
    def can_login(self) -> bool:
        """检查是否可以登录"""
        if self.is_locked:
            return False
        if self.is_suspended:
            if self.suspension_until and datetime.now() < self.suspension_until:
                return False
            else:
                # 暂停时间已过，自动恢复
                self.unsuspend_account()
        return True
    
    def get_status_summary(self) -> Dict[str, Any]:
        """获取账户状态摘要"""
        return {
            'username': self.username,
            'email': self.email,
            'is_verified': self.is_verified,
            'is_locked': self.is_locked,
            'is_suspended': self.is_suspended,
            'roles': self.roles,
            'permissions': self.permissions,
            'login_count': self.login_count,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'lock_reason': self.lock_reason,
            'suspension_reason': self.suspension_reason,
            'suspension_until': self.suspension_until.isoformat() if self.suspension_until else None,
        }