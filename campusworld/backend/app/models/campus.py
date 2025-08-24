"""
校园相关模型定义 - 纯图数据设计

所有数据存储在Node中，通过type和typeclass区分
Campus: type='campus', typeclass='app.models.campus.Campus'
CampusMember: 通过图关系表示用户与校园的成员关系
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from .base import DefaultObject


class Campus(DefaultObject):
    """
    校园模型 - 纯图数据设计
    
    继承自DefaultObject，所有数据存储在Node中
    type='campus', typeclass='app.models.campus.Campus'
    """
    
    def __init__(self, name: str, code: str, **kwargs):
        # 设置校园特定的节点类型
        self._node_type = 'campus'
        
        # 设置校园默认属性
        campus_attrs = {
            # 校园基本信息
            'code': code,  # 校园代码
            'full_name': kwargs.get('full_name', name),  # 完整名称
            'short_name': kwargs.get('short_name'),  # 简称
            
            # 校园类型和分类
            'campus_type': kwargs.get('campus_type', 'university'),  # university, college, school
            'category': kwargs.get('category'),  # 分类标签
            'level': kwargs.get('level', 'undergraduate'),  # undergraduate, graduate, mixed
            
            # 位置信息
            'address': kwargs.get('address'),
            'city': kwargs.get('city'),
            'province': kwargs.get('province'),
            'country': kwargs.get('country', 'China'),
            'coordinates': kwargs.get('coordinates', {}),  # 经纬度信息
            
            # 校园描述
            'history': kwargs.get('history'),  # 历史介绍
            'features': kwargs.get('features'),  # 特色介绍
            
            # 统计信息
            'member_count': kwargs.get('member_count', 0),
            'max_members': kwargs.get('max_members', 1000),
            'activity_count': kwargs.get('activity_count', 0),
            
            # 设置和配置
            'settings': kwargs.get('settings', {}),  # 校园特定设置
            'rules': kwargs.get('rules'),  # 校园规则
            'announcements': kwargs.get('announcements'),  # 公告信息
            
            **kwargs
        }
        
        super().__init__(name=name, **campus_attrs)
    
    def __repr__(self):
        name = self._node_attributes.get('name', 'Unknown')
        code = self._node_attributes.get('code', 'Unknown')
        return f"<Campus(uuid='{self._node_uuid}', name='{name}', code='{code}')>"
    
    # ==================== 校园属性访问器 ====================
    
    @property
    def code(self) -> str:
        """获取校园代码"""
        return self._node_attributes.get('code', '')
    
    @code.setter
    def code(self, value: str):
        """设置校园代码"""
        self.set_node_attribute('code', value)
    
    @property
    def full_name(self) -> str:
        """获取完整名称"""
        return self._node_attributes.get('full_name', '')
    
    @full_name.setter
    def full_name(self, value: str):
        """设置完整名称"""
        self.set_node_attribute('full_name', value)
    
    @property
    def short_name(self) -> Optional[str]:
        """获取简称"""
        return self._node_attributes.get('short_name')
    
    @short_name.setter
    def short_name(self, value: Optional[str]):
        """设置简称"""
        self.set_node_attribute('short_name', value)
    
    @property
    def campus_type(self) -> str:
        """获取校园类型"""
        return self._node_attributes.get('campus_type', 'university')
    
    @campus_type.setter
    def campus_type(self, value: str):
        """设置校园类型"""
        self.set_node_attribute('campus_type', value)
    
    @property
    def category(self) -> Optional[str]:
        """获取分类"""
        return self._node_attributes.get('category')
    
    @category.setter
    def category(self, value: Optional[str]):
        """设置分类"""
        self.set_node_attribute('category', value)
    
    @property
    def level(self) -> str:
        """获取级别"""
        return self._node_attributes.get('level', 'undergraduate')
    
    @level.setter
    def level(self, value: str):
        """设置级别"""
        self.set_node_attribute('level', value)
    
    @property
    def address(self) -> Optional[str]:
        """获取地址"""
        return self._node_attributes.get('address')
    
    @address.setter
    def address(self, value: Optional[str]):
        """设置地址"""
        self.set_node_attribute('address', value)
    
    @property
    def city(self) -> Optional[str]:
        """获取城市"""
        return self._node_attributes.get('city')
    
    @city.setter
    def city(self, value: Optional[str]):
        """设置城市"""
        self.set_node_attribute('city', value)
    
    @property
    def province(self) -> Optional[str]:
        """获取省份"""
        return self._node_attributes.get('province')
    
    @province.setter
    def province(self, value: Optional[str]):
        """设置省份"""
        self.set_node_attribute('province', value)
    
    @property
    def country(self) -> str:
        """获取国家"""
        return self._node_attributes.get('country', 'China')
    
    @country.setter
    def country(self, value: str):
        """设置国家"""
        self.set_node_attribute('country', value)
    
    @property
    def coordinates(self) -> Dict[str, Any]:
        """获取坐标"""
        return self._node_attributes.get('coordinates', {})
    
    @coordinates.setter
    def coordinates(self, value: Dict[str, Any]):
        """设置坐标"""
        self.set_node_attribute('coordinates', value)
    
    @property
    def history(self) -> Optional[str]:
        """获取历史"""
        return self._node_attributes.get('history')
    
    @history.setter
    def history(self, value: Optional[str]):
        """设置历史"""
        self.set_node_attribute('history', value)
    
    @property
    def features(self) -> Optional[str]:
        """获取特色"""
        return self._node_attributes.get('features')
    
    @features.setter
    def features(self, value: Optional[str]):
        """设置特色"""
        self.set_node_attribute('features', value)
    
    @property
    def member_count(self) -> int:
        """获取成员数量"""
        return self._node_attributes.get('member_count', 0)
    
    @member_count.setter
    def member_count(self, value: int):
        """设置成员数量"""
        self.set_node_attribute('member_count', value)
    
    @property
    def max_members(self) -> int:
        """获取最大成员数"""
        return self._node_attributes.get('max_members', 1000)
    
    @max_members.setter
    def max_members(self, value: int):
        """设置最大成员数"""
        self.set_node_attribute('max_members', value)
    
    @property
    def activity_count(self) -> int:
        """获取活动数量"""
        return self._node_attributes.get('activity_count', 0)
    
    @activity_count.setter
    def activity_count(self, value: int):
        """设置活动数量"""
        self.set_node_attribute('activity_count', value)
    
    @property
    def settings(self) -> Dict[str, Any]:
        """获取设置"""
        return self._node_attributes.get('settings', {})
    
    @settings.setter
    def settings(self, value: Dict[str, Any]):
        """设置设置"""
        self.set_node_attribute('settings', value)
    
    @property
    def rules(self) -> Optional[str]:
        """获取规则"""
        return self._node_attributes.get('rules')
    
    @rules.setter
    def rules(self, value: Optional[str]):
        """设置规则"""
        self.set_node_attribute('rules', value)
    
    @property
    def announcements(self) -> Optional[str]:
        """获取公告"""
        return self._node_attributes.get('announcements')
    
    @announcements.setter
    def announcements(self, value: Optional[str]):
        """设置公告"""
        self.set_node_attribute('announcements', value)
    
    # ==================== 校园方法 ====================
    
    def get_members(self):
        """获取所有成员关系"""
        return self.get_relationships("campus_member")
    
    def get_active_members(self):
        """获取活跃成员"""
        members = self.get_members()
        return [m for m in members if m.get_attribute("is_active", True)]
    
    def get_member_count(self) -> int:
        """获取活跃成员数量"""
        return len(self.get_active_members())
    
    def get_admin_members(self):
        """获取管理员成员"""
        members = self.get_active_members()
        return [m for m in members if m.get_attribute("role") in ["admin", "owner"]]
    
    def can_accept_more_members(self) -> bool:
        """检查是否可以接受更多成员"""
        return self.get_member_count() < self.max_members
    
    def add_member(self, user, role: str = "member") -> bool:
        """添加成员"""
        if not self.can_accept_more_members():
            return False
        
        try:
            relationship = user.create_relationship(
                target=self,
                rel_type="campus_member",
                role=role,
                status="active",
                joined_at=datetime.now(),
                is_active=True,
                activity_count=0,
                contribution_score=0
            )
            
            if relationship:
                # 更新成员数量
                self.member_count = self.get_member_count()
                return True
            return False
        except Exception as e:
            print(f"添加成员失败: {e}")
            return False
    
    def remove_member(self, user) -> bool:
        """移除成员"""
        try:
            success = user.remove_relationship(self, "campus_member")
            if success:
                # 更新成员数量
                self.member_count = self.get_member_count()
            return success
        except Exception as e:
            print(f"移除成员失败: {e}")
            return False
    
    def get_member_role(self, user) -> str:
        """获取用户在校园中的角色"""
        relationships = user.get_relationships("campus_member")
        for rel in relationships:
            if rel.target_id == self.id:
                return rel.get_attribute("role", "guest")
        return "guest"
    
    def update_member_role(self, user, new_role: str) -> bool:
        """更新成员角色"""
        relationships = user.get_relationships("campus_member")
        for rel in relationships:
            if rel.target_id == self.id:
                rel.set_attribute("role", new_role)
                return True
        return False
    
    def get_location_info(self) -> Dict[str, Any]:
        """获取位置信息"""
        return {
            "address": self.address,
            "city": self.city,
            "province": self.province,
            "country": self.country,
            "coordinates": self.coordinates
        }
    
    def update_member_count(self) -> None:
        """更新成员数量统计"""
        self.member_count = self.get_member_count()
    
    def update_setting(self, key: str, value: Any) -> None:
        """更新设置"""
        settings = self.settings.copy()
        settings[key] = value
        self.settings = settings
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """获取设置"""
        return self.settings.get(key, default)
    
    def add_announcement(self, announcement: str) -> None:
        """添加公告"""
        if self.announcements:
            announcements = f"{self.announcements}\n\n{announcement}"
        else:
            announcements = announcement
        self.announcements = announcements
    
    def set_coordinates(self, latitude: float, longitude: float) -> None:
        """设置坐标"""
        self.coordinates = {
            "latitude": latitude,
            "longitude": longitude,
            "updated_at": datetime.now().isoformat()
        }


# 注意：CampusMember 现在通过图关系表示，不再是独立的模型类
# 成员关系通过 campus_member 类型的关系来表示，关系属性包括：
# - role: 角色 (member, moderator, admin, owner)
# - status: 状态 (active, inactive, suspended, graduated)
# - joined_at: 加入时间
# - left_at: 离开时间
# - join_reason: 加入原因
# - nickname: 在校园中的昵称
# - bio: 在校园中的个人介绍
# - avatar_url: 在校园中的头像
# - permissions: 校园特定权限
# - settings: 个人设置
# - activity_count: 活动计数
# - contribution_score: 贡献分数
# - is_active: 是否活跃