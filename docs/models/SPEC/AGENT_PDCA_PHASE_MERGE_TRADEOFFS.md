# Agent PDCA: merging or skipping Check / Act (tradeoffs)

CampusWorld’s default `npc_agent` NLP path uses **Plan → Do → Check → Act** with optional Check-driven Plan/Do retry.

## Why keep four phases by default

- **Check** enforces “no claims beyond tool observations” and can emit `RETRY: need_tools=…` without exposing raw guardrail text to the user.
- **Act** polishes tone while constraining “no new facts”; skipping it risks subtle hallucinations when the Do draft is already verbose.

## Options considered (not default)

1. **Skip Act when Do is short** — saves one LLM call but requires a reliable heuristic (length, language, risk class); wrong skips regress quality.
2. **Skip Check for purely informational ticks** — fastest failure mode when intent classifiers mis-label verify_state requests.
3. **Fuse Check + Act** — one call must both audit and rewrite; models often optimize for polish and weaken auditing.

## Recommendation

Keep **four phases** until observability shows stable intent classification and a measurable latency budget. Prefer **slim Do/Check/Act system prompts** and **tool-manifest narrowing** (feature-flagged) before merging phases.

## Related configuration

See `agents.llm.by_service_id.<service>.extra` in `backend/config/settings.yaml`, including `tool_gather_max_rounds_per_phase`, `pdca_use_slim_followup_system`, optional `enable_intent_tool_manifest_subset`, optional `use_prompt_cache` (merged into `LlmCallSpec.extra` per `llm_client.py`), and optional `enable_stm_llm_compaction` (STM volume / latency; see F12).

Per-phase LLM on/off and models belong on the **`npc_agent` graph node**: `attributes.phase_llm` (not under `agents.llm.extra`). Default assistant seeds may set **`phase_llm.do.mode: skip`** to save one Do HTTP call while keeping **Plan** enabled; tuning latency versus polish remains an ops choice.

**Resolver defaults vs AICO seed:** `merge_phase_config` / `_default_phase_config` (`phase_llm_resolve.py`) apply when a phase key is **missing** on the node: **`act` defaults to `skip`**; **`plan` / `do` / `check` default to non-skip** (`PhaseLlmMode.plan`) so Do still runs unless the instance sets `do.mode: skip`. The **default AICO** `npc_agent` created or upgraded by `ensure_aico_npc_agent` (`seed_data.py`) **does** set `do` / `check` / `act` to `skip` and `plan` to `fast`—that is a **seeded node default**, not the global omission default.

---

## Skip Do (`phase_llm.do.mode: skip`): user-visible draft (D1)

When the Do phase LLM is skipped, the framework still runs Plan (possibly with ToolGather). **User-visible reply** (SSH / API message) is **`plan_out` stripped only**—no Plan-phase observation appendix. Raw F08 blocks (`format_tool_observation_block`) and headings such as `--- Tool observations (plan phase) ---` are **runtime / Check context**, not end-user copy.

- **`plan_out`**: last textual output from the Plan phase ReAct loop (model prose). The Plan model should incorporate tool-backed facts into this prose when tools ran in-plan; operators tune prompts toward that behaviour.

- **`plan_tools_text`**: concatenated F08 observation text from Plan-phase ToolGather. Appended to the **Check-phase user blob only** (labeled as runtime grounding, not shown to user) when Check LLM is enabled, so the guardrail can still verify claims against observations. **Trace / structured logs** retain observation payloads separately (`plan_tool_observations`, etc.).

- **Empty `plan_out` with non-empty observations**: user-visible draft may be empty → framework empty-reply policy applies; fixing this is primarily **Plan prompting** (summarize after tools), not re-exposing raw observations on SSH.

**Implementation anchor:** `assemble_plan_skip_do_draft` returns `(plan_out).strip()`; `plan_grounding_for_check` in `_run_inner` (`llm_pdca.py`).

**Act**, when not skipped, polishes the user-visible draft; **`final_text` then need not equal `plan_out`** verbatim.

---

## `final_text` versus `plan_out`: recommended equivalence rules (D4)

Use these for **contract tests** and release review; they avoid brittle full-string equality where Act or retries participate.

| Scenario | Recommended assertion |
|----------|------------------------|
| **Do skip, Check skip, Act skip** | User draft is **`plan_out` only**. **`normalize(final_text) == normalize(plan_out)`** (after strip). |
| **Do skip, Check skip, Act not skip** | Do **not** require `final_text == plan_out`. Assert **`final_text == normalize(act_out)`** (or non-empty polish). Act **input** is the user-visible draft (`plan_out`-based), not raw `plan_tools_text`. |
| **Check RETRY then second Plan/Do** | Assert on **post-retry** `final_text`; pin intermediate traces separately. The current `LlmPDCAFramework` **does not** invoke a second Check LLM in the same tick after retry (only replan + optional second Do); count LLM calls in tests accordingly. |
| **`normalize` for tests** | Strip outer whitespace; normalize newlines to `\n`; optional single pass collapsing excessive blank lines — **golden / harness tests** should share one helper and document it next to the tests. **Unit tests** may use exact string equality when inputs have no benign whitespace variance (e.g. `test_llm_pdca_skip_do.py`). |
| **Regression guard** | User-visible `final_text` must **not** contain F08 delimiters (`tool_observation begin`) nor the Plan-phase observation heading; observability belongs in trace/logs. |

Phase-one performance scope **freezes** conditional “skip Do by heuristic”; only explicit **`phase_llm.do.mode: skip`** plus the D1 assembly rules above.
