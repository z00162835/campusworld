# `west`

> 见 [`FAMILY_direction.md`](FAMILY_direction.md) 族规范（含 Architecture Role、Implementation contract、i18n status、错误表与 Tests）。本页仅记录其特有差异。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `west` |
| `CommandType` | GAME（`GameCommand`，`game_name` 依注册） |
| Class | `app.commands.game.direction_command.FixedDirectionCommand` |
| Primary implementation | [`direction_command.py`](../../../../backend/app/commands/game/direction_command.py)（`build_direction_commands()` 中构造） |
| Internal move direction | `FixedDirectionCommand(..., direction="west")`；`normalize_direction` 后为 **`west`**。 |
| Locale | `commands.west` in `backend/app/commands/i18n/locales/{zh-CN,en-US}.yaml`（仅 `description` 已就位；错误/成功句仍走族级硬编码） |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| **Aliases（以注册表为准）** | `registry_aliases`: `w` |
| Last reviewed | 2026-04-26 |

## 特有差异

- 无；行为与族规范一致（无参，沿当前房间出边按 `west` 方向移动）。

## 相关

- 族规范：[FAMILY_direction.md](FAMILY_direction.md)
- 参数化入口：[CMD_go](CMD_go.md)
