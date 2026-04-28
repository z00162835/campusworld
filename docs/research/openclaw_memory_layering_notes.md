# OpenClaw-style memory layering (reference notes)

**Non-normative.** F02 adopts **layered memory** (raw / working → long-term curation) without binding to OpenClaw’s file layout or runtime.

| OpenClaw concept (informal) | CampusWorld mapping |
|-----------------------------|---------------------|
| Session / chat log | `agent_memory_entries` (`kind` = `raw`, `working`, …) |
| Long-term MEMORY file / curated facts | `agent_long_term_memory` |
| Compaction / summarization | Promotion job (see `docs/architecture/adr/ADR-F02-Memory-Promotion.md`) |
| Retrieval | v1: SQL filters; Phase 2 optional vectors (F02 Non-Goals) |

Official docs move frequently; treat links as hints. Implementation truth is **F02 SPEC** + DDL.
