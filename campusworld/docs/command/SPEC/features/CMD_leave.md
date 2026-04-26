# `leave`

> **Architecture Role**: 离开当前世界，回到奇点屋（GAME）。无参纯命令，禁止携带任何参数；具体回退由 `game_handler.leave_world` 完成。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `leave` |
| `CommandType` | GAME |
| File | [`backend/app/commands/game/leave_world_command.py`](../../../../backend/app/commands/game/leave_world_command.py) |
| Locale | `commands.leave`（别名 `ooc` 见快照） |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

## Synopsis

```
leave
```

- 无参；任何参数会触发 `用法: leave` 错误（见源码内中文硬编码字符串）。
- 别名 `ooc`（以快照为准）。

## Implementation contract

- 有任意参数 → `error_result("用法: leave")`（精确字符串，见码）。
- 无参：调用 `game_handler.leave_world`；`success` 为假 → `message` 错误；否则成功消息字符串。

## i18n status

- 当前错误文案 `用法: leave` 为中文硬编码，见 `leave_world_command.py`。
- TODO：迁移到 `commands.leave.error.usage`，与 `commands.who.*` 同 helper 模式接入。
- 本期不动代码，仅锚定 TODO。

## Tests

- 见 `test_game_handler` 与 `leave_world` 引用。
