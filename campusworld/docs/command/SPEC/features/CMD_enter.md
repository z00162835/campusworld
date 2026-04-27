# `enter`

> **Architecture Role**: 通用「进入」入口（GAME）；既可作为方向命令在世界内沿 `enter` 出边移动，也作为奇点屋向具体世界的入口分发器。**当前实现优先世界入口分发**；方向语义在世界内无参时由 `FixedDirectionCommand(direction="enter")` 代理。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `enter` |
| `CommandType` | GAME |
| Class | `app.commands.game.enter_world_command.EnterWorldCommand` |
| Primary implementation | [`backend/app/commands/game/enter_world_command.py`](../../../../backend/app/commands/game/enter_world_command.py) |
| Locale | `commands.enter` |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

## Synopsis

```
enter <world_name> [spawn_key]
enter
```

- `enter <world_name> [spawn_key]`：从奇点屋进入指定世界（须已 `leave` 离开当前世界）。
- 无参 `enter`：在世界内等价于方向命令 `enter`（由 `FixedDirectionCommand(direction="enter")` 代理；与 [`CMD_in`](CMD_in.md) 是不同主名）。
- 来源：`get_usage()` → `enter <world_name> [spawn_key]  # 世界入口；无参数时在世界内按方向 enter 移动`。

## Implementation contract

- **语义定位**：`enter` 是通用“进入”命令，不是 world 专属命令。它既可作为方向移动语义（进入可进入空间对象），也可在当前实现中承载 world 入口分发。
- **无参**（`not args`）：在会话内用 `FixedDirectionCommand(name=..., direction="enter")` 代理，等价于 **方向 enter** 的移动，见 [`direction_command.py`](../../../../backend/app/commands/game/direction_command.py) 与 [CMD_in.md](CMD_in.md) 差异（`in` 为另一 FixedDirection 命令）。
- **有参**：
  - 当前实现优先走 world 入口分发：`world_name` 小写、可选 `spawn_key`；空世界名 `世界名不能为空`。
  - `world_entry_service.build_entry_request` + `authorize_entry`；`not decision.ok` → `decision.message` 等。
  - `game_handler.enter_world`：失败消息分支映射 `error` 码 `WORLD_ENTRY_GAME_UNAVAILABLE` / `WORLD_ENTRY_FORBIDDEN` / `WORLD_ENTRY_FAILED`（与消息子串，见 `execute`）。
- **成功**：`success_result(result.get("message", f"已进入世界 {world_name}"))`。

## i18n status

- 当前错误文案为中文硬编码（如 `世界名不能为空`、`已进入世界 {world_name}`），见 `enter_world_command.py`。
- TODO：迁移到 `commands.enter.error.*` / `commands.enter.success.*`，与 `quit`/`time`/`stats`/`whoami` 的 helper 统一（见 [`commands.who.*`](../../../../backend/app/commands/i18n/locales/en-US.yaml) 模式）。
- 本期不动代码，仅锚定 TODO。

## Tests

- `backend/tests/ssh/test_game_handler.py`；`enter` 相关游戏命令测。
