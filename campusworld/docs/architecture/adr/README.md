# Architecture Decision Records (ADR)

| ADR | Topic |
|-----|--------|
| [ADR-F02-Agent-Runtime](ADR-F02-Agent-Runtime.md) | Python agent worker, command-first, service principal |
| [ADR-F02-Memory-Promotion](ADR-F02-Memory-Promotion.md) | Raw → long-term memory promotion |
| [ADR-F02-Cognition-PDCA](ADR-F02-Cognition-PDCA.md) | Pluggable cognition, PDCA default |
| [ADR-F03-AICO-NL-Pipeline](ADR-F03-AICO-NL-Pipeline.md) | AICO NLP + LLM + PDCA, prompts, memory context |
| [ADR-F04-AT-Dispatch](ADR-F04-AT-Dispatch.md) | `@` prefix dispatch vs CmdSet, auth aligned with `aico` |
| [ADR-F08-Tool-Gather](ADR-F08-Tool-Gather.md) | Frozen tool surface, ToolGather, PDCA phase injection |
| ADR-F09-Agent-Four-Layers（占位） | 见 [`docs/models/SPEC/features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md`](../../models/SPEC/features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md) §9；定稿后补本文档 |
| [REVIEW-AICO](REVIEW-AICO.md) | PR checklist for agent NLP / `@` / YAML changes |

**Implementation audit (not an ADR):** [Agent runtime consistency matrix (F09)](../Agent_Runtime_Consistency_Matrix.md) — code vs F09 layered claims; complements ADR-F09 when that ADR is finalized.
