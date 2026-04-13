# Commands SPEC

> **Architecture Role**: 命令系统是**知识与能力层**的核心组成部分，是 Agent/用户与**世界语义**交互的主要接口。系统借鉴 MUD 游戏的设计原理构筑世界语义，但 CampusWorld 本身不是游戏，而是智慧园区 OS。命令是用户/Agent 与知识本体交互的标准方式，通过命令操作图数据模型中的实体。

## Module Overview

命令系统（`backend/app/commands/`）提供类似 MUD 终端的命令执行框架，命令是**系统命令**，通过 `CommandRegistry` 自动发现和管理。

智能体服务（`type_code=npc_agent`）**默认**经本命令层操作图语义，契约见 [`docs/models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md`](../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)。

```
输入 → CommandRegistry → BaseCommand.execute() → CommandResult → 输出
```

## Core Abstractions

### 核心类

### 命令分类

| 类型 | 说明 | 典型命令 |
|------|------|----------|
| `SYSTEM` | 系统级命令，所有用户可用，用于系统交互 | `look`, `who`, `help`, `time` |
| `GAME` | 世界交互命令，访问知识本体中的实体（房间/角色/物品） | `go`, `say`, `inventory` |
| `ADMIN` | 管理命令，需要管理员权限 | `create room`, `dig`, `set exit` |

> 注：`GAME` 类型指"世界语义交互命令"，而非"游戏命令"。CampusWorld 是智慧园区 OS，`look` 是查看世界实体的标准命令，属于系统命令。

### BaseCommand 接口

```python
class BaseCommand(ABC):
    name: str
    description: str
    aliases: List[str]
    command_type: CommandType

    @abstractmethod
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult: ...

    def validate_args(self, args: List[str]) -> bool: ...
    def check_permission(self, context: CommandContext) -> bool: ...
    def get_help(self) -> str: ...
    def get_usage(self) -> str: ...
```

### 命令注册表

```python
command_registry.register_command(MyCommand())
command_registry.get_command("look")        # by name
command_registry.get_command("l")           # by alias
command_registry.list_all_commands()
command_registry.execute("look", context, args)
```

## User Stories

1. **执行命令**: 用户在 SSH 终端输入 `look`，命令系统解析命令名、查找命令、执行、返回结果
2. **权限控制**: 管理员命令在执行前通过 `check_permission()` 验证权限
3. **命令别名**: `look` 和 `l` 指向同一命令，用户体验一致
4. **统一对象查看**: `look bulletin_board` 与 `look stone` 走同一命令路径，仅对象描述内容不同

## Unified Look/Object Design

`look` 应保持“统一命令 + 对象自描述”模式（参考 Evennia 的 `return_appearance` 设计）：

1. 命令层负责目标解析（解析出要看的对象）。
2. 命令层调用对象描述接口（如 `get_appearance(context)`）。
3. 对象返回展示文本（静态对象返回静态描述；动态对象可返回列表/详情）。
4. 命令层统一输出，不为某类对象建立特殊协议分支。

这意味着公告栏对象（`system_bulletin_board`）不应通过专用命令通道实现，而应作为普通对象被 `look` 查看；其差异只在对象内部描述逻辑委托到公告栏服务层。

## Command Execution State

```
用户输入 "look north"
    ↓
CommandRegistry.parse("look north")
    ↓
查找命令 "look" → LookCommand
    ↓
验证参数 ["north"]
    ↓
检查权限 context.has_permission(required)
    ↓
execute(context, ["north"])
    ↓
CommandResult.success_result("向北移动到食堂")
    ↓
返回给 SSH 会话 / HTTP 响应
```

## 已有命令清单

### 系统命令
| 命令 | 别名 | 类型 | 说明 |
|------|------|------|------|
| `look` | `l/examine` | SYSTEM | 查看当前空间/对象（世界语义入口） |
| `quit` | `exit/q` | SYSTEM | 退出会话 |
| `who` | `whoelse` | SYSTEM | 查看在线用户 |
| `help` | `?/h` | SYSTEM | 帮助信息 |
| `time` | `date` | SYSTEM | 系统时间 |

### 世界交互命令
| 命令 | 别名 | 类型 | 说明 |
|------|------|------|------|
| `go` | `walk/move` | GAME | 移动到指定方向/空间 |
| `say` | `chat/shout` | GAME | 在当前空间广播消息 |
| `inventory` | `i/inv` | GAME | 查看背包/物品列表 |
| `take` | `get/grab` | GAME | 拾取物品 |
| `drop` | `put/place` | GAME | 丢弃物品 |

### 建造命令
| 命令 | 类型 | 说明 |
|------|------|------|
| `create room` | ADMIN | 创建房间 |
| `create building` | ADMIN | 创建建筑 |
| `set exit` | ADMIN | 设置出口 |
| `dig` | ADMIN | 挖掘房间（快捷方式）|

### 知识库命令（规划）

内置知识世界 **campuslibrary**（OS 级全局知识库）通过顶层命令 **`cl`** 维护与检索；子命令 **`search`**（检索）、**`ingest`**（录入）、**`del`**（软删除，`is_active=false`）。奇点屋可见该世界入口但 **不可 `enter` 穿越**，须用 `cl`。契约见 [`docs/models/SPEC/features/F06_CAMPUSLIBRARY_KNOWLEDGE_WORLD.md`](../../models/SPEC/features/F06_CAMPUSLIBRARY_KNOWLEDGE_WORLD.md)。

## Acceptance Criteria

- [ ] 命令注册表自动发现 `commands/` 下的所有命令子类
- [ ] `look` 命令返回当前房间的完整描述（名称、描述、出口、物品）
- [ ] `look` 对对象采用统一分发：`look bulletin_board` 与 `look <other_object>` 走相同命令链路
- [ ] 权限不足时命令返回 `CommandResult.error_result("权限不足")`
- [ ] 命令别名系统工作正常（`l` 等同于 `look`）
- [ ] 不存在的命令返回 `CommandResult.error_result("未知命令")`

## Design Decisions

1. **为何命令与协议分离**: BaseCommand 不依赖 SSH 或 HTTP，任何协议层都可以通过 CommandContext 调用命令
2. **为何用 dataclass 而非 Pydantic**: CommandContext 是内部数据结构，性能优先，dataclass 更轻量
3. **为何用 CommandType 枚举**: 便于命令分类、权限组管理和日志分类

## Open Questions

- [ ] 是否需要命令历史记录（undo/redo）？
- [ ] 是否需要命令别名自定义功能？
- [ ] 命令执行超时机制是否需要？

## Dependencies

- 依赖 `backend/app/core/log/`（日志）
- 依赖 `backend/app/models/`（图数据模型，命令操作实体）
- 依赖 `backend/app/game_engine/`（游戏状态）
- 被 `backend/app/ssh/` 和 `backend/app/protocols/` 调用
- 知识库命令 **`cl`** 契约见 [`docs/models/SPEC/features/F06_CAMPUSLIBRARY_KNOWLEDGE_WORLD.md`](../../models/SPEC/features/F06_CAMPUSLIBRARY_KNOWLEDGE_WORLD.md)（实现待落地）