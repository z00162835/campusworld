# Direction Command Family — `go` + 12 fixed-direction shortcuts

> **Architecture Role**: 世界内移动（GAME）；以 `MovementCommand._move` 为共享主干，`go <direction>` 为参数化入口，12 个固定方向命令为 `FixedDirectionCommand` 子类捷径。本族规范是 [`CMD_go`](CMD_go.md) 与各 [`CMD_north`/`CMD_south`/...] 的 **族级 SSOT**；per-direction 文档仅保留 `Internal move direction` 等差异。

## Family Metadata

| Field | Value |
|--------|--------|
| Family | `direction` |
| `CommandType` | GAME（`GameCommand`，`game_name` 依注册） |
| Primary implementation | [`backend/app/commands/game/direction_command.py`](../../../../backend/app/commands/game/direction_command.py) |
| Shared core | `MovementCommand._move`（成员包括 `go`、`FixedDirectionCommand` 子类） |
| Direction normalization | [`app.game_engine.direction_util.normalize_direction`](../../../../backend/app/game_engine/direction_util.py) |
| Locale roots | `commands.go.*` / `commands.<direction>.*` in `backend/app/commands/i18n/locales/{zh-CN,en-US}.yaml` |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

## Family Roster（与 `build_direction_commands()` 对齐）

| Command | Aliases (registry) | Internal direction (`normalize_direction`) | Per-page |
|---------|--------------------|---------------------------------------------|----------|
| `go`        | `walk` | 由首参解析 | [CMD_go](CMD_go.md) |
| `north`     | `n`    | `north`     | [CMD_north](CMD_north.md) |
| `south`     | `s`    | `south`     | [CMD_south](CMD_south.md) |
| `east`      | `e`    | `east`      | [CMD_east](CMD_east.md) |
| `west`      | `w`    | `west`      | [CMD_west](CMD_west.md) |
| `northeast` | `ne`   | `northeast` | [CMD_northeast](CMD_northeast.md) |
| `northwest` | `nw`   | `northwest` | [CMD_northwest](CMD_northwest.md) |
| `southeast` | `se`   | `southeast` | [CMD_southeast](CMD_southeast.md) |
| `southwest` | `sw`   | `southwest` | [CMD_southwest](CMD_southwest.md) |
| `up`        | `u`    | `up`        | [CMD_up](CMD_up.md) |
| `down`      | `d`    | `down`      | [CMD_down](CMD_down.md) |
| `in`        | (none) | `enter`（构造 `direction="enter"`，规范化保持 `enter`） | [CMD_in](CMD_in.md) |
| `out`       | `o`    | `out`       | [CMD_out](CMD_out.md) |

`enter`（顶层 `EnterWorldCommand`）不属于本族；它在世界内无参时复用 `FixedDirectionCommand(direction="enter")`，但顶层主名是世界入口分发器，详见 [CMD_enter](CMD_enter.md)。

## Synopsis（族级）

```
go <direction>
<direction>           # 12 个固定方向命令；不接受额外方向参数
```

- `go`：必须有一个方向位（首参），由 `MovementCommand._resolve_input_direction` 经 `normalize_direction` 规范化。
- 固定方向命令：`FixedDirectionCommand._resolve_input_direction` 恒返回 `self._fixed_direction`，**不接受**额外方向参数（与 `go <dir>` 的差异）。

## Implementation contract（族级共享）

- `MovementCommand.execute`：
  1. 调用 `_resolve_input_direction(args)` 得到归一方向；缺失（仅 `go` 入口可能）→ 错误 `用法: go <direction>`。
  2. 调用 `_move(user_id, direction)` 得到 `(ok, message, error_code)`；`ok=True` → `success_result`，否则 `error_result(message, error=error_code)`；异常包装为 `error_result(f"移动失败: {e}")`。
- `_move` 主路径（参考 `direction_command.py`）：
  - 取当前账号节点 `location_id`；不在世界 / 位置无效时返回族级错误句。
  - 在当前房间出边中匹配 `connects_to`，按 `attributes.direction` 做规范化比对；多目标 / 跨世界桥 / gate 出口等分支均由 `_move` 完成。
  - 成功路径更新账号 `location_id` 与 `attributes`，提交事务；用户可见消息形如 `你向 <direction> 移动，来到 <target_name>`，跨世界桥另有 `你通过跨世界连接向 <direction> 移动，来到 <target_name>（<world>）` 句式。
- `FixedDirectionCommand`：构造时调用 `normalize_direction(direction)` 一次，存入 `self._fixed_direction`；之后 `_resolve_input_direction` 恒返回该值。

## i18n status（族级 TODO）

- 当前 `_move` 与 `MovementCommand.execute` 的 **所有用户可见字符串均为中文硬编码**（用法、成功句、错误分支、跨世界桥句式等），未走 `commands.*` YAML。
- 与本族协同的 `MovementCommand.execute` 异常包装 `移动失败: {e}` 同样硬编码。
- TODO：整组迁移到 `commands.go.error.*` / `commands.go.success.*`（族级共享），per-direction 仅在需要差异化句式时引入 `commands.<direction>.*` 覆盖；helper 模式与 `commands.who.*`、`commands.quit.goodbye` 同。
- 本期不动代码，仅锚定 TODO；具体迁移顺序建议先做错误句式（影响 agent 错误识别），再做成功句。

## 错误形态（族级，文案为现行硬编码，待 i18n）

| 触发条件 | 用户可见消息（中文硬编码） | `error` 码 |
|----------|----------------------------|------------|
| `go` 缺少方向参数 | `用法: go <direction>` | — |
| 当前不在世界 | 见 `_move` 早期分支 | `_move` 第三项 |
| 位置无效 / `location_id` 非法 | 见 `_move` | `_move` 第三项 |
| 方向不可达 | 列出 `available_dirs` | — |
| 跨世界桥关闭 | `_move` 跨世界分支 | — |
| 多目标数据冲突 | `_move` 多目标分支 | — |
| 移动过程异常 | `移动失败: {e}` | — |

> 详细分支文案请以 `direction_command.py` 内 `_move` 实现为唯一权威；本表只列触发条件与定位锚点。

## 与其他命令的关系

- `enter`（顶层）：在奇点屋时为世界入口分发；在世界内无参时由 `FixedDirectionCommand(direction="enter")` 代理，与 `in` 主名同向但不同主名。详见 [CMD_enter](CMD_enter.md)。
- `leave`：离开世界，回到奇点屋。**不属于本族**，但与移动语义相邻；详见 [CMD_leave](CMD_leave.md)。

## Tests

- `backend/tests/commands/test_direction_command.py`
- 在 `backend/tests` 中按 `direction_command` / `FixedDirection` / 移动相关关键字检索，包括 SSH 移动用例。

## Non-Goals

- 不复制 `_move` 全量逻辑；以源码为最终权威。
- 不在族规范里讨论「方向语义之外」的世界入口分发（见 `enter`）或离场流程（见 `leave`）。
