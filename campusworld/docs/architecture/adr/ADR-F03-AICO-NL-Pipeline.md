# ADR-F03: AICO — NLP + LLM + PDCA Runtime

## Status

Accepted — 2026-04-12 (updated: node-sourced phase_llm, prompt_overrides, LTM tick hook)

## Context

F03 requires the default assistant **AICO** to use **natural language** input, **PDCA** cognition aligned with `agent_run_records.phase`, optional **memory** injection, and **LLM** calls with configurable **system** and **per-phase** prompts. The earlier **rules-only** `PDCAFramework` sample remains for `agent_run` / sys_worker tickets.

## Decision

1. **`FrameworkRunContext`** carries optional **`system_prompt`**, **`phase_prompts`**, **`memory_context`**, and **`phase_llm_overrides`** for one tick (F03 §5.5–5.6). Base connection and default prompts load from **`agents.llm.by_service_id`** in YAML via **`resolve_agent_llm_config`** ([`agent_llm_config.py`](../../../backend/app/game_engine/agent_runtime/agent_llm_config.py)), then merge **`nodes.attributes.model_config`** (whitelist: `temperature`, `max_tokens`, `model`), then **`prompt_overrides`**.

2. **`phase_llm`** and **`mode_models`** live on **`npc_agent.nodes.attributes`** (per-instance PDCA routing), parsed by **`parse_phase_llm_from_attributes`** ([`agent_node_phase_llm.py`](../../../backend/app/game_engine/agent_runtime/agent_node_phase_llm.py)). Per-phase **`mode`** = `fast` | `plan` | `think` | `skip`; **`skip`** skips the LLM call; trace records **`skipped: true`**. Tick-level **`phase_llm_overrides`** in **`FrameworkRunContext`** merges on top.

3. **`LlmClient.complete(system=..., user=..., call_spec=...)`** accepts **`LlmCallSpec`**; **`StubLlmClient`** and **`OpenAiCompatibleHttpLlmClient`** implement the protocol. **`build_llm_client_from_service_config`** selects HTTP when **`use_http_llm: true`** and **`api_key_env`** resolves.

4. **`LlmPDCAFramework`** implements Plan → Do → Check → Act with per-phase **`call_spec`**; **`framework_id`** is **`PDCA_LLM`**.

5. **`LlmPdcaAssistantWorker`** binds **`SqlAlchemyMemoryPort`**, **`RegistryToolExecutor`**, and **`LlmPDCAFramework`**. Shared entry: **`run_npc_agent_nlp_tick`** ([`npc_agent_nlp.py`](../../../backend/app/commands/npc_agent_nlp.py)) used by **`agent_nlp`**, **`aico`**, and **`@handle`** dispatch.

6. **F04 `@<handle>`**: **`try_dispatch_at_line`** ([`at_agent_dispatch.py`](../../../backend/app/commands/at_agent_dispatch.py)) runs before normal command resolution in **`SSHHandler`** and **`HTTPHandler`**. Requires the same authorization as **`agent_nlp`**.

7. **Optional LTM**: When YAML **`extra.enable_ltm`** is true, **`run_npc_agent_nlp_tick`** calls **`build_ltm_memory_context_for_tick`** ([`ltm_semantic_retrieval.py`](../../../backend/app/services/ltm_semantic_retrieval.py)) to populate **`memory_context`** (recent LTM summaries; semantic KNN may extend when query embeddings are available).

8. **Seed**: **`ensure_aico_npc_agent`** ([`seed_data.py`](../../../backend/db/seed_data.py)) creates **`service_id=aico`**, **`trait_mask=370`**, **`location_id`** = Singularity root room, and backfills **`phase_llm` / `mode_models`** on existing nodes when missing.

## Consequences

- F04 users type **`@aico hello`** or **`aico hello`** without a separate registry command name for `@`.
- Replacing **StubLlmClient** with HTTP is configuration-driven (`use_http_llm` + env key).
- PDCA routing changes per agent instance without editing global YAML (only connection/prompt defaults remain in YAML).

## References

- [F03 — AICO SPEC](../../models/SPEC/features/F03_AICO_DEFAULT_SYSTEM_ASSISTANT.md)
- [F04 — @ protocol](../../models/SPEC/features/F04_AT_AGENT_INTERACTION_PROTOCOL.md)
- [ADR-F02-Cognition-PDCA](ADR-F02-Cognition-PDCA.md)
