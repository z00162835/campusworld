# ADR-F08 — ToolGather、冻结工具面与 PDCA 阶段注入

**Status:** Accepted  
**Date:** 2026-04-15  
**Context:** [F08 — AICO 工具调用与命令上下文](../../models/SPEC/features/F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md)、[F09 — Agent 四层](../../models/SPEC/features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)

## Decision

1. **Resolved tool surface（初始化）**  
   在 `LlmPdcaAssistantWorker.create` 中调用 `build_resolved_tool_surface(node_tool_allowlist, tool_command_context)`，得到 `frozenset` 允许的命令名。交集语义：`RegistryToolExecutor.list_tool_ids(tool_ctx)`（策略过滤后的注册表名）再经 `ToolRouter(allowlist)`；并移除默认 **`aico`**，避免工具路径嵌套 NLP。

2. **PreauthorizedToolExecutor（运行时）**  
   对上述集合内的命令：`command_registry.get_command` + `execute`，**不**在每调一次重复 `authorize_command`。理由：允许集已在构造面时与策略一致；动态撤销不在 v1 范围。

3. **ToolGather**  
   从各 PDCA 阶段 LLM 文本中解析首个含 `"commands"` 的 JSON 计划（见 F08 §7），顺序执行 0..N 条，格式化为 `ToolObservation`，追加到 `command_trace`，并注入**下一**阶段 LLM 的 user 载荷（Plan→Do、Do→Check、Check→Act）。**Act** 阶段 LLM 之后不再执行新工具（避免与润色语义冲突）。

4. **预算**  
   `ToolGatherBudgets` 由 `agents.llm.extra` 可选键驱动；全 tick 与每阶段条数/字符上限在 `tool_gather.gather_tool_observations` 中强制执行。

5. **横切钩子占位**  
   `thinking_pipeline.AgentTickHooks` / `NoOpAgentTickHooks` 供后续与 PhaseHandler 正交扩展；当前默认 no-op。

## Consequences

- 测试可对 `PreauthorizedToolExecutor`、`tool_gather`、`LlmPDCAFramework` 分层覆盖。  
- 与 F08 原文「每调 `authorize_command`」字面的差异以本 ADR 为准。  
- 完整 **Pre→Post** 管线与 **PhaseInnerLoop** 多轮微步可在后续迭代加强，不阻塞本 ADR。

## References

- `backend/app/game_engine/agent_runtime/resolved_tool_surface.py`  
- `backend/app/game_engine/agent_runtime/tool_gather.py`  
- `backend/app/game_engine/agent_runtime/frameworks/llm_pdca.py`  
- `backend/app/game_engine/agent_runtime/thinking_pipeline.py`
