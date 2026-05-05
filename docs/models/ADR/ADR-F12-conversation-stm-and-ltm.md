# ADR: F12 Conversation STM, Mode B Lock, LTM Scope, Redis Boundary

## Context

F12 defines short-term memory (STM) per ConversationScope, compaction, long-term memory (LTM) metadata filtering, and Mode B possession. PostgreSQL is the sole durability authority for STM and locks in v1.

## Decisions

1. **Mode A STM table** `agent_conversation_stm`: unique `(caller_account_node_id, transport_session_id, agent_node_id, conversation_thread_id)`. Payload: JSONB message list + `rolling_summary`, generations for flush/cache coherence.
2. **Exclusive shared daemon (`system_shared_exclusive`)** — table `agent_daemon_stm_lock`: one row per `agent_node_id` with lock columns + STM JSON in the same row; `SELECT … FOR UPDATE` for conflict checks; **`locked_by_account_node_id` is written only after a successful NLP tick** (passthrough / failed ticks do not refresh `last_successful_tick_at`). Transport close (SSH `SessionManager.remove_session`, WebSocket disconnect) clears rows whose `lock_transport_session_id` matches, when `npc_agent.daemon_possession.possession_release_on_transport_close` is true (platform default; not under `agents.llm` service_id).
3. **Thread directory** `agent_conversation_thread`: supports `aico -l`; updated when a thread is touched.
4. **Implicit default thread on transport**: The default `conversation_thread_id` for per-user-assistant dialogue is also stored on the transport handle (`SSHSession.command_ephemeral` / `WSConnection.command_ephemeral`, key `stm_default_thread:<agent_node_id>`) so successive commands in one SSH or WebSocket session reuse the same thread without requiring `CommandContext.metadata` to persist across commands. Restored rows must match `agent_conversation_thread` for `(id, owner, agent, transport_session_id)`. `aico -nd` clears ephemeral for that agent; `aico -cd` persists the chosen thread into ephemeral.
5. **LTM** `agent_long_term_memory`: **`caller_account_node_id` is NOT NULL** (after migration); `conversation_thread_id` optional on writes; retrieval default `user_agent` (cross-thread); optional `ltm_retrieval_scope=thread`. Mode B writes must use the same account id as the daemon lock holder.
6. **Flush idempotency**: Mode A keys include `conversation_thread_id` + `flush_generation` (flush enqueue logic may follow F07).
7. **Redis**: not used for STM or locks in v1; optional read-through cache only in a later phase (compare `stm_generation`).
8. **Provider caching (D19)**: `prompt_fingerprint` carried on `LlmCallSpec.extra`; per-provider HTTP adapters map to vendor cache fields; correct behavior without cache is mandatory.

## Consequences

- SQL SSOT section `conversation_multi_turn_memory` in `database_schema.sql`; migration step `ensure_multi_turn_conversation_memory_schema`.
- NLP tick loads/writes STM around `run_npc_agent_nlp_tick`; Plan receives full STM+LTM text; Do receives minimal memory pointer (D5).
