"""
CampusWorld 模型包 - 纯图数据设计

所有模型基于图数据结构，存储在统一的Node表中
通过type和typeclass区分不同的对象类型
"""

# 基础模型
from .base import DefaultObject, DefaultAccount, GraphNodeInterface, GraphRelationshipInterface
from .user import User
from .campus import Campus
from .world import World, WorldObject

# 图数据结构系统
from .graph import (
    Node, 
    GraphNode, 
    Relationship
)
from .graph_sync import GraphSynchronizer

# 工厂和组件系统
from .factory import (
    ModelFactory, 
    ComponentMixin, 
    InventoryMixin, 
    StatsMixin, 
    CombatMixin,
    model_factory
)

__all__ = [
    # 基础模型
    "DefaultObject",
    "DefaultAccount",
    "GraphNodeInterface",
    "GraphRelationshipInterface",
    
    # 具体模型
    "User",
    "Campus",
    "World",
    "WorldObject",
    
    # 图数据结构系统
    "Node",
    "GraphNode",
    "Relationship",
    "GraphSynchronizer",
    
    # 工厂和组件系统
    "ModelFactory",
    "ComponentMixin",
    "InventoryMixin",
    "StatsMixin",
    "CombatMixin",
    "model_factory",
]

# 注册模型到工厂 - 纯图数据设计
model_factory.register_model("user", User)
model_factory.register_model("campus", Campus)
model_factory.register_model("world", World)
model_factory.register_model("world_object", WorldObject)

# 注册图节点模型
model_factory.register_model("graph_node", GraphNode)
model_factory.register_model("relationship", Relationship)
