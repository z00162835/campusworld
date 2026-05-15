# `notice`

> **Architecture Role**: 系统公告管理（ADMIN）；`publish`/`edit`/`archive` 为写操作，`list`/`view` 为读操作。一次执行只走单个子命令路径，子分支与错误文案均为中文硬编码。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `notice` |
| `CommandType` | ADMIN |
| Class | `app.commands.admin.notice_command.NoticeCommand` |
| Primary implementation | [`backend/app/commands/admin/notice_command.py`](../../../../backend/app/commands/admin/notice_command.py) |
| Locale | `commands.notice`（`notices` 别名，见快照） |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-05-15 |

## Synopsis

```
notice publish <title> | <content_md>
notice edit <id> <title> | <content_md>
notice archive <id>
notice list [all|published|draft|archived] [page]
notice view <id>
```

- 顶层用法（与源码错误文案一致）：`用法: notice <publish|edit|archive|list|view> ...`。
- `list` 的 `status` 仅接受 `all|published|draft|archived`；`page` 为整数。
- `view`：`notice view <id>`；读取单条公告完整内容（标题、作者、时间、正文）；正文经 `render_notice_md_to_terminal` 渲染为终端安全文本，超长内容自动分块。
- 写操作经 `bulletin_board_service`；`list`/`view` 为只读。

## Implementation contract

- 无子命令/空 `args[0]` → `用法: notice <publish|edit|archive|list|view> ...`。
- **dispatch**：`publish` → `notice publish <title> | <content_md>` 管道；缺 `|` 等错误以源码为准；`edit` / `archive` 路径见 `_edit` / `_archive` 中文错误句。
- **list**：`notice list [status] [page]`；`status` 非法时 `status 仅支持 all|published|draft|archived`；体由 `bulletin_board_service.admin_list_notices` 与格式拼接。
- **view**：`notice view <id>`；通过 `bulletin_board_service.get_notice_by_id` 获取公告数据，`public_only=False` 以支持查看所有状态公告；正文经 `render_notice_md_to_terminal` 渲染，`split_terminal_chunks` 分块输出。
- 未知子命令 → `未知操作: {action}`。
- **副作用**：`publish`/`edit`/`archive` 写 `bulletin_board_service`；`list`/`view` 为读。

## i18n status

- `notice.view.header`、`notice.view.author`、`notice.view.time` 提供 view 输出标题行 i18n。
- `notice.view.error.usage`、`notice.view.error.invalid_id`、`notice.view.error.not_found` 提供 view 错误文案 i18n。
- 原有 `publish/edit/archive/list` 错误中文硬编码问题已锚定（见上期 TODO），本期不动。

## Tests

- `backend/tests/commands/test_notice_command.py` 包含 view 相关测试：
  - `test_notice_command_view_success`：view 成功显示公告内容
  - `test_notice_command_view_not_found`：view 不存在的公告 ID
  - `test_notice_command_view_invalid_id`：view 无效 ID
  - `test_notice_command_view_missing_id`：view 缺少 ID 参数
