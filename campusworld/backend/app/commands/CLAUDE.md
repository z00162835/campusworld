# Commands Module - 命令系统

> **Architecture Role**: 命令系统是**知识与能力层**的核心组成部分，是 Agent/用户与**世界语义**交互的主要接口。用户通过命令操作图数据模型中的实体（查看 Room、创建 Building、移动 Character），命令系统将自然语言指令映射为图数据结构上的操作。SSH 终端和 HTTP API 都通过命令系统与知识本体交互。

游戏命令框架，支持动态命令注册和执行。

## 模块结构

```
commands/
├── base.py              # 基础类和接口
├── registry.py          # 命令注册表
├── context.py           # 命令上下文
├── cmdset.py            # 命令集
├── character.py         # 角色相关命令
├── system_commands.py   # 系统命令
├── init_commands.py    # 命令初始化
│
├── builder/             # 建造类命令
│   ├── __init__.py
│   ├── create_command.py
│   └── model_discovery.py
│
├── game/                # 游戏命令
│   ├── __init__.py
│   └── look_command.py
│
└── admin/               # 管理命令
    ├── __init__.py
    └── ...
```

## 核心概念

### BaseCommand

所有命令的基类，定义命令接口:

```python
from commands.base import BaseCommand, CommandContext, CommandType, CommandResult

class MyCommand(BaseCommand):
    def __init__(self):
        super().__init__(
            name="mycommand",
            description="命令描述",
            aliases=["mc"],
            command_type=CommandType.GAME
        )

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        # 命令逻辑
        return CommandResult.success_result("执行结果")
```

### 命令子类

- `SystemCommand`: 系统命令基类
- `GameCommand`: 游戏命令基类
- `AdminCommand`: 管理员命令基类

### CommandContext

命令执行上下文，包含:

- `user_id`: 用户ID
- `username`: 用户名
- `session_id`: 会话ID
- `permissions`: 权限列表
- `session`: SSH会话
- `game_state`: 游戏状态
- `caller`: 调用者对象
- `metadata`: 元数据

提供方法:
- `get_caller()`: 获取调用者对象
- `has_permission(permission)`: 检查权限
- `get_game_state(key, default)`: 获取游戏状态

### CommandType

命令类型枚举:

- `SYSTEM`: 系统命令
- `GAME`: 游戏命令
- `ADMIN`: 管理命令

## 命令注册

### 自动发现

```python
from commands.registry import CommandRegistry, command_registry

# 注册命令
command_registry.register_command(MyCommand())

# 获取命令
cmd = command_registry.get_command("mycommand")

# 列出所有命令
all_commands = command_registry.list_all_commands()
```

## 现有命令

### 游戏命令

| 命令 | 描述 |
|------|------|
| look/l | 查看当前房间/对象 |
| go [方向] | 移动到指定方向 |

**Look 行为要点**

- **出口**：房间展示的方向出口 = 节点属性 `room_exits` 的键 **加上** 从当前房间出发的 **`connects_to` 关系**（`attributes.direction` 经 `normalize_direction`；无 direction 时用目标 `package_node_id`），去重后按罗盘序排序。
- **列表行**：房间内对象列表统一 **`- *{display_name}*{hints}`**（`hints` 为可选后缀，如设备状态、公告摘要）。
- **多匹配消歧**：SSH 下多匹配时写入会话 **`command_ephemeral["look_disambiguation_entries"]`**，随后可用 **`look 1`**、**`look 2`**…（与列表序号一致）；无 `context.session` 时仅提示使用完整名称。
| say | 说话 |
| help | 帮助 |

### 建造命令

| 命令 | 描述 |
|------|------|
| create room | 创建房间 |
| create building | 创建建筑 |
| set exit | 设置出口 |

### 系统命令

| 命令 | 描述 |
|------|------|
| quit/exit | 退出 |
| who | 在线用户 |
| time | 系统时间 |

## 使用示例

```python
from commands.registry import command_registry
from commands.context import CommandContext

# 执行命令
context = CommandContext(
    user_id="1",
    username="player",
    session_id="sess123",
    permissions=["player"]
)

result = command_registry.execute("look", context, [])
print(result)
```
