"""
用户模型定义 - 纯图数据设计

基于DefaultAccount实现，所有数据存储在Node中
通过type='user'和typeclass区分用户对象
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from .base import DefaultAccount
from .root_manager import root_manager
from  app.core.log import get_logger, LoggerNames;
from .graph import Node
from app.core.database import SessionLocal


class User(DefaultAccount):
    """
    用户模型 - 纯图数据设计
    
    继承自DefaultAccount，所有数据存储在Node中
    type='user', typeclass='app.models.user.User'
    """
    
    def __init__(self, username: str, email: str, **kwargs):
        # 设置用户特定的节点类型
        self._node_type = 'user'
        self.logger = get_logger(LoggerNames.GAME)
        
        # 设置用户默认属性
        user_attrs = {
            # 扩展的个人信息
            'nickname': kwargs.get('nickname'),
            'phone': kwargs.get('phone'),
            'date_of_birth': kwargs.get('date_of_birth'),
            'gender': kwargs.get('gender'),  # male, female, other
            
            # 学术信息
            'student_id': kwargs.get('student_id'),
            'major': kwargs.get('major'),
            'grade': kwargs.get('grade'),  # 年级
            'graduation_year': kwargs.get('graduation_year'),
            
            # 社交信息
            'social_links': kwargs.get('social_links', {}),  # 社交媒体链接
            'interests': kwargs.get('interests', []),  # 兴趣爱好
            
            # 设置和偏好
            'language': kwargs.get('language', 'zh-CN'),
            'timezone': kwargs.get('timezone', 'Asia/Shanghai'),
            'notification_settings': kwargs.get('notification_settings', {}),
            
            # 统计信息
            'login_count': kwargs.get('login_count', 0),
            'last_activity': kwargs.get('last_activity', datetime.now().isoformat()) if kwargs.get('last_activity') is None else kwargs.get('last_activity'),
            
            **kwargs
        }
        
        super().__init__(username=username, email=email, **user_attrs)
    
    def __repr__(self):
        username = self._node_attributes.get('username', 'Unknown')
        email = self._node_attributes.get('email', 'Unknown')
        return f"<User(uuid='{self._node_uuid}', username='{username}', email='{email}')>"
    
    # ==================== 用户属性访问器 ====================
    
    @property
    def nickname(self) -> Optional[str]:
        """获取昵称"""
        return self._node_attributes.get('nickname')
    
    @nickname.setter
    def nickname(self, value: Optional[str]):
        """设置昵称"""
        self.set_node_attribute('nickname', value)
    
    @property
    def phone(self) -> Optional[str]:
        """获取电话"""
        return self._node_attributes.get('phone')
    
    @phone.setter
    def phone(self, value: Optional[str]):
        """设置电话"""
        self.set_node_attribute('phone', value)
    
    @property
    def date_of_birth(self):
        """获取出生日期"""
        return self._node_attributes.get('date_of_birth')
    
    @date_of_birth.setter
    def date_of_birth(self, value):
        """设置出生日期"""
        self.set_node_attribute('date_of_birth', value)
    
    @property
    def gender(self) -> Optional[str]:
        """获取性别"""
        return self._node_attributes.get('gender')
    
    @gender.setter
    def gender(self, value: Optional[str]):
        """设置性别"""
        self.set_node_attribute('gender', value)
    
    @property
    def student_id(self) -> Optional[str]:
        """获取学号"""
        return self._node_attributes.get('student_id')
    
    @student_id.setter
    def student_id(self, value: Optional[str]):
        """设置学号"""
        self.set_node_attribute('student_id', value)
    
    @property
    def major(self) -> Optional[str]:
        """获取专业"""
        return self._node_attributes.get('major')
    
    @major.setter
    def major(self, value: Optional[str]):
        """设置专业"""
        self.set_node_attribute('major', value)
    
    @property
    def grade(self) -> Optional[str]:
        """获取年级"""
        return self._node_attributes.get('grade')
    
    @grade.setter
    def grade(self, value: Optional[str]):
        """设置年级"""
        self.set_node_attribute('grade', value)
    
    @property
    def graduation_year(self) -> Optional[int]:
        """获取毕业年份"""
        return self._node_attributes.get('graduation_year')
    
    @graduation_year.setter
    def graduation_year(self, value: Optional[int]):
        """设置毕业年份"""
        self.set_node_attribute('graduation_year', value)
    
    @property
    def social_links(self) -> Dict[str, str]:
        """获取社交链接"""
        return self._node_attributes.get('social_links', {})
    
    @social_links.setter
    def social_links(self, value: Dict[str, str]):
        """设置社交链接"""
        self.set_node_attribute('social_links', value)
    
    @property
    def interests(self) -> List[str]:
        """获取兴趣爱好"""
        return self._node_attributes.get('interests', [])
    
    @interests.setter
    def interests(self, value: List[str]):
        """设置兴趣爱好"""
        self.set_node_attribute('interests', value)
    
    @property
    def language(self) -> str:
        """获取语言"""
        return self._node_attributes.get('language', 'zh-CN')
    
    @language.setter
    def language(self, value: str):
        """设置语言"""
        self.set_node_attribute('language', value)
    
    @property
    def timezone(self) -> str:
        """获取时区"""
        return self._node_attributes.get('timezone', 'Asia/Shanghai')
    
    @timezone.setter
    def timezone(self, value: str):
        """设置时区"""
        self.set_node_attribute('timezone', value)
    
    @property
    def notification_settings(self) -> Dict[str, Any]:
        """获取通知设置"""
        return self._node_attributes.get('notification_settings', {})
    
    @notification_settings.setter
    def notification_settings(self, value: Dict[str, Any]):
        """设置通知设置"""
        self.set_node_attribute('notification_settings', value)
    
    @property
    def login_count(self) -> int:
        """获取登录次数"""
        return self._node_attributes.get('login_count', 0)
    
    @login_count.setter
    def login_count(self, value: int):
        """设置登录次数"""
        self.set_node_attribute('login_count', value)
    
    @property
    def last_activity(self):
        """获取最后活动时间"""
        return self._node_attributes.get('last_activity')
    
    @last_activity.setter
    def last_activity(self, value):
        """设置最后活动时间"""
        self.set_node_attribute('last_activity', value)
    
    # ==================== 用户方法 ====================
    
    def get_display_name(self) -> str:
        """获取显示名称，优先使用昵称"""
        return self.nickname or self.name or self.username
    
    def get_academic_info(self) -> Dict[str, Any]:
        """获取学术信息"""
        return {
            "student_id": self.student_id,
            "major": self.major,
            "grade": self.grade,
            "graduation_year": self.graduation_year
        }
    
    def update_last_activity(self) -> None:
        """更新最后活动时间"""
        self.last_activity = datetime.now()
    
    def increment_login_count(self) -> None:
        """增加登录次数"""
        self.login_count = self.login_count + 1
        self.update_last_login()
    
    def add_interest(self, interest: str) -> None:
        """添加兴趣"""
        interests = self.interests.copy()
        if interest not in interests:
            interests.append(interest)
            self.interests = interests
    
    def remove_interest(self, interest: str) -> None:
        """移除兴趣"""
        interests = self.interests.copy()
        if interest in interests:
            interests.remove(interest)
            self.interests = interests
    
    def add_social_link(self, platform: str, url: str) -> None:
        """添加社交链接"""
        social_links = self.social_links.copy()
        social_links[platform] = url
        self.social_links = social_links
    
    def remove_social_link(self, platform: str) -> None:
        """移除社交链接"""
        social_links = self.social_links.copy()
        if platform in social_links:
            del social_links[platform]
            self.social_links = social_links
    
    def update_notification_setting(self, key: str, value: Any) -> None:
        """更新通知设置"""
        settings = self.notification_settings.copy()
        settings[key] = value
        self.notification_settings = settings
    
    # ==================== 关系管理 ====================
    
    def get_campus_memberships(self):
        """获取校园成员身份"""
        # 通过图关系获取
        relationships = self.get_relationships("campus_member")
        return relationships
    
    def get_active_world_activities(self):
        """获取活跃的世界活动"""
        # 通过图关系获取
        relationships = self.get_relationships("world_activity")
        return [rel for rel in relationships if rel.get_attribute("is_active", True)]
    
    def has_campus_access(self, campus_id: int) -> bool:
        """检查是否有指定校园的访问权限"""
        memberships = self.get_campus_memberships()
        for membership in memberships:
            if membership.target_id == campus_id:
                return True
        return False
    
    def get_campus_role(self, campus_id: int) -> str:
        """获取在指定校园中的角色"""
        memberships = self.get_campus_memberships()
        for membership in memberships:
            if membership.target_id == campus_id:
                return membership.get_attribute("role", "guest")
        return "guest"
    
    def can_manage_campus(self, campus_id: int) -> bool:
        """检查是否可以管理指定校园"""
        role = self.get_campus_role(campus_id)
        return role in ["admin", "manager", "owner"]
    
    def join_campus(self, campus, role: str = "member") -> bool:
        """加入校园"""
        try:
            relationship = self.create_relationship(
                target=campus,
                rel_type="campus_member",
                role=role,
                joined_at=datetime.now()
            )
            return relationship is not None
        except Exception as e:
            self.logger .error(f"加入校园失败: {e}")
            return False
    
    def leave_campus(self, campus) -> bool:
        """离开校园"""
        try:
            return self.remove_relationship(campus, "campus_member")
        except Exception as e:
            self.logger.error(f"离开校园失败: {e}")
            return False
    
    def get_node_attribute(self, key: str, default: Any = None) -> Any:
        """获取节点属性（别名方法）"""
        return self._node_attributes.get(key, default)
    
    # ==================== 用户spawn和位置管理 ====================
    
    def spawn_to_singularity_room(self) -> bool:
        """
        将用户spawn到奇点房间
        
        参考Evennia的DefaultHome设计，确保用户登录后出现在Singularity Room
        """
        try:
            # 确保根节点存在
            if not root_manager.ensure_root_node_exists():
                self.logger.error("无法确保根节点存在")
                return False
            
            # 获取根节点
            root_node = root_manager.get_root_node()
            if not root_node:
                self.logger.error("无法获取根节点")
                return False
            
            # 设置用户位置到根节点
            self.location_id = root_node.id
            self.home_id = root_node.id  # 同时设置为home
            
            # 更新最后活动时间
            self.set_node_attribute('last_activity', datetime.now().isoformat())
            
            # 同步到数据库
            self.sync_to_node()
            
            return True
            
        except Exception as e:
            self.logger.error(f"用户spawn到奇点房间失败: {e}")
            return False
    
    def spawn_to_home(self) -> bool:
        """
        将用户spawn到home位置
        
        如果home_id未设置，则spawn到奇点房间
        """
        try:
            # 检查是否有home_id
            if self.home_id:
                # 有home_id，直接移动到home
                self.location_id = self.home_id
                self.set_node_attribute('last_activity', datetime.now().isoformat())
                self.sync_to_node()
                return True
            else:
                # 没有home_id，spawn到奇点房间
                return self.spawn_to_singularity_room()
                
        except Exception as e:
            self.logger.error(f"用户spawn到home失败: {e}")
            return False
    
    def set_home_to_singularity_room(self) -> bool:
        """
        将用户的home设置为奇点房间
        
        确保所有用户的默认home都是奇点房间
        """
        try:
            # 确保根节点存在
            if not root_manager.ensure_root_node_exists():
                return False
            
            # 获取根节点
            root_node = root_manager.get_root_node()
            if not root_node:
                return False
            
            # 设置home_id
            self.home_id = root_node.id
            self.sync_to_node()
            
            return True
            
        except Exception as e:
            self.logger.error(f"设置home到奇点房间失败: {e}")
            return False
    
    def get_current_location_info(self) -> Optional[Dict[str, Any]]:
        """获取当前位置信息"""
        try:
            if not self.location_id:
                return None
            
            session = SessionLocal()
            try:
                location_node = session.query(Node).filter(
                    Node.id == self.location_id
                ).first()
                
                if not location_node:
                    return None
                
                return {
                    'id': location_node.id,
                    'uuid': str(location_node.uuid),
                    'name': location_node.name,
                    'type': location_node.type_code,
                    'description': location_node.description,
                    'is_root': location_node.attributes.get('is_root', False) if location_node.attributes else False,
                    'is_home': location_node.attributes.get('is_home', False) if location_node.attributes else False,
                    'room_capacity': location_node.attributes.get('room_capacity', 0) if location_node.attributes else 0,
                    'is_public': location_node.is_public,
                    'is_accessible': location_node.attributes.get('is_accessible', True) if location_node.attributes else True
                }
                
            finally:
                session.close()
                
        except Exception as e:
            self.logger.error(f"获取当前位置信息失败: {e}")
            return None
    
    def can_enter_location(self, location_id: int) -> bool:
        """检查是否可以进入指定位置"""
        try:
            session = SessionLocal()
            try:
                location_node = session.query(Node).filter(
                    Node.id == location_id
                ).first()
                
                if not location_node:
                    return False
                
                # 检查位置是否可访问
                if not location_node.attributes.get('is_accessible', True) if location_node.attributes else True:
                    return False
                
                # 检查权限要求
                required_permissions = location_node.attributes.get('permission_required', []) if location_node.attributes else []
                if required_permissions:
                    for permission in required_permissions:
                        if not self.has_permission(permission):
                            return False
                
                # 检查角色要求
                required_roles = location_node.attributes.get('role_required', []) if location_node.attributes else []
                if required_roles:
                    user_roles = self._node_attributes.get('roles', [])
                    if not any(role in user_roles for role in required_roles):
                        return False
                
                return True
                
            finally:
                session.close()
                
        except Exception as e:
            self.logger.error(f"检查位置访问权限失败: {e}")
            return False
    
    def move_to_location(self, location_id: int) -> bool:
        """移动到指定位置"""
        try:
            # 检查是否可以进入该位置
            if not self.can_enter_location(location_id):
                print("无法进入该位置")
                return False
            
            # 移动用户
            self.location_id = location_id
            self.set_node_attribute('last_activity', datetime.now().isoformat())
            self.sync_to_node()
            
            return True
            
        except Exception as e:
            self.logger.error(f"移动用户失败: {e}")
            return False
    
    def get_spawn_info(self) -> Dict[str, Any]:
        """获取用户spawn信息"""
        return {
            'user_id': self.id,
            'username': self.username,
            'current_location_id': self.location_id,
            'home_id': self.home_id,
            'last_activity': self._node_attributes.get('last_activity'),
            'is_in_singularity_room': self._is_in_singularity_room(),
            'can_spawn_to_home': self.home_id is not None
        }
    
    def _is_in_singularity_room(self) -> bool:
        """检查是否在奇点房间"""
        try:
            if not self.location_id:
                return False
            session = SessionLocal()
            try:
                location_node = session.query(Node).filter(
                    Node.id == self.location_id
                ).first()
                
                if not location_node:
                    return False
                
                return location_node.attributes.get('is_root', False) if location_node.attributes else False
                
            finally:
                session.close()
                
        except Exception as e:
            self.logger.error(f"检查是否在奇点房间失败: {e}")
            return False