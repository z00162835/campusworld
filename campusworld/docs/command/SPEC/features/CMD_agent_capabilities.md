# `agent_capabilities`

> **Architecture Role**: 单 agent 能力查询（SYSTEM）；**作用于具体 `service_id`**，与 [`CMD_agent_tools`](CMD_agent_tools.md) 的「全局工具注册表」语义不同：本命令返回某个 agent 节点（`npc_agent`）的 typeclass、决策模式、cognition、固定能力位等。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `agent_capabilities` |
| `CommandType` | SYSTEM |
| File | [`backend/app/commands/agent_commands.py`](../../../../backend/app/commands/agent_commands.py) |
| Locale | `commands.agent_capabilities` |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json)（别名 `agent.capabilities`） |
| Last reviewed | 2026-04-26 |

## Synopsis

```
agent_capabilities <service_id>
```

- 单参形态；无参 → `usage: agent_capabilities <service_id>`。
- 需活跃 DB 会话（`database session required`）。
- 与 `agent_tools` 的差异：前者按 **agent 节点** 自省（实例视角），后者扫描 **全局命令注册表**（系统视角）。

## Implementation contract

- 无参 → `usage: agent_capabilities <service_id>`。
- 无 `db_session` → `database session required`。
- `resolve_npc_agent_by_handle` 错误原样 `error_result(rerr)`。
- 成功：`message` 为 `json.dumps(data)`，字段含 `service_id`, `agent_node_id`, `typeclass`, `decision_mode`, `cognition`, 固定 `capabilities` 列表（`command.execute`, `agent.memory`）。
