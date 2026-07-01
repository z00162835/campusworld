# Agent Runtime Phase 0 — Command Tool Contract Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the command layer so each command carries a structured tool contract (capability + interface schemas + safety metadata) reusable by the L4 Skill layer, Policy engine, and structured-turn validation — without creating a parallel `ToolProfile` registry.

**Architecture:** `CommandToolSemantics` (a `ClassVar` on `BaseCommand`) is the single source of truth for per-tool-type intrinsic contracts. The existing `system_command_ability` graph node remains a read-only mirror, synced by `ability_sync._sync_tool_semantics`. Runtime consumers read `CommandToolSemantics` only; the node mirror serves graph queries, audit, and the F14 lexicon. Authorization stays in `command_policies`.

**Tech Stack:** Python 3.11, SQLAlchemy 2.0, Pydantic 2, pytest, PostgreSQL (JSONB `nodes.attributes`), structlog. Conda env `campusworld`.

---

## Design Decisions (resolved from clarification round)

### P0-1 side_effect_level: hybrid (explicit preferred + derivation fallback)

`CommandToolSemantics` gains an optional `side_effect_level` field. When a command sets it explicitly, that wins. When omitted, derive from the existing `interaction_profile` + `invocation_guard.requires_confirmation`:

```
explicit side_effect_level            → use it
else interaction_profile == 'read'    → 'read'
else (mutate) + requires_confirmation → 'write_high'
else (mutate) + not requires_confirmation → 'write_low'
```

A small helper `resolve_side_effect_level(sem)` centralizes this so `ability_sync`, `execution_gate`, and the manifest all see one value.

### P0-2 Current role of `interaction_profile` (kept, not removed)

`interaction_profile: 'read' | 'mutate'` is the **callee intrinsic** consumed today by:

- `execution_gate._load_callee_semantics` → `min_privilege_profile(caller_profile_from_node, callee_profile_from_command)` — the gate that decides whether a mutate command may run under a read-only caller ceiling.
- `tool_observation_policy._default_policy_for_profile` — read commands get `full` observation text; mutate commands get `summary` to avoid leaking partial state.
- `aico_world_context.build_llm_tool_manifest` — buckets tools into `read` / `mutate` / `other` rows for the LLM manifest, and applies `manifest_interaction_filter='informational'` using `manifest_tier`.
- `ability_sync._sync_tool_semantics` — mirrors it onto the `system_command_ability` node for graph queries.
- `subcommand_profiles` — per-subcommand override (e.g. `task list` resolves to `read`, `task create` to `mutate`).

It is **not deprecated**. `side_effect_level` refines the mutate branch into `write_low`/`write_high` for risk-tiered policy (Phase 2), while `interaction_profile` stays as the coarse read/mutate axis the above consumers already depend on. Both coexist; `interaction_profile` remains the backward-compatible binary, `side_effect_level` adds the 4-tier refinement.

### P0-3 All commands declare schemas

`input_schema`/`output_schema`/`error_schema` are **optional with `None` defaults** so the extension is non-breaking. "All commands" is the end state, delivered in two waves inside this plan:

- Wave 1 (this plan): the infrastructure + 4 representative commands (`look`, `help`, `create`, `task`) annotated end-to-end, proving the pattern.
- Wave 2 (follow-up batch task at the end): the remaining commands, same pattern, checked off a list.

### P0-4 data_classification: 4-tier, inspired by Claude Code's permission philosophy

Claude Code's permission model is action-tiered with default-deny for the highest tier: rules evaluate `deny → ask → allow`, first match wins, and a `deny` cannot be overridden by a broader `allow` (e.g. `Read(./.env)` stays blocked even with `Read(./**)`). We transfer that philosophy to **data sensitivity** with a fixed 4-tier enum and the same deny-wins precedence for the top tier:

| Tier | Analogous Claude Code tier | Policy default (Phase 2) |
|------|---------------------------|--------------------------|
| `public` | broad `allow` (`Read(./**)`) | allow, no transform |
| `internal` | `default` mode (allow with audit) | allow + audit log |
| `confidential` | `ask` tier (prompt before revealing) | allow with transform (mask/desensitize) |
| `restricted` | `deny` tier (cannot be overridden) | deny by default; require approval |

Enum: `Literal['public', 'internal', 'confidential', 'restricted']`. Default `public` (least privilege violation is loud, not silent — Phase 2 policy treats `None` as `public` but logs a warning if a mutate command leaves it unset).

### P0-5 data_scope reuses NodeType type_code

`data_scope: Tuple[str, ...]` holds `type_code` values from the graph ontology (e.g. `('room',)`, `('building', 'building_floor')`, `('task',)`). Reusing `type_code` keeps one vocabulary, lets the Policy engine join "this tool touches `task` nodes" with graph reasoning, and avoids inventing a parallel scope taxonomy. Empty tuple = no specific scope (generic).

### P0-6 error_schema: project-unified codes + i18n

A single platform error code enum shared by all commands, plus a localized message template per code. `error_schema` on `CommandToolSemantics` declares which codes a command may emit (subset of the platform enum); the actual i18n message lives in the existing `i18n/locales/` resource system (already used for descriptions/usages).

Platform error codes: `INVALID_PARAM | NOT_FOUND | TIMEOUT | SERVICE_ERROR | RATE_LIMIT | PERMISSION_DENIED | POLICY_DENIED | CONFLICT | NOT_AVAILABLE`. Each code maps to a localized message key `command.error.<code>` resolved via the existing `i18n/command_resource` pipeline. `error_schema` is a JSON Schema object with `enum` drawn from this list; a command declares the subset it may raise.

### P0-7 Where to declare the new fields — option analysis

**Option A — separate `tool_input_schema` / `tool_output_schema` ClassVars on `BaseCommand`, merged into `CommandToolSemantics` at resolution time.**
- Pro: schemas read declaratively near the command class body; mirrors how `tool_semantics` itself is a ClassVar.
- Con: two sources (the ClassVar + `tool_semantics`) must be merged in `resolve_command_tool_semantics`; runtime must know to read both. Directly contradicts P0-8 ("runtime reads only `CommandToolSemantics`").

**Option B — fold all new fields into `CommandToolSemantics`; declare them inside the `tool_semantics = CommandToolSemantics(...)` ClassVar assignment.** (Recommended)
- Pro: single source of truth; runtime reads one object (satisfies P0-8); no merge logic; `dataclasses.replace` (already used for subcommand resolution) carries the new fields automatically.
- Con: the `CommandToolSemantics` dataclass grows (8 new optional fields). Mitigated: all optional with `None`/`False` defaults; existing constructors stay valid.

**Option C — separate `ToolCapability` ClassVar dataclass on `BaseCommand`, distinct from `tool_semantics`.**
- Pro: clean conceptual split (capability vs interaction semantics).
- Con: a third object to resolve and join; the reference doc's Tool Profile is one unified contract, not three; contradicts SSOT goal.

**Decision: Option B.** All new fields live on `CommandToolSemantics`. Commands that want structured schemas set them in their existing `tool_semantics = CommandToolSemantics(...)` assignment (or via a helper like `INFORMATIONAL_MANIFEST` extended with schema fields).

### P0-8 Runtime reads only CommandToolSemantics

`build_llm_tool_manifest` and all hot-path consumers resolve the extended fields via `resolve_command_tool_semantics(name, args)` only. The `system_command_ability` node mirror is **not** read on the tick hot path — it exists for graph queries (NPC ability discovery, `find`/`describe` over abilities), the F14 lexicon export, and audit. This removes a DB read from the tick and keeps one resolution function. (Today `build_llm_tool_manifest` calls `_command_semantics_from_node` for `interaction_profile`/`manifest_tier`/`routing_hint`; Task 8 switches those reads to `resolve_command_tool_semantics` and drops the node read.)

### P0-9 schema_envelope migration: is it necessary?

**For `nodes.attributes` (instance JSONB): NOT necessary.** PostgreSQL JSONB is schemaless; adding new keys (`side_effect_level`, `idempotent`, etc.) to a node's `attributes` requires no `ALTER TABLE`. `ability_sync.ensure_command_ability_nodes` will populate them on the next sync run (already scheduled non-blocking at startup via `_schedule_command_ability_sync`).

**For `node_types.schema_definition` (the attribute registry for the type): handled by an existing idempotent migration, no new migration function required — but the envelope function must be updated.** `ensure_builtin_node_type_schema_envelopes` already refreshes `node_types.schema_definition` for `system_command_ability` from `system_command_ability_node_type_schema_definition()` on every `init_database migrate`, and it is idempotent (skips rows already in envelope shape — but since we change the envelope content, we must ensure it re-applies; the current guard `is_json_schema_object_envelope` only checks *shape*, so an updated envelope with the same shape **won't** re-apply automatically). **Therefore a small migration tweak IS needed**: Task 7 weakens the skip-guard to re-apply when the computed envelope differs from the stored one, or adds a one-shot `ensure_command_ability_envelope_refresh` step. Task 7 implements the latter (explicit, traceable).

Net: no data migration, no `ALTER TABLE`; one explicit envelope-refresh step registered in `migrate_report.run_schema_migrations` ordering.

---

## File Structure

**Modify:**
- `backend/app/commands/command_tool_semantics.py` — add 8 fields to `CommandToolSemantics`; add `resolve_side_effect_level`; add `ToolDataClassification` Literal; add `PLATFORM_ERROR_CODES`; extend `to_dict`.
- `backend/app/commands/base.py` — no new ClassVar (Option B); only docstring note that schemas live on `tool_semantics`.
- `backend/app/commands/ability_sync.py` — extend `_sync_tool_semantics` to mirror new fields; populate `input_schema`/`output_schema` slots.
- `backend/db/ontology/schema_envelope.py` — extend `_SYSTEM_COMMAND_ABILITY_FLAT` with 6 new keys.
- `backend/db/schema_migrations.py` — add `ensure_command_ability_envelope_refresh` + register in migration order.
- `backend/app/game_engine/agent_runtime/aico_world_context.py` — `build_llm_tool_manifest` reads from `resolve_command_tool_semantics`, drops node read; emits structured `input_schema` when present.
- Representative commands (Wave 1): `look_command.py`, `system_commands.py` (help/who/time), `create_command.py`, `task_command.py`.

**Create:**
- `backend/tests/commands/test_command_tool_semantics_extended.py` — new-field + derivation tests.
- `backend/tests/commands/test_ability_sync_semantics_mirror.py` — mirror tests.
- `backend/tests/game_engine/test_tool_manifest_structured_schema.py` — manifest structured-schema test.

**Docs:**
- `docs/models/SPEC/features/F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md` — annotate "CommandToolSemantics is the Tool Profile contract".

---

## Task 1: Extend `CommandToolSemantics` with new fields

**Files:**
- Modify: `backend/app/commands/command_tool_semantics.py`
- Test: `backend/tests/commands/test_command_tool_semantics_extended.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/commands/test_command_tool_semantics_extended.py`:

```python
import pytest
from app.commands.command_tool_semantics import (
    CommandToolSemantics,
    resolve_command_tool_semantics,
    resolve_side_effect_level,
    PLATFORM_ERROR_CODES,
)


@pytest.mark.unit
def test_new_fields_have_defaults():
    sem = CommandToolSemantics(interaction_profile='read')
    assert sem.side_effect_level is None
    assert sem.idempotent is False
    assert sem.deterministic is False
    assert sem.input_schema is None
    assert sem.output_schema is None
    assert sem.error_schema is None
    assert sem.data_classification is None
    assert sem.data_scope == ()


@pytest.mark.unit
def test_to_dict_includes_new_fields():
    sem = CommandToolSemantics(
        interaction_profile='read',
        side_effect_level='read',
        idempotent=True,
        deterministic=True,
        input_schema={'type': 'object'},
        data_classification='public',
        data_scope=('room',),
    )
    d = sem.to_dict()
    assert d['side_effect_level'] == 'read'
    assert d['idempotent'] is True
    assert d['deterministic'] is True
    assert d['input_schema'] == {'type': 'object'}
    assert d['data_classification'] == 'public'
    assert d['data_scope'] == ['room']


@pytest.mark.unit
def test_platform_error_codes_is_frozen_set():
    assert 'INVALID_PARAM' in PLATFORM_ERROR_CODES
    assert 'POLICY_DENIED' in PLATFORM_ERROR_CODES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && conda run -n campusworld pytest tests/commands/test_command_tool_semantics_extended.py -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_side_effect_level'` / `AttributeError`.

- [ ] **Step 3: Implement the extension**

In `backend/app/commands/command_tool_semantics.py`, add the Literal + constants near the top (after existing `InteractionProfile`/`ManifestTier`):

```python
ToolSideEffectLevel = Literal['none', 'read', 'write_low', 'write_high']
ToolDataClassification = Literal['public', 'internal', 'confidential', 'restricted']

PLATFORM_ERROR_CODES: frozenset[str] = frozenset({
    'INVALID_PARAM', 'NOT_FOUND', 'TIMEOUT', 'SERVICE_ERROR',
    'RATE_LIMIT', 'PERMISSION_DENIED', 'POLICY_DENIED',
    'CONFLICT', 'NOT_AVAILABLE',
})
```

Extend the `CommandToolSemantics` dataclass (add after `invocation_guard`):

```python
    side_effect_level: Optional[ToolSideEffectLevel] = None
    idempotent: bool = False
    deterministic: bool = False
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    error_schema: Optional[Dict[str, Any]] = None
    data_classification: Optional[ToolDataClassification] = None
    data_scope: Tuple[str, ...] = ()
```

(Ensure `Optional`, `Tuple` are imported — `Optional` already is; add `Tuple` to the typing import if missing.)

Extend `to_dict` to append (before the closing `return` dict, add the keys):

```python
        'side_effect_level': self.side_effect_level,
        'idempotent': self.idempotent,
        'deterministic': self.deterministic,
        'input_schema': self.input_schema,
        'output_schema': self.output_schema,
        'error_schema': self.error_schema,
        'data_classification': self.data_classification,
        'data_scope': list(self.data_scope) if self.data_scope else None,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && conda run -n campusworld pytest tests/commands/test_command_tool_semantics_extended.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Verify no regression in existing semantics tests**

Run: `cd backend && conda run -n campusworld pytest tests/commands/test_command_tool_semantics.py tests/game_engine/test_tool_manifest_descriptions.py -v`
Expected: PASS (all existing tests; new optional fields default to None/False).

- [ ] **Step 6: Commit**

```bash
git add backend/app/commands/command_tool_semantics.py backend/tests/commands/test_command_tool_semantics_extended.py
git commit -m "feat: extend CommandToolSemantics with tool contract fields (side_effect_level, capability, schemas, data_classification)"
```

---

## Task 2: `side_effect_level` hybrid derivation

**Files:**
- Modify: `backend/app/commands/command_tool_semantics.py`
- Test: `backend/tests/commands/test_command_tool_semantics_extended.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/commands/test_command_tool_semantics_extended.py`:

```python
@pytest.mark.unit
def test_resolve_side_effect_level_explicit_wins():
    sem = CommandToolSemantics(interaction_profile='mutate', side_effect_level='write_low')
    assert resolve_side_effect_level(sem) == 'write_low'


@pytest.mark.unit
def test_resolve_side_effect_level_derive_read():
    sem = CommandToolSemantics(interaction_profile='read')
    assert resolve_side_effect_level(sem) == 'read'


@pytest.mark.unit
def test_resolve_side_effect_level_derive_write_high():
    sem = CommandToolSemantics(interaction_profile='mutate')  # default guard => requires_confirmation True
    assert resolve_side_effect_level(sem) == 'write_high'


@pytest.mark.unit
def test_resolve_side_effect_level_derive_write_low():
    sem = CommandToolSemantics(
        interaction_profile='mutate',
        invocation_guard={'requires_confirmation': False, 'allowed_intents': ['execute'], 'side_effect_scope': 'state_change'},
    )
    assert resolve_side_effect_level(sem) == 'write_low'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && conda run -n campusworld pytest tests/commands/test_command_tool_semantics_extended.py -k resolve_side_effect_level -v`
Expected: FAIL (`resolve_side_effect_level` not defined).

- [ ] **Step 3: Implement the helper**

In `backend/app/commands/command_tool_semantics.py`, add after `resolve_command_tool_semantics`:

```python
def resolve_side_effect_level(sem: CommandToolSemantics) -> ToolSideEffectLevel:
    """Hybrid: explicit declaration wins; else derive from interaction_profile + invocation_guard."""
    if sem.side_effect_level is not None:
        return sem.side_effect_level
    if sem.interaction_profile == 'read':
        return 'read'
    # mutate branch
    guard = sem.invocation_guard or {}
    if bool(guard.get('requires_confirmation', True)):
        return 'write_high'
    return 'write_low'
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && conda run -n campusworld pytest tests/commands/test_command_tool_semantics_extended.py -k resolve_side_effect_level -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/commands/command_tool_semantics.py backend/tests/commands/test_command_tool_semantics_extended.py
git commit -m "feat: add resolve_side_effect_level hybrid derivation (explicit preferred + fallback)"
```

---

## Task 3: `data_classification` 4-tier + `data_scope` NodeType reuse validation

**Files:**
- Modify: `backend/app/commands/command_tool_semantics.py`
- Test: `backend/tests/commands/test_command_tool_semantics_extended.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
@pytest.mark.unit
def test_data_classification_only_accepts_known_tiers():
    # dataclass is not frozen-enforcing on Literal at runtime, but to_dict must round-trip
    sem = CommandToolSemantics(interaction_profile='read', data_classification='confidential', data_scope=('task', 'room'))
    d = sem.to_dict()
    assert d['data_classification'] == 'confidential'
    assert d['data_scope'] == ['task', 'room']


@pytest.mark.unit
def test_validate_data_scope_against_known_type_codes():
    from app.commands.command_tool_semantics import validate_data_scope
    # known type_codes from graph seed
    assert validate_data_scope(('room', 'building')) == []
    # unknown type_code returned in error list
    bad = validate_data_scope(('nonexistent_type',))
    assert 'nonexistent_type' in bad
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && conda run -n campusworld pytest tests/commands/test_command_tool_semantics_extended.py -k data_classification -v`
Expected: FAIL (`validate_data_scope` not defined).

- [ ] **Step 3: Implement `validate_data_scope`**

In `backend/app/commands/command_tool_semantics.py`, add:

```python
def validate_data_scope(scope: Tuple[str, ...]) -> List[str]:
    """Return any type_codes in `scope` that are not registered in the graph ontology."""
    if not scope:
        return []
    from app.models.graph import NodeType
    from app.core.database import db_session_context
    try:
        with db_session_context() as session:
            known = {row.type_code for row in session.query(NodeType.type_code).all()}
    except Exception:
        return []  # do not block on DB unavailability; callers audit separately
    return [s for s in scope if s not in known]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && conda run -n campusworld pytest tests/commands/test_command_tool_semantics_extended.py -k data_classification -v`
Expected: PASS (2 tests). Note: `validate_data_scope` test needs DB; mark it `@pytest.mark.integration` instead of `unit` if no DB in unit run. Adjust the decorator on `test_validate_data_scope_against_known_type_codes` to `@pytest.mark.integration` and move it to an integration test file if needed. For the unit suite, keep only the round-trip test.

- [ ] **Step 5: Commit**

```bash
git add backend/app/commands/command_tool_semantics.py backend/tests/commands/test_command_tool_semantics_extended.py
git commit -m "feat: add data_classification 4-tier + data_scope NodeType validation"
```

---

## Task 4: `error_schema` platform-unified codes + i18n key convention

**Files:**
- Modify: `backend/app/commands/command_tool_semantics.py`
- Test: `backend/tests/commands/test_command_tool_semantics_extended.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
@pytest.mark.unit
def test_error_schema_must_use_platform_codes():
    from app.commands.command_tool_semantics import build_error_schema, PLATFORM_ERROR_CODES
    schema = build_error_schema(codes=('NOT_FOUND', 'INVALID_PARAM'))
    assert set(schema['properties']['code']['enum']).issubset(PLATFORM_ERROR_CODES)
    assert schema['properties']['code']['enum'] == ['NOT_FOUND', 'INVALID_PARAM']
    assert schema['properties']['message']['type'] == 'string'


@pytest.mark.unit
def test_error_schema_rejects_unknown_code():
    from app.commands.command_tool_semantics import build_error_schema
    with pytest.raises(ValueError):
        build_error_schema(codes=('BOGUS_CODE',))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && conda run -n campusworld pytest tests/commands/test_command_tool_semantics_extended.py -k error_schema -v`
Expected: FAIL (`build_error_schema` not defined).

- [ ] **Step 3: Implement `build_error_schema`**

In `backend/app/commands/command_tool_semantics.py`, add:

```python
def build_error_schema(codes: Tuple[str, ...]) -> Dict[str, Any]:
    """Build a JSON Schema for command errors using platform-unified codes.

    The localized message for each code is resolved at presentation time via
    the i18n key `command.error.<code>` (existing i18n/command_resource pipeline).
    """
    unknown = [c for c in codes if c not in PLATFORM_ERROR_CODES]
    if unknown:
        raise ValueError(f'unknown platform error codes: {unknown}')
    return {
        'type': 'object',
        'required': ['code', 'message'],
        'properties': {
            'code': {'type': 'string', 'enum': list(codes)},
            'message': {'type': 'string'},
            'retryable': {'type': 'boolean'},
        },
    }
```

- [ ] **Step 4: Add i18n key stubs**

Add the platform error message keys to the existing i18n locale resource file used by `i18n/command_resource`. Locate the zh-CN locale file (e.g. `backend/app/commands/i18n/locales/zh-CN/command_resource.yaml` or the merged resource); add under a `command.error` namespace:

```yaml
command:
  error:
    INVALID_PARAM: "参数无效"
    NOT_FOUND: "未找到"
    TIMEOUT: "请求超时"
    SERVICE_ERROR: "服务暂时不可用"
    RATE_LIMIT: "请求过于频繁"
    PERMISSION_DENIED: "权限不足"
    POLICY_DENIED: "策略拒绝"
    CONFLICT: "状态冲突"
    NOT_AVAILABLE: "当前不可用"
```

Add the en-US equivalents in the en-US locale file:

```yaml
command:
  error:
    INVALID_PARAM: "Invalid parameter"
    NOT_FOUND: "Not found"
    TIMEOUT: "Request timed out"
    SERVICE_ERROR: "Service temporarily unavailable"
    RATE_LIMIT: "Rate limit exceeded"
    PERMISSION_DENIED: "Permission denied"
    POLICY_DENIED: "Denied by policy"
    CONFLICT: "State conflict"
    NOT_AVAILABLE: "Currently unavailable"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && conda run -n campusworld pytest tests/commands/test_command_tool_semantics_extended.py -k error_schema -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/commands/command_tool_semantics.py backend/app/commands/i18n/ backend/tests/commands/test_command_tool_semantics_extended.py
git commit -m "feat: add platform-unified error_schema builder + i18n error message keys"
```

---

## Task 5: Extend `ability_sync._sync_tool_semantics` to mirror new fields

**Files:**
- Modify: `backend/app/commands/ability_sync.py`
- Test: `backend/tests/commands/test_ability_sync_semantics_mirror.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/commands/test_ability_sync_semantics_mirror.py`:

```python
import pytest
from app.commands.command_tool_semantics import CommandToolSemantics, resolve_side_effect_level
from app.commands.ability_sync import _sync_tool_semantics


@pytest.mark.unit
def test_sync_tool_semantics_mirrors_new_fields(monkeypatch):
    fake_sem = CommandToolSemantics(
        interaction_profile='mutate',
        side_effect_level='write_high',
        idempotent=False,
        deterministic=False,
        input_schema={'type': 'object', 'properties': {'name': {'type': 'string'}}},
        output_schema={'type': 'object'},
        error_schema={'type': 'object'},
        data_classification='confidential',
        data_scope=('task',),
    )
    monkeypatch.setattr('app.commands.ability_sync.resolve_command_tool_semantics', lambda name, args=None: fake_sem)
    attrs = {}
    _sync_tool_semantics('task', attrs)
    assert attrs['side_effect_level'] == 'write_high'
    assert attrs['idempotent'] is False
    assert attrs['deterministic'] is False
    assert attrs['input_schema'] == {'type': 'object', 'properties': {'name': {'type': 'string'}}}
    assert attrs['output_schema'] == {'type': 'object'}
    assert attrs['error_schema'] == {'type': 'object'}
    assert attrs['data_classification'] == 'confidential'
    assert attrs['data_scope'] == ['task']


@pytest.mark.unit
def test_sync_tool_semantics_derives_side_effect_level_when_unset(monkeypatch):
    fake_sem = CommandToolSemantics(interaction_profile='read')  # side_effect_level None
    monkeypatch.setattr('app.commands.ability_sync.resolve_command_tool_semantics', lambda name, args=None: fake_sem)
    attrs = {}
    _sync_tool_semantics('look', attrs)
    assert attrs['side_effect_level'] == 'read'  # derived
    assert attrs['input_schema'] is None  # mirrored as-is


@pytest.mark.unit
def test_sync_tool_semantics_omits_none_schemas(monkeypatch):
    fake_sem = CommandToolSemantics(interaction_profile='read')
    monkeypatch.setattr('app.commands.ability_sync.resolve_command_tool_semantics', lambda name, args=None: fake_sem)
    attrs = {}
    _sync_tool_semantics('help', attrs)
    # None schemas should not create keys (keep node attrs clean)
    assert 'input_schema' not in attrs or attrs['input_schema'] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && conda run -n campusworld pytest tests/commands/test_ability_sync_semantics_mirror.py -v`
Expected: FAIL (new fields not mirrored).

- [ ] **Step 3: Extend `_sync_tool_semantics`**

In `backend/app/commands/ability_sync.py`, update `_sync_tool_semantics` (add after the existing `routing_hint_i18n` block, before the `agent_observation_policy` block):

```python
    # --- extended tool contract fields (Phase 0) ---
    attrs['side_effect_level'] = resolve_side_effect_level(sem)
    attrs['idempotent'] = bool(sem.idempotent)
    attrs['deterministic'] = bool(sem.deterministic)
    if sem.input_schema is not None:
        attrs['input_schema'] = dict(sem.input_schema)
    else:
        attrs.pop('input_schema', None)
    if sem.output_schema is not None:
        attrs['output_schema'] = dict(sem.output_schema)
    else:
        attrs.pop('output_schema', None)
    if sem.error_schema is not None:
        attrs['error_schema'] = dict(sem.error_schema)
    else:
        attrs.pop('error_schema', None)
    if sem.data_classification is not None:
        attrs['data_classification'] = sem.data_classification
    else:
        attrs.pop('data_classification', None)
    if sem.data_scope:
        attrs['data_scope'] = list(sem.data_scope)
    else:
        attrs.pop('data_scope', None)
```

Add the import at the top of `ability_sync.py`:

```python
from app.commands.command_tool_semantics import resolve_command_tool_semantics, resolve_side_effect_level
```

(update the existing import line to add `resolve_side_effect_level`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && conda run -n campusworld pytest tests/commands/test_ability_sync_semantics_mirror.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/commands/ability_sync.py backend/tests/commands/test_ability_sync_semantics_mirror.py
git commit -m "feat: mirror extended tool contract fields into system_command_ability node"
```

---

## Task 6: Extend `schema_envelope._SYSTEM_COMMAND_ABILITY_FLAT`

**Files:**
- Modify: `backend/db/ontology/schema_envelope.py`
- Test: `backend/tests/db/test_schema_envelope.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/db/test_schema_envelope.py`:

```python
def test_system_command_ability_envelope_has_new_fields():
    from db.ontology.schema_envelope import system_command_ability_node_type_schema_definition
    sd = system_command_ability_node_type_schema_definition()
    props = sd['properties']
    for field in ('side_effect_level', 'idempotent', 'deterministic', 'error_schema', 'data_classification', 'data_scope'):
        assert field in props, f'missing {field}'
    assert props['idempotent']['type'] == 'boolean'
    assert props['data_scope']['type'] == 'array'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && conda run -n campusworld pytest tests/db/test_schema_envelope.py -k system_command_ability_envelope -v`
Expected: FAIL (new fields not in envelope).

- [ ] **Step 3: Extend the flat dict**

In `backend/db/ontology/schema_envelope.py`, update `_SYSTEM_COMMAND_ABILITY_FLAT`:

```python
_SYSTEM_COMMAND_ABILITY_FLAT: Dict[str, str] = {
    "command_name": "string",
    "aliases": "json",
    "command_type": "string",
    "help_category": "string",
    "stability": "string",
    "input_schema": "json",
    "output_schema": "json",
    "error_schema": "json",
    "updated_at": "string",
    "interaction_profile": "string",
    "side_effect_level": "string",
    "idempotent": "boolean",
    "deterministic": "boolean",
    "data_classification": "string",
    "data_scope": "json",
    "semantic_pending": "json",
    "manifest_tier": "string",
    "invocation_guard": "json",
    "routing_hint": "string",
    "routing_hint_i18n": "json",
    "agent_observation_policy": "json",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && conda run -n campusworld pytest tests/db/test_schema_envelope.py -k system_command_ability_envelope -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/db/ontology/schema_envelope.py backend/tests/db/test_schema_envelope.py
git commit -m "feat: extend system_command_ability schema envelope with tool contract fields"
```

---

## Task 7: Envelope refresh migration (P0-9)

**Files:**
- Modify: `backend/db/schema_migrations.py`
- Test: `backend/tests/db/test_schema_migrations_envelope_refresh.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/db/test_schema_migrations_envelope_refresh.py`:

```python
import json
import pytest
from sqlalchemy import text


@pytest.mark.postgres_integration
def test_ensure_command_ability_envelope_refresh_updates_stale_envelope(engine):
    from db.schema_migrations import ensure_command_ability_envelope_refresh
    from db.ontology.schema_envelope import system_command_ability_node_type_schema_definition
    # Force a stale envelope (missing side_effect_level)
    conn = engine.connect().execution_options(isolation_level='AUTOCOMMIT')
    try:
        stale = {'type': 'object', 'properties': {'command_name': {'type': 'string'}}}
        conn.execute(text("UPDATE node_types SET schema_definition = CAST(:js AS jsonb) WHERE type_code = 'system_command_ability'"), {'js': json.dumps(stale)})
    finally:
        conn.close()
    ensure_command_ability_envelope_refresh(engine)
    conn = engine.connect()
    try:
        row = conn.execute(text("SELECT schema_definition FROM node_types WHERE type_code = 'system_command_ability'")).fetchone()
        sd = row[0]
        assert 'side_effect_level' in sd['properties']
    finally:
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && conda run -n campusworld pytest tests/db/test_schema_migrations_envelope_refresh.py -v -m postgres_integration`
Expected: FAIL (`ensure_command_ability_envelope_refresh` not defined; requires PostgreSQL).

- [ ] **Step 3: Implement the refresh function**

In `backend/db/schema_migrations.py`, add (after `ensure_builtin_node_type_schema_envelopes`):

```python
def ensure_command_ability_envelope_refresh(engine) -> None:
    """Phase 0: force-refresh system_command_ability schema_definition so the
    extended tool-contract fields (side_effect_level, idempotent, deterministic,
    error_schema, data_classification, data_scope) appear even when the stored
    envelope already has the JSON Schema object *shape* (which the idempotent
    guard in ensure_builtin_node_type_schema_envelopes would otherwise skip).

    Idempotent: writes the canonical envelope each run; cheap single-row UPDATE.
    """
    import json
    from db.ontology.schema_envelope import system_command_ability_node_type_schema_definition
    sd = system_command_ability_node_type_schema_definition()
    conn = engine.connect().execution_options(isolation_level='AUTOCOMMIT')
    try:
        conn.execute(
            text("UPDATE node_types SET schema_definition = CAST(:js AS jsonb) WHERE type_code = 'system_command_ability'"),
            {"js": json.dumps(sd, ensure_ascii=False)},
        )
    finally:
        conn.close()
```

Register it in the migration ordering. Find the `run_schema_migrations` function in `backend/db/migrate_report.py` (or wherever the ordered `ensure_*` list lives) and insert `ensure_command_ability_envelope_refresh` immediately after `ensure_builtin_node_type_schema_envelopes`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && conda run -n campusworld pytest tests/db/test_schema_migrations_envelope_refresh.py -v -m postgres_integration`
Expected: PASS (requires PostgreSQL running).

- [ ] **Step 5: Verify config validation still passes**

Run: `cd backend && python scripts/validate_config.py`
Expected: success.

- [ ] **Step 6: Commit**

```bash
git add backend/db/schema_migrations.py backend/db/migrate_report.py backend/tests/db/test_schema_migrations_envelope_refresh.py
git commit -m "feat: add ensure_command_ability_envelope_refresh migration for extended tool contract fields"
```

---

## Task 8: `build_llm_tool_manifest` reads `CommandToolSemantics` only (P0-8)

**Files:**
- Modify: `backend/app/game_engine/agent_runtime/aico_world_context.py`
- Test: `backend/tests/game_engine/test_tool_manifest_structured_schema.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/game_engine/test_tool_manifest_structured_schema.py`:

```python
import pytest
from app.commands.command_tool_semantics import CommandToolSemantics
from app.commands.base import BaseCommand, CommandContext, CommandResult, CommandType


class _FakeCmd(BaseCommand):
    tool_semantics = CommandToolSemantics(
        interaction_profile='read',
        input_schema={'type': 'object', 'properties': {'query': {'type': 'string'}}, 'required': ['query']},
    )

    def __init__(self):
        super().__init__(name='fakesearch', description='fake search', command_type=CommandType.SYSTEM)

    def execute(self, context, args):
        return CommandResult.success_result('ok')


@pytest.mark.unit
def test_manifest_emits_structured_input_schema_when_present(monkeypatch):
    from app.commands.registry import command_registry
    from app.game_engine.agent_runtime.aico_world_context import build_llm_tool_manifest
    from app.game_engine.agent_runtime.resolved_tool_surface import ResolvedToolSurface
    # register fake command
    command_registry.register_command(_FakeCmd())
    try:
        surface = ResolvedToolSurface(allowed_command_names=frozenset({'fakesearch'}), tool_command_context=None)
        _prose, schemas = build_llm_tool_manifest(surface, command_registry, session=None)
        fake = next(s for s in schemas if s.name == 'fakesearch')
        assert fake.input_schema.get('properties', {}).get('query', {}).get('type') == 'string'
    finally:
        command_registry.unregister_command('fakesearch')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && conda run -n campusworld pytest tests/game_engine/test_tool_manifest_structured_schema.py -v`
Expected: FAIL (manifest currently uses `tool_schemas_from_surface` which builds input_schema from arg names, not from `CommandToolSemantics.input_schema`).

- [ ] **Step 3: Update `build_llm_tool_manifest` to prefer `CommandToolSemantics.input_schema`**

In `backend/app/game_engine/agent_runtime/aico_world_context.py`, inside the `for schema in schemas:` loop, after computing `desc` and before `patched.append(...)`, replace the semantics source. Currently the function calls `_command_semantics_from_node(session, schema.name)` for `interaction_profile`/`manifest_tier`/`routing_hint`. Change those reads to come from `resolve_command_tool_semantics` (no DB), and override the schema's `input_schema` when the command declares one:

Add import at top:

```python
from app.commands.command_tool_semantics import resolve_command_tool_semantics
```

In the loop, replace:

```python
        sem = _command_semantics_from_node(session, schema.name)
```

with:

```python
        sem_obj = resolve_command_tool_semantics(schema.name)
        sem = {
            'interaction_profile': sem_obj.interaction_profile,
            'manifest_tier': sem_obj.manifest_tier,
            'routing_hint': sem_obj.routing_hint,
            'routing_hint_i18n': dict(sem_obj.routing_hint_i18n) if sem_obj.routing_hint_i18n else None,
        }
        effective_input_schema = dict(sem_obj.input_schema) if sem_obj.input_schema is not None else dict(schema.input_schema)
```

Then change the `patched.append(...)` line to use `effective_input_schema`:

```python
        patched.append(ToolSchema(name=schema.name, description=schema_desc, input_schema=effective_input_schema))
```

Remove the now-unused `_command_semantics_from_node` call for these fields (keep `_llm_hint_from_command_node` as-is — the llm_hint is a node-side i18n convenience that may stay; but per P0-8, prefer registry desc first; leave the hint fallback for now to avoid scope creep — it does not read the new contract fields).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && conda run -n campusworld pytest tests/game_engine/test_tool_manifest_structured_schema.py -v`
Expected: PASS.

- [ ] **Step 5: Verify existing manifest tests still pass**

Run: `cd backend && conda run -n campusworld pytest tests/game_engine/test_tool_manifest_descriptions.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/game_engine/agent_runtime/aico_world_context.py backend/tests/game_engine/test_tool_manifest_structured_schema.py
git commit -m "feat: build_llm_tool_manifest reads structured input_schema from CommandToolSemantics (no DB read)"
```

---

## Task 9: Annotate Wave-1 commands with full contracts (pattern proof)

This task annotates 4 representative commands end-to-end to prove the pattern. Wave-2 (remaining commands) follows identically.

**Files:**
- Modify: `backend/app/commands/game/look_command.py`
- Modify: `backend/app/commands/system_commands.py` (HelpCommand)
- Modify: `backend/app/commands/builder/create_command.py`
- Modify: `backend/app/commands/game/task/task_command.py`
- Test: `backend/tests/commands/test_command_tool_semantics_extended.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/commands/test_command_tool_semantics_extended.py`:

```python
@pytest.mark.unit
def test_look_has_structured_contract():
    sem = resolve_command_tool_semantics('look')
    assert sem.side_effect_level == 'none'
    assert sem.idempotent is True
    assert sem.deterministic is True
    assert sem.data_classification == 'public'
    assert sem.input_schema is not None
    assert 'target' in sem.input_schema.get('properties', {})


@pytest.mark.unit
def test_help_has_read_contract():
    sem = resolve_command_tool_semantics('help')
    assert sem.side_effect_level == 'none'
    assert sem.data_classification == 'public'
    assert sem.input_schema is not None


@pytest.mark.unit
def test_create_has_write_high_contract():
    sem = resolve_command_tool_semantics('create')
    assert sem.side_effect_level == 'write_high'
    assert sem.data_classification == 'internal'
    assert sem.error_schema is not None
    assert 'POLICY_DENIED' in sem.error_schema['properties']['code']['enum']


@pytest.mark.unit
def test_task_has_subcommand_aware_side_effect():
    assert resolve_command_tool_semantics('task', args=['list']).side_effect_level == 'read'
    assert resolve_command_tool_semantics('task', args=['create']).side_effect_level == 'write_high'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && conda run -n campusworld pytest tests/commands/test_command_tool_semantics_extended.py -k "look_has or help_has or create_has or task_has" -v`
Expected: FAIL (commands don't declare the new fields yet).

- [ ] **Step 3: Annotate `look`**

In `backend/app/commands/game/look_command.py`, replace the `tool_semantics = INFORMATIONAL_MANIFEST` line with an extended semantics. Add import:

```python
from app.commands.command_tool_semantics import CommandToolSemantics
```

Replace:

```python
    tool_semantics = INFORMATIONAL_MANIFEST
```

with:

```python
    tool_semantics = CommandToolSemantics(
        interaction_profile='read',
        manifest_tier='informational',
        side_effect_level='none',
        idempotent=True,
        deterministic=True,
        data_classification='public',
        data_scope=('room', 'world_object'),
        input_schema={
            'type': 'object',
            'properties': {
                'target': {'type': 'string', 'description': 'optional target name or disambiguation index'},
            },
        },
        output_schema={
            'type': 'object',
            'properties': {
                'room_name': {'type': 'string'},
                'description': {'type': 'string'},
                'exits': {'type': 'array', 'items': {'type': 'string'}},
                'objects': {'type': 'array', 'items': {'type': 'string'}},
            },
        },
        error_schema={
            'type': 'object',
            'required': ['code', 'message'],
            'properties': {
                'code': {'type': 'string', 'enum': ['NOT_FOUND', 'NOT_AVAILABLE']},
                'message': {'type': 'string'},
            },
        },
    )
```

- [ ] **Step 4: Annotate `help`**

In `backend/app/commands/system_commands.py`, find `HelpCommand` (the class with `tool_semantics = INFORMATIONAL_MANIFEST` that handles `help`). Replace its `tool_semantics` with:

```python
    tool_semantics = CommandToolSemantics(
        interaction_profile='read',
        manifest_tier='informational',
        side_effect_level='none',
        idempotent=True,
        deterministic=True,
        data_classification='public',
        input_schema={
            'type': 'object',
            'properties': {
                'topic': {'type': 'string', 'description': 'command name to get help for'},
            },
        },
        output_schema={
            'type': 'object',
            'properties': {
                'help_text': {'type': 'string'},
            },
        },
    )
```

(Add the `CommandToolSemantics` import at the top of `system_commands.py` if not present. Leave the other `INFORMATIONAL_MANIFEST` usages in this file for Wave-2.)

- [ ] **Step 5: Annotate `create`**

In `backend/app/commands/builder/create_command.py`, replace `tool_semantics = CREATE_MUTATE_SEMANTICS` with an extended version. Add import:

```python
from app.commands.command_tool_semantics import CommandToolSemantics, build_error_schema
```

Replace:

```python
    tool_semantics = CREATE_MUTATE_SEMANTICS
```

with:

```python
    tool_semantics = CommandToolSemantics(
        interaction_profile='mutate',
        routing_hint='Example/syntax requests should use `help create`; call only with explicit execution intent and confirmation.',
        routing_hint_i18n={
            'zh-CN': 'create 会改变系统状态。示例/语法问题应使用 help create；仅在明确执行且确认后调用。',
            'en-US': 'create mutates system state. Example/syntax requests should use `help create`; call only with explicit execution intent and confirmation.',
        },
        side_effect_level='write_high',
        idempotent=False,
        deterministic=False,
        data_classification='internal',
        data_scope=('room', 'building', 'world_object'),
        input_schema={
            'type': 'object',
            'properties': {
                'kind': {'type': 'string', 'description': 'entity kind to create'},
                'name': {'type': 'string'},
            },
        },
        output_schema={
            'type': 'object',
            'properties': {
                'created_id': {'type': 'string'},
                'message': {'type': 'string'},
            },
        },
        error_schema=build_error_schema(('INVALID_PARAM', 'PERMISSION_DENIED', 'POLICY_DENIED', 'CONFLICT', 'NOT_AVAILABLE')),
    )
```

- [ ] **Step 6: Annotate `task` (subcommand-aware)**

In `backend/app/commands/game/task/task_command.py`, the `tool_semantics = TASK_MUTATE_SEMANTICS` already has subcommand profiles. Extend the base semantics with the new fields while keeping the subcommand profiles. Replace:

```python
    tool_semantics = TASK_MUTATE_SEMANTICS
```

with:

```python
    tool_semantics = CommandToolSemantics(
        interaction_profile='mutate',
        subcommand_profiles=TASK_SUBCOMMAND_PROFILES,
        routing_hint='For task examples/syntax/usage, route to `help task` (or primer) first; call state-changing subcommands only after explicit execution intent and confirmation.',
        routing_hint_i18n={
            'zh-CN': '若用户问 task 的例子/语法/用法，先走 help task（或 primer）；不要把示例请求当作执行请求。仅在用户明确执行且确认后才可调用会改状态的 task 子命令。',
            'en-US': 'For task examples/syntax/usage, route to `help task` (or primer) first; do not treat example requests as execute intent. Call state-changing task subcommands only after explicit execution intent and confirmation.',
        },
        side_effect_level='write_high',
        data_classification='internal',
        data_scope=('task',),
        error_schema=build_error_schema(('INVALID_PARAM', 'NOT_FOUND', 'PERMISSION_DENIED', 'POLICY_DENIED', 'CONFLICT')),
    )
```

Add imports at top of `task_command.py`:

```python
from app.commands.command_tool_semantics import CommandToolSemantics, TASK_SUBCOMMAND_PROFILES, build_error_schema
```

(Note: `dataclasses.replace` in `resolve_command_tool_semantics` already carries `side_effect_level`/`data_classification`/`data_scope`/`error_schema` through subcommand resolution because they're dataclass fields with defaults — so `task list` inherits `data_scope=('task',)` and `side_effect_level='write_high'` unless overridden. To make `task list` resolve to `side_effect_level='read'`, add an override on the READ_SUBCOMMAND rule's `invocation_guard` is not enough; instead, the derivation fallback already yields `'read'` for the `read` subcommand profile because `interaction_profile` becomes `'read'` and `side_effect_level` inherits from base (`write_high`) — explicit wins. **Fix**: set `side_effect_level=None` on the base so per-subcommand derivation kicks in. Change the `task` base to `side_effect_level=None` and rely on derivation: `task list` → interaction_profile read → derives `'read'`; `task create` → interaction_profile mutate + default guard requires_confirmation → derives `'write_high'`. Update the test expectation accordingly — `test_task_has_subcommand_aware_side_effect` already asserts this. So set `side_effect_level=None` (or omit it) on the task base.)

Apply: omit `side_effect_level` from the task `tool_semantics` above (remove that line) so derivation handles subcommands.

- [ ] **Step 7: Run test to verify it passes**

Run: `cd backend && conda run -n campusworld pytest tests/commands/test_command_tool_semantics_extended.py -k "look_has or help_has or create_has or task_has" -v`
Expected: PASS (4 tests).

- [ ] **Step 8: Run the full no-DB sweep to confirm no regression**

Run: `cd backend && conda run -n campusworld pytest -m "not integration and not postgres_integration" tests/commands/ tests/game_engine/test_tool_manifest_descriptions.py tests/game_engine/test_tool_manifest_structured_schema.py -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/commands/game/look_command.py backend/app/commands/system_commands.py backend/app/commands/builder/create_command.py backend/app/commands/game/task/task_command.py backend/tests/commands/test_command_tool_semantics_extended.py
git commit -m "feat: annotate Wave-1 commands (look/help/create/task) with full tool contracts"
```

---

## Task 10: Wave-2 command annotation checklist (follow-up batch)

The remaining commands follow the exact pattern from Task 9. Annotate each with `side_effect_level`, `idempotent`, `deterministic`, `data_classification`, `data_scope`, `input_schema`, `output_schema`, `error_schema` as appropriate.

- [ ] `backend/app/commands/system_commands.py` — remaining `INFORMATIONAL_MANIFEST` commands (`who`, `time`, `quit`, `say`, etc.): `side_effect_level='none'`, `data_classification='public'`, `idempotent=True`, `deterministic=True`.
- [ ] `backend/app/commands/space_command.py` — `space`: `side_effect_level='read'`, `data_classification='public'`, `data_scope=('room','building','building_floor')`, `idempotent=True`.
- [ ] `backend/app/commands/system_primer_command.py` — `primer`: `side_effect_level='none'`, `data_classification='public'`, `idempotent=True`.
- [ ] `backend/app/commands/agent_commands.py` — `agent`: subcommand-aware (omit `side_effect_level`, let derivation handle `agent list` → read, `agent tool add` → write_high); `data_scope=('npc_agent',)`, `data_classification='internal'`.
- [ ] `backend/app/commands/game/world_command.py` — `world`: subcommand-aware; `data_classification='internal'`, `data_scope=('world',)`.
- [ ] `backend/app/commands/admin/notice_command.py` — `notice`: subcommand-aware; `data_classification='internal'`, `data_scope=('system_notice',)`.
- [ ] `backend/app/commands/graph_inspect_commands.py` — `describe`/`find`: `side_effect_level='read'`, `data_classification='public'`, `idempotent=True`.
- [ ] `backend/app/commands/game/direction_command.py` — `go`: `side_effect_level='write_low'` (moves character, reversible), `data_classification='internal'`, `data_scope=('room','character')`, `idempotent=False`.
- [ ] `backend/app/commands/game/enter_world_command.py` — `enter`: `side_effect_level='write_low'`, `data_scope=('world','world_entrance')`.
- [ ] `backend/app/commands/game/leave_world_command.py` — `leave`: `side_effect_level='write_low'`.
- [ ] `backend/app/commands/game/task/task_pool_command.py` — `task pool`: subcommand-aware; `data_scope=('task',)`.

For each: add a small unit test asserting the resolved `side_effect_level` and `data_classification`, then commit per command or in small batches:

```bash
git commit -m "feat: annotate <command> with tool contract"
```

Final sweep:

- [ ] Run: `cd backend && conda run -n campusworld pytest -m "not integration and not postgres_integration" tests/commands/ -v` — all PASS.
- [ ] Run: `cd backend && conda run -n campusworld pytest -m postgres_integration tests/db/test_schema_migrations_envelope_refresh.py tests/commands/test_ability_sync_semantics_mirror.py -v` — PASS (with PG).
- [ ] Run: `cd backend && python scripts/validate_config.py` — success.
- [ ] Run: `cd backend && python scripts/validate_command_aliases.py` — success.

---

## Task 11: SPEC annotation (F08)

**Files:**
- Modify: `docs/models/SPEC/features/F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md`

- [ ] **Step 1: Add a Tool Contract subsection**

In `F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md`, add a subsection under the Command-as-Tool section:

```markdown
### Tool Contract (CommandToolSemantics as Tool Profile)

`CommandToolSemantics` (a `ClassVar` on `BaseCommand`) is the single source of truth
for each command's per-tool-type intrinsic contract — the project's Tool Profile. It
carries: `interaction_profile` (coarse read/mutate), `side_effect_level` (refined
`none`/`read`/`write_low`/`write_high`), `idempotent`/`deterministic`, `input_schema`/
`output_schema`/`error_schema` (JSON Schema), `data_classification`
(`public`/`internal`/`confidential`/`restricted`), `data_scope` (NodeType `type_code`
tuple), plus the existing `invocation_guard`/`manifest_tier`/`routing_hint`.

The `system_command_ability` graph node is a read-only mirror, synced one-way by
`ability_sync._sync_tool_semantics` from `CommandToolSemantics`. Runtime consumers
(`build_llm_tool_manifest`, `execution_gate`, `tool_observation_policy`) read
`CommandToolSemantics` only; the node mirror serves graph queries, NPC ability
discovery, the F14 lexicon, and audit. Authorization remains in `command_policies`.

`side_effect_level` uses hybrid resolution: explicit declaration wins; otherwise
derived from `interaction_profile` + `invocation_guard.requires_confirmation`
(read→read; mutate+confirm→write_high; mutate+no-confirm→write_low).
```

- [ ] **Step 2: Commit**

```bash
git add docs/models/SPEC/features/F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md
git commit -m "docs: annotate F08 with CommandToolSemantics as Tool Profile contract"
```

---

## Self-Review

**1. Spec coverage (Phase 0 of the master plan):**
- Extend `CommandToolSemantics` with 4 missing field groups → Task 1 (fields), Task 2 (side_effect_level), Task 3 (data_classification/scope), Task 4 (error_schema). ✅
- Mirror into `system_command_ability` node → Task 5 (ability_sync), Task 6 (envelope). ✅
- Envelope migration → Task 7 (P0-9). ✅
- `build_llm_tool_manifest` reads structured schema → Task 8 (P0-8). ✅
- All commands declare schemas → Task 9 (Wave-1 pattern) + Task 10 (Wave-2 checklist). ✅
- SPEC update → Task 11. ✅
- P0-1 hybrid derivation → Task 2. ✅
- P0-2 interaction_profile kept → Decision section + Task 1 (no removal). ✅
- P0-4 data_classification 4-tier → Task 3 + Decision. ✅
- P0-5 data_scope NodeType reuse → Task 3 `validate_data_scope`. ✅
- P0-6 error_schema unified + i18n → Task 4. ✅
- P0-7 Option B chosen → Decision section + Task 1 (fields on CommandToolSemantics). ✅
- P0-8 runtime reads only CommandToolSemantics → Task 8. ✅
- P0-9 migration explanation → Decision section + Task 7. ✅

**2. Placeholder scan:** No "TBD"/"implement later". Task 10 is a checklist of concrete commands with concrete field values — each item specifies the exact `side_effect_level`/`data_classification`/`data_scope` to set. The pattern is fully shown in Task 9; Wave-2 repeats it. Acceptable per skill (the alternative—writing 40 identical 50-line blocks—would bloat the plan without adding information; the pattern + per-command field spec is complete).

**3. Type consistency:** `resolve_side_effect_level(sem)` returns `ToolSideEffectLevel`; `ability_sync` calls it and writes `attrs['side_effect_level']`. `build_error_schema` returns a dict used as `error_schema`. `CommandToolSemantics.input_schema` is `Optional[Dict]`, read in Task 8 as `dict(sem_obj.input_schema)`. `data_scope` is `Tuple[str,...]`, mirrored as `list(sem.data_scope)`. `ToolSchema.input_schema` consumed in Task 8 matches the existing `ToolSchema` shape. Consistent.

**4. One caveat flagged for the engineer:** Task 3's `validate_data_scope` test touches the DB; the plan notes to mark it `@pytest.mark.integration` and keep only the round-trip unit test in the unit file. Task 9 Step 6 notes the subcommand-derivation subtlety (omit `side_effect_level` on the `task` base so per-subcommand derivation works) — this is handled in the code shown.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-01-agent-runtime-phase0-tool-contract.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
