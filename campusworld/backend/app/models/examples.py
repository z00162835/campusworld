"""
模型系统使用示例

展示如何使用DefaultObject、DefaultAccount和组件系统
"""

from typing import Dict, Any
from .base import DefaultObject, DefaultAccount
from .factory import model_factory, InventoryMixin, StatsMixin, CombatMixin


# 示例1: 创建带有组件的自定义对象
class PlayerObject(DefaultObject, InventoryMixin, StatsMixin, CombatMixin):
    """
    玩家对象示例
    
    继承自DefaultObject，并混入多个组件
    """
    
    __tablename__ = "player_objects"
    
    # 玩家特定属性
    player_class = Column(String(50), default="warrior")  # 职业
    player_race = Column(String(50), default="human")     # 种族
    
    def __repr__(self):
        return f"<PlayerObject(id={self.id}, name='{self.name}', class='{self.player_class}')>"
    
    def get_player_info(self) -> Dict[str, Any]:
        """获取玩家信息"""
        return {
            "id": self.id,
            "name": self.name,
            "class": self.player_class,
            "race": self.player_race,
            "level": self.level,
            "health": f"{self.health}/{self.max_health}",
            "experience": f"{self.experience}/{self.max_experience}",
            "inventory_size": len(self.inventory) if self.inventory else 0
        }


# 示例2: 使用模型工厂创建对象
def create_player_with_factory(name: str, player_class: str, player_race: str) -> Dict[str, Any]:
    """
    使用模型工厂创建玩家对象配置
    """
    # 创建基础配置
    base_config = model_factory.create_custom_object(
        name=name,
        object_type="player",
        player_class=player_class,
        player_race=player_race
    )
    
    # 添加玩家特定配置
    player_config = {
        **base_config,
        "level": 1,
        "health": 100,
        "max_health": 100,
        "energy": 100,
        "max_energy": 100,
        "attack": 15,
        "defense": 8,
        "stats": {
            "strength": 10,
            "agility": 8,
            "intelligence": 6,
            "charisma": 7
        }
    }
    
    return player_config


# 示例3: 创建带有组件的模型类
def create_custom_model_example():
    """
    展示如何动态创建带有组件的模型类
    """
    # 创建一个带有物品栏和属性的对象类
    InventoryStatsObject = model_factory.create_model_with_components(
        DefaultObject, 
        "inventory", 
        "stats"
    )
    
    # 创建一个带有战斗功能的玩家类
    CombatPlayer = model_factory.create_model_with_components(
        DefaultObject,
        "inventory",
        "stats", 
        "combat"
    )
    
    return InventoryStatsObject, CombatPlayer


# 示例4: 对象交互示例
class GameObject(DefaultObject, InventoryMixin, CombatMixin):
    """
    游戏对象示例
    
    展示对象间的交互
    """
    
    __tablename__ = "game_objects"
    
    def interact_with(self, other: 'GameObject') -> Dict[str, Any]:
        """与其他对象交互"""
        if not self.is_active or not other.is_active:
            return {"success": False, "message": "对象不可交互"}
        
        # 检查是否可以战斗
        if hasattr(self, 'attack') and hasattr(other, 'take_damage'):
            result = self.attack_target(other)
            return {
                "type": "combat",
                "attacker": self.name,
                "target": other.name,
                **result
            }
        
        # 检查是否可以交易物品
        if hasattr(self, 'inventory') and hasattr(other, 'inventory'):
            return {
                "type": "trade",
                "message": f"{self.name} 和 {other.name} 可以交易物品"
            }
        
        return {
            "type": "interaction",
            "message": f"{self.name} 与 {other.name} 进行了互动"
        }


# 示例5: 校园世界集成示例
class CampusWorldObject(DefaultObject, StatsMixin):
    """
    校园世界对象示例
    
    展示如何将校园和世界系统集成
    """
    
    __tablename__ = "campus_world_objects"
    
    campus_id = Column(Integer, nullable=True)  # 关联校园
    world_id = Column(Integer, nullable=True)   # 关联世界
    
    def get_context_info(self) -> Dict[str, Any]:
        """获取上下文信息"""
        info = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "campus_id": self.campus_id,
            "world_id": self.world_id,
            "level": self.level,
            "stats": self.stats
        }
        
        # 添加位置信息
        if hasattr(self, 'location'):
            info["location"] = self.location.name if self.location else None
        
        return info


# 使用示例
if __name__ == "__main__":
    # 创建玩家配置
    warrior_config = create_player_with_factory(
        name="勇士阿瑞斯",
        player_class="warrior", 
        player_race="human"
    )
    print("勇士配置:", warrior_config)
    
    # 创建自定义模型类
    InventoryStatsObject, CombatPlayer = create_custom_model_example()
    print("自定义模型类:", InventoryStatsObject.__name__, CombatPlayer.__name__)
    
    # 列出可用组件
    print("可用组件:", model_factory.list_components())
    
    # 列出可用模型
    print("可用模型:", model_factory.list_models())
