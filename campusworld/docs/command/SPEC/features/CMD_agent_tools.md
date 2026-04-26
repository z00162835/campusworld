# `agent_tools`

> **Architecture Role**: 工具注册表枚举（SYSTEM）；**默认枚举全局工具注册表**（所有当前调用上下文可见的命令名），与 [`CMD_agent_capabilities`](CMD_agent_capabilities.md) 的「单 agent 视角」互补。可选附带 `service_id` 后按该 agent 的 `tool_allowlist` 过滤。

## Metadata (anchoring)

| Field | Value |
|--------|--------|
| Command | `agent_tools` |
| `CommandType` | SYSTEM |
| File | [`backend/app/commands/agent_commands.py`](../../../../backend/app/commands/agent_commands.py) |
| Locale | `commands.agent_tools`（别名 `agent.tools`） |
| Anchored snapshot | [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) |
| Last reviewed | 2026-04-26 |

## Synopsis

```
agent_tools
agent_tools <service_id>
```

- **无参**：返回当前上下文可见的全部命令名（`{"tools": [...]}` JSON）。
- **一参**（`service_id`）：返回该 agent 节点 `tool_allowlist` 过滤后的工具 id 列表（`RegistryToolExecutor` + `ToolRouter`）；需活跃 DB 会话。
- 二者 **不等价**：无参视角是「系统注册了哪些命令」；带参视角是「这个 agent 实际能调用哪些」。

## Implementation contract

- **无参**：`{"tools": sorted(command names from get_available_commands(context))}` 在 `message` 的 JSON 串中（`ensure_ascii=False`）。
- **一参**（`service_id`）：无 session → `database session required`；否则按节点 `tool_allowlist` 与 `RegistryToolExecutor`/`ToolRouter` 过滤后的工具 id 列表，JSON 在 `message`。
