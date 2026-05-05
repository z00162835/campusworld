# ADR-F10 — AICO ToolGather single gate (`ToolRuntimeView`)

**Status:** Accepted  
**Date:** 2026-04-30  
**Context:** F10（性能与延迟）、F08（ToolGather）。`LlmPDCAFramework` 在 Plan / Do 等多条分支上都要判断是否允许调用 `gather_tool_observations`；分散的空指针与预算判断容易产生不一致与重复日志噪声。

## Decision

- 引入 **`resolve_tool_runtime_view`**（`backend/app/game_engine/agent_runtime/tool_runtime_view.py`），输入冻结的执行器、命令上下文、`ToolGatherBudgets` 与 `ToolGatherCounters`，输出不可变的 **`ToolRuntimeView`**（`can_execute`、`reason`、`executor`、`tool_context`、`budgets`）。
- 所有 ToolGather 调用路径在进入 `gather_tool_observations` 之前 **必须先** 经由该解析函数；`can_execute` 为 false 时写入 **`step: tool_gather_skip`**（含 **`reason`**、**`phase`**，ReAct 下可含 **`round`**），而非静默跳过。

## Consequences

- **正面：** 门控逻辑单测可集中覆盖；与 F10 §8「工具可用性单点判定」对齐。
- **负面：** 新增一层间接调用；调用方须传入最新的 counters（tick 级累积）。

**规范交叉引用：** [`docs/models/SPEC/features/F10_AICO_PERFORMANCE_AND_LATENCY.md`](../../models/SPEC/features/F10_AICO_PERFORMANCE_AND_LATENCY.md) §8、[`docs/models/SPEC/features/F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md`](../../models/SPEC/features/F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) §9。
