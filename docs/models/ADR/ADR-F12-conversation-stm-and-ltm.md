# ADR: F12 Conversation STM, Mode B Lock, LTM Scope, Redis Boundary

## Context

F12 defines short-term memory (STM) per ConversationScope, compaction, long-term memory (LTM) metadata filtering, and Mode B possession. PostgreSQL is the sole durability authority for STM and locks in v1.

## Decisions

1. **Mode A STM table** `agent_conversation_stm`: unique `(caller_account_node_id, transport_session_id, agent_node_id, conversation_thread_id)`. Payload: JSONB message list + `rolling_summary`, generations for flush/cache coherence.
2. **Mode B** `agent_daemon_stm_lock`: one row per `agent_node_id` with lock columns + STM JSON in the same row; `SELECT … FOR UPDATE` for conflict checks; **`locked_by_account_node_id` is written only after a successful NLP tick** (passthrough / failed ticks do not refresh `last_successful_tick_at`). Transport close (SSH `SessionManager.remove_session`, WebSocket disconnect) clears rows whose `lock_transport_session_id` matches, when `npc_agent.daemon_possession.possession_release_on_transport_close` is true (platform default; not under `agents.llm` service_id).
3. **Thread directory** `agent_conversation_thread`: supports `aico -l`; updated when a thread is touched.
4. **LTM** `agent_long_term_memory`: **`caller_account_node_id` is NOT NULL** (after migration); `conversation_thread_id` optional on writes; retrieval default `user_agent` (cross-thread); optional `ltm_retrieval_scope=thread`. Mode B writes must use the same account id as the daemon lock holder.
5. **Flush idempotency**: Mode A keys include `conversation_thread_id` + `flush_generation` (flush enqueue logic may follow F07).
6. **Redis**: not used for STM or locks in v1; optional read-through cache only in a later phase (compare `stm_generation`).
7. **Provider caching (D19)**: `prompt_fingerprint` carried on `LlmCallSpec.extra`; per-provider HTTP adapters map to vendor cache fields; correct behavior without cache is mandatory.

## Consequences

- SQL SSOT section `conversation_multi_turn_memory` in `database_schema.sql`; migration step `ensure_multi_turn_conversation_memory_schema`.
- NLP tick loads/writes STM around `run_npc_agent_nlp_tick`; Plan receives full STM+LTM text; Do receives minimal memory pointer (D5).
