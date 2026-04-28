# `look`

> **Architecture Role**: 世界内观察（GAME）；无参为当前房 `return_appearance` 式展示，有参为对象/消歧查看；与 `describe` 分工见 [F01](F01_FIND_COMMAND.md) §10。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `look` |
| `CommandType` | GAME (`game_name` 类字段 `campus_life`) |
| Class | `app.commands.game.look_command.LookCommand` |
| Primary implementation | [`backend/app/commands/game/look_command.py`](../../../../backend/app/commands/game/look_command.py)；外观组块见 [`look_appearance.py`](../../../../backend/app/commands/game/look_appearance.py) |
| Locale | `commands.look` in `backend/app/commands/i18n/locales/{zh-CN,en-US}.yaml` |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

**Aliases（以注册表为准）**：`registry_aliases`: `l`, `lookat`（`class_declared_aliases` 另含 `examine`，与 `describe` 冲突，**不**在全局别名表中指向 `look`；终端输入 `examine` 由 `describe` 处理。）

## Synopsis

- 无参：查看当前位置房间（依赖账号 `location_id` / 图房间解析，见 `execute` → `_look_room` → `_get_current_room`）。
- 有参：将首参作目标；若首参为纯数字，走消歧选择 `_resolve_look_disambiguation_index`；否则 `_search_objects` → 0 / 1 / 多匹配分支。

## Implementation contract

- **入口**（`LookCommand.execute`）:
  - `not args` → `_look_room`；当前房间无法解析时 `无法确定当前位置`。
  - 有 `args` → `target = args[0]`，`target_args = args[1:]`；数字 → 消歧索引；否则 `_look_object`。
- **多匹配** `_show_multiple_matches` / 单对象 `_build_object_description` 使用图与会话；错误示例 `找不到 '<target>'`（用户可见，未 i18n 的字符串在源码中）。
- **数据 / 消歧**: 非 JSON 主路径为主；`LOOK_DISAMIGUATION_KEY` 等用于上下文字典键（`look_command.py`）。
- **副作用**: 只读；查 DB、查图、不写用户位姿（不替代 `go` / `enter`）。

## 旁注

- 设计目标：与 Evennia 式 `return_appearance` 对齐的「单命令 + 对象自描述」；与公告栏、世界入口展示等的交互见实现与 `look_appearance` 调用链。

## Tests

- `backend/tests/` 中 `look` 相关用例与 SSH 游戏路径（`grep -R "look" backend/tests` 可定位）。

## Non-Goals / Roadmap

- 不在这里约定「未来 MUD 扩展」；若 `execute` 增加行为，本契约与快照须同步。
