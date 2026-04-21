# AICO Tool Description Audit

> Role of this document: a maintainer-facing audit of every command in
> AICO's default `tool_allowlist`, comparing the command's registered
> `description` (surfaced to the LLM via `build_llm_tool_manifest`)
> against what a tool-calling agent actually needs to choose it well.
> Keep this file in sync with `backend/db/seed_data.py::tool_allowlist`
> whenever the allowlist changes. Treat low-scoring entries as bug
> reports: the fix is almost always a tighter docstring or a
> `llm_hint` override on the command's `system_command_ability` node.

## Description precedence (what the LLM actually sees)

`build_llm_tool_manifest` (see
`backend/app/game_engine/agent_runtime/aico_world_context.py`) resolves
a tool description with the following precedence:

1. `attributes.llm_hint` on the `system_command_ability` graph node
   for that command (runtime override, no code change needed).
2. `BaseCommand.description` from code.
3. `BaseCommand.get_help()` (rarely reached; fallback only).

The manifest text additionally appends the command's `get_usage()` and
a worked JSON example, so a short description is acceptable as long as
the name + usage combination disambiguates the tool.

## Scoring rubric

Every tool is rated on four dimensions. Each dimension is either "ok"
(✓) or "needs work" (✗). The overall grade is the worst of the four
— we only ship "A" tools to the allowlist.

- **Purpose clarity** — answers *"when should I call this?"* in one
  sentence. A tool description that only restates the command name
  fails (e.g. "Show current user" for `whoami` is borderline; "Show
  version information" for `version` is borderline).
- **Input contract** — either the args are obvious from the name
  (`whoami`, `time`) or `get_usage()` makes them explicit. Hidden
  flags (`--for`, `--raw`) must be either documented inline in the
  description or covered by `_get_specific_help()`.
- **Observability** — description mentions the *shape* of the output
  when that is not obvious. Commands that return structured `data`
  (e.g. `find`) should say so.
- **No hallucination bait** — description does not invite the LLM to
  make up capabilities the command lacks (e.g. a `find` description
  promising "semantic search" when the implementation only does ILIKE
  on `name`/`description`).

## Current allowlist (Tier‑1 discovery suite)

The allowlist comes from `backend/db/seed_data.py::ensure_aico_npc_agent`.
Naming follows Evennia's admin set where applicable: the graph-search
verb is **`find`** (aliases: `@find`, `locate`), and the node-details
verb is **`describe`** (aliases: `examine`, `ex`). Allowlist aliases are
normalized to the primary name at surface-build time, so entries spelled
with any registered alias still filter correctly.

The definitive grammar, AND-combination semantics, and performance strategy
live in [`F01_FIND_COMMAND`](../../commands/SPEC/features/F01_FIND_COMMAND.md);
audit entries below should not diverge from it.

```
help, look, time, version, whoami,
primer, find, describe,
agent, agent_capabilities, agent_tools
```

| Name                | Registered description                                                                                                                                                                                                      | Usage                                                                                                       | Purpose | Input | Output | No-halu | Grade |
|---------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------|:-------:|:-----:|:------:|:-------:|:-----:|
| `help`              | List available commands for the current caller, or show detailed help for one command.                                                                                                                                      | `help [<command>]`                                                                                          |  ✓      |  ✓    |  ✓     |  ✓      | **A** |
| `look`              | 查看当前环境或特定物品                                                                                                                                                                                                        | `look [<target>]`                                                                                           |  ✓      |  ✓    |  ✓     |  ✓      | **A** |
| `time`              | Show current time                                                                                                                                                                                                           | `time`                                                                                                      |  ✓      |  ✓    |  ✓     |  ✓      | **A** |
| `version`           | Show version information                                                                                                                                                                                                    | `version`                                                                                                   |  ✓      |  ✓    |  ✓     |  ✓      | **A** |
| `whoami`            | Show current user                                                                                                                                                                                                           | `whoami`                                                                                                    |  ✓      |  ✓    |  ✓     |  ✓      | **A** |
| `primer`            | Show the CampusWorld system primer (world design, ontology, invariants).                                                                                                                                                    | `primer [<section> \| --toc \| --raw \| --for <service_id>]`                                                |  ✓      |  ✓    |  ✓     |  ✓      | **A** |
| `find`              | Find graph nodes. Flags AND-compose: -n name, -des desc, -t type, -loc id, -l N, -a (capped). Shortcuts: #<id>, *<account>. Returns data.results [{id,type_code,name,location_id,description}] + total/next_offset. Not semantic.                                           | see [F01_FIND_COMMAND](../../commands/SPEC/features/F01_FIND_COMMAND.md) §1                                 |  ✓      |  ✓    |  ✓     |  ✓      | **A** |
| `describe`          | Show a single graph node's details (type, name, description, attrs, edges).                                                                                                                                                 | `describe <node_id \| #<id> \| node_name>`                                                                  |  ✓      |  ✓    |  ✓     |  ✓      | **A** |
| `agent`             | Inspect and drive agents. Subcommands: `agent list`, `agent status <id>`, `agent nlp <handle> <text>`. Prefer `agent_capabilities <service_id>` when you only need the capability summary.                                 | `agent [list\|status <id> \| nlp <handle> <text>]`                                                          |  ✓      |  ✓    |  ✓     |  ✓      | **A** |
| `agent_capabilities`| List agent capabilities for a service_id                                                                                                                                                                                    | `agent_capabilities <service_id>`                                                                           |  ✓      |  ✓    |  ✓     |  ✓      | **A** |
| `agent_tools`       | List every command registered in the agent tool registry with its category. This is the global registry, NOT the current agent's callable surface — use `agent_capabilities <service_id>` for what a specific agent may invoke. | `agent_tools`                                                                                               |  ✓      |  ✓    |  ✓     |  ✓      | **A** |

## Findings and recommended fixes

Fixes can be applied in one of two places:

- **Code**: edit the `description=` argument in the command's
  `__init__`. This is the right fix when the tool was added recently
  and the wording is simply incomplete.
- **Runtime**: write an `llm_hint` string into
  `attributes.llm_hint` on the matching `system_command_ability`
  node. This is the right fix when we want to tailor the tool's
  presentation per deployment (e.g. tighter wording in prod, longer
  hints in a staging eval), or when the code description has to stay
  short for CLI help.

### Round 1 (2026-04) — shipped

The previous B/C grades below were all fixed in code; every entry in
the allowlist is now graded **A** above. The before/after descriptions
are kept in the changelog so future audits can see *why* the wording
changed.

- **`help` (was B)** — description now covers caller scope **and**
  the bullet-list output shape: "List available commands for the
  current caller, or show detailed help for one command." (see
  `system_commands.py::HelpCommand`).
- **`find` (was B)** — description now names the full `data` payload
  (`results`, `total`, `next_offset`) and explicitly disclaims
  "not semantic search" so the LLM does not over-promise fuzzy
  matching. The wording is deliberately kept under the 240-character
  manifest truncation so the disclaimer always reaches the model
  (see `graph_inspect_commands.py::FindCommand`).
- **`agent` (was C)** — description now enumerates subcommands
  (`list`, `status <id>`, `nlp <handle> <text>`) and points at the
  cheaper `agent_capabilities` tool when only a summary is needed
  (see `agent_commands.py::AgentCommand`).
- **`agent_tools` (was B)** — description now disambiguates the
  *global registry* from the *current agent's callable surface*, so
  an LLM that sees a command here does not assume it can invoke it
  immediately (see `agent_commands.py::AgentToolsCommand`).

## Structural gaps (not command-level)

- `find` now carries a `data.next_offset` field that is `None` when
  the current result list is the entire match set, and `len(results)`
  when the caller should re-issue the query with an offset. The
  `--offset` switch itself is not yet exposed; when it lands, the
  manifest description above should be amended to mention it. A
  source comment near `_render_find_results` codifies this contract
  so future edits don't drift.
- `describe` output is human-first. If we add a `--json` flag later,
  the LLM-manifest description should be updated to mention it so
  agents know when to prefer structured output.

## Process — how to use this doc

1. When adding a new command to AICO's `tool_allowlist`, add a row to
   the table above. A PR that grows the allowlist without also
   updating this file should be bounced.
2. When an eval shows AICO using a tool incorrectly (wrong args,
   unnecessary call, or failing to call when it should), the first
   debugging step is to re-read this file and check whether the
   description would have led the model astray.
3. Re-grade the whole table quarterly; fold any "B" or "C" entries
   that persist into a cleanup backlog issue.
