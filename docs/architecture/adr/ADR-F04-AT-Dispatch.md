# ADR-F04: `@` Prefix Dispatch vs CmdSet

## Status

Accepted — 2026-04-12

## Context

F04 requires **`@<handle> <payload>`** to reach **`npc_agent`** instances from any room, with handle resolution (**`service_id`**, optional **`handle_aliases`**, uniqueness, **`enabled`**) and authorization aligned with the registered **`aico`** command policy.

Evennia typically merges **CmdSets** (account/character/session) and parses the line into a command. CampusWorld already uses a **single shell** with [`split_command_line`](../../../backend/app/commands/shell_words.py) (POSIX-style quotes) for registered commands.

## Decision

1. **`@` is not a registered command name.** [SSHHandler](../../../backend/app/protocols/ssh_handler.py) / [HTTPHandler](../../../backend/app/protocols/http_handler.py) call **`try_dispatch_at_line`** **before** `command_registry.get_command(...)`. This avoids reserving `@` as a command prefix character in the registry and matches common MUD-style “line escape” patterns.

2. **Authorization** for `@` lines uses **`authorize_command(aico)`**, so policy and audit paths match the **`aico`** shorthand (same NLP entry path as line-prefix dispatch).

3. **Handle resolution** is centralized in **[`resolve_npc_agent_by_handle`](../../../backend/app/commands/npc_agent_resolve.py)** and reused by **`at_agent_dispatch`**, **`aico`**, **`agent_capabilities`**, **`agent_tools`**, and other agent commands that resolve by `service_id` / alias.

4. **Future**: A full Evennia-like CmdSet stack is **not** required for F04; a prefix hook remains valid if CmdSets are introduced later (e.g. high-priority session command).

## Consequences

- **`help`** listings do not need to show `@` as a command name; users discover **`aico`**, **`agent`**, and F04 docs.
- Error messages may include **`Type 'help' for available commands.`** for parity with unknown-command UX.

## References

- [F04 — @ protocol](../../../models/SPEC/features/F04_AT_AGENT_INTERACTION_PROTOCOL.md)
- [ADR-F03 — AICO NL Pipeline](ADR-F03-AICO-NL-Pipeline.md)
