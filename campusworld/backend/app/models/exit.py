"""
出口模型定义 - 纯图数据设计

"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime

from .base import DefaultObject

if TYPE_CHECKING:
    from .room import Room
    from .character import Character
    from .user import User


class Exit(DefaultObject):
    """
    出口模型 - 纯图数据设计

    连接源房间和目标房间，支持访问控制、别名、描述等功能
    """
    
    def __init__(self, name: str, source_room_id: int, destination_room_id: int, 
                 config: Dict[str, Any] = None, **kwargs):
        # 设置出口特定的节点类型
        self._node_type = 'exit'
        
        # 设置出口默认属性
        default_attrs = {
            # ==================== 基础信息 ====================
            "exit_name": name,  # 出口名称，如 "north", "east"
            "exit_aliases": [],  # 别名列表，如 ["n", "north"]
            "exit_description": "",  # 出口描述
            "exit_short_description": "",  # 简短描述
            
            # ==================== 连接信息 ====================
            "source_room_id": source_room_id,  # 源房间ID
            "destination_room_id": destination_room_id,  # 目标房间ID
            
            # ==================== 访问控制 ====================
            "exit_locks": {},  # 锁系统，如 {"traverse": "perm:admin"}
            "exit_permissions": [],  # 所需权限列表
            "exit_requirements": [],  # 其他要求列表
            "exit_roles": [],  # 所需角色列表
            
            # ==================== 状态信息 ====================
            "is_hidden": False,  # 是否隐藏（不可见但可通过）
            "is_locked": False,  # 是否锁定
            "is_one_way": False,  # 是否单向（不自动创建反向出口）
            "is_closed": False,  # 是否关闭（如门）
            "is_broken": False,  # 是否损坏
            
            # ==================== 移动相关 ====================
            "move_message": "",  # 移动时的消息（离开源房间）
            "arrive_message": "",  # 到达时的消息（进入目标房间）
            "move_fail_message": "",  # 移动失败时的消息
            "exit_cost": 0,  # 移动消耗（如体力、时间）
            "exit_delay": 0,  # 移动延迟（秒）
            
            # ==================== 出口类型 ====================
            "exit_type": "normal",  # normal, door, portal, teleport, stairs, elevator, window
            "exit_subtype": "",  # 子类型，如 "wooden_door", "glass_door"
            
            # ==================== 特殊属性 ====================
            "exit_key": None,  # 钥匙对象ID（用于锁定的门）
            "exit_script": None,  # 出口脚本ID
            "exit_effects": [],  # 出口效果列表
            
            # ==================== 时间信息 ====================
            "exit_created_date": None,  # 出口创建日期
            "exit_last_used": None,  # 最后使用时间
            "exit_use_count": 0,  # 使用次数统计
        }
        
        # 设置默认标签
        default_tags = ['exit', 'normal']
        
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
        exit_type = default_attrs.get('exit_type', 'normal')
        if exit_type != 'normal':
            default_tags.append(exit_type)
        
        if default_attrs.get('is_locked'):
            default_tags.append('locked')
        if default_attrs.get('is_hidden'):
            default_tags.append('hidden')
        if default_attrs.get('is_one_way'):
            default_tags.append('one_way')
        
        default_config = {
            'attributes': default_attrs,
            'tags': default_tags,
        }
        
        # 设置出口的位置为源房间
        default_config['location_id'] = source_room_id
        
        super().__init__(name=name, **default_config)
    
    def __repr__(self):
        exit_name = self._node_attributes.get('exit_name', '')
        source_id = self._node_attributes.get('source_room_id')
        dest_id = self._node_attributes.get('destination_room_id')
        exit_type = self._node_attributes.get('exit_type', 'normal')
        return f"<Exit(name='{exit_name}', type='{exit_type}', {source_id}->{dest_id})>"
    
    # ==================== 别名管理 ====================
    
    def add_alias(self, alias: str) -> bool:
        """添加别名"""
        try:
            aliases = self._node_attributes.get('exit_aliases', [])
            alias_lower = alias.lower()
            if alias_lower not in aliases:
                aliases.append(alias_lower)
                self.set_node_attribute('exit_aliases', aliases)
                self.sync_to_node()
                return True
            return False
        except Exception as e:
            print(f"添加别名失败: {e}")
            return False
    
    def remove_alias(self, alias: str) -> bool:
        """移除别名"""
        try:
            aliases = self._node_attributes.get('exit_aliases', [])
            alias_lower = alias.lower()
            if alias_lower in aliases:
                aliases.remove(alias_lower)
                self.set_node_attribute('exit_aliases', aliases)
                self.sync_to_node()
                return True
            return False
        except Exception as e:
            print(f"移除别名失败: {e}")
            return False
    
    def get_aliases(self) -> List[str]:
        """获取所有别名"""
        return self._node_attributes.get('exit_aliases', []).copy()
    
    
    # ==================== 访问控制 ====================
    
    def can_traverse(self, character: 'Character') -> bool:
        """检查角色是否可以通过此出口"""
        # 检查是否隐藏（隐藏的出口需要特殊权限才能看到和使用）
        if self._node_attributes.get('is_hidden', False):
            # 隐藏的出口需要特殊权限
            if not self._check_hidden_access(character):
                return False
        
        # 检查是否锁定
        if self._node_attributes.get('is_locked', False):
            return False
        
        # 检查是否关闭（如门）
        if self._node_attributes.get('is_closed', False):
            return False
        
        # 检查是否损坏
        if self._node_attributes.get('is_broken', False):
            return False
        
        # 检查权限
        required_perms = self._node_attributes.get('exit_permissions', [])
        if required_perms:
            for perm in required_perms:
                if not self._check_permission(character, perm):
                    return False
        
        # 检查角色
        required_roles = self._node_attributes.get('exit_roles', [])
        if required_roles:
            if not self._check_roles(character, required_roles):
                return False
        
        # 检查锁系统
        locks = self._node_attributes.get('exit_locks', {})
        if locks:
            if not self._check_locks(character, locks):
                return False
        
        return True
    
    def _check_hidden_access(self, character: 'Character') -> bool:
        """检查是否有访问隐藏出口的权限"""
        # 默认需要管理员权限
        if hasattr(character, 'has_permission'):
            return character.has_permission('admin') or character.has_permission('builder')
        return False
    
    def _check_permission(self, character: 'Character', permission: str) -> bool:
        """检查权限"""
        if hasattr(character, 'has_permission'):
            return character.has_permission(permission)
        return False
    
    def _check_roles(self, character: 'Character', required_roles: List[str]) -> bool:
        """检查角色"""
        if hasattr(character, 'get_roles'):
            character_roles = character.get_roles()
            return any(role in character_roles for role in required_roles)
        return False
    
    def _check_locks(self, character: 'Character', locks: Dict[str, str]) -> bool:
        """检查锁系统"""
        # 简单的锁检查实现，可以根据需要扩展
        traverse_lock = locks.get('traverse', '')
        if traverse_lock:
            # 解析锁字符串，如 "perm:admin" 或 "role:builder"
            if traverse_lock.startswith('perm:'):
                perm = traverse_lock.split(':', 1)[1]
                return self._check_permission(character, perm)
            elif traverse_lock.startswith('role:'):
                role = traverse_lock.split(':', 1)[1]
                return self._check_roles(character, [role])
        return True
    
    def lock(self, lock_type: str = "traverse") -> bool:
        """锁定出口"""
        try:
            self.set_node_attribute('is_locked', True)
            # 更新锁系统
            locks = self._node_attributes.get('exit_locks', {})
            locks[lock_type] = "lock"
            self.set_node_attribute('exit_locks', locks)
            self.sync_to_node()
            return True
        except Exception as e:
            print(f"锁定出口失败: {e}")
            return False
    
    def unlock(self) -> bool:
        """解锁出口"""
        try:
            self.set_node_attribute('is_locked', False)
            self.sync_to_node()
            return True
        except Exception as e:
            print(f"解锁出口失败: {e}")
            return False
    
    def hide(self) -> bool:
        """隐藏出口"""
        try:
            self.set_node_attribute('is_hidden', True)
            self.sync_to_node()
            return True
        except Exception as e:
            print(f"隐藏出口失败: {e}")
            return False
    
    def show(self) -> bool:
        """显示出口"""
        try:
            self.set_node_attribute('is_hidden', False)
            self.sync_to_node()
            return True
        except Exception as e:
            print(f"显示出口失败: {e}")
            return False
    
    # ==================== 移动相关 ====================
    
    def get_description(self, character: 'Character' = None) -> str:
        """获取出口描述"""
        desc = self._node_attributes.get('exit_description', '')
        if not desc:
            # 默认描述
            dest_room = self.get_destination_room()
            if dest_room:
                dest_name = dest_room._node_name
                return f"通向 {dest_name} 的出口"
        return desc
    
    def get_move_message(self, character: 'Character') -> str:
        """获取移动消息（离开源房间时）"""
        msg = self._node_attributes.get('move_message', '')
        if not msg:
            exit_name = self._node_attributes.get('exit_name', '')
            msg = f"{character.name if hasattr(character, 'name') else 'Someone'} 向{exit_name}离开了。"
        return msg
    
    def get_arrive_message(self, character: 'Character') -> str:
        """获取到达消息（进入目标房间时）"""
        msg = self._node_attributes.get('arrive_message', '')
        if not msg:
            exit_name = self._node_attributes.get('exit_name', '')
            msg = f"{character.name if hasattr(character, 'name') else 'Someone'} 从{exit_name}到达了。"
        return msg
    
    def get_fail_message(self, character: 'Character') -> str:
        """获取移动失败消息"""
        msg = self._node_attributes.get('move_fail_message', '')
        if not msg:
            if self._node_attributes.get('is_locked'):
                msg = "出口被锁定了。"
            elif self._node_attributes.get('is_closed'):
                msg = "出口被关闭了。"
            else:
                msg = "你无法通过这个出口。"
        return msg
    
    def traverse(self, character: 'Character') -> bool:
        """通过出口移动角色"""
        # 检查是否可以通行
        if not self.can_traverse(character):
            return False
        
        # 获取目标房间
        dest_room = self.get_destination_room()
        if not dest_room:
            return False
        
        # 移动前钩子
        if not self.at_pre_traverse(character, dest_room):
            return False
        
        # 发送移动消息（给源房间的其他角色）
        move_msg = self.get_move_message(character)
        # TODO: 实现消息发送给源房间的其他角色
        
        # 执行移动
        old_location_id = character.location_id if hasattr(character, 'location_id') else None
        if hasattr(character, 'move_to') and character.move_to(dest_room):
            # 更新使用统计
            self._update_usage_stats()
            
            # 移动后钩子
            self.at_post_traverse(character, old_location_id, dest_room)
            
            # 发送到达消息（给目标房间的其他角色）
            arrive_msg = self.get_arrive_message(character)
            # TODO: 实现消息发送给目标房间的其他角色
            
            return True
        
        return False
    
    def at_pre_traverse(self, character: 'Character', destination: 'Room') -> bool:
        """移动前钩子"""
        # 消耗资源
        cost = self._node_attributes.get('exit_cost', 0)
        if cost > 0:
            # TODO: 实现资源消耗逻辑
            pass
        
        # 检查延迟
        delay = self._node_attributes.get('exit_delay', 0)
        if delay > 0:
            # TODO: 实现延迟逻辑
            pass
        
        return True
    
    def at_post_traverse(self, character: 'Character', source_room_id: Optional[int], 
                        destination: 'Room'):
        """移动后钩子"""
        # 可以在这里触发事件、记录日志等
        pass
    
    def _update_usage_stats(self):
        """更新使用统计"""
        try:
            use_count = self._node_attributes.get('exit_use_count', 0)
            self.set_node_attribute('exit_use_count', use_count + 1)
            self.set_node_attribute('exit_last_used', datetime.now().isoformat())
            self.sync_to_node()
        except Exception as e:
            print(f"更新使用统计失败: {e}")
    
    # ==================== 房间访问 ====================
    
    def get_source_room(self) -> Optional['Room']:
        """获取源房间对象"""
        try:
            from .graph import Node
            from app.core.database import SessionLocal
            
            source_id = self._node_attributes.get('source_room_id')
            if not source_id:
                return None
            
            session = SessionLocal()
            try:
                # 从数据库加载房间节点
                if isinstance(source_id, int):
                    room_node = session.query(Node).filter(
                        Node.id == source_id,
                        Node.type_code == 'room',
                        Node.is_active == True
                    ).first()
                else:
                    return None
                
                if room_node:
                    # 转换为 Room 对象
                    from .room import Room
                    room_obj = Room(
                        name=room_node.name,
                        config={'attributes': room_node.attributes or {}}
                    )
                    room_obj._node_uuid = str(room_node.uuid)
                    if hasattr(room_node, 'id'):
                        room_obj.id = room_node.id
                    return room_obj
                
                return None
            finally:
                session.close()
                
        except Exception as e:
            print(f"获取源房间失败: {e}")
            return None
    
    def get_destination_room(self) -> Optional['Room']:
        """获取目标房间对象"""
        try:
            from .graph import Node
            from app.core.database import SessionLocal
            
            dest_id = self._node_attributes.get('destination_room_id')
            if not dest_id:
                return None
            
            session = SessionLocal()
            try:
                # 从数据库加载房间节点
                if isinstance(dest_id, int):
                    room_node = session.query(Node).filter(
                        Node.id == dest_id,
                        Node.type_code == 'room',
                        Node.is_active == True
                    ).first()
                else:
                    return None
                
                if room_node:
                    # 转换为 Room 对象
                    from .room import Room
                    room_obj = Room(
                        name=room_node.name,
                        config={'attributes': room_node.attributes or {}}
                    )
                    room_obj._node_uuid = str(room_node.uuid)
                    if hasattr(room_node, 'id'):
                        room_obj.id = room_node.id
                    return room_obj
                
                return None
            finally:
                session.close()
                
        except Exception as e:
            print(f"获取目标房间失败: {e}")
            return None
    
    # ==================== 出口信息方法 ====================
    
    def get_exit_info(self) -> Dict[str, Any]:
        """获取出口详细信息"""
        return {
            'id': self.id if hasattr(self, 'id') else None,
            'uuid': self._node_uuid,
            'name': self._node_name,
            'exit_name': self._node_attributes.get('exit_name'),
            'aliases': self.get_aliases(),
            'description': self.get_description(),
            'exit_type': self._node_attributes.get('exit_type'),
            'source_room_id': self._node_attributes.get('source_room_id'),
            'destination_room_id': self._node_attributes.get('destination_room_id'),
            'is_locked': self._node_attributes.get('is_locked', False),
            'is_hidden': self._node_attributes.get('is_hidden', False),
            'is_one_way': self._node_attributes.get('is_one_way', False),
            'is_closed': self._node_attributes.get('is_closed', False),
            'use_count': self._node_attributes.get('exit_use_count', 0),
            'last_used': self._node_attributes.get('exit_last_used'),
        }
    
    def get_short_description(self) -> str:
        """获取出口简短描述"""
        short_desc = self._node_attributes.get('exit_short_description', '')
        if short_desc:
            return short_desc
        
        # 如果没有简短描述，从完整描述中截取
        full_desc = self._node_attributes.get('exit_description', '')
        if len(full_desc) > 50:
            return full_desc[:47] + "..."
        return full_desc if full_desc else self._node_attributes.get('exit_name', '')

