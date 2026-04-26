# `find`

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `find` |
| `CommandType` | SYSTEM |
| Class | `app.commands.graph_inspect_commands.FindCommand` |
| Primary implementation | [`backend/app/commands/graph_inspect_commands.py`](../../../../backend/app/commands/graph_inspect_commands.py) |
| Locale | `backend/app/commands/i18n/locales/{zh-CN,en-US}.yaml` → `commands.find` |
| Anchored snapshot | [`docs/command/SPEC/_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) (`git_commit`, `class_declared_aliases` / `registry_aliases`) |
| Last reviewed | 2026-04-26 |

## SSOT 声明

- **深文档与图检索契约**（参数解析、分页、`CommandResult.data`、`find`/`describe` 互斥等）的**唯一权威**为 [F01_FIND_COMMAND.md](F01_FIND_COMMAND.md)。本页仅作索引与元数据，**不重复** F01 中的行为与字段表。

## Implementation contract（摘要，真源 = 代码 + F01）

- **行为**：只读图查询；`execute` 在 `app.commands.graph_inspect_commands` 的 `FindCommand`；需活跃 DB 会话，否则 `find requires an active DB session`（见该文件）。
- **与 `describe` 的边界**：F01 定义双命令协同；实现文件与 F01 同步更新。

## Tests

- 见 `backend/tests/commands/test_graph_inspect_commands.py` 及 F01 所列用例名。

## Non-Goals / Roadmap

- 新的检索语义或 `data` 键变更须先改代码与 F01，再增链本页。
