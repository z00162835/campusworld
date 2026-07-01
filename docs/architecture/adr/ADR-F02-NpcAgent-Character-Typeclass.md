# ADR-F02: NpcAgent Character Typeclass Refactor

## Status

Proposed — 2026-06-29

## Context

The `npc_agent` graph node is implemented by the Python typeclass
[`NpcAgent`](../../../backend/app/models/things/agents.py), which currently
extends [`WorldThing`](../../../backend/app/models/things/base.py). `WorldThing`
is a thin marker base over [`DefaultObject`](../../../backend/app/models/base.py)
that provides no behavior beyond room-list hooks. In parallel,
[`Character`](../../../backend/app/models/character.py) defines the Evennia-style
role tree (CmdSet, move hooks, action-cost hooks, RPG attributes) but is **not**
an ancestor of `NpcAgent`; the `agents.py` module docstring previously noted the
intention to "align with the Evennia role tree later".

F02 §6.1 invariant #1 requires that the agent `type_code` stays **`npc_agent`**
— it forbids merging agents into `character` or introducing a new `agent`
type_code. The agent runtime (`AgentWorker`, `agent_*` memory tables,
`service_account_id` binding) is already decoupled from the Character RPG layer:
[`resolve_npc_agent_by_handle`](../../../backend/app/commands/npc_agent_resolve.py)
returns a raw `Node` ORM row, not a `NpcAgent` typeclass instance, and the AICO
seed writes nodes via `Node(...)` with explicit attributes, bypassing the
typeclass constructor entirely. The `go` / direction movement commands operate
on the account node and never call `Character.at_action_cost` or
`Character._at_pre_move`; `at_action_cost` is only invoked by `CharacterCmdSet`
commands (`run` / `jump` / `talk` / `rest` / `stats`).

This ADR records the decision to align the Python typeclass tree with the
Evennia role tree **without** touching the agent runtime contract.

## Decision

1. **`NpcAgent` extends `Character`** instead of `WorldThing`. The module path
   stays `app.models.things.agents.NpcAgent` so the `typeclass` string and the
   HiCampus entity registry remain valid.

2. **`type_code` stays `npc_agent`** — consistent with
   [F02 §6.1](../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)
   invariant #1. Merging the ontology `type_code` into `character` (formerly
   "Option B") is explicitly rejected.

3. **RPG defaults are inert, not stripped.** `NpcAgent.__init__` calls
   `super().__init__()` (i.e. `Character.__init__`), so the Character RPG
   default attributes (`level`, `strength`, `health`, `energy`, `mana`,
   `action_costs`, `recovery_rates`, …) are written to `_node_attributes`.
   They are made inert by overrides:
   - `_initialize_base_stats` → no-op (no `character_type` buffs)
   - `at_action_cost` / `at_action_result` → no-op / zero-cost
   - `_init_cmdsets` does not mount `CharacterCmdSet`, so the RPG micro-commands
     (`run` / `jump` / `talk` / `rest` / `stats`) are unreachable and no runtime
     path reads or writes the RPG keys.
   Character properties (`energy`, `health`, …) use `.get(..., default)` and do
   not crash when keys are absent. Existing DB nodes (AICO seed written via
   `Node(...)`) have no orphan RPG keys; no data migration is performed.

4. **CmdSet branches by `agent_role`; `CharacterCmdSet` and `NPCCmdSet` are
   peer extension slots.** `NpcAgent._init_cmdsets` does **not** call
   `super()._init_cmdsets()` (which would mount `CharacterCmdSet`), and instead
   branches on the node's `agent_role`:
   - `sys_worker` → empty CmdSet
   - `narrative_npc` (and unspecified) → mount `NPCCmdSet` only

   `NPCCmdSet` is the agent-side extension slot, peer to `CharacterCmdSet` for
   roles; it is currently empty (`_init_npc_commands` is a no-op) and reserved
   for future NPC-specific object-level commands. The agent's actual workflow
   still goes through the global `command_registry` + `RegistryToolExecutor` +
   service-account principal
   ([`command_context_for_npc_agent`](../../../backend/app/commands/agent_command_context.py));
   the CmdSet is only an object-level extension point and does not participate
   in NLP ticks.

5. **Agent runtime unchanged.** `app/game_engine/agent_runtime/`, the
   `agent_*` memory tables, `service_account_id` binding, and
   `resolve_npc_agent_by_handle` semantics do not change with the typeclass
   parent. Resolution still keys on `Node.type_code == 'npc_agent'` and
   `node.id`.

6. **Ontology parent alignment with a `character` prerequisite row.** A
   `character` row is added to
   [`GRAPH_SEED_ONTOLOGY_NODE_ROWS`](../../../backend/db/schema_migrations.py)
   with `parent_type_code = default_object` and `typeclass = Character`, placed
   **before** the `npc_agent` row so the `parent_type_code` foreign key is
   satisfied. The `npc_agent` row's `parent_type_code` changes from
   `world_thing` to `character`. The existing
   [`ensure_graph_seed_ontology`](../../../backend/db/schema_migrations.py)
   implementation already runs `ON CONFLICT (type_code) DO UPDATE SET
   parent_type_code = EXCLUDED.parent_type_code, …`, so updating the tuple
   repairs existing DB rows; no new migration function is required.

7. **Display behavior preserved.** `get_display_extra_name_info` and
   `room_line_format_kwargs` (activity/mood hints) are unchanged.

8. **Defaults `is_npc=True, is_ai=True`.** `NpcAgent(name=...)` sets
   `is_npc=True` and `is_ai=True` (tags include `npc` and `ai`), semantics
   "NPC and AI". This only affects the Python constructor path; the AICO seed
   writes via `Node(...)` and needs no backfill.

9. **Implementation surface is `agents.py` only.** Only
   [`agents.py`](../../../backend/app/models/things/agents.py) is modified for
   the typeclass; `Character` base class is not changed, avoiding Player/NPC/
   Agent split regressions.

10. **`character` node_types row is ontology-only.** The new `character` row
    carries only `typeclass` / `parent_type_code` / `classname` / `module_path`
    and no `schema_definition` / `schema_default` instance-schema extension, to
    avoid colliding with the F02 `npc_agent` schema.

## Non-Goals

- Merging `type_code` into `character` or introducing `type_code=agent`.
- Introducing RPG game-play for agents.
- Changing `entity_inspect` / `semantic_map` `entity_kind: 'agent'` in Phase 1
  (kept as `'agent'`, not merged to `'person'`).
- Migrating the F02 `npc_agent` schema into the `character` attribute dictionary.
- Modifying the `Character` base class.

## Typeclass Contract

```
DefaultObject
└── Character
    └── NpcAgent            type_code = 'npc_agent'
                            attributes: F02 schema (graph_seed) + inert RPG defaults
                            is_npc=True, is_ai=True
                            CmdSet: by agent_role (sys_worker=∅, narrative_npc=NPCCmdSet)
                            hooks: _initialize_base_stats / at_action_cost / at_action_result = no-op
```

`NpcAgent.__init__` pops `disable_auto_sync` from kwargs (so it is not merged
into `_node_attributes` by `Character.__init__`), defaults `is_npc=True` and
`is_ai=True`, and calls `super().__init__()`. Because `Character.__init__`
writes `_node_type='character'` and `DefaultObject.__init__` (invoked from
within that `super().__init__()`) calls `self.at_object_creation()` **before**
control returns to `NpcAgent.__init__`, the `_node_type` / `_node_type_code`
restoration to `'npc_agent'` is performed inside the `at_object_creation`
override — *before* `sync_to_node` runs — so a sync-enabled construction
persists `type_code='npc_agent'` (not `'character'`). `at_object_creation` also
gates sync on the popped `disable_auto_sync` flag, since `Character.__init__`
routes constructor kwargs into `attributes` rather than passing
`disable_auto_sync` through to `DefaultObject.__init__` as a top-level keyword.
`NpcAgent.__init__` re-asserts the restoration after `super().__init__()`
returns as a defensive redundancy.

## Ontology Migration

`GRAPH_SEED_ONTOLOGY_NODE_ROWS` gains a `character` row (parent
`default_object`) before the `npc_agent` row, and the `npc_agent` row's parent
changes from `world_thing` to `character`. The existing
`ensure_graph_seed_ontology` upsert (`ON CONFLICT DO UPDATE`) repairs existing
DB rows; no dedicated migration step is added.

## Runtime Invariants (Unchanged)

- Resolution by `Node.type_code == 'npc_agent'` and `node.id`.
- `resolve_npc_agent_by_handle`, `command_context_for_npc_agent`, agent memory
  DDL, and the F02 `graph_seed_node_types.yaml` `npc_agent` schema block are
  untouched.
- `entity_kind` for `type_code=npc_agent` stays `'agent'`.

## Consequences

- Positive: `NpcAgent` shares Character move/look extension points; `NPCCmdSet`
  becomes the agent-side extension slot.
- Risk: Character's RPG defaults and `CharacterCmdSet` are present in the base
  `__init__`; the `_init_cmdsets` override and no-op hooks must remain in place
  to keep them inert. Future changes to `Character.__init__` should be reviewed
  against this ADR.

## Implementation Checklist

- [`backend/app/models/things/agents.py`](../../../backend/app/models/things/agents.py) — only typeclass edit: `class NpcAgent(Character)`, `__init__` calls `super().__init__()` with `is_npc=True`/`is_ai=True`, pops `disable_auto_sync`, restores `_node_type`/`_node_type_code`, overrides `at_object_creation` / `_initialize_base_stats` / `_init_cmdsets` / `at_action_cost` / `at_action_result`.
- [`backend/db/schema_migrations.py`](../../../backend/db/schema_migrations.py) — add `character` row; change `npc_agent` parent to `character`.
- [`docs/ontology/GRAPH_SEED_NODE_TYPES_MATRIX.md`](../../ontology/GRAPH_SEED_NODE_TYPES_MATRIX.md) — add `character` target row; update `npc_agent` parent.
- [`docs/games/hicampus/SPEC/features/F02_ENTITY_TYPE_REGISTRY.md`](../../games/hicampus/SPEC/features/F02_ENTITY_TYPE_REGISTRY.md) — `npc_agent` parent column → `character`.
- [`backend/tests/models/test_things_typeclasses.py`](../../../backend/tests/models/test_things_typeclasses.py) — `isinstance(NpcAgent, Character)`, `is_npc=True`/`is_ai=True`, CmdSet branch, no-op hooks.
- [`backend/tests/db/test_graph_seed_ontology_matrix.py`](../../../backend/tests/db/test_graph_seed_ontology_matrix.py) — update expected parent map.
- **Not modified:** `Character` base class, `graph_seed_node_types.yaml` F02 schema, `entity_kind` mapping, frontend inspect classification.

## Acceptance Criteria

- [ ] `NpcAgent` Python MRO: `NpcAgent → Character → DefaultObject`.
- [ ] `NpcAgent("x").get_node_type() == 'npc_agent'`.
- [ ] `isinstance(NpcAgent(...), Character)` is true.
- [ ] `is_npc=True` and `is_ai=True` defaults; tags include `npc` and `ai`.
- [ ] RPG defaults inert: `_initialize_base_stats` / `at_action_cost` / `at_action_result` are no-ops; `CharacterCmdSet` is not mounted; RPG keys are not read or written by any runtime path.
- [ ] `sys_worker` instance has an empty CmdSet; `narrative_npc` (and unspecified) mounts `NPCCmdSet` only; neither mounts `CharacterCmdSet`.
- [ ] `node_types` has a `character` row and `npc_agent.parent_type_code = 'character'`.
- [ ] `test_things_typeclasses.test_npc_agent_smoke` and the ontology matrix unit test pass.
- [ ] F02 §6.1 five invariants still hold (see table below).

### F02 §6.1 Invariant Cross-Check

| F02 §6.1 Invariant | Status under this ADR |
|--------------------|-----------------------|
| 1. `type_code` unique, stays `npc_agent` | Held — ontology `type_code` unchanged |
| 2. Instance `attributes` only static config | Held — RPG defaults are inert constructor noise, not runtime config |
| 3. Write-graph default path is Command layer | Held — agent runtime unchanged |
| 4. Capability/tool enumeration via commands | Held — CmdSet is object-level extension only |
| 5. F11 principal for any graph write | Held — `command_context_for_npc_agent` unchanged |

## Review Checklist (PR)

- **F02 §6.1**: `type_code` still `npc_agent`; no `agent` type_code introduced.
- **F11**: Agent command context still uses service-account principal; no silent admin bypass.
- **Secrets**: No API keys or raw URLs in `nodes.attributes` or memory payloads.
- **RPG isolation**: `CharacterCmdSet` not mounted on `NpcAgent`; RPG hooks no-op.
- **Ontology**: `character` row precedes `npc_agent`; `parent_type_code` FK satisfied.
- **Typeclass smoke**: `NpcAgent(...).get_node_type() == 'npc_agent'`; `isinstance(_, Character)`.

## Related

- [F02 §3.1 / §6.1](../../models/SPEC/features/F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)
- [F09 L1 — Type & data layer](../../models/SPEC/features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)
- [ADR-F02-Agent-Runtime](ADR-F02-Agent-Runtime.md)
- [GRAPH_SEED_NODE_TYPES_MATRIX](../../ontology/GRAPH_SEED_NODE_TYPES_MATRIX.md)
