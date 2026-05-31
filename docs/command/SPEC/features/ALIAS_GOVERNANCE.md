# Command alias governance

> SSOT for **effective** command tokens: live `CommandRegistry` after `initialize_commands()`. Snapshot: [`../_generated/registry_snapshot.json`](../_generated/registry_snapshot.json) (`registry_aliases` per command).

## Two dispatch paths

| Path | Entry | Token source |
|------|--------|--------------|
| **Primary** | SSH, HTTP, WS, Agent tooling | `command_registry` (global) |
| **Character API** | `Character.execute_command()` | `CharacterCmdSet` only — **no** Registry fallback |

Global commands (`look`, `go`, `help`, …) must use the primary path. Character CmdSet holds **character-only** commands (`run`, `jump`, `rest`, `talk`, `charstats`).

## Registration order (alias preemption)

In [`backend/app/commands/init_commands.py`](../../../../backend/app/commands/init_commands.py):

1. SYSTEM + GRAPH_INSPECT + AGENT (includes `describe` with `examine`, `ex`)
2. ADMIN + GAME (includes `look` with `l`, `lookat`)
3. Builder cmdset (`create`, …)

If two commands declare the same alias, **earlier registration wins**; later alias is dropped (`class_declared_aliases` may differ from `registry_aliases`).

## Namespace layers

| Layer | Rule | Examples |
|-------|------|----------|
| L1 single-char | Globally unique | `n`, `s`, `e`, `w`, `l`, `h`, `q`, `d`, `u`, `o` |
| L2 short words | 2–4 chars | `exit`, `walk`, `ver`, `ooc`, `lookat` |
| L3 MUX / admin | `@` prefix or ADMIN | `@find`, `spawn`, `build` |
| L4 object nick | Not cmd aliases | `look_appearance` match strings |

## Evennia comparison (intentional diffs)

| CampusWorld | Evennia default | Note |
|-------------|-----------------|------|
| `describe` + `examine`, `ex` | `@examine` + `@ex` (Builder) | CampusWorld: SYSTEM read-only graph inspect, not Builder `@examine` |
| `find` + `@find`, `locate` | `@find` + `@search`, `@locate` | Primary name `find` (no `@`) for SSH/Agent |
| `look` + `l`, `lookat` | `look` + `l`, `ls` | No `ls` alias yet (backlog) |
| `quit` + `exit`, `q` | `quit` only | Traditional MUD extension |

## Confusable pairs (documented, not changed)

| Tokens | Resolve to | Risk |
|--------|------------|------|
| `ex` vs `exit` | `describe` vs `quit` | Typo / prefix similarity |
| `in` vs `enter` | direction vs world entry | Different semantics; see [CMD_in](CMD_in.md), [CMD_enter](CMD_enter.md) |
| `o` vs `ooc` | `out` vs `leave` | Different semantics |
| `stats` alias `system` | `stats` | Do not confuse with “system commands” category |

## Reserved future tokens

Planned global commands — occupancy emits **warning** in `validate_command_aliases.py`:

`say`, `speak`, `i`, `inv`, `r`, `inventory`

`TalkCommand` in CharacterCmdSet currently uses `say`/`speak`; remove or merge when global `say` registers.

## Validation

From `backend/` (Conda env `campusworld`):

```bash
python scripts/export_command_registry_snapshot.py
python scripts/validate_command_aliases.py
python scripts/validate_command_aliases.py --check-db   # requires PostgreSQL
python scripts/validate_command_aliases.py --report-evennia
```

Not in CI (local / release checklist only). `--check-db` drift is **error**.

## Lexicon / ability nodes

`system_command_ability` node `attributes.aliases` are synced from registry via `ability_sync`. After alias changes:

1. `ensure_command_ability_nodes(session)`
2. `lexicon -b` → `lexicon -a <id>`
3. Update `backend/data/shards/*.jsonl` `lexicon_active_id` if active id changed

## Backlog

- `cmdstring` on `CommandContext.metadata` (Evennia `self.cmdstring`)
- `look` → `ls` alias
- Global `say` / `inventory` registration and CharacterCmdSet cleanup
