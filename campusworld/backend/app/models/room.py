"""
房间模型定义 - 纯图数据设计

"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime

from .base import DefaultObject

if TYPE_CHECKING:
    from .user import User


class Room(DefaultObject):
    """
    房间模型 - 纯图数据设计

    """
    
    def __init__(self, name: str, config: Dict[str, Any] = None, **kwargs):
        # 设置房间特定的节点类型
        self._node_type = 'room'
        
        # 设置房间默认属性
        default_attrs = {
            # ==================== 基础信息 ====================
            "uns": "RES001/BLD001/FLOOR01/ROOM001",  # 统一命名空间标识, 格式是：园区代码/建筑代码/楼层代码/房间代码
            "room_type": "normal",  # normal, home, special, classroom, office, lab, etc.
            "room_code": "ROOM001",  # 房间代码, 如：ROOM001
            "room_name": "示例房间",  # 房间名称
            "room_name_en": "Example Room",  # 房间英文名称
            "room_description": "",  # 房间描述
            "room_short_description": "",  # 房间简短描述
            
            # ==================== 位置信息 ====================
            "room_address": "",  # 房间地址
            "room_floor": 1,  # 所在楼层
            "room_building": "",  # 所在建筑
            "room_campus": "",  # 所在园区
            
            # ==================== 地理坐标 ====================
            "room_latitude": 0.0,  # 纬度
            "room_longitude": 0.0,  # 经度
            "room_altitude": 0.0,  # 海拔
            
            # ==================== 物理属性 ====================
            "room_area": 0.0,  # 房间面积(平方米)
            "room_height": 3.0,  # 房间高度(米)
            "room_capacity": 0,  # 房间容量(人)
            "room_rooms": 0,  # 子房间数量
            
            # ==================== 环境属性 ====================
            "room_temperature": 20,  # 温度(摄氏度)
            "room_humidity": 50,  # 湿度百分比
            "room_lighting": "normal",  # normal, dim, bright, dark
            "room_weather": "normal",  # normal, sunny, rainy, cloudy, snowing, etc.
            "room_time": "normal",  # normal, morning, afternoon, evening, night
            "room_date": "normal",  # normal, today, tomorrow, next week, etc.
            "room_season": "normal",  # normal, spring, summer, autumn, winter
            
            # ==================== 状态属性 ====================
            "room_status": "active",  # active, inactive, maintenance, renovation
            "is_public": True,  # 是否公开
            "is_accessible": True,  # 是否可访问
            "is_lighted": True,  # 是否有照明
            "is_indoors": True,  # 是否室内
            
            # ==================== 特殊标识 ====================
            "is_root": False,  # 是否为根节点
            "is_home": False,  # 是否为默认home
            "is_special": False,  # 是否为特殊房间
            
            # ==================== 访问控制 ====================
            "access_requirements": [],  # 访问要求
            "permission_required": [],  # 所需权限
            "role_required": [],  # 所需角色
            
            # ==================== 房间规则 ====================
            "allow_teleport": True,  # 是否允许传送
            
            # ==================== 房间内容 ====================
            "room_objects": [],  # 房间内的对象ID列表
            "room_functions": [],  # 房间功能列表,对象ID列表
            "room_services": [],  # 房间服务列表,对象ID列表
            "room_amenities": [],  # 房间设施列表,对象ID列表
            "room_equipment": [],  # 房间设备列表,对象ID列表
            "room_exits": {},  # 出口信息 {direction: target_room_id}
            "room_scripts": [],  # 房间脚本
            
            # ==================== 房间效果 ====================
            "room_effects": [],  # 房间效果列表
            "room_ambiance": "",  # 房间氛围描述
            
            # ==================== 数字孪生 ====================
            "room_dtmodels": {},  # 数字孪生模型信息
            
            # ==================== 时间信息 ====================
            "room_created_date": None,  # 房间创建日期
            "room_last_renovation": None,  # 最后翻新日期
            "room_expected_lifespan": 30,  # 预期寿命(年)
            
            # ==================== 管理信息 ====================
            "room_manager": "",  # 房间管理员
            "room_manager_phone": "",  # 管理员电话
            "room_manager_email": "",  # 管理员邮箱
            "room_owner": "",  # 房间所有者
        }
        
        # 设置默认标签
        default_tags = ['room', 'normal']
        
        # 合并配置
        if config:
            # 合并attributes
            if 'attributes' in config:
                default_attrs.update(config['attributes'])
            # 合并tags
            if 'tags' in config:
                default_tags.extend(config['tags'])
        
        # 合并kwargs
        default_attrs.update(kwargs)
        
        # 根据配置更新标签
        if default_attrs.get('is_root'):
            default_tags.append('root')
        if default_attrs.get('is_home'):
            default_tags.append('home')
        if default_attrs.get('is_special'):
            default_tags.append('special')
        if default_attrs.get('room_type'):
            default_tags = ['room', default_attrs['room_type']] + [tag for tag in default_tags if tag not in ['room', default_attrs['room_type']]]
        
        default_config = {
            'attributes': default_attrs,
            'tags': default_tags,
        }
        
        super().__init__(name=name, **default_config)
    
    def __repr__(self):
        room_type = self._node_attributes.get('room_type', 'normal')
        is_root = self._node_attributes.get('is_root', False)
        root_indicator = " [ROOT]" if is_root else ""
        return f"<Room(name='{self._node_name}', type='{room_type}'{root_indicator})>"
    
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
        capacity = self._node_attributes.get('room_capacity', 0)
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
    
    # ==================== 房间信息方法 ====================
    
    def get_room_summary(self) -> str:
        """获取房间摘要信息"""
        name = self._node_name
        uns = self._node_attributes.get('uns', '')
        room_type = self._node_attributes.get('room_type', '')
        room_code = self._node_attributes.get('room_code', '')
        room_status = self._node_attributes.get('room_status', '')
        room_area = self._node_attributes.get('room_area', 0)
        room_capacity = self._node_attributes.get('room_capacity', 0)
        room_address = self._node_attributes.get('room_address', '')
        
        summary = f"""
房间信息摘要:
  名称: {name}
  统一命名空间标识: {uns}
  代码: {room_code}
  类型: {room_type}
  状态: {room_status}
  地址: {room_address}
  面积: {room_area} 平方米
  容量: {room_capacity} 人
  当前对象数: {self.get_object_count()} 个
        """
        
        return summary.strip()
    
    def get_room_info(self) -> Dict[str, Any]:
        """获取房间详细信息"""
        return {
            'id': self.id,
            'uuid': self._node_uuid,
            'name': self._node_name,
            'uns': self._node_attributes.get('uns'),
            'type': self._node_attributes.get('room_type'),
            'code': self._node_attributes.get('room_code'),
            'status': self._node_attributes.get('room_status'),
            'description': self._node_attributes.get('room_description'),
            'short_description': self._node_attributes.get('room_short_description'),
            'is_root': self._node_attributes.get('is_root', False),
            'is_home': self._node_attributes.get('is_home', False),
            'is_special': self._node_attributes.get('is_special', False),
            'is_public': self._node_attributes.get('is_public', True),
            'is_accessible': self._node_attributes.get('is_accessible', True),
            'location': {
                'address': self._node_attributes.get('room_address'),
                'floor': self._node_attributes.get('room_floor'),
                'building': self._node_attributes.get('room_building'),
                'campus': self._node_attributes.get('room_campus'),
                'coordinates': {
                    'latitude': self._node_attributes.get('room_latitude'),
                    'longitude': self._node_attributes.get('room_longitude'),
                    'altitude': self._node_attributes.get('room_altitude')
                }
            },
            'physical_properties': {
                'area': self._node_attributes.get('room_area'),
                'height': self._node_attributes.get('room_height'),
                'capacity': self._node_attributes.get('room_capacity'),
                'rooms': self._node_attributes.get('room_rooms')
            },
            'environment': {
                'temperature': self._node_attributes.get('room_temperature'),
                'humidity': self._node_attributes.get('room_humidity'),
                'lighting': self._node_attributes.get('room_lighting'),
                'weather': self._node_attributes.get('room_weather'),
                'time': self._node_attributes.get('room_time'),
                'season': self._node_attributes.get('room_season')
            },
            'functions': self._node_attributes.get('room_functions', []),
            'services': self._node_attributes.get('room_services', []),
            'amenities': self._node_attributes.get('room_amenities', []),
            'equipment': self._node_attributes.get('room_equipment', []),
            'capacity': {
                'max_capacity': self._node_attributes.get('room_capacity'),
                'current_objects': self.get_object_count(),
                'is_full': self.is_full()
            },
            'exits': list(self.get_exits().keys()),
            'effects': [e['name'] for e in self.get_effects()],
            'manager': {
                'name': self._node_attributes.get('room_manager'),
                'phone': self._node_attributes.get('room_manager_phone'),
                'email': self._node_attributes.get('room_manager_email')
            },
            'created_at': self._node_created_at.isoformat() if self._node_created_at else None,
            'updated_at': self._node_updated_at.isoformat() if self._node_updated_at else None
        }
    
    def get_short_description(self) -> str:
        """获取房间简短描述"""
        short_desc = self._node_attributes.get('room_short_description', '')
        if short_desc:
            return short_desc
        
        # 如果没有简短描述，从完整描述中截取
        full_desc = self._node_attributes.get('room_description', '')
        if len(full_desc) > 100:
            return full_desc[:97] + "..."
        return full_desc
    
    def get_detailed_description(self) -> str:
        """获取房间详细描述"""
        desc = self._node_attributes.get('room_description', '')
        if not desc:
            return f"这是一个{self._node_attributes.get('room_type', 'normal')}房间。"
        
        # 添加房间状态信息
        status_info = []
        
        if self._node_attributes.get('is_root', False):
            status_info.append("这是系统的根节点。")
        
        if self._node_attributes.get('is_home', False):
            status_info.append("这是默认的起始地点。")
        
        if not self._node_attributes.get('is_lighted', True):
            status_info.append("房间内光线昏暗。")
        
        capacity = self._node_attributes.get('room_capacity', 0)
        if capacity > 0:
            current_count = self.get_object_count()
            status_info.append(f"房间内当前有{current_count}个对象，容量为{capacity}。")
        
        if status_info:
            desc += "\n\n" + " ".join(status_info)
        
        return desc


class SingularityRoom(Room):
    """
    奇点房间 - 系统的根节点和默认home
    
    继承自Room，作为所有用户的默认登录地点
    参考Evennia的DefaultHome设计模式
    """
    
    def __init__(self, config: Dict[str, Any] = None, **kwargs):
        # 设置奇点房间的特定属性
        singularity_attrs = {
            'uns': 'SYSTEM/SINGULARITY/ROOT/ROOM001',  # 系统级统一命名空间标识
            'room_type': 'singularity',
            'room_code': 'ROOM001',
            'room_name': '奇点屋',
            'room_name_en': 'Singularity Room',
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
        
        # 合并配置
        if config and 'attributes' in config:
            singularity_attrs.update(config['attributes'])
        
        super().__init__(name="Singularity Room", attributes=singularity_attrs)
    
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
{self._node_attributes.get('room_description', '')}

欢迎，{username}！你已成功进入CampusWorld系统。
这是你的起点，也是你探索这个虚拟世界的门户。

当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
房间状态: 正常
在线用户: 可通过 'who' 命令查看

输入 'help' 获取帮助信息。
"""
