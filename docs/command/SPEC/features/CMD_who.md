# `who`

> **Architecture Role**: 在线用户列表（SYSTEM）；**不是** `whoami` 的别名。显示所有活跃 SSH 会话用户及其位置信息。

## Metadata (anchoring)

| Field | Value |
|--------|-------|
| Command | `who` |
| `CommandType` | SYSTEM |
| Class | `app.commands.system_commands.WhoCommand` |
| Primary implementation | [`backend/app/commands/system_commands.py`](../../../../backend/app/commands/system_commands.py) |
| Locale | `commands.who` in `backend/app/commands/i18n/locales/{zh-CN,en-US}.yaml` |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |
 
**Design Note**: `who` 为独立命令；`whoami` 仅返回当前身份，不再占用 `who` 别名。

## Synopsis

```
who
```

显示所有当前在线用户的列表，包括用户名、位置、连接时长和空闲时间。

## Implementation contract

### 架构前提

- `SessionManager`（`app.ssh.session.SessionManager`）管理所有活跃 SSH 会话
- `SSHProtocolHandler` 实例持有自己的 `SessionManager`（`protocol_handler.py:39`），**不是**全局单例；`who` 只能看到同一 handler 实例内的会话
- 用户位置通过 `GameHandler.get_user_location()` 查询图节点 `location_id` 解析

### 主路径

1. `WhoCommand.execute(context, args)` 从 `context.metadata.get("session_manager")` 获取 `SessionManager`
2. 调用 `session_manager.get_active_sessions()` 获取所有活跃会话
3. 对每个会话查询用户位置：`GameHandler.get_user_location(session.user_id)`
4. 格式化输出表格

### 数据流

```
who
  → WhoCommand.execute(context, [])
  → context.metadata.get("session_manager")
  → session_manager.get_active_sessions()
  → GameHandler.get_user_location(user_id)  # per session
  → format_table(sessions, locations)
  → CommandResult.success_result(table_text)
```

### `session_manager` 访问（方案 A）

`session_manager` 通过 `context.metadata["session_manager"]` 传入。调用方在创建 `CommandContext` 时注入：

```python
# console.py, protocol_handler.py 等处创建 context 时
context = CommandContext(
    user_id=user_id,
    username=username,
    session_id=session_id,
    permissions=permissions,
    metadata={"session_manager": self.session_manager},
    ...
)
```

`WhoCommand.execute()` 内访问：
```python
sm = context.metadata.get("session_manager") if context.metadata else None
if sm is None:
    return CommandResult.error_result(
        "Online user list unavailable.",
        error="session_manager not available in context"
    )
```

### 输出字段定义

| 列名 | 数据来源 | 说明 |
|------|----------|------|
| `Player` | `session.username` | 用户名 |
| `Location` | `GameHandler.get_user_location(user_id)['name']` | 图节点 `name`；直取不翻译 |
| `Idle` | `now - session.last_activity` | 空闲时间；格式 `Nm`（不足1分钟显示 `0m`） |
| `Duration` | `now - session.connected_at` | 连接时长；格式 `Hm` 或 `Hd`（超过24h 用天数） |

### 输出格式示例

**英文 (`en-US`):**
```
CampusWorld Online Users
==========================
Player       Location                     Idle    Duration
----------   --------------------------   -----   --------
alice        Singularity Hub               0m      5m
bob          HiCampus/Plaza                3m      12m

2 users online (2 active sessions).
```

**中文 (`zh-CN`):**
```
CampusWorld 在线用户
====================
用户          位置                          空闲    时长
----------   --------------------------   -----   -----
alice        奇点屋                         0m      5m
bob          HiCampus/广场                  3m      12m

2 位用户在线（2 个活跃会话）。
```

**位置名称处理**：`location['name']` 直接从图节点读取，不做翻译；`type_code` 用于区分场景（如 `room` 为世界内，`world_entrance` 为奇点屋入口）。

### 错误形态

| 场景 | `CommandResult` | 说明 |
|------|-----------------|------|
| 无活跃会话 | `success=True, message="No users online."` | 正常返回空列表 |
| `session_manager` 不可用 | `success=False, message="Online user list unavailable."` | context 未注入 |
| 数据库查询失败 | `success=True, message=<table + footer + warning>` | 主表保持可读，位置列降级为 `-`，并追加 `Location information unavailable.` 警告行 |

### 多会话用户聚合

同一用户可能有多条 SSH 会话。展示粒度为**会话级**：
- 每条活跃会话一行
- 用户名相同的会话，标记会话数量：`alice (x2)`

### 权限

SYSTEM 命令，对所有用户开放。

### 副作用

只读；不写图、不写 session 状态。

## i18n 规范

所有用户可见字符串必须通过 i18n 资源文件定义：

### Locale 资源键

```
commands.who.title          # 标题（"CampusWorld Online Users" / "CampusWorld 在线用户"）
commands.who.header.player   # 列头-用户（"Player" / "用户"）
commands.who.header.location # 列头-位置（"Location" / "位置"）
commands.who.header.idle    # 列头-空闲（"Idle" / "空闲"）
commands.who.header.duration # 列头-时长（"Duration" / "时长"）
commands.who.footer          # 脚注（"{n} users online ({m} active sessions)." / "{n} 位用户在线（{m} 个活跃会话）"）
commands.who.error.unavailable # 错误："Online user list unavailable."
commands.who.error.no_sessions # 空列表："No users online."
```

### 格式化规则

| 字段 | 规则 |
|------|------|
| `Idle` | `<=0m` 显示 `0m`；`< 60m` 显示 `Nm`；`>= 60m` 显示 `Nh` |
| `Duration` | `< 60m` 显示 `Nm`；`< 24h` 显示 `Nh`；`>= 24h` 显示 `Nd` |
| 位置名称 | 不翻译，直取 `location['name']` |
| 用户名 | 不翻译，直取 `session.username` |

## Alias Separation

`WhoamiCommand` 已移除 `who` 别名，`who` 与 `whoami` 语义分离。

## Non-Goals / Roadmap

- **过滤选项**（`who --location <room>`）：后续版本
- **全局 SessionManager**：需将 `SessionManager` 改为全局单例，否则多 SSH 连接时数据不完整
- **WebSocket 会话覆盖**：目前仅覆盖 SSH
- **历史在线记录**：非实时，需持久化

## 相关

- 总表: [../SPEC.md](../SPEC.md)
- `whoami`: [CMD_whoami.md](CMD_whoami.md)
- `SessionManager`: `backend/app/ssh/session.py`
- `GameHandler`: `backend/app/ssh/game_handler.py`
- i18n 资源: `backend/app/commands/i18n/locales/{zh-CN,en-US}.yaml`

## Tests

- `backend/tests/commands/test_who_command.py`
- fixtures: `_FakeSessionManager`, `_FakeGameHandler`, `_ctx`
- 测试场景：
  1. 有活跃会话 → 表格输出正确
  2. 无活跃会话 → `"No users online."`
  3. `session_manager` 不可用 → error result
  4. 位置查询失败 → 位置列降级为 `-`，并在输出末尾追加 warning
  5. i18n: `resolve_locale(context)` 返回 `zh-CN` 时标题为中文
