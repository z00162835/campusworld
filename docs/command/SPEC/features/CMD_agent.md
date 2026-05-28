# `agent` command

**Scope**: Unified CLI for NPC agent directory listing, status, tool allowlists, and static capability summaries. Natural-language assistant entry remains **`aico`** (see AICO / `@` specs); it is **not** merged into `agent`.

## Syntax

| Invocation | Behavior |
|--------------|----------|
| `agent list` | Table of active `npc_agent` rows (`id`, name, status, `agent_node_id`). |
| `agent status <id>` | Single-row JSON for handle / `service_id` / alias match (exactly one agent). |
| `agent tool` | Table of all agents with effective tool ids per agent. |
| `agent tool <id>` | JSON `{"tools":[...]}` for one agent; structured payload includes `id`, `agent_node_id`, `excluded_by_policy`. |
| `agent tool add \|del <id> <tool>...` | Idempotent edit of `nodes.attributes.tool_allowlist` (primary command names). Requires **`admin.agent.tools.manage`**. **`add`** rejects unknown registry names; **`del`** also accepts names already on that agent's stored allowlist (for cleaning retired commands). |
| `agent show <id>` | JSON capability summary (`typeclass`, `decision_mode`, static capability keys). Same visibility rules as other read-only `agent` subcommands (no separate `agent.capabilities` gate). |

Invalid subcommands yield usage (see registry help).

## Structured fields (`CommandResult.data`)

- **`id`**: Logical agent identifier (prefer `attributes.service_id`, else node id string).
- **`agent_node_id`**: Graph node primary key.
- Legacy key **`service_id`** is **not** emitted in JSON (breaking change from older `agent_tools` / `agent list` payloads).

## Permissions

- Read paths (`list`, `status`, `tool` query, `show`): follow the standard command policy for `agent` (no extra permission key for `show`).
- `agent tool add` / `agent tool del`: **`admin.agent.tools.manage`** (unchanged from prior `agent_tools` write path).
- Write validation: **`add`** — every tool must resolve via `command_registry` (unknown → `AGENT_TOOLS_UNKNOWN_TOOL`, no write). **`del`** — same, **or** the name matches an entry on the agent's current `tool_allowlist` (case-insensitive), so legacy allowlist rows can be removed after commands are unregistered.

## Migration (breaking)

Retired top-level commands **`agent_tools`** and **`agent_capabilities`** are **not** registered. Use **`agent`** subcommands instead:

| Old CLI | New CLI |
|---------|---------|
| `agent_capabilities <id>` | `agent show <id>` |
| `agent_tools` | `agent tool` |
| `agent_tools <id>` | `agent tool <id>` |
| `agent_tools add <id> <tool>...` | `agent tool add <id> <tool>...` |
| `agent_tools del <id> <tool>...` | `agent tool del <id> <tool>...` |

- JSON consumers must use **`id`** instead of **`service_id`** where applicable.
- Aliases **`agent.capabilities`** / **`agent.tools`** are retired with the old top-level names.

### Manual cleanup (existing databases)

Remove legacy names from an agent node's stored allowlist (example for AICO):

```bash
agent tool del aico agent_capabilities agent_tools
```

Optional: deactivate orphan `system_command_ability` graph nodes for retired command names, then re-export the tool-router lexicon (`lexicon export`) so enrich snapshots no longer list them.

## Agent tool semantics

- 类级 **`read`**；`agent tool add` / `agent tool del` 经 `subcommand_profiles` 解析为 **`mutate`**。
- `manifest_tier=informational`（进入 AICO Plan manifest）。
- 见快照 `tool_semantics` 与 `backend/app/commands/command_tool_semantics.py`。

## Implementation

- [`backend/app/commands/agent_commands.py`](../../../../backend/app/commands/agent_commands.py): `AgentCommand`, `AicoCommand`; `get_agent_commands()` registers **`aico`** and **`agent`** only.
