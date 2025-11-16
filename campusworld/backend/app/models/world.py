"""
世界相关模型定义 - 纯图数据设计

所有数据存储在Node中，通过type和typeclass区分
World: type='world', typeclass='app.models.world.World'
WorldObject: type='world_object', typeclass='app.models.world.WorldObject'
"""

from typing import Optional, Dict, Any
from datetime import datetime

from .base import DefaultObject


class World(DefaultObject):
    """
    世界模型 - 纯图数据设计
    
    继承自DefaultObject，所有数据存储在Node中
    type='world', typeclass='app.models.world.World'
    """
    
    def __init__(self, name: str, **kwargs):
        # 设置世界特定的节点类型
        self._node_type = 'world'
        
        # 设置世界默认属性
        world_attrs = {
            # 世界基本信息
            'world_type': kwargs.get('world_type', 'virtual'),  # virtual, physical, mixed
            'theme': kwargs.get('theme'),  # 主题
            'genre': kwargs.get('genre'),  # 类型
            'difficulty': kwargs.get('difficulty', 'normal'),  # easy, normal, hard, expert
            
            # 世界设置
            'max_players': kwargs.get('max_players', 100),
            'is_private': kwargs.get('is_private', False),
            'requires_invitation': kwargs.get('requires_invitation', False),
            'allow_guest': kwargs.get('allow_guest', True),
            
            # 世界状态
            'status': kwargs.get('status', 'active'),  # active, inactive, maintenance, closed
            'season': kwargs.get('season'),  # 季节或版本
            'version': kwargs.get('version', '1.0'),
            
            # 统计信息
            'player_count': kwargs.get('player_count', 0),
            'object_count': kwargs.get('object_count', 0),
            'activity_count': kwargs.get('activity_count', 0),
            'total_visits': kwargs.get('total_visits', 0),
            
            # 配置信息
            'rules': kwargs.get('rules'),  # 世界规则
            'welcome_message': kwargs.get('welcome_message'),  # 欢迎消息
            'settings': kwargs.get('settings', {}),  # 世界设置
            'physics': kwargs.get('physics', {}),  # 物理设置
            'environment': kwargs.get('environment', {}),  # 环境设置
            
            # 创建者信息
            'creator_id': kwargs.get('creator_id'),
            'created_by': kwargs.get('created_by'),
            
            **kwargs
        }
        
        super().__init__(name=name, **world_attrs)
    
    def __repr__(self):
        name = self._node_attributes.get('name', 'Unknown')
        world_type = self._node_attributes.get('world_type', 'virtual')
        return f"<World(uuid='{self._node_uuid}', name='{name}', type='{world_type}')>"
    
    # ==================== 世界属性访问器 ====================
    
    @property
    def world_type(self) -> str:
        """获取世界类型"""
        return self._node_attributes.get('world_type', 'virtual')
    
    @world_type.setter
    def world_type(self, value: str):
        """设置世界类型"""
        self.set_node_attribute('world_type', value)
    
    @property
    def max_players(self) -> int:
        """获取最大玩家数"""
        return self._node_attributes.get('max_players', 100)
    
    @max_players.setter
    def max_players(self, value: int):
        """设置最大玩家数"""
        self.set_node_attribute('max_players', value)
    
    @property
    def player_count(self) -> int:
        """获取玩家数量"""
        return self._node_attributes.get('player_count', 0)
    
    @player_count.setter
    def player_count(self, value: int):
        """设置玩家数量"""
        self.set_node_attribute('player_count', value)
    
    @property
    def status(self) -> str:
        """获取状态"""
        return self._node_attributes.get('status', 'active')
    
    @status.setter
    def status(self, value: str):
        """设置状态"""
        self.set_node_attribute('status', value)
    
    # ==================== 世界方法 ====================
    
    def get_objects(self):
        """获取世界中的所有对象"""
        return self.get_relationships("contains")
    
    def get_players(self):
        """获取世界中的所有玩家"""
        return self.get_relationships("world_activity")
    
    def add_player(self, user, role: str = "player") -> bool:
        """添加玩家"""
        try:
            relationship = user.create_relationship(
                target=self,
                rel_type="world_activity",
                role=role,
                status="active",
                joined_at=datetime.now(),
                is_active=True
            )
            
            if relationship:
                self.player_count = len(self.get_players())
                return True
            return False
        except Exception as e:
            print(f"添加玩家失败: {e}")
            return False


class WorldObject(DefaultObject):
    """
    世界对象模型 - 纯图数据设计
    
    继承自DefaultObject，所有数据存储在Node中
    type='world_object', typeclass='app.models.world.WorldObject'
    """
    
    def __init__(self, name: str, **kwargs):
        # 设置世界对象特定的节点类型
        self._node_type = 'world_object'
        
        # 设置世界对象默认属性
        object_attrs = {
            # 对象基本信息
            'object_type': kwargs.get('object_type', 'item'),  # item, npc, building, decoration
            'category': kwargs.get('category'),  # 分类
            'rarity': kwargs.get('rarity', 'common'),  # common, uncommon, rare, epic, legendary
            
            # 对象属性
            'value': kwargs.get('value', 0),  # 价值
            'weight': kwargs.get('weight', 0),  # 重量
            'durability': kwargs.get('durability', 100),  # 耐久度
            
            # 状态信息
            'is_interactive': kwargs.get('is_interactive', True),  # 是否可交互
            'is_movable': kwargs.get('is_movable', True),  # 是否可移动
            'is_tradable': kwargs.get('is_tradable', True),  # 是否可交易
            
            # 位置信息
            'position': kwargs.get('position', {}),  # 位置坐标
            'rotation': kwargs.get('rotation', {}),  # 旋转角度
            
            # 功能信息
            'functions': kwargs.get('functions', []),  # 功能列表
            'effects': kwargs.get('effects', []),  # 效果列表
            
            **kwargs
        }
        
        super().__init__(name=name, **object_attrs)
    
    def __repr__(self):
        name = self._node_attributes.get('name', 'Unknown')
        object_type = self._node_attributes.get('object_type', 'item')
        return f"<WorldObject(uuid='{self._node_uuid}', name='{name}', type='{object_type}')>"
    
    # ==================== 世界对象属性访问器 ====================
    
    @property
    def object_type(self) -> str:
        """获取对象类型"""
        return self._node_attributes.get('object_type', 'item')
    
    @object_type.setter
    def object_type(self, value: str):
        """设置对象类型"""
        self.set_node_attribute('object_type', value)
    
    @property
    def category(self) -> Optional[str]:
        """获取分类"""
        return self._node_attributes.get('category')
    
    @category.setter
    def category(self, value: Optional[str]):
        """设置分类"""
        self.set_node_attribute('category', value)
    
    @property
    def rarity(self) -> str:
        """获取稀有度"""
        return self._node_attributes.get('rarity', 'common')
    
    @rarity.setter
    def rarity(self, value: str):
        """设置稀有度"""
        self.set_node_attribute('rarity', value)
    
    # ==================== 世界对象方法 ====================
    
    def move_to(self, x: float, y: float, z: float = 0) -> None:
        """移动到指定位置"""
        self.set_node_attribute('position', {
            'x': x,
            'y': y,
            'z': z,
            'updated_at': datetime.now().isoformat()
        })
    
    def use(self, user) -> Dict[str, Any]:
        """使用对象"""
        if not self._node_attributes.get('is_interactive', True):
            return {"success": False, "message": "对象不可交互"}
        
        return {
            "success": True,
            "message": f"{user.name} 使用了 {self.name}",
            "effects": self._node_attributes.get('effects', [])
        }
