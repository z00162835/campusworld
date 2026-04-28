# `go`

> **Architecture Role**: 世界内多方向移动（GAME）；`MovementCommand` 为显式 `go <direction>` 入口，与 [CMD_north](CMD_north.md) 等 `FixedDirectionCommand` 子命令共享 `_move` 实现（[`direction_command.py`](../../../../backend/app/commands/game/direction_command.py)）。族级共享语义见 [`FAMILY_direction.md`](FAMILY_direction.md)。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `go` |
| `CommandType` | GAME |
| Class | `app.commands.game.direction_command.MovementCommand`（`name="go"`） |
| Primary implementation | [`backend/app/commands/game/direction_command.py`](../../../../backend/app/commands/game/direction_command.py) |
| Locale | `commands.go`（别名 `walk`） |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

## Synopsis

```
go <direction>
```

- 必含一个方向位（`normalize_direction` 解析）；缺失时报 `用法: go <direction>`（中文硬编码，TODO i18n）。
- 接受方向词及其常见缩写（`n/s/e/w/ne/nw/se/sw/u/d/in/out/enter/leave` 等，规则以 `app.game_engine.direction_util.normalize_direction` 为准）。
- 与 `FixedDirectionCommand` 子命令（north/south/…）的差异：本命令把首参当方向；子命令固定方向不接受额外方向参数。

## Implementation contract

- **用法**：首参为方向，经 `normalize_direction`；未解析到方向时 `error_result("用法: go <direction>")`（`MovementCommand` 在 `name=="go"` 时解析参数）。
- **成功/失败**：`_move` 返回的 `(ok,msg,err)` 映射为 `success_result` 或 `error_result(msg, error=err)`；异常时 `error_result("移动失败: {e}")`。
- **与 FixedDirection 子命令**：`north` 等**无参**时仍用同一 `_move` 主干；见各 `CMD_{direction}.md`。

**副作用**：更新账号 `location_id` / 属性、提交事务（`direction_command.py` 内 `db_session` / `with db_session_context` 路径，以实码为准）。

## i18n status

- 当前错误文案 `用法: go <direction>`、`移动失败: {e}` 为中文硬编码，见 `direction_command.py`。族级共享错误（不可达方向、跨世界桥关闭等）也由 `_move` 元组返回中文字符串。
- TODO：方向族整体迁移到 `commands.go.error.*` 与 `commands.<direction>.error.*`，与 [`FAMILY_direction.md`](FAMILY_direction.md) 的 i18n TODO 同节奏推进。
- 本期不动代码，仅锚定 TODO。
