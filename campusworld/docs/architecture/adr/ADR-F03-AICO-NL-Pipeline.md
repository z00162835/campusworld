# ADR-F03: AICO — NLP + LLM + PDCA Runtime

## Status

Accepted — 2026-04-12 (updated: phase_llm + F04 dispatch + seed)

## Context

F03 requires the default assistant **AICO** to use **natural language** input, **PDCA** cognition aligned with `agent_run_records.phase`, optional **memory** injection, and **LLM** calls with configurable **system** and **per-phase** prompts. The earlier **rules-only** `PDCAFramework` sample remains for `agent_run` / sys_worker tickets.

## Decision

1. **`FrameworkRunContext`** carries optional **`system_prompt`**, **`phase_prompts`**, **`memory_context`**, and **`phase_llm_overrides`** for one tick (F03 §5.5–5.6). Base defaults load from **`agents.llm.by_service_id`** in YAML via **`resolve_agent_llm_config`** (`agent_llm_config.py`).

2. **`phase_llm`** (per phase: `mode` = `fast` | `plan` | `think` | `skip`, plus optional `model` / `temperature` / `max_tokens` / `timeout_sec` / `extra`) and **`mode_models`** map logical modes to concrete model ids. **`skip`** skips the LLM call for that phase; trace records **`skipped: true`**.

3. **`LlmClient.complete(system=..., user=..., call_spec=...)`** accepts **`LlmCallSpec`**; **`StubLlmClient`** and **`OpenAiCompatibleHttpLlmClient`** implement the protocol. **`build_llm_client_from_service_config`** selects HTTP when **`use_http_llm: true`** and **`api_key_env`** resolves.

4. **`LlmPDCAFramework`** implements Plan → Do → Check → Act with per-phase **`call_spec`**; **`framework_id`** is **`PDCA_LLM`**.

5. **`LlmPdcaAssistantWorker`** binds **`SqlAlchemyMemoryPort`**, **`RegistryToolExecutor`**, and **`LlmPDCAFramework`**. Shared entry: **`run_npc_agent_nlp_tick`** (`npc_agent_nlp.py`) used by **`agent_nlp`**, **`aico`**, and **`@handle`** dispatch.

6. **F04 `@<handle>`**: **`try_dispatch_at_line`** (`at_agent_dispatch.py`) runs before normal command resolution in **`SSHHandler`** and **`HTTPHandler`**. Requires the same authorization as **`agent_nlp`**.

7. **Memory retrieval** is **not** embedded in the framework constructor: callers set **`memory_context`** on the context; optional LTM is gated by **`extra.enable_ltm`** in YAML.

8. **Seed**: **`ensure_aico_npc_agent`** (`seed_data.py`) creates **`service_id=aico`**, **`trait_mask=370`**, **`location_id`** = Singularity root room, after **`ensure_root_node`**.

## Consequences

- F04 users type **`@aico hello`** or **`aico hello`** without a separate registry command name for `@`.
- Replacing **StubLlmClient** with HTTP is configuration-driven (`use_http_llm` + env key).

## References

- [F03 — AICO SPEC](../../models/SPEC/features/F03_AICO_DEFAULT_SYSTEM_ASSISTANT.md)
- [F04 — @ protocol](../../models/SPEC/features/F04_AT_AGENT_INTERACTION_PROTOCOL.md)
- [ADR-F02-Cognition-PDCA](ADR-F02-Cognition-PDCA.md)
