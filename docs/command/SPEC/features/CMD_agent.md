# `agent`

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `agent` |
| `CommandType` | SYSTEM |
| Class | `app.commands.agent_commands.AgentCommand` |
| Primary implementation | [`backend/app/commands/agent_commands.py`](../../../../backend/app/commands/agent_commands.py) |
| Locale | `commands.agent`（列表表头、状态展示文案、空列表与页脚等见 [`backend/app/commands/i18n/locales/`](../../../../backend/app/commands/i18n/locales/)） |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

## Synopsis

- `get_usage()` 当前返回: `agent <list|status> ...`（见源码）。

## Implementation contract

- **无 `db_session`** → `error_result`；文案走 **`commands.agent.error.no_session`**（见 locale YAML，默认 en 为 `database session required`）。
- **无子命令/空参**（`not args`）→ `error_result(self.get_usage())`。
- **子命令**（`execute` 实现与类 docstring 对照）:
  - 仅实现 **`list`** 与 **`status`**：
    - **`agent list`**（可见性与字段见 F05）:
      - **`message`**：人类可读的**多行表格**（与 `world list`、`agent_tools` 无参形式一致：表头行、分隔线、每行一实例、空行、总数页脚与可选 `hint`）。表内 **状态列** 为按 **`resolve_locale(context)`** 从 `commands.agent.status_value.*` 解析后的展示串；**机器三态**仍只在结构化负载中提供。
      - **`data`**：`{ "agents": [ ... ], "total": N }`，每项为 `_agent_row_dict`（`service_id`, `name`, `status` 为三态英文明文, `agent_node_id`），供 JSON/程序消费（SSH 仅依赖 `message` 的规则见 `protocols` 说明）。
    - `agent status <service_id_or_handle>`：两参；若匹配非恰好一个节点，返回常数 `AGENT_STATUS_ACCESS_ERROR`（`agent not found or not accessible`）。
  - 其他首参（含 `nlp`）**未实现**：落入 `return CommandResult.error_result(self.get_usage())`（即**非**独立 `agent nlp` 子命令路径）。
- **与类 docstring 差异**：`__init__` 的英文长描述中提及 `agent nlp`；`execute` **不**含该分支。文档以本 **Implementation contract** 为准，避免双源。

**`agent status` 输出**: `success` 为 JSON 串（`ensure_ascii=False`）在 `message` 中（与 list 区分：list 的 `message` 为表格文本）。

## Non-Goals / Roadmap

- 若未来增加 `agent nlp`，须同时改 `get_usage`/`execute` 与本文档与 locales。

## Tests

- 见 `agent` / `AGENT_STATUS` 相关；`backend/tests/commands/test_agent_f05_commands.py`（`agent list` 结构断言使用 `result.data`）。
