# CampusWorld 模型系统

## 概述

CampusWorld 模型系统参考 Evennia MUD 引擎的设计理念，提供了一个灵活、可扩展的数据模型架构。系统支持层次化继承、组件混入、动态类型创建等高级特性。

## 核心设计理念

### 1. 层次化继承
- **DefaultObject**: 所有本体类类型对象的基类
- **DefaultAccount**: 用户账户的基类
- 通过继承实现功能的组合和扩展

### 2. 组件系统
- 通过 Mixin 类实现功能的模块化
- 支持动态组合不同的功能组件
- 每个组件都是独立的、可重用的功能单元

### 3. 模型工厂
- 支持动态创建和注册模型类型
- 提供组件组合的自动化机制
- 支持运行时模型类型扩展

## 基础模型类

### DefaultObject
所有本体类类型对象的基类，提供：

- **基础属性**: 名称、描述、关键词、标签
- **位置系统**: 当前位置、默认位置、内容管理
- **动态属性**: 支持运行时添加/修改属性
- **标签系统**: 灵活的标签管理
- **权限控制**: 访问级别和可见性控制

```python
from app.models.base import DefaultObject

class MyObject(DefaultObject):
    __tablename__ = "my_objects"
    
    # 自定义属性
    custom_field = Column(String(100))
    
    def custom_method(self):
        # 使用基类功能
        self.add_tag("custom")
        self.set_attribute("last_used", datetime.now())
```

### DefaultAccount
用户账户的基类，提供：

- **认证信息**: 用户名、邮箱、密码哈希
- **个人信息**: 全名、简介、头像
- **权限管理**: 角色、权限、访问级别
- **安全功能**: 登录尝试记录、账户锁定
- **状态管理**: 活跃状态、验证状态

```python
from app.models.base import DefaultAccount

class MyUser(DefaultAccount):
    __tablename__ = "my_users"
    
    # 扩展信息
    phone = Column(String(20))
    
    def can_access_feature(self, feature_name: str) -> bool:
        return self.has_permission(f"feature.{feature_name}")
```

## 组件系统

### 可用组件

#### InventoryMixin
为对象添加物品栏功能：

```python
from app.models.factory import InventoryMixin

class Player(DefaultObject, InventoryMixin):
    __tablename__ = "players"
    
    # 自动获得物品栏相关字段和方法
    # - inventory: 物品栏
    # - max_inventory_size: 最大容量
    # - add_item(), remove_item(), get_item(), has_item()
```

#### StatsMixin
为对象添加属性系统：

```python
from app.models.factory import StatsMixin

class Character(DefaultObject, StatsMixin):
    __tablename__ = "characters"
    
    # 自动获得属性相关字段和方法
    # - stats: 基础属性
    # - level: 等级
    # - experience: 经验值
    # - get_stat(), set_stat(), modify_stat(), level_up()
```

#### CombatMixin
为对象添加战斗功能：

```python
from app.models.factory import CombatMixin

class Fighter(DefaultObject, CombatMixin):
    __tablename__ = "fighters"
    
    # 自动获得战斗相关字段和方法
    # - health, max_health: 生命值
    # - attack, defense: 攻击力和防御力
    # - take_damage(), heal(), attack_target()
```

### 自定义组件

创建自定义组件：

```python
from app.models.factory import ComponentMixin
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy import Column, Integer, String

class MagicMixin(ComponentMixin):
    """魔法组件"""
    
    @declared_attr
    def mana(cls):
        return Column(Integer, default=100)
    
    @declared_attr
    def max_mana(cls):
        return Column(Integer, default=100)
    
    def get_component_name(self) -> str:
        return "magic"
    
    def get_component_version(self) -> str:
        return "1.0.0"
    
    def cast_spell(self, spell_name: str, mana_cost: int) -> bool:
        if self.mana >= mana_cost:
            self.mana -= mana_cost
            return True
        return False
```

## 模型工厂

### 基本用法

```python
from app.models.factory import model_factory, DefaultObject

# 创建带有组件的模型类
CombatCharacter = model_factory.create_model_with_components(
    DefaultObject, 
    "inventory", 
    "stats", 
    "combat"
)

# 创建自定义对象配置
player_config = model_factory.create_custom_object(
    name="英雄",
    object_type="player",
    level=10,
    health=200
)
```

### 注册自定义组件

```python
from app.models.factory import model_factory

# 注册自定义组件
model_factory.register_component("magic", MagicMixin)

# 现在可以在创建模型时使用
MagicFighter = model_factory.create_model_with_components(
    DefaultObject,
    "combat",
    "magic"
)
```

## 具体模型

### User
继承自 DefaultAccount，提供用户相关功能：

- 扩展个人信息（昵称、电话、生日等）
- 学术信息（学号、专业、年级等）
- 社交信息（兴趣、社交媒体链接等）
- 校园成员身份管理
- 世界活动参与记录

### Campus
继承自 DefaultObject，代表校园空间：

- 校园基本信息（代码、名称、类型等）
- 位置信息（地址、城市、坐标等）
- 成员管理（成员数量、最大容量等）
- 活动关联（校园内的世界活动）

### World
继承自 DefaultObject，代表虚拟世界：

- 世界设置（类型、难度、玩家限制等）
- 时间系统（时间流逝速度、开始/结束时间）
- 玩家管理（当前玩家数量、状态等）
- 对象和活动管理

### WorldObject
继承自 DefaultObject，代表世界中的对象：

- 对象类型（玩家、NPC、物品、位置等）
- 属性系统（等级、生命值、能量值等）
- 位置和移动（坐标、朝向、移动能力等）
- 交互功能（可见性、交互性等）

### WorldActivity
记录世界中的活动：

- 活动类型（事件、任务、战斗、交易等）
- 时间管理（开始时间、结束时间、持续时间）
- 参与设置（参与者限制、等级要求等）
- 状态管理（计划中、进行中、已完成等）

## 使用示例

### 创建玩家对象

```python
from app.models.factory import model_factory, DefaultObject

# 创建带有完整功能的玩家类
PlayerClass = model_factory.create_model_with_components(
    DefaultObject,
    "inventory",
    "stats", 
    "combat"
)

class Player(PlayerClass):
    __tablename__ = "players"
    
    # 玩家特定字段
    player_class = Column(String(50))
    player_race = Column(String(50))
    
    def get_player_info(self):
        return {
            "name": self.name,
            "class": self.player_class,
            "level": self.level,
            "health": f"{self.health}/{self.max_health}",
            "inventory_size": len(self.inventory)
        }
```

### 对象交互

```python
# 玩家攻击怪物
def combat_example():
    player = Player(name="勇士", player_class="warrior")
    monster = Monster(name="巨龙", health=500)
    
    # 使用战斗组件的方法
    result = player.attack_target(monster)
    print(f"攻击结果: {result}")
    
    # 使用属性组件的方法
    player.add_experience(100)
    if player.level > 1:
        print(f"升级了！当前等级: {player.level}")
```

### 校园世界集成

```python
class CampusWorldPlayer(DefaultObject, StatsMixin):
    __tablename__ = "campus_world_players"
    
    campus_id = Column(Integer, ForeignKey("campuses.id"))
    world_id = Column(Integer, ForeignKey("worlds.id"))
    
    def get_context_info(self):
        return {
            "name": self.name,
            "campus_id": self.campus_id,
            "world_id": self.world_id,
            "level": self.level,
            "stats": self.stats
        }
```

## 最佳实践

### 1. 组件选择
- 根据对象的功能需求选择合适的组件
- 避免过度使用组件，保持模型的简洁性
- 优先使用现有组件，减少重复代码

### 2. 继承层次
- 保持继承层次清晰，避免过深的继承链
- 使用组合优于继承，通过组件实现功能
- 基类应该提供通用功能，具体功能通过组件实现

### 3. 性能考虑
- JSON字段（如attributes、tags）适合存储动态数据
- 关系查询要考虑N+1问题，适当使用预加载
- 大量数据的统计字段考虑使用缓存

### 4. 扩展性
- 通过组件系统实现功能的模块化
- 使用模型工厂支持运行时类型创建
- 保持接口的一致性，便于后续扩展

## 总结

CampusWorld 模型系统提供了一个强大而灵活的架构，支持：

- **层次化设计**: 通过继承实现功能的组织
- **组件化架构**: 通过混入实现功能的组合
- **工厂模式**: 支持动态创建和扩展
- **类型安全**: 基于 SQLAlchemy 的类型系统
- **扩展性**: 支持自定义组件和模型类型

这个系统为 CampusWorld 项目提供了坚实的基础，支持复杂的业务逻辑和未来的功能扩展。
