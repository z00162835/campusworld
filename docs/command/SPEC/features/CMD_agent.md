# `agent` command

**Scope**: Unified CLI for NPC agent directory listing, status, tool allowlists, and static capability summaries. Natural-language assistant entry remains **`aico`** (see AICO / `@` specs); it is **not** merged into `agent`.

## Syntax

| Invocation | Behavior |
|--------------|----------|
| `agent list` | Table of active `npc_agent` rows (`id`, name, status, `agent_node_id`). |
| `agent status <id>` | Single-row JSON for handle / `service_id` / alias match (exactly one agent). |
| `agent tool` | Table of all agents with effective tool ids per agent. |
| `agent tool <id>` | JSON `{"tools":[...]}` for one agent; structured payload includes `id`, `agent_node_id`, `excluded_by_policy`. |
| `agent tool add \|del <id> <tool>...` | Idempotent edit of `nodes.attributes.tool_allowlist` (primary command names). Requires **`admin.agent.tools.manage`**. |
| `agent show <id>` | JSON capability summary (`typeclass`, `decision_mode`, static capability keys). Same visibility rules as other read-only `agent` subcommands (no separate `agent.capabilities` gate). |

Invalid subcommands yield usage (see registry help).

## Structured fields (`CommandResult.data`)

- **`id`**: Logical agent identifier (prefer `attributes.service_id`, else node id string).
- **`agent_node_id`**: Graph node primary key.
- Legacy key **`service_id`** is **not** emitted in JSON (breaking change from older `agent_tools` / `agent list` payloads).

## Permissions

- Read paths (`list`, `status`, `tool` query, `show`): follow the standard command policy for `agent` (no extra permission key for `show`).
- `agent tool add` / `agent tool del`: **`admin.agent.tools.manage`** (unchanged from prior `agent_tools` write path).

## Migration (breaking)

- CLI commands **`agent_tools`** and **`agent_capabilities`** are **removed** from registration; use **`agent tool`** and **`agent show`**.
- JSON consumers must use **`id`** instead of **`service_id`** where applicable.

## Implementation

- [`backend/app/commands/agent_commands.py`](../../../../backend/app/commands/agent_commands.py): `AgentCommand`, `AicoCommand`; `get_agent_commands()` registers **`aico`** and **`agent`** only.
