"""
模型工厂和组件系统

参考Evennia的设计，提供：
- 模型工厂：动态创建和注册模型
- 组件系统：通过mixin扩展模型功能
- 类型注册：支持自定义模型类型
"""

from typing import Dict, Type, Any, Optional, List
from abc import ABC, abstractmethod
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from .base import DefaultObject, DefaultAccount


class ComponentMixin(ABC):
    """
    组件混入基类
    
    通过继承此类来为模型添加特定功能
    """
    
    @abstractmethod
    def get_component_name(self) -> str:
        """获取组件名称"""
        pass
    
    @abstractmethod
    def get_component_version(self) -> str:
        """获取组件版本"""
        pass


class InventoryMixin(ComponentMixin):
    """
    物品栏组件
    
    为对象添加物品栏功能
    """
    
    @declared_attr
    def inventory(cls):
        """物品栏"""
        return Column(JSON, default=list)
    
    @declared_attr
    def max_inventory_size(cls):
        """最大物品栏容量"""
        return Column(Integer, default=20)
    
    def get_component_name(self) -> str:
        return "inventory"
    
    def get_component_version(self) -> str:
        return "1.0.0"
    
    def add_item(self, item: dict) -> bool:
        """添加物品到物品栏"""
        if not self.inventory:
            self.inventory = []
        
        if len(self.inventory) >= self.max_inventory_size:
            return False
        
        self.inventory.append(item)
        return True
    
    def remove_item(self, item_id: str) -> bool:
        """从物品栏移除物品"""
        if not self.inventory:
            return False
        
        for i, item in enumerate(self.inventory):
            if item.get("id") == item_id:
                del self.inventory[i]
                return True
        return False
    
    def get_item(self, item_id: str) -> Optional[dict]:
        """获取物品栏中的物品"""
        if not self.inventory:
            return None
        
        for item in self.inventory:
            if item.get("id") == item_id:
                return item
        return None
    
    def has_item(self, item_id: str) -> bool:
        """检查是否有指定物品"""
        return self.get_item(item_id) is not None


class StatsMixin(ComponentMixin):
    """
    属性组件
    
    为对象添加属性系统
    """
    
    @declared_attr
    def stats(cls):
        """基础属性"""
        return Column(JSON, default=dict)
    
    @declared_attr
    def level(cls):
        """等级"""
        return Column(Integer, default=1)
    
    @declared_attr
    def experience(cls):
        """经验值"""
        return Column(Integer, default=0)
    
    @declared_attr
    def max_experience(cls):
        """升级所需经验值"""
        return Column(Integer, default=100)
    
    def get_component_name(self) -> str:
        return "stats"
    
    def get_component_version(self) -> str:
        return "1.0.0"
    
    def get_stat(self, stat_name: str, default: int = 0) -> int:
        """获取属性值"""
        if not self.stats:
            self.stats = {}
        return self.stats.get(stat_name, default)
    
    def set_stat(self, stat_name: str, value: int) -> None:
        """设置属性值"""
        if not self.stats:
            self.stats = {}
        self.stats[stat_name] = value
    
    def modify_stat(self, stat_name: str, modifier: int) -> None:
        """修改属性值"""
        current = self.get_stat(stat_name)
        self.set_stat(stat_name, current + modifier)
    
    def add_experience(self, amount: int) -> bool:
        """增加经验值"""
        self.experience += amount
        
        # 检查是否可以升级
        if self.experience >= self.max_experience:
            self.level_up()
            return True
        return False
    
    def level_up(self) -> None:
        """升级"""
        self.level += 1
        self.experience = 0
        self.max_experience = int(self.max_experience * 1.5)  # 经验值需求增加


class CombatMixin(ComponentMixin):
    """
    战斗组件
    
    为对象添加战斗功能
    """
    
    @declared_attr
    def health(cls):
        """生命值"""
        return Column(Integer, default=100)
    
    @declared_attr
    def max_health(cls):
        """最大生命值"""
        return Column(Integer, default=100)
    
    @declared_attr
    def attack(cls):
        """攻击力"""
        return Column(Integer, default=10)
    
    @declared_attr
    def defense(cls):
        """防御力"""
        return Column(Integer, default=5)
    
    @declared_attr
    def is_alive(cls):
        """是否存活"""
        return Column(Boolean, default=True)
    
    def get_component_name(self) -> str:
        return "combat"
    
    def get_component_version(self) -> str:
        return "1.0.0"
    
    def take_damage(self, damage: int) -> int:
        """受到伤害"""
        actual_damage = max(1, damage - self.defense)
        self.health = max(0, self.health - actual_damage)
        
        if self.health <= 0:
            self.is_alive = False
        
        return actual_damage
    
    def heal(self, amount: int) -> int:
        """治疗"""
        if not self.is_alive:
            return 0
        
        old_health = self.health
        self.health = min(self.max_health, self.health + amount)
        return self.health - old_health
    
    def attack_target(self, target: 'CombatMixin') -> dict:
        """攻击目标"""
        if not self.is_alive or not target.is_alive:
            return {"success": False, "message": "无法攻击"}
        
        damage = self.attack
        actual_damage = target.take_damage(damage)
        
        return {
            "success": True,
            "damage": actual_damage,
            "target_health": target.health,
            "target_alive": target.is_alive
        }
    
    def get_health_percentage(self) -> float:
        """获取生命值百分比"""
        if self.max_health <= 0:
            return 0.0
        return (self.health / self.max_health) * 100


class ModelFactory:
    """
    模型工厂
    
    负责创建和注册自定义模型类型
    """
    
    def __init__(self):
        self._registered_models: Dict[str, Type] = {}
        self._component_registry: Dict[str, Type[ComponentMixin]] = {}
    
    def register_model(self, name: str, model_class: Type) -> None:
        """注册模型类"""
        self._registered_models[name] = model_class
    
    def get_model(self, name: str) -> Optional[Type]:
        """获取注册的模型类"""
        return self._registered_models.get(name)
    
    def list_models(self) -> List[str]:
        """列出所有注册的模型"""
        return list(self._registered_models.keys())
    
    def register_component(self, name: str, component_class: Type[ComponentMixin]) -> None:
        """注册组件类"""
        self._component_registry[name] = component_class
    
    def get_component(self, name: str) -> Optional[Type[ComponentMixin]]:
        """获取注册的组件类"""
        return self._component_registry.get(name)
    
    def list_components(self) -> List[str]:
        """列出所有注册的组件"""
        return list(self._component_registry.keys())
    
    def create_model_with_components(self, base_class: Type, *component_names: str) -> Type:
        """
        创建带有指定组件的模型类
        
        Args:
            base_class: 基础模型类
            *component_names: 组件名称列表
            
        Returns:
            新的模型类
        """
        components = []
        for name in component_names:
            component_class = self.get_component(name)
            if component_class:
                components.append(component_class)
            else:
                raise ValueError(f"Component '{name}' not found")
        
        # 创建新的模型类
        class_name = f"{base_class.__name__}With{''.join(c.capitalize() for c in component_names)}"
        
        # 动态创建类
        new_class = type(class_name, (base_class,) + tuple(components), {})
        
        return new_class
    
    def create_custom_object(self, name: str, object_type: str, **attributes) -> Dict[str, Any]:
        """
        创建自定义对象
        
        Args:
            name: 对象名称
            object_type: 对象类型
            **attributes: 对象属性
            
        Returns:
            对象配置字典
        """
        base_config = {
            "name": name,
            "type": object_type,
            "attributes": attributes or {},
            "tags": [object_type],
            "is_active": True,
            "is_public": True,
            "access_level": "normal"
        }
        
        # 根据类型添加特定配置
        if object_type == "player":
            base_config.update({
                "is_movable": True,
                "is_interactive": True,
                "is_visible": True,
                "level": 1,
                "health": 100,
                "max_health": 100,
                "energy": 100,
                "max_energy": 100
            })
        elif object_type == "npc":
            base_config.update({
                "is_movable": False,
                "is_interactive": True,
                "is_visible": True,
                "level": 1,
                "health": 50,
                "max_health": 50
            })
        elif object_type == "item":
            base_config.update({
                "is_movable": True,
                "is_interactive": True,
                "is_visible": True,
                "rarity": "common"
            })
        elif object_type == "location":
            base_config.update({
                "is_movable": False,
                "is_interactive": False,
                "is_visible": True
            })
        
        return base_config


# 全局模型工厂实例
model_factory = ModelFactory()

# 注册默认组件
model_factory.register_component("inventory", InventoryMixin)
model_factory.register_component("stats", StatsMixin)
model_factory.register_component("combat", CombatMixin)

# 注册默认模型
model_factory.register_model("default_object", DefaultObject)
model_factory.register_model("default_account", DefaultAccount)
model_factory.register_model("user", None)  # 将在导入后注册
model_factory.register_model("campus", None)
model_factory.register_model("world", None)
model_factory.register_model("world_object", None)
model_factory.register_model("world_activity", None)
