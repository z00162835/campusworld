"""
房间模型定义 - 纯图数据设计

参考Evennia的DefaultRoom设计，实现游戏世界中的房间/地点
所有数据都存储在Node中，type为'room'
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime

from .base import DefaultObject

if TYPE_CHECKING:
    from .user import User


class Room(DefaultObject):
    """
    房间模型 - 纯图数据设计
    
    继承自DefaultObject，提供房间相关功能
    所有数据都存储在Node中，type为'room'
    参考Evennia的DefaultRoom设计模式
    """
    
    def __init__(self, name: str, **kwargs):
        # 设置房间特定的节点类型
        self._node_type = 'room'
        
        # 设置房间默认属性
        room_attrs = {
            # 房间基本信息
            'room_type': kwargs.get('room_type', 'normal'),  # normal, home, special, etc.
            'room_description': kwargs.get('room_description', ''),
            'room_short_description': kwargs.get('room_short_description', ''),
            
            # 房间状态
            'is_public': kwargs.get('is_public', True),
            'is_accessible': kwargs.get('is_accessible', True),
            'is_lighted': kwargs.get('is_lighted', True),
            'is_indoors': kwargs.get('is_indoors', True),
            
            # 房间属性
            'room_capacity': kwargs.get('room_capacity', 0),  # 0表示无限制
            'room_temperature': kwargs.get('room_temperature', 20),  # 摄氏度
            'room_humidity': kwargs.get('room_humidity', 50),  # 湿度百分比
            'room_lighting': kwargs.get('room_lighting', 'normal'),  # normal, dim, bright, dark
            'room_weather': kwargs.get('room_weather', 'normal'),  # normal, sunny, rainy, cloudy, snowing, etc.
            'room_time': kwargs.get('room_time', 'normal'),  # normal, morning, afternoon, evening, night
            'room_date': kwargs.get('room_date', 'normal'),  # normal, today, tomorrow, next week, etc.
            'room_season': kwargs.get('room_season', 'normal'),  # normal, spring, summer, autumn, winter
            'room_latitude': kwargs.get('room_latitude', 0),  # 纬度
            'room_longitude': kwargs.get('room_longitude', 0),  # 经度
            'room_altitude': kwargs.get('room_altitude', 0),  # 海拔
            'room_geojson': kwargs.get('room_geojson', {}),  # 房间GEOJSON的数据
            
            # 特殊标识
            'is_root': kwargs.get('is_root', False),  # 是否为根节点
            'is_home': kwargs.get('is_home', False),  # 是否为默认home
            'is_special': kwargs.get('is_special', False),  # 是否为特殊房间
            
            # 房间内容
            'room_objects': kwargs.get('room_objects', []),  # 房间内的对象ID列表
            'room_exits': kwargs.get('room_exits', {}),  # 出口信息 {direction: target_room_id}
            'room_scripts': kwargs.get('room_scripts', []),  # 房间脚本
            
            # 访问控制
            'access_requirements': kwargs.get('access_requirements', []),  # 访问要求
            'permission_required': kwargs.get('permission_required', []),  # 所需权限
            'role_required': kwargs.get('role_required', []),  # 所需角色
            
            # 房间规则
            'allow_teleport': kwargs.get('allow_teleport', True),  # 是否允许传送
            
            # 房间效果
            'room_effects': kwargs.get('room_effects', []),  # 房间效果列表
            'room_ambiance': kwargs.get('room_ambiance', ''),  # 房间氛围描述
            
            **kwargs
        }
        
        super().__init__(name=name, **room_attrs)
    
    def __repr__(self):
        room_type = self._node_attributes.get('room_type', 'normal')
        is_root = self._node_attributes.get('is_root', False)
        root_indicator = " [ROOT]" if is_root else ""
        return f"<Room(name='{self._node_name}', type='{room_type}'{root_indicator})>"
    
    # ==================== 房间属性访问器 ====================
    
    @property
    def room_type(self) -> str:
        """获取房间类型"""
        return self._node_attributes.get('room_type', 'normal')
    
    @room_type.setter
    def room_type(self, value: str):
        """设置房间类型"""
        self.set_node_attribute('room_type', value)
    
    @property
    def room_description(self) -> str:
        """获取房间描述"""
        return self._node_attributes.get('room_description', '')
    
    @room_description.setter
    def room_description(self, value: str):
        """设置房间描述"""
        self.set_node_attribute('room_description', value)
    
    @property
    def is_root(self) -> bool:
        """是否为根节点"""
        return self._node_attributes.get('is_root', False)
    
    @is_root.setter
    def is_root(self, value: bool):
        """设置是否为根节点"""
        self.set_node_attribute('is_root', value)
    
    @property
    def is_home(self) -> bool:
        """是否为默认home"""
        return self._node_attributes.get('is_home', False)
    
    @is_home.setter
    def is_home(self, value: bool):
        """设置是否为默认home"""
        self.set_node_attribute('is_home', value)
    
    @property
    def room_capacity(self) -> int:
        """获取房间容量"""
        return self._node_attributes.get('room_capacity', 0)
    
    @room_capacity.setter
    def room_capacity(self, value: int):
        """设置房间容量"""
        self.set_node_attribute('room_capacity', value)
    
    # ==================== 房间内容管理 ====================
    
    def add_object(self, obj_id: int) -> bool:
        """添加对象到房间"""
        try:
            room_objects = self._node_attributes.get('room_objects', [])
            if obj_id not in room_objects:
                room_objects.append(obj_id)
                self.set_node_attribute('room_objects', room_objects)
                return True
            return False
        except Exception as e:
            print(f"添加对象到房间失败: {e}")
            return False
    
    def remove_object(self, obj_id: int) -> bool:
        """从房间移除对象"""
        try:
            room_objects = self._node_attributes.get('room_objects', [])
            if obj_id in room_objects:
                room_objects.remove(obj_id)
                self.set_node_attribute('room_objects', room_objects)
                return True
            return False
        except Exception as e:
            print(f"从房间移除对象失败: {e}")
            return False
    
    def get_objects(self) -> List[int]:
        """获取房间内的对象ID列表"""
        return self._node_attributes.get('room_objects', []).copy()
    
    def has_object(self, obj_id: int) -> bool:
        """检查房间是否包含指定对象"""
        return obj_id in self._node_attributes.get('room_objects', [])
    
    def get_object_count(self) -> int:
        """获取房间内对象数量"""
        return len(self._node_attributes.get('room_objects', []))
    
    def is_full(self) -> bool:
        """检查房间是否已满"""
        capacity = self.room_capacity
        if capacity <= 0:  # 0表示无限制
            return False
        return self.get_object_count() >= capacity
    
    # ==================== 出口管理 ====================
    
    def add_exit(self, direction: str, target_room_id: int) -> bool:
        """添加出口"""
        try:
            room_exits = self._node_attributes.get('room_exits', {})
            room_exits[direction] = target_room_id
            self.set_node_attribute('room_exits', room_exits)
            return True
        except Exception as e:
            print(f"添加出口失败: {e}")
            return False
    
    def remove_exit(self, direction: str) -> bool:
        """移除出口"""
        try:
            room_exits = self._node_attributes.get('room_exits', {})
            if direction in room_exits:
                del room_exits[direction]
                self.set_node_attribute('room_exits', room_exits)
                return True
            return False
        except Exception as e:
            print(f"移除出口失败: {e}")
            return False
    
    def get_exits(self) -> Dict[str, int]:
        """获取所有出口"""
        return self._node_attributes.get('room_exits', {}).copy()
    
    def get_exit(self, direction: str) -> Optional[int]:
        """获取指定方向的出口目标房间ID"""
        return self._node_attributes.get('room_exits', {}).get(direction)
    
    def has_exit(self, direction: str) -> bool:
        """检查是否有指定方向的出口"""
        return direction in self._node_attributes.get('room_exits', {})
    
    # ==================== 访问控制 ====================
    
    def can_access(self, user: 'User') -> bool:
        """检查用户是否可以访问此房间"""
        # 检查房间是否可访问
        if not self._node_attributes.get('is_accessible', True):
            return False
        
        # 检查权限要求
        required_permissions = self._node_attributes.get('permission_required', [])
        if required_permissions:
            for permission in required_permissions:
                if not user.has_permission(permission):
                    return False
        
        # 检查角色要求
        required_roles = self._node_attributes.get('role_required', [])
        if required_roles:
            user_roles = user._node_attributes.get('roles', [])
            if not any(role in user_roles for role in required_roles):
                return False
        
        return True
    
    def can_enter(self, user: 'User') -> bool:
        """检查用户是否可以进入此房间"""
        # 检查基本访问权限
        if not self.can_access(user):
            return False
        
        # 检查房间容量
        if self.is_full():
            return False
        
        return True
    
    # ==================== 房间效果 ====================
    
    def add_effect(self, effect_name: str, effect_data: Dict[str, Any]) -> bool:
        """添加房间效果"""
        try:
            room_effects = self._node_attributes.get('room_effects', [])
            effect = {
                'name': effect_name,
                'data': effect_data,
                'added_at': datetime.now().isoformat()
            }
            room_effects.append(effect)
            self.set_node_attribute('room_effects', room_effects)
            return True
        except Exception as e:
            print(f"添加房间效果失败: {e}")
            return False
    
    def remove_effect(self, effect_name: str) -> bool:
        """移除房间效果"""
        try:
            room_effects = self._node_attributes.get('room_effects', [])
            room_effects = [e for e in room_effects if e.get('name') != effect_name]
            self.set_node_attribute('room_effects', room_effects)
            return True
        except Exception as e:
            print(f"移除房间效果失败: {e}")
            return False
    
    def get_effects(self) -> List[Dict[str, Any]]:
        """获取所有房间效果"""
        return self._node_attributes.get('room_effects', []).copy()
    
    def has_effect(self, effect_name: str) -> bool:
        """检查是否有指定效果"""
        effects = self._node_attributes.get('room_effects', [])
        return any(e.get('name') == effect_name for e in effects)
    
    # ==================== 房间信息 ====================
    
    def get_room_info(self) -> Dict[str, Any]:
        """获取房间详细信息"""
        return {
            'id': self.id,
            'uuid': self._node_uuid,
            'name': self._node_name,
            'type': self.room_type,
            'description': self.room_description,
            'is_root': self.is_root,
            'is_home': self.is_home,
            'is_public': self._node_attributes.get('is_public', True),
            'is_accessible': self._node_attributes.get('is_accessible', True),
            'capacity': self.room_capacity,
            'current_objects': self.get_object_count(),
            'is_full': self.is_full(),
            'exits': list(self.get_exits().keys()),
            'effects': [e['name'] for e in self.get_effects()],
            'created_at': self._node_attributes.get('created_at'),
            'updated_at': self._node_attributes.get('updated_at')
        }
    
    def get_short_description(self) -> str:
        """获取房间简短描述"""
        short_desc = self._node_attributes.get('room_short_description', '')
        if short_desc:
            return short_desc
        
        # 如果没有简短描述，从完整描述中截取
        full_desc = self.room_description
        if len(full_desc) > 100:
            return full_desc[:97] + "..."
        return full_desc
    
    def get_detailed_description(self) -> str:
        """获取房间详细描述"""
        desc = self.room_description
        if not desc:
            return f"这是一个{self.room_type}房间。"
        
        # 添加房间状态信息
        status_info = []
        
        if self.is_root:
            status_info.append("这是系统的根节点。")
        
        if self.is_home:
            status_info.append("这是默认的起始地点。")
        
        if not self._node_attributes.get('is_lighted', True):
            status_info.append("房间内光线昏暗。")
        
        if self.room_capacity > 0:
            current_count = self.get_object_count()
            status_info.append(f"房间内当前有{current_count}个对象，容量为{self.room_capacity}。")
        
        if status_info:
            desc += "\n\n" + " ".join(status_info)
        
        return desc


class SingularityRoom(Room):
    """
    奇点房间 - 系统的根节点和默认home
    
    继承自Room，作为所有用户的默认登录地点
    参考Evennia的DefaultHome设计模式
    """
    
    def __init__(self, **kwargs):
        # 设置奇点房间的特定属性
        singularity_attrs = {
            'room_type': 'singularity',
            'room_description': self._get_default_description(),
            'room_short_description': '奇点屋',
            'is_root': True,
            'is_home': True,
            'is_special': True,
            'is_public': True,
            'is_accessible': True,
            'is_lighted': True,
            'is_indoors': True,
            'room_capacity': 0,  # 无限制
            'room_temperature': 22,
            'room_humidity': 45,
            'room_lighting': 'bright',
            'allow_pvp': False,
            'allow_combat': False,
            'allow_magic': True,
            'allow_teleport': True,
            'room_ambiance': '这是CampusOS的主入口，所有的新旅程都从这里开始。',
            **kwargs
        }
        
        super().__init__(name="Singularity Room", **singularity_attrs)
    
    def _get_default_description(self) -> str:
        """获取默认描述"""
        return """
欢迎来到CampusOS的主入口

这是所有用户进入CampusWorld的起点。
在这里，你可以感受到无限的可能性，就像宇宙大爆炸前的奇点一样，
蕴含着整个世界的潜力。

房间内光线柔和，温度适宜，空气中弥漫着一种神秘而充满希望的氛围。
四周的墙壁似乎没有边界，延伸向无尽的远方。

你可以在这里：
- 熟悉系统的基本操作
- 查看可用的命令和功能
- 准备开始你的Campusworld之旅
- 与其他用户交流

输入 'help' 查看可用命令，或输入 'look' 查看周围环境。
"""
    
    def __repr__(self):
        return f"<SingularityRoom(name='{self._node_name}', is_root=True, is_home=True)>"
    
    def get_welcome_message(self, username: str) -> str:
        """获取用户欢迎消息"""
        return f"""
{self.room_description}

欢迎，{username}！你已成功进入CampusWorld系统。
这是你的起点，也是你探索这个虚拟世界的门户。

当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
房间状态: 正常
在线用户: 可通过 'who' 命令查看

输入 'help' 获取帮助信息。
"""
