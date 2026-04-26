# `in`

> 见 [`FAMILY_direction.md`](FAMILY_direction.md) 族规范（含 Architecture Role、Implementation contract、i18n status、错误表与 Tests）。本页仅记录其特有差异。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `in` |
| `CommandType` | GAME（`GameCommand`，`game_name` 依注册） |
| Class | `app.commands.game.direction_command.FixedDirectionCommand` |
| Primary implementation | [`direction_command.py`](../../../../backend/app/commands/game/direction_command.py)（`build_direction_commands()` 中构造） |
| Internal move direction | `FixedDirectionCommand(..., direction="enter")`；`normalize_direction` 后为 **`enter`**。 |
| Locale | `commands.in` in `backend/app/commands/i18n/locales/{zh-CN,en-US}.yaml`（仅 `description` 已就位；错误/成功句仍走族级硬编码） |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| **Aliases（以注册表为准）** | —（`class_declared_aliases` 与 `registry_aliases` 皆为空） |
| Last reviewed | 2026-04-26 |

## 特有差异

- **构造方向与主名不一致**：注册主名为 `in`，但 `FixedDirectionCommand(direction="enter")`；`normalize_direction("enter")` 仍为 `enter`。
- 这是 `in` 与 `enter`（顶层 [CMD_enter](CMD_enter.md)）的唯一桥接点：在世界内无参 `enter` 也走 `FixedDirectionCommand(direction="enter")`，与本主名同向。
- `class_declared_aliases` 与 `registry_aliases` **均为空**（详见快照）。

## 相关

- 族规范：[FAMILY_direction.md](FAMILY_direction.md)
- 参数化入口：[CMD_go](CMD_go.md)
