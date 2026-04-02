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
from .room import Room, SingularityRoom
from .system import (
    BulletinBoard,
    SystemCommandAbility,
    SystemNotice,
    WorldRuntimeState,
    WorldInstallJob,
)
from .exit import Exit
from .things import (
    AccessTerminal,
    AvDisplay,
    ConferenceSeating,
    Furniture,
    LightingFixture,
    LogicalZone,
    LoungeFurniture,
    NetworkAccessPoint,
    NpcAgent,
    WorldThing,
)

# 图数据结构系统
from .graph import (
    Node,
    Relationship
)

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
    "Room",
    "SingularityRoom",
    "BulletinBoard",
    "SystemCommandAbility",
    "SystemNotice",
    "WorldRuntimeState",
    "WorldInstallJob",
    "Exit",
    "AccessTerminal",
    "AvDisplay",
    "ConferenceSeating",
    "Furniture",
    "LightingFixture",
    "LogicalZone",
    "LoungeFurniture",
    "NetworkAccessPoint",
    "NpcAgent",
    "WorldThing",
    
    # 图数据结构系统
    "Node",
    "Relationship",
    
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
model_factory.register_model("room", Room)
model_factory.register_model("system_bulletin_board", BulletinBoard)
model_factory.register_model("system_command_ability", SystemCommandAbility)
model_factory.register_model("system_notice", SystemNotice)
model_factory.register_model("exit", Exit)
model_factory.register_model("network_access_point", NetworkAccessPoint)
model_factory.register_model("av_display", AvDisplay)
model_factory.register_model("lighting_fixture", LightingFixture)
model_factory.register_model("conference_seating", ConferenceSeating)
model_factory.register_model("lounge_furniture", LoungeFurniture)

# 注册图节点模型
model_factory.register_model("graph_node", Node)
model_factory.register_model("relationship", Relationship)
