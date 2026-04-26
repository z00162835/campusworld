# `agent`

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `agent` |
| `CommandType` | SYSTEM |
| Class | `app.commands.agent_commands.AgentCommand` |
| Primary implementation | [`backend/app/commands/agent_commands.py`](../../../../backend/app/commands/agent_commands.py) |
| Locale | `commands.agent`（长段描述在 YAML） |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

## Synopsis

- `get_usage()` 当前返回: `agent <list|status> ...`（见源码）。

## Implementation contract

- **无 `db_session`** → `database session required`。
- **无子命令/空参**（`not args`）→ `error_result(self.get_usage())`。
- **子命令**（`execute` 实现与类 docstring 对照）:
  - 仅实现 **`list`** 与 **`status`**：
    - `agent list`：所有活跃 `npc_agent` 的 JSON 列表（`{"agents": [...]}` 形态，字段 `service_id`, `name`, `status`, `agent_node_id` 等，见 `_agent_row_dict`）。
    - `agent status <service_id_or_handle>`：两参；若匹配非恰好一个节点，返回常数 `AGENT_STATUS_ACCESS_ERROR`（`agent not found or not accessible`）。
  - 其他首参（含 `nlp`）**未实现**：落入 `return CommandResult.error_result(self.get_usage())`（即**非**独立 `agent nlp` 子命令路径）。
- **与类 docstring 差异**：`__init__` 的英文长描述中提及 `agent nlp`；`execute` **不**含该分支。文档以本 **Implementation contract** 为准，避免双源。

**输出**: `success` 为 JSON 串（`ensure_ascii=False`）在 `message` 中。

## Non-Goals / Roadmap

- 若未来增加 `agent nlp`，须同时改 `get_usage`/`execute` 与本文档与 locales。

## Tests

- 见 `agent` / `AGENT_STATUS` 相关；`backend/tests/commands/`。
