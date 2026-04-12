# ADR-F02: Raw → Long-Term Memory Promotion

## Status

Accepted — 2026-04-09

## Context

F02 splits **raw / working** rows (`agent_memory_entries`, `kind` in `raw`, `working`, …) from **curated long-term** rows (`agent_long_term_memory`). Promotion must be explicit and auditable.

## Decision

**Triggers (v1, any combination per deployment):**

| Trigger | Description |
|--------|-------------|
| **Scheduled job** | Batch process `agent_memory_entries` older than retention window; summarize or copy with `source_memory_entry_id` set. |
| **Manual command** | Operator-invoked promotion (e.g. future `agent memory promote …`). |
| **LLM summary** | Optional: `decision_mode` includes LLM; writes new LTM row with summary + structured `payload`. |

**Retention:** Raw rows may be TTL-deleted after successful promotion or after a max age; exact TTL is **environment config**, not stored in graph attributes.

**Graph consistency:** `agent_long_term_memory.graph_node_id` / `relationship_id` are **hints**; authoritative detail remains on `nodes` / `relationships` (see F02 §9.0.1).

## Consequences

- `backend/scripts/promote_raw_to_ltm.py` is a **stub** until product rules fix batch size and summarization.
- Vector search on LTM is **Phase 2** (non-blocking).
