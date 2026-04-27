# `notice`

> **Architecture Role**: 系统公告管理（GAME）；`publish`/`edit`/`archive` 为写操作，`list` 为读操作。一次执行只走单个子命令路径，子分支与错误文案均为中文硬编码。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `notice` |
| `CommandType` | GAME |
| Class | `app.commands.game.notice_command.NoticeCommand` |
| Primary implementation | [`backend/app/commands/game/notice_command.py`](../../../../backend/app/commands/game/notice_command.py) |
| Locale | `commands.notice`（`notices` 别名，见快照） |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

## Synopsis

```
notice publish <title> | <content_md>
notice edit <id> <title> | <content_md>
notice archive <id>
notice list [all|published|draft|archived] [page]
```

- 顶层用法（与源码错误文案一致）：`用法: notice <publish|edit|archive|list> ...`。
- `list` 的 `status` 仅接受 `all|published|draft|archived`；`page` 为整数。
- 写操作经 `bulletin_board_service`；`list` 为只读。

## Implementation contract

- 无子命令/空 `args[0]` → `用法: notice <publish|edit|archive|list> ...`。
- **dispatch**：`publish` → `notice publish <title> | <content_md>` 管道；缺 `|` 等错误以源码为准；`edit` / `archive` 路径见 `_edit` / `_archive` 中文错误句。
- **list**：`notice list [status] [page]`；`status` 非法时 `status 仅支持 all|published|draft|archived`；体由 `bulletin_board_service.admin_list_notices` 与格式拼接。
- 未知子命令 → `未知操作: {action}`。
- **副作用**：`publish`/`edit`/`archive` 写 `bulletin_board_service`；`list` 为读。

## i18n status

- 当前所有用户可见错误为中文硬编码（如 `用法: notice <publish|edit|archive|list> ...`、`status 仅支持 all|published|draft|archived`、`未知操作: {action}`），见 `notice_command.py`。
- TODO：迁移到 `commands.notice.error.*` / `commands.notice.usage.*`；当前 `_publish` / `_edit` / `_archive` / `_list` 内多个错误句各自独立，应整组迁移避免散乱。
- 本期不动代码，仅锚定 TODO。

## Tests

- `backend/tests/services/test_bulletin_board_service.py` 等经服务层间接受影响。
