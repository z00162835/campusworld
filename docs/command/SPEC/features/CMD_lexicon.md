# `lexicon`

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `lexicon` |
| `CommandType` | ADMIN（`AdminCommand`） |
| Class | `app.commands.lexicon_command.LexiconCommand` |
| Primary implementation | [`backend/app/commands/lexicon_command.py`](../../../../backend/app/commands/lexicon_command.py) |
| Locale | `commands.lexicon` in [`backend/app/commands/i18n/locales/*.yaml`](../../../../backend/app/commands/i18n/locales/en-US.yaml) |
| Data layout | [`backend/app/game_engine/agent_runtime/tool_router/paths.py`](../../../../backend/app/game_engine/agent_runtime/tool_router/paths.py) → `backend/data/lexicon/` |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-05-06 |

**Aliases**: 无（以快照为准）。

## Synopsis

- `lexicon -b`：从当前上下文的数据库会话导出图节点快照，写入新版本目录（`entries.jsonl` + `meta.json`），并计算 `lexicon_revision`。
- `lexicon -l`：列出 `data/lexicon/` 下各版本目录；标注当前 **active**（由根目录 `active.txt` 原子指针解析）。
- `lexicon -d <id>`：删除指定版本目录；**禁止**删除当前激活版本。
- `lexicon -a <id>`：将 `active.txt` 设为该版本（临时文件再 `replace`）。

用法块来自 locale：`commands.lexicon.usage.block`（`get_localized_usage` / 无参 usage）。

## Implementation contract

- **权限**：一律要求 `admin.world.manage`；不满足 → `error.permission_denied`（i18n）。
- **无参或未知首参**：返回 `usage_result`，文案为本地化 usage 块。
- **`-b`**：依赖 `context.db_session`；缺失 → `error.no_db_session`。成功消息键 `success.build`，`data` 含 `id`、`lexicon_revision`。
- **`-l`**：空目录 → `success.empty_versions`。非空时首行为 `list.header`，后续行为 `list.row`（`active` 列为 `list.yes` / `list.no`）。
- **`-d`**：缺 id → `usage_line.delete`。当前激活 → `error.delete_active`。未知 id → `error.unknown_id`。成功 → `success.delete`。
- **`-a`**：缺 id → `usage_line.activate`。未知 id → `error.unknown_id`。成功 → `success.activate`。

行集构建与 revision 计算见 [`lexicon_export.py`](../../../../backend/app/game_engine/agent_runtime/tool_router/lexicon_export.py)；运行时加载见 [`lexicon_store.py`](../../../../backend/app/game_engine/agent_runtime/tool_router/lexicon_store.py)（供 Tool Router enrich）。

## i18n status

- 用户可见字符串（描述、用法块、表格头/行、错误与成功）均在 **`commands.lexicon.*`**（`en-US` / `zh-CN`）；`execute` 使用 `resolve_locale(context)`。
- 一行简介：`commands.lexicon.description`（`get_localized_description`）。

## Tests

- `backend/tests/commands/test_lexicon_command.py`

## Non-Goals

- 不在此命令内做远程同步或 CDN；不替代 `world install` 图种子流程。
- 训练数据 layout 见 [`tool_router/data/README.md`](../../../../backend/app/models/agent_model/tool_router/data/README.md)。
