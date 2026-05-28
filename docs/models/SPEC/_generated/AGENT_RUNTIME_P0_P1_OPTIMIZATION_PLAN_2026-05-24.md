# Agent Runtime P0/P1 Optimization Plan Snapshot

**Status:** Active

**Generated:** 2026-05-24

**Scope:** Agent Runtime mandatory evidence, ToolObservation policy, and minimal AICO runtime profile extraction.

## Decisions

| ID | Decision |
|----|----------|
| D1 | Mandatory evidence is tick-wide: Plan / Do / retry Plan / retry Do successful ToolObservation can satisfy mandatory. |
| D2 | ToolObservation summary is deterministic and does not use hash. Summary format keeps the first non-empty line and `original_chars=<n>`. |
| D3 | Observation policy source is code defaults plus `system_command_ability.attributes.agent_observation_policy` override. |
| D4 | Mandatory gap user-facing text appends a short system hint and does not overwrite assistant text. |
| D5 | Stable semantics belong in F08 / F14 / F03 / F13; TODO tracks execution; generated snapshot keeps detailed plan context. |
| D6 | P1 uses a minimal `AgentRuntimeProfile`; AICO-specific orchestration is not split out in this phase. |
| D7 | Real token streaming, full-chain cancel, and live eval are excluded from this phase. |
| D8 | Recommended profile and policy paths are adopted for AICO. |
| D9 | Unknown commands and `semantic_pending=true` commands default to ToolObservation `summary`; registered commands with `interaction_profile=read` default to `full`; `mutate` defaults to `summary`. |
| D10 | Mandatory gaps may run one bounded repair retry; retry is not an unbounded regular `RETRY: need_tools=` loop. |
| D11 | P0 user fallback is a short appended system hint; full structured user failure blocks are deferred to P1 while machine trace/log remain structured. |

## P0 Plan

- [x] Extend mandatory gap evaluation from Plan-only evidence to tick-wide ToolObservation evidence.
- [x] Preserve failure diagnostics for missing mandatory tool, permission denied, budget skipped, and failed tool execution.
- [x] Add observed tools and observed phases to mandatory gap trace for review and debugging.
- [x] Introduce `ToolObservationPolicy` with `full`, `summary`, and `blocked` modes.
- [x] Apply the same observation policy to LLM ToolObservation content and trace `message_preview`.
- [x] Keep summary deterministic and compact without hashing.
- [x] Default unknown / semantic-pending command observations to `summary`; registered read-profile commands on `full`; mutate on `summary`.
- [x] Allow one bounded mandatory repair retry before final fallback.
- [x] Keep P0 mandatory fallback as an appended short system hint while preserving structured machine diagnostics.

## P1 Plan

- [x] Add `AgentRuntimeProfile` protocol and no-op profile.
- [x] Extract AICO-specific informational manifest subset, NDJSON lifecycle, REPL progress, observability hooks, and full-chain debug switch into `AicoRuntimeProfile`.
- [x] Keep common `run_npc_agent_nlp_tick` lifecycle as the source of truth for config, STM/LTM, worker construction, PDCA tick, STM append, and `CommandResult`.
- [x] Treat the Worker-created frozen `ResolvedToolSurface` as the only source of truth for AICO informational manifest subset derivation.
- [x] Ensure generic runtime components do not depend on AICO profile.
- [x] Move framework full-chain logging behind a generic observability adapter supplied by runtime profiles.
- [x] Move full-chain tick scope enter/exit into runtime profiles.
- [x] Move LLM HTTP run/correlation and HTTP exchange dispatch behind the generic runtime observability context.
- [x] Use a profile factory registry instead of a hard-coded service-id branch.
- [x] Cache ToolObservation policy resolution per command within one gather call.
- [ ] Track real token streaming, full-chain cancel, and live eval as separate future work.

## Verification

- Focused backend tests cover mandatory tick-wide evidence, observation policy modes, AICO stream parity, and runtime profile no-op behavior.
- SPEC layout validation remains required after docs edits.
