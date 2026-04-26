# `world`

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `world` |
| `CommandType` | ADMIN（`AdminCommand`） |
| Class | `app.commands.game.world_command.WorldCommand` |
| Primary implementation | [`backend/app/commands/game/world_command.py`](../../../../backend/app/commands/game/world_command.py) |
| Locale | `commands.world` in `backend/app/commands/i18n/locales/*.yaml` |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

**Aliases**: `registry_aliases` 含 `worlds`（以快照为准）。

## Synopsis

- `get_usage()` 覆盖：顶层 `world <list|install|uninstall|reload|status|validate|repair|content> ...`；`world content <validate|diff|apply> ...`；`world bridge <add|remove|list|validate> ...`（与 `--dry-run` / `--two-way` / `--bridge-type` 等标志）。具体子串以源码 `get_usage` 为准。

## Implementation contract

- **路由**（`execute`）:
  - 无子命令：返回 `error_result(self.get_usage())`。
  - 首参 `bridge` → `_bridge`；`content` → `_content`；其余需落在 `_SUB_PERM` 的键中，否则 `未知 world 子命令: {action}`。
- **子命令权限**（`*_has_sub_permission` 与 `permission_checker`）:
  - `list` / `status` → `admin.world.read`
  - `install` / `uninstall` / `reload` → `admin.world.manage`
  - `validate` / `repair` / `content` → `admin.world.maintain`
- **非 `_SUB_PERM` 动作**:
  - `bridge`：`add`/`remove` 需 `admin.world.bridge.manage`；`list`/`validate` 需 `admin.world.bridge.read`；否则 `WORLD_BRIDGE_*` 错误见源码。
- **写副作用**：`install`/`uninstall`/`reload`/`content apply` 等会调用引擎/游戏管理器/覆盖逻辑；`list` 等为读。
- **用户可见错误示例**：`Permission denied for world {action}`（`error=WORLD_FORBIDDEN` 等，见 `execute` 与各 helper）。

## i18n status

- 当前用户可见错误（如 `Permission denied for world {action}`、`未知 world 子命令: {action}`、`WORLD_BRIDGE_*` 错误等）混合中英文硬编码，见 `world_command.py`。
- TODO：迁移到 `commands.world.error.*`；考虑到子命令分支多，建议先统一顶层 dispatch 的错误文案再下沉到 `_bridge` / `_content` 子路径。
- 本期不动代码，仅锚定 TODO。

## 旁注

- HiCampus 空间脚本与 `world validate` 等见 CLAUDE 中「世界包」与包内 `package/README`；**行为以本实现文件为准**。

## Tests

- `backend/tests` 中 `world`、拓扑与 bridge 相关用例（`grep` `WorldCommand` / `world `）。

## Non-Goals / Roadmap

- 不重复 `docs/games/hicampus` 的叙事内容；本契约仅绑定 Python 子命令与权限位。
