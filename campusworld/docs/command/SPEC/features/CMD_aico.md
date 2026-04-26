# `aico`

> **Architecture Role**: Agent 自然语言入口（SYSTEM）；将用户消息交给 `run_npc_agent_nlp_tick`，与 `@<handle>` 同管线；`CommandResult` 与 `data` 形态见实码与 `SPEC.md`「Assistant NLP」节。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `aico` |
| `CommandType` | SYSTEM |
| Class | `app.commands.agent_commands.AicoCommand` |
| Primary implementation | [`backend/app/commands/agent_commands.py`](../../../../backend/app/commands/agent_commands.py)；NLP 委托 [`backend/app/commands/npc_agent_nlp.py`](../../../../backend/app/commands/npc_agent_nlp.py)（`run_npc_agent_nlp_tick` / `assistant_nlp_command_result`） |
| Locale | `commands.aico` |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

## Synopsis

- `get_usage()`: `aico <message...>`（`execute` 中无参则 `usage: aico <message...>`）。

## Implementation contract

- **前提**：`context.db_session` 必存在，否则 `database session required`。
- **无参** → `error_result("usage: aico <message...>")`。
- 解析 `service_id`/`aico` 的助手节点：失败则 `resolve` 层错误原样；若节点 `decision_mode` 非 `llm`（大小写不敏感）→ `aico requires decision_mode=llm on the agent node`。
- 成功路径：`run_npc_agent_nlp_tick` 后 `session.commit()`，返回 `assistant_nlp_command_result("aico", res, service_id=...)`。
- **`CommandResult`**:
  - `message`：人类可读文本（`res.message` strip）。
  - `data`：`{ok, phase, handle, service_id?}` 由 `assistant_nlp_command_result` 设置（`npc_agent_nlp.py` 内定义）；与 [SPEC.md](../SPEC.md) 中 Assistant NLP 段落一致，以**源码**为准。

## 旁注

- LLM 不可用、passthrough 等行为见 `run_npc_agent_nlp_tick` 与引擎配置；不在这里作超出实现的断言。

## Tests

- `backend/tests/commands/test_registry_tool_executor_auth.py` 等；`aico` 在策略中的可见性；引擎侧工具清单测试。

## Non-Goals / Roadmap

- LTM/记忆侧叙述见独立模型文档；本页仅 `AicoCommand` 壳与 `data` 键名。
