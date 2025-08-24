"""
用户模型定义 - 纯图数据设计

基于DefaultAccount实现，所有数据存储在Node中
通过type='user'和typeclass区分用户对象
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from .base import DefaultAccount


class User(DefaultAccount):
    """
    用户模型 - 纯图数据设计
    
    继承自DefaultAccount，所有数据存储在Node中
    type='user', typeclass='app.models.user.User'
    """
    
    def __init__(self, username: str, email: str, **kwargs):
        # 设置用户特定的节点类型
        self._node_type = 'user'
        
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
            'last_activity': kwargs.get('last_activity'),
            
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
            print(f"加入校园失败: {e}")
            return False
    
    def leave_campus(self, campus) -> bool:
        """离开校园"""
        try:
            return self.remove_relationship(campus, "campus_member")
        except Exception as e:
            print(f"离开校园失败: {e}")
            return False
    
    def get_node_attribute(self, key: str, default: Any = None) -> Any:
        """获取节点属性（别名方法）"""
        return self._node_attributes.get(key, default)