# AICO / Agent NLP — PR review checklist

Use when changing `agent_runtime`, `agent_commands`, `@` dispatch, or `agents.llm` YAML.

- **Secrets**: No API keys in graph `nodes.attributes` or committed YAML; only `api_key_env` references.
- **Authz**: `@` lines and **`aico`** use **`aico`** policy (`authorize_command(aico)`); no bypass of `authorize_command`.
- **Audit**: `agent_run_records.command_trace` distinguishes **skipped** phases vs real LLM outputs.
- **Tests**: **`LlmPDCAFramework`** in `tests/game_engine/test_llm_pdca_framework.py` (including **`phase_llm.check: skip`**); assistant NLP units in `tests/commands/test_npc_agent_nlp.py`; PostgreSQL integration in `tests/commands/test_agent_f02_commands.py` (capabilities + stub-LLM `run_npc_agent_nlp_tick` → **`agent_run_records`**); `@` dispatch in `tests/commands/test_f04_at_dispatch.py` as applicable.
- **Config**: `python scripts/validate_config.py` passes after YAML changes.
