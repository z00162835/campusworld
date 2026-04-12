# AICO / Agent NLP — PR review checklist

Use when changing `agent_runtime`, `agent_commands`, `@` dispatch, or `agents.llm` YAML.

- **Secrets**: No API keys in graph `nodes.attributes` or committed YAML; only `api_key_env` references.
- **Authz**: `@` / `agent_nlp` / `aico` use **`agent_nlp`** policy; no bypass of `authorize_command`.
- **Audit**: `agent_run_records.command_trace` distinguishes **skipped** phases vs real LLM outputs.
- **Tests**: Unit tests for **`LlmPDCAFramework`** (including **`phase_llm.check: skip`**); integration tests for **`agent_nlp`** when PostgreSQL available.
- **Config**: `python scripts/validate_config.py` passes after YAML changes.
