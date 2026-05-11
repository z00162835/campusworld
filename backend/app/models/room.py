"""
房间模型定义 - 纯图数据设计

"""
from typing import Dict, Any, List, Optional, TYPE_CHECKING, Union
from datetime import datetime
from .base import DefaultObject
if TYPE_CHECKING:
    from .user import User
    from .exit import Exit

class Room(DefaultObject):
    """
    房间模型 - 纯图数据设计

    """

    def __init__(self, name: str, config: Dict[str, Any]=None, **kwargs):
        """
        房间模型初始化。

        注意：name 是必需参数，不提供默认值，避免意外创建与奇点屋同名的房间。
        """
        if not name or not name.strip():
            raise ValueError('房间名称不能为空')
        self._node_type = 'room'
        disable_auto_sync = bool(kwargs.pop('disable_auto_sync', False))
        default_attrs = {'uns': 'RES001/BLD001/FLOOR01/ROOM001', 'room_type': 'normal', 'room_code': 'ROOM001', 'room_name': '示例房间', 'room_name_en': 'Example Room', 'room_description': '', 'room_short_description': '', 'room_address': '', 'room_floor': 1, 'room_building': '', 'room_campus': '', 'room_latitude': 0.0, 'room_longitude': 0.0, 'room_altitude': 0.0, 'room_area': 0.0, 'room_height': 3.0, 'room_capacity': 0, 'room_rooms': 0, 'room_temperature': 20, 'room_humidity': 50, 'room_lighting': 'normal', 'room_weather': 'normal', 'room_time': 'normal', 'room_date': 'normal', 'room_season': 'normal', 'room_status': 'active', 'is_public': True, 'is_accessible': True, 'is_lighted': True, 'is_indoors': True, 'is_root': False, 'is_home': False, 'is_special': False, 'access_requirements': [], 'permission_required': [], 'role_required': [], 'allow_teleport': True, 'room_objects': [], 'room_functions': [], 'room_services': [], 'room_amenities': [], 'room_equipment': [], 'room_exits': {}, 'room_exit_ids': [], 'room_scripts': [], 'room_effects': [], 'room_ambiance': '', 'room_dtmodels': {}, 'room_created_date': None, 'room_last_renovation': None, 'room_expected_lifespan': 30}
        default_tags = ['room', 'normal']
        if config:
            if 'attributes' in config:
                default_attrs.update(config['attributes'])
            if 'tags' in config:
                default_tags.extend(config['tags'])
        default_attrs.update(kwargs)
        if default_attrs.get('is_root'):
            default_tags.append('root')
        if default_attrs.get('is_home'):
            default_tags.append('home')
        if default_attrs.get('is_special'):
            default_tags.append('special')
        if default_attrs.get('room_type'):
            default_tags = ['room', default_attrs['room_type']] + [tag for tag in default_tags if tag not in ['room', default_attrs['room_type']]]
        default_config = {'attributes': default_attrs, 'tags': default_tags}
        super().__init__(name=name, disable_auto_sync=disable_auto_sync, **default_config)

    def __repr__(self):
        room_type = self._node_attributes.get('room_type', 'normal')
        is_root = self._node_attributes.get('is_root', False)
        root_indicator = ' [ROOT]' if is_root else ''
        return f"<Room(name='{self._node_name}', type='{room_type}'{root_indicator})>"

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
            print(f'添加对象到房间失败: {e}')
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
            print(f'从房间移除对象失败: {e}')
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
        if capacity <= 0:
            return False
        return self.get_object_count() >= capacity

    def add_exit(self, direction: str, target_room_id: int, aliases: List[str]=None, create_reverse: bool=True, reverse_name: str=None, **kwargs) -> Optional['Exit']:
        """
        添加出口 - 创建 Exit 对象
        
        Args:
            direction: 出口方向名称，如 "north", "east"
            target_room_id: 目标房间ID
            aliases: 出口别名列表，如 ["n", "north"]
            create_reverse: 是否自动创建反向出口
            reverse_name: 反向出口名称，如果不提供则自动生成
            **kwargs: 其他出口属性
        
        Returns:
            Exit对象，如果创建失败则返回None
        """
        try:
            existing_exit = self.find_exit(direction)
            if existing_exit:
                print(f"出口 '{direction}' 已存在")
                return None
            from .exit import Exit
            exit_obj = Exit(name=direction, source_room_id=self.id if hasattr(self, 'id') else None, destination_room_id=target_room_id, config={'attributes': {'exit_aliases': aliases or [], **kwargs}})
            exit_obj.sync_to_node()
            exit_ids = self._node_attributes.get('room_exit_ids', [])
            if hasattr(exit_obj, 'id') and exit_obj.id:
                exit_ids.append(exit_obj.id)
            else:
                exit_ids.append(exit_obj._node_uuid)
            self.set_node_attribute('room_exit_ids', exit_ids)
            room_exits = self._node_attributes.get('room_exits', {})
            room_exits[direction] = target_room_id
            self.set_node_attribute('room_exits', room_exits)
            self.sync_to_node()
            if create_reverse and (not exit_obj._node_attributes.get('is_one_way', False)):
                reverse = reverse_name or self._get_reverse_direction(direction)
                if reverse:
                    pass
            return exit_obj
        except Exception as e:
            print(f'添加出口失败: {e}')
            import traceback
            traceback.print_exc()
            return None

    def remove_exit(self, direction: str) -> bool:
        """
        移除出口
        
        Args:
            direction: 出口方向名称或别名
        
        Returns:
            bool: 是否成功移除
        """
        try:
            exit_obj = self.find_exit(direction)
            if not exit_obj:
                return False
            exit_ids = self._node_attributes.get('room_exit_ids', [])
            exit_uuid = exit_obj._node_uuid
            exit_ids = [eid for eid in exit_ids if eid != exit_uuid and (hasattr(exit_obj, 'id') and eid != exit_obj.id)]
            self.set_node_attribute('room_exit_ids', exit_ids)
            room_exits = self._node_attributes.get('room_exits', {})
            exit_name = exit_obj._node_attributes.get('exit_name', direction)
            if exit_name in room_exits:
                del room_exits[exit_name]
            self.set_node_attribute('room_exits', room_exits)
            self.sync_to_node()
            exit_obj.set_node_active(False)
            exit_obj.sync_to_node()
            return True
        except Exception as e:
            print(f'移除出口失败: {e}')
            return False

    def get_exits(self) -> List['Exit']:
        """
        获取所有出口对象
        
        Returns:
            Exit对象列表
        """
        try:
            exit_ids = self._node_attributes.get('room_exit_ids', [])
            exits = []
            for exit_id in exit_ids:
                exit_obj = self._get_exit_by_id(exit_id)
                if exit_obj:
                    exits.append(exit_obj)
            return exits
        except Exception as e:
            print(f'获取出口列表失败: {e}')
            return []

    def get_exit(self, direction: str) -> Optional['Exit']:
        """
        获取指定方向的出口对象
        
        Args:
            direction: 出口方向名称或别名
        
        Returns:
            Exit对象，如果不存在则返回None
        """
        return self.find_exit(direction)

    def find_exit(self, name: str) -> Optional['Exit']:
        """
        根据名称或别名查找出口
        
        Args:
            name: 出口名称或别名
        
        Returns:
            Exit对象，如果不存在则返回None
        """
        try:
            exits = self.get_exits()
            for exit_obj in exits:
                if exit_obj.match_name(name):
                    return exit_obj
            return None
        except Exception as e:
            print(f'查找出口失败: {e}')
            return None

    def has_exit(self, direction: str) -> bool:
        """
        检查是否有指定方向的出口
        
        Args:
            direction: 出口方向名称或别名
        
        Returns:
            bool: 是否存在该出口
        """
        return self.find_exit(direction) is not None

    def get_exit_directions(self) -> List[str]:
        """
        获取所有出口方向名称
        
        Returns:
            出口方向名称列表
        """
        exits = self.get_exits()
        return [exit_obj._node_attributes.get('exit_name', '') for exit_obj in exits if exit_obj._node_attributes.get('exit_name')]

    def _get_exit_by_id(self, exit_id: Union[int, str]) -> Optional['Exit']:
        """
        根据ID或UUID获取出口对象
        
        Args:
            exit_id: 出口ID或UUID
        
        Returns:
            Exit对象，如果不存在则返回None
        """
        try:
            from .model_manager import model_manager
            from .graph import Node
            from app.core.database import SessionLocal
            session = SessionLocal()
            try:
                if isinstance(exit_id, int):
                    node = session.query(Node).filter(Node.id == exit_id).first()
                else:
                    node = session.query(Node).filter(Node.uuid == exit_id).first()
                if node and node.type_code == 'exit':
                    from app.models.exit import Exit
                    from app.models.graph_sync import GraphSynchronizer
                    exit_obj = GraphSynchronizer().sync_node_to_object(node, Exit)
                    if exit_obj is not None and hasattr(node, 'id'):
                        exit_obj.id = node.id
                    return exit_obj
                return None
            finally:
                session.close()
        except Exception as e:
            print(f'根据ID获取出口失败: {e}')
            return None

    def _get_reverse_direction(self, direction: str) -> Optional[str]:
        """
        获取反向方向
        
        Args:
            direction: 方向名称
        
        Returns:
            反向方向名称，如果无法确定则返回None
        """
        reverse_map = {'north': 'south', 'south': 'north', 'east': 'west', 'west': 'east', 'northeast': 'southwest', 'southwest': 'northeast', 'northwest': 'southeast', 'southeast': 'northwest', 'up': 'down', 'down': 'up', 'in': 'out', 'out': 'in', 'enter': 'exit', 'exit': 'enter'}
        return reverse_map.get(direction.lower())

    def can_access(self, user: 'User') -> bool:
        """检查用户是否可以访问此房间"""
        if not self._node_attributes.get('is_accessible', True):
            return False
        required_permissions = self._node_attributes.get('permission_required', [])
        if required_permissions:
            for permission in required_permissions:
                if not user.has_permission(permission):
                    return False
        required_roles = self._node_attributes.get('role_required', [])
        if required_roles:
            user_roles = user._node_attributes.get('roles', [])
            if not any((role in user_roles for role in required_roles)):
                return False
        return True

    def can_enter(self, user: 'User') -> bool:
        """检查用户是否可以进入此房间"""
        if not self.can_access(user):
            return False
        if self.is_full():
            return False
        return True

    def add_effect(self, effect_name: str, effect_data: Dict[str, Any]) -> bool:
        """添加房间效果"""
        try:
            room_effects = self._node_attributes.get('room_effects', [])
            effect = {'name': effect_name, 'data': effect_data, 'added_at': datetime.now().isoformat()}
            room_effects.append(effect)
            self.set_node_attribute('room_effects', room_effects)
            return True
        except Exception as e:
            print(f'添加房间效果失败: {e}')
            return False

    def remove_effect(self, effect_name: str) -> bool:
        """移除房间效果"""
        try:
            room_effects = self._node_attributes.get('room_effects', [])
            room_effects = [e for e in room_effects if e.get('name') != effect_name]
            self.set_node_attribute('room_effects', room_effects)
            return True
        except Exception as e:
            print(f'移除房间效果失败: {e}')
            return False

    def get_effects(self) -> List[Dict[str, Any]]:
        """获取所有房间效果"""
        return self._node_attributes.get('room_effects', []).copy()

    def has_effect(self, effect_name: str) -> bool:
        """检查是否有指定效果"""
        effects = self._node_attributes.get('room_effects', [])
        return any((e.get('name') == effect_name for e in effects))

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
        summary = f'\n房间信息摘要:\n  名称: {name}\n  统一命名空间标识: {uns}\n  代码: {room_code}\n  类型: {room_type}\n  状态: {room_status}\n  地址: {room_address}\n  面积: {room_area} 平方米\n  容量: {room_capacity} 人\n  当前对象数: {self.get_object_count()} 个\n        '
        return summary.strip()

    def get_room_info(self) -> Dict[str, Any]:
        """获取房间详细信息"""
        return {'id': self.id, 'uuid': self._node_uuid, 'name': self._node_name, 'uns': self._node_attributes.get('uns'), 'type': self._node_attributes.get('room_type'), 'code': self._node_attributes.get('room_code'), 'status': self._node_attributes.get('room_status'), 'description': self._node_attributes.get('room_description'), 'short_description': self._node_attributes.get('room_short_description'), 'is_root': self._node_attributes.get('is_root', False), 'is_home': self._node_attributes.get('is_home', False), 'is_special': self._node_attributes.get('is_special', False), 'is_public': self._node_attributes.get('is_public', True), 'is_accessible': self._node_attributes.get('is_accessible', True), 'location': {'address': self._node_attributes.get('room_address'), 'floor': self._node_attributes.get('room_floor'), 'building': self._node_attributes.get('room_building'), 'campus': self._node_attributes.get('room_campus'), 'coordinates': {'latitude': self._node_attributes.get('room_latitude'), 'longitude': self._node_attributes.get('room_longitude'), 'altitude': self._node_attributes.get('room_altitude')}}, 'physical_properties': {'area': self._node_attributes.get('room_area'), 'height': self._node_attributes.get('room_height'), 'capacity': self._node_attributes.get('room_capacity'), 'rooms': self._node_attributes.get('room_rooms')}, 'environment': {'temperature': self._node_attributes.get('room_temperature'), 'humidity': self._node_attributes.get('room_humidity'), 'lighting': self._node_attributes.get('room_lighting'), 'weather': self._node_attributes.get('room_weather'), 'time': self._node_attributes.get('room_time'), 'season': self._node_attributes.get('room_season')}, 'functions': self._node_attributes.get('room_functions', []), 'services': self._node_attributes.get('room_services', []), 'amenities': self._node_attributes.get('room_amenities', []), 'equipment': self._node_attributes.get('room_equipment', []), 'capacity': {'max_capacity': self._node_attributes.get('room_capacity'), 'current_objects': self.get_object_count(), 'is_full': self.is_full()}, 'exits': self.get_exit_directions(), 'exits_info': [exit_obj.get_exit_info() for exit_obj in self.get_exits()], 'effects': [e['name'] for e in self.get_effects()], 'manager': {'name': self._node_attributes.get('room_manager'), 'phone': self._node_attributes.get('room_manager_phone'), 'email': self._node_attributes.get('room_manager_email')}, 'created_at': self._node_created_at.isoformat() if self._node_created_at else None, 'updated_at': self._node_updated_at.isoformat() if self._node_updated_at else None}

    def get_short_description(self) -> str:
        """获取房间简短描述"""
        short_desc = self._node_attributes.get('room_short_description', '')
        if short_desc:
            return short_desc
        full_desc = self._node_attributes.get('room_description', '')
        if len(full_desc) > 100:
            return full_desc[:97] + '...'
        return full_desc

    def get_detailed_description(self) -> str:
        """获取房间详细描述"""
        desc = self._node_attributes.get('room_description', '')
        if not desc:
            return f"这是一个{self._node_attributes.get('room_type', 'normal')}房间。"
        status_info = []
        if self._node_attributes.get('is_root', False):
            status_info.append('这是系统的根节点。')
        if self._node_attributes.get('is_home', False):
            status_info.append('这是默认的起始地点。')
        if not self._node_attributes.get('is_lighted', True):
            status_info.append('房间内光线昏暗。')
        capacity = self._node_attributes.get('room_capacity', 0)
        if capacity > 0:
            current_count = self.get_object_count()
            status_info.append(f'房间内当前有{current_count}个对象，容量为{capacity}。')
        if status_info:
            desc += '\n\n' + ' '.join(status_info)
        return desc

class SingularityRoom(Room):
    """
    奇点房间 - 系统的根节点和默认home
    
    继承自Room，作为所有用户的默认登录地点
    参考Evennia的DefaultHome设计模式
    """

    def __init__(self, config: Dict[str, Any]=None, **kwargs):
        singularity_attrs = {'uns': 'SYSTEM/SINGULARITY/ROOT/ROOM001', 'room_type': 'singularity', 'room_code': 'ROOM001', 'room_name': '奇点屋', 'room_name_en': 'Singularity Room', 'room_description': self._get_default_description(), 'room_short_description': '奇点屋', 'is_root': True, 'is_home': True, 'is_special': True, 'is_public': True, 'is_accessible': True, 'is_lighted': True, 'is_indoors': True, 'room_capacity': 0, 'room_temperature': 22, 'room_humidity': 45, 'room_lighting': 'bright', 'allow_pvp': False, 'allow_combat': False, 'allow_magic': True, 'allow_teleport': True, 'room_ambiance': '这是CampusOS的主入口，所有的新旅程都从这里开始。', **kwargs}
        if config and 'attributes' in config:
            singularity_attrs.update(config['attributes'])
        super().__init__(name='Singularity Room', config={'attributes': singularity_attrs}, **kwargs)

    def _get_default_description(self) -> str:
        """获取默认描述"""
        return "\n欢迎来到CampusOS的主入口\n\n这是所有用户进入CampusWorld的起点。\n在这里，你可以感受到无限的可能性，就像宇宙大爆炸前的奇点一样，\n蕴含着整个世界的潜力。\n\n房间内光线柔和，温度适宜，空气中弥漫着一种神秘而充满希望的氛围。\n四周的墙壁似乎没有边界，延伸向无尽的远方。\n\n你可以在这里：\n- 熟悉系统的基本操作\n- 查看可用的命令和功能\n- 准备开始你的Campusworld之旅\n- 与其他用户交流\n\n输入 'help' 查看可用命令，或输入 'look' 查看周围环境。\n"

    def __repr__(self):
        return f"<SingularityRoom(name='{self._node_name}', is_root=True, is_home=True)>"

    def get_welcome_message(self, username: str) -> str:
        """获取用户欢迎消息"""
        return f"\n{self._node_attributes.get('room_description', '')}\n\n欢迎，{username}！你已成功进入CampusWorld系统。\n这是你的起点，也是你探索这个虚拟世界的门户。\n\n当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n房间状态: 正常\n在线用户: 可通过 'who' 命令查看\n\n输入 'help' 获取帮助信息。\n"
