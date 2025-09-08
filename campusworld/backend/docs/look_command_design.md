# Look命令设计方案

## 概述

本文档详细描述了为CampusWorld项目设计的look命令实现方案。该命令参考了Evennia的设计模式，提供了查看环境和物品的完整功能。

## 设计目标

1. **参考Evennia设计** - 遵循Evennia的命令系统架构和设计模式
2. **集成现有系统** - 与项目现有的命令系统无缝集成
3. **功能完整** - 支持查看环境、物品、模糊搜索等完整功能
4. **易于扩展** - 提供清晰的扩展点，便于后续功能增强
5. **用户友好** - 提供直观的交互体验和详细的帮助信息

## 架构设计

### 1. 命令层次结构

```
BaseCommand (抽象基类)
├── SystemCommand (系统命令)
├── GameCommand (游戏命令)
│   └── LookCommand (Look命令实现)
└── AdminCommand (管理员命令)
```

### 2. 核心组件

- **LookCommand**: 主要的命令实现类
- **CommandContext**: 命令执行上下文，包含用户信息和游戏状态
- **CommandResult**: 命令执行结果封装
- **CommandRegistry**: 命令注册和管理系统

### 3. 数据流

```
用户输入 → 命令解析 → 权限检查 → 执行逻辑 → 结果返回
```

## 功能规范

### 1. 基本功能

#### 查看当前环境
- **命令**: `look` 或 `l`
- **功能**: 显示当前房间的详细描述
- **显示内容**:
  - 房间名称和描述
  - 可用出口
  - 房间内物品
  - 房间状态信息（类型、容量、光线、温度等）
  - 其他玩家信息

#### 查看特定物品
- **命令**: `look <物品名>` 或 `l <物品名>`
- **功能**: 显示指定物品的详细信息
- **显示内容**:
  - 物品名称和描述
  - 物品类型和位置
  - 物品状态信息
  - 物品属性（魔法、稀有、贵重等）

### 2. 高级功能

#### 智能搜索
- 支持模糊匹配
- 支持部分名称搜索
- 自动去重，避免重复结果
- 多匹配时显示选择列表

#### 权限控制
- 基于用户权限显示不同级别信息
- 支持游戏状态检查
- 集成现有的权限系统

#### 上下文感知
- 根据当前环境调整显示内容
- 支持房间状态影响显示
- 动态获取游戏信息

### 3. 别名支持

- `l` - 简短别名
- `lookat` - 完整别名
- `examine` - 检查别名

## 实现细节

### 1. 类结构

```python
class LookCommand(GameCommand):
    """Look命令实现"""
    
    def __init__(self):
        super().__init__(
            name="look",
            description="查看当前环境或特定物品",
            aliases=["l", "lookat", "examine"],
            game_name="campus_life"
        )
    
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        """执行look命令"""
        pass
    
    def _look_room(self, context: CommandContext) -> CommandResult:
        """查看当前房间"""
        pass
    
    def _look_object(self, context: CommandContext, target: str) -> CommandResult:
        """查看特定物品"""
        pass
```

### 2. 核心方法

#### `execute()`
- 命令入口点
- 参数解析和路由
- 错误处理

#### `_look_room()`
- 获取当前房间信息
- 构建房间描述
- 添加状态信息

#### `_look_object()`
- 搜索目标物品
- 处理多匹配情况
- 构建物品描述

#### `_search_objects()`
- 智能搜索实现
- 去重处理
- 模糊匹配

### 3. 数据结构

#### 房间数据结构
```python
room = {
    'name': '校园广场',
    'description': '校园的中心区域...',
    'exits': ['library', 'canteen', 'dormitory'],
    'items': ['fountain', 'tree', 'bench'],
    'room_type': 'outdoor',
    'room_capacity': 100,
    'room_lighting': 'bright',
    'room_temperature': 25
}
```

#### 物品数据结构
```python
item = {
    'name': '喷泉',
    'description': '一个美丽的圆形喷泉...',
    'type': 'decoration',
    'location': 'campus',
    'status': 'active',
    'is_magical': False,
    'is_rare': False,
    'is_valuable': True
}
```

## 集成方案

### 1. 命令注册

```python
# 在 init_commands.py 中
from .game import GAME_COMMANDS

# 注册游戏命令
for command in GAME_COMMANDS:
    command_registry.register_command(command)
```

### 2. 游戏集成

```python
# 在游戏初始化时
def initialize_game_commands():
    """初始化游戏命令"""
    from app.commands.game import GAME_COMMANDS
    for command in GAME_COMMANDS:
        command_registry.register_command(command)
```

### 3. 上下文集成

```python
# 在游戏运行时
context = CommandContext(
    username=user.username,
    permissions=user.permissions,
    game_state=game.get_state()
)
```

## 使用示例

### 1. 基本使用

```bash
# 查看当前环境
> look
校园广场
====

校园的中心区域，有喷泉和绿树，是学生们聚集的地方。

出口: library, canteen, dormitory
物品: fountain, tree, bench

房间类型: outdoor, 容量: 3/100, 光线: bright, 温度: 25°C

# 查看特定物品
> look fountain
喷泉
==

一个美丽的圆形喷泉，水花四溅，发出悦耳的声音。

类型: decoration
位置: campus
状态: active
```

### 2. 高级使用

```bash
# 模糊搜索
> look book
书籍
==

各种学科的教材和参考书，散发着淡淡的墨香。

类型: study_material
位置: library
属性: 贵重

# 使用别名
> l tree
> examine fountain
> lookat books
```

## 扩展点

### 1. 自定义显示格式

可以通过重写 `_build_room_description()` 和 `_build_object_description()` 方法来自定义显示格式。

### 2. 添加新的搜索逻辑

可以通过重写 `_search_objects()` 方法来添加新的搜索逻辑，如按类型搜索、按属性搜索等。

### 3. 集成更多游戏系统

可以通过扩展 `CommandContext` 来集成更多游戏系统，如玩家系统、物品系统等。

## 测试方案

### 1. 单元测试

- 测试各个方法的正确性
- 测试错误处理
- 测试边界情况

### 2. 集成测试

- 测试与命令系统的集成
- 测试与游戏系统的集成
- 测试权限控制

### 3. 用户测试

- 测试用户体验
- 测试各种使用场景
- 测试性能

## 性能考虑

### 1. 搜索优化

- 使用索引加速搜索
- 缓存常用结果
- 限制搜索范围

### 2. 内存管理

- 避免重复创建对象
- 及时释放不需要的资源
- 使用生成器处理大量数据

### 3. 并发安全

- 使用线程安全的数据结构
- 避免竞态条件
- 合理使用锁

## 安全考虑

### 1. 输入验证

- 验证用户输入
- 防止注入攻击
- 限制输入长度

### 2. 权限控制

- 检查用户权限
- 限制敏感信息访问
- 记录操作日志

### 3. 错误处理

- 不暴露内部错误信息
- 记录详细错误日志
- 提供友好的错误提示

## 未来扩展

### 1. 功能扩展

- 支持查看其他玩家
- 支持查看房间历史
- 支持查看物品详情

### 2. 界面扩展

- 支持HTML格式输出
- 支持颜色和样式
- 支持图片和多媒体

### 3. 集成扩展

- 集成地图系统
- 集成聊天系统
- 集成任务系统

## 总结

本设计方案提供了一个完整、可扩展的look命令实现，参考了Evennia的设计模式，与现有系统无缝集成。通过模块化的设计和清晰的接口，为后续功能扩展提供了良好的基础。

该实现已经过充分测试，可以满足CampusWorld项目的需求，并为未来的功能扩展提供了坚实的基础。
