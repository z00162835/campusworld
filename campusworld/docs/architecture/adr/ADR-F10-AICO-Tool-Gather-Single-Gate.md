# ADR-F10 — AICO ToolGather 单点判定（ToolRuntimeView）

**Status:** Accepted  
**Date:** 2026-04-24  
**Context:** [F10 — AICO 性能与延迟](../../models/SPEC/features/F10_AICO_PERFORMANCE_AND_LATENCY.md)、[F08 — 工具上下文与 Agent 循环](../../models/SPEC/features/F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md)、[ADR-F08 — ToolGather](./ADR-F08-Tool-Gather.md)

## Decision

1. **单点判定**  
   在 ``LlmPDCAFramework`` 内，凡需执行 ``gather_tool_observations`` 的路径（``_phase_react_loop``、``_gather_tools_after_llm``）在调用前统一经由 ``resolve_tool_runtime_view(...) -> ToolRuntimeView``。仅当 ``view.can_execute`` 为真时传入 ``view.executor`` 与 ``view.tool_context`` 调用 gather。

2. **语义不变（对齐 F08 / ADR-F08）**  
   ``PreauthorizedToolExecutor``、冻结工具面、预算字段与 ``gather_tool_observations`` 内部逻辑不改；本 ADR 只收敛「是否允许进入 gather」的分支，不绕过授权语义。

3. **预算与缺失依赖**  
   ``can_execute`` 为假的原因枚举为：``missing_executor``、``missing_tool_context``、``tick_command_budget_exhausted``、``tick_char_budget_exhausted``。为假时由框架写入 ``command_trace`` 行 ``step: tool_gather_skip``（含 ``reason``、``phase``），替代在已耗尽 tick 预算时仍进入 gather 再在循环首条命中 cap 的行为，减少无效调用。

4. **并行只读工具 / fast-tick**  
   不在本 ADR 范围；若引入并行 gather 或 phase 合并，须另立 ADR。

## Consequences

- 测试可针对 ``resolve_tool_runtime_view`` 与 trace 中的 ``tool_gather_skip`` 做单元断言。  
- 与「并行只读白名单」相关的顺序语义仍待后续 ADR。

## References

- ``backend/app/game_engine/agent_runtime/tool_runtime_view.py``  
- ``backend/app/game_engine/agent_runtime/frameworks/llm_pdca.py``  
- ``backend/app/game_engine/agent_runtime/tool_gather.py``
