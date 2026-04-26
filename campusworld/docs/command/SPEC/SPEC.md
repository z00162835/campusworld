# Commands SPEC

> **Architecture Role**: 命令系统是**知识与能力层**的核心组成部分，是 Agent/用户与**世界语义**交互的主要接口。系统借鉴 MUD 的设计原理构筑世界语义，但 CampusWorld 本身不是，而是智慧园区 OS。命令是用户/Agent 与知识本体交互的标准方式，通过命令操作图数据模型中的实体。

> **Doc root**: 本规范树为仓库内 **[`docs/command/SPEC/`](.)**（`features/` 为各命令分册与 `F01`/`F02` 深文档，`_generated/` 为注册表 JSON 快照，`template/` 为新建 `CMD_*` 模板）。

## Module Overview

命令系统（`backend/app/commands/`）提供类似 MUD 终端的命令执行框架，命令是**系统命令**，通过 `CommandRegistry` 自动发现和管理。

智能体服务（`type_code=npc_agent`）**默认**经本命令层操作图语义，契约见 [`docs/models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md`](../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)。

```
输入 → CommandRegistry → BaseCommand.execute() → CommandResult → 输出
```

## Core Abstractions

### 核心类

### 命令分类

| 类型 | 说明 | 典型命令（以注册表为准） |
|------|------|----------|
| `SYSTEM` | 系统可调用命令（图检索、Agent 工具、帮助等） | `help`, `find`, `aico`, `agent_capabilities` |
| `GAME` | 世界内交互（`look`、方向移动、进/出世界、公告等） | `look`, `go`, `enter`, `leave` |
| `ADMIN` | 管理/建造型 | `create`, `world` |

> 注：实现中 **`look` 为 `GAME`（`LookCommand`）**；**`world` 为 `ADMIN`（`WorldCommand`）**。以 [`registry_snapshot.json`](_generated/registry_snapshot.json) 为准。未在注册表中的 MUD 式名（如 `say` / `inventory`）**不**列为此版已提供命令；**`who`（在线列表）与 `whoami`（当前身份）** 为两条独立命令，分别见 [CMD_who](features/CMD_who.md) / [CMD_whoami](features/CMD_whoami.md)。

### 一命令一 SPEC

每个已注册主名有 [`features/CMD_<name>.md`](features/)；**有效别名**以快照的 `registry_aliases` 为准。生成快照（在 `backend` 下、Conda 环境 `campusworld`）：`python scripts/export_command_registry_snapshot.py`；对账（可选）：`python scripts/verify_command_spec_files.py`。

与实现 1:1 的验收见 [ACCEPTANCE.md](ACCEPTANCE.md)。

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
用户输入 "n" 或 "go north"（例：原址移动，非 look）
    ↓
解析主命令 "n" 或 "go" → FixedDirection 或 MovementCommand
    ↓
execute(context, [...])
    ↓
CommandResult（成功/失败，自然语言在实现中构造）
    ↓
返回给 SSH 会话 / HTTP 响应
```

`look` 有参时首段为目标名（含数字消歧、多匹配），不解析为 `go`；移动请用方向子命令或 `go <dir>`。详见 [CMD_look](features/CMD_look.md) / [CMD_go](features/CMD_go.md)。

## 已有命令清单（= `initialize_commands` 注册主名）

下列 **「别名」** 为快照中 `registry_aliases`（可覆盖类声明的冲突名）。短描述为 locale `commands.<name>.description` 摘要；**行为契约**以 `CMD_*.md` 与实现为准。

| 主名 | 类型 | 有效别名 | SPEC |
|------|------|----------|------|
| `aico` | SYSTEM | — | [CMD_aico](features/CMD_aico.md) |
| `agent` | SYSTEM | — | [CMD_agent](features/CMD_agent.md) |
| `agent_capabilities` | SYSTEM | `agent.capabilities` | [CMD_agent_capabilities](features/CMD_agent_capabilities.md) |
| `agent_tools` | SYSTEM | `agent.tools` | [CMD_agent_tools](features/CMD_agent_tools.md) |
| `create` | ADMIN | `spawn`, `build`, `make` | [CMD_create](features/CMD_create.md) |
| `create_info` | ADMIN | `cinfo`, `model_info` | [CMD_create_info](features/CMD_create_info.md) |
| `describe` | SYSTEM | `ex`, `examine` | [CMD_describe](features/CMD_describe.md) 深契约占 [F01](features/F01_FIND_COMMAND.md) |
| `find` | SYSTEM | `@find`, `locate` | [CMD_find](features/CMD_find.md) 深契约占 [F01](features/F01_FIND_COMMAND.md) |
| `help` | SYSTEM | `h`, `?` | [CMD_help](features/CMD_help.md) |
| `primer` | SYSTEM | `manual` | [CMD_primer](features/CMD_primer.md) |
| `quit` | SYSTEM | `exit`, `q` | [CMD_quit](features/CMD_quit.md) |
| `stats` | SYSTEM | `stat`, `system` | [CMD_stats](features/CMD_stats.md) |
| `time` | SYSTEM | `date` | [CMD_time](features/CMD_time.md) |
| `type` | SYSTEM | — | [CMD_type](features/CMD_type.md) |
| `version` | SYSTEM | `ver` | [CMD_version](features/CMD_version.md) |
| `who` | SYSTEM | — | [CMD_who](features/CMD_who.md) |
| `whoami` | SYSTEM | — | [CMD_whoami](features/CMD_whoami.md) |
| `down` | GAME | `d` | [CMD_down](features/CMD_down.md) |
| `east` | GAME | `e` | [CMD_east](features/CMD_east.md) |
| `enter` | GAME | — | [CMD_enter](features/CMD_enter.md) |
| `go` | GAME | `walk` | [CMD_go](features/CMD_go.md) |
| `in` | GAME | — | [CMD_in](features/CMD_in.md) |
| `leave` | GAME | `ooc` | [CMD_leave](features/CMD_leave.md) |
| `look` | GAME | `l`, `lookat` | [CMD_look](features/CMD_look.md) |
| `north` | GAME | `n` | [CMD_north](features/CMD_north.md) |
| `northeast` | GAME | `ne` | [CMD_northeast](features/CMD_northeast.md) |
| `northwest` | GAME | `nw` | [CMD_northwest](features/CMD_northwest.md) |
| `notice` | GAME | `notices` | [CMD_notice](features/CMD_notice.md) |
| `out` | GAME | `o` | [CMD_out](features/CMD_out.md) |
| `south` | GAME | `s` | [CMD_south](features/CMD_south.md) |
| `southeast` | GAME | `se` | [CMD_southeast](features/CMD_southeast.md) |
| `southwest` | GAME | `sw` | [CMD_southwest](features/CMD_southwest.md) |
| `up` | GAME | `u` | [CMD_up](features/CMD_up.md) |
| `west` | GAME | `w` | [CMD_west](features/CMD_west.md) |
| `world` | ADMIN | `worlds` | [CMD_world](features/CMD_world.md) |

### 方向命令族（`go` + 12 固定方向捷径）

`go` 与 12 个 `FixedDirectionCommand` 子命令（`north`/`south`/`east`/`west`/`northeast`/`northwest`/`southeast`/`southwest`/`up`/`down`/`in`/`out`）共享 `MovementCommand._move` 主干；**族级 SSOT** 为 [`FAMILY_direction.md`](features/FAMILY_direction.md)，per-direction `CMD_*.md` 已瘦身为只列差异的索引。

### 知识库命令（规划）

内置知识世界 **campuslibrary**（OS 级全局知识库）通过顶层命令 **`cl`** 维护与检索；子命令 **`search`**（检索）、**`ingest`**（录入）、**`del`**（软删除，`is_active=false`）。奇点屋可见该世界入口但 **不可 `enter` 穿越**，须用 `cl`。契约见 [`docs/models/SPEC/features/F06_CAMPUSLIBRARY_KNOWLEDGE_WORLD.md`](../../models/SPEC/features/F06_CAMPUSLIBRARY_KNOWLEDGE_WORLD.md)。

### 图检索命令

CampusWorld 的只读图检索由 `find`（列表）与 `describe`（单节点深度）两命令承担；两者的 **唯一权威契约** 在 [`docs/command/SPEC/features/F01_FIND_COMMAND.md`](features/F01_FIND_COMMAND.md)，本文件不再重复描述参数与返回契约。

## Acceptance Criteria

- [ ] 与注册表/别名：每个主命令有对应 `features/CMD_<name>.md` 或 `find`/`describe` 的 F01 深文档；`registry_snapshot` 可复现
- [ ] `look` 在有效路径上返回可解析的当前房信息或目标对象描述；无位置时与实现一致
- [ ] 权限不足/拒绝路径与 `command_policies` 及 Admin 子命令实现一致
- [ ] 别名在全局表中唯一时解析为预期主名（如 `l` → `look`；`examine` → `describe`）
- [ ] Per-command 详细验收与 1:1 规则见 [ACCEPTANCE.md](ACCEPTANCE.md) 中「Per-command SPEC」

## Assistant NLP (`aico` / `@<handle>`)

- **`aico <message>`** 与 **`@<handle> <message>`** 共用 `run_npc_agent_nlp_tick`；成功时 **`CommandResult.message` 仅为助手最终可读文本**（非 JSON 包装）。机器可读字段放在 **`CommandResult.data`**：`ok`、`phase`（如 `act` 或 `passthrough`）、`handle`、`service_id`。
- **无可用 HTTP LLM**（未配置 `use_http_llm`、未设置对应 API key 环境变量等）时，**不**进入 PDCA / 不写 agent memory run；`phase` 为 **`passthrough`**，`message` 为 **回显用户输入**（trim 后）。
- 详细行为与 AICO 默认见模型侧文档；按用户隔离的记忆与 LTM 异步晋升见后续特性文档，不在本命令契约内展开。

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
- 依赖 `backend/app/game_engine/`（状态）
- 被 `backend/app/ssh/` 和 `backend/app/protocols/` 调用
- 知识库命令 **`cl`** 契约见 [`docs/models/SPEC/features/F06_CAMPUSLIBRARY_KNOWLEDGE_WORLD.md`](../../models/SPEC/features/F06_CAMPUSLIBRARY_KNOWLEDGE_WORLD.md)（实现待落地）