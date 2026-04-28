# F10 — AICO 性能与延迟（tick SLO、可观测性、实现收敛）

> **Architecture Role：** 在 [**F03**](F03_AICO_DEFAULT_SYSTEM_ASSISTANT.md)（AICO 实例与 LLM 配置）与 [**F08**](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md)（Command-as-Tool、ToolGather）之上，规定 **单次 NLP tick 的延迟预算、度量与 SLO**，并对 **实现侧重复逻辑与工具门控分散** 给出 **收敛方向** 与 **分阶段路线图**。不改变 F03/F08 的授权语义与工具契约；具体编排或大改须另附 ADR。

**文档状态：Draft**

**交叉引用：** [**F03**](F03_AICO_DEFAULT_SYSTEM_ASSISTANT.md)（AICO、`agents.llm`、`phase_llm`）、[**F08**](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md)（ToolGather、冻结工具面 R2）、[**F09**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)（L3 思考管线边界）、[**F02**](F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)（`agent_run_records` / `command_trace`）。

**实现锚点（非 exhaustive）：** [`backend/app/commands/npc_agent_nlp.py`](../../../../backend/app/commands/npc_agent_nlp.py)（`run_npc_agent_nlp_tick`）、[`backend/app/game_engine/agent_runtime/worker.py`](../../../../backend/app/game_engine/agent_runtime/worker.py)（`LlmPdcaAssistantWorker`）、[`backend/app/game_engine/agent_runtime/frameworks/llm_pdca.py`](../../../../backend/app/game_engine/agent_runtime/frameworks/llm_pdca.py)（`LlmPDCAFramework`、`_run_inner`、`_phase_react_loop`、`_call_llm_dual_track`）、[`backend/app/game_engine/agent_runtime/tool_gather.py`](../../../../backend/app/game_engine/agent_runtime/tool_gather.py)（`ToolGatherBudgets`、`gather_tool_observations`）、[`backend/app/game_engine/agent_runtime/resolved_tool_surface.py`](../../../../backend/app/game_engine/agent_runtime/resolved_tool_surface.py)（`build_resolved_tool_surface`、`PreauthorizedToolExecutor`）、[`backend/app/game_engine/agent_runtime/command_caller_graph.py`](../../../../backend/app/game_engine/agent_runtime/command_caller_graph.py)、[`backend/app/game_engine/agent_runtime/phase_llm_resolve.py`](../../../../backend/app/game_engine/agent_runtime/phase_llm_resolve.py)、[`backend/app/game_engine/agent_runtime/llm_providers/minimax_anthropic.py`](../../../../backend/app/game_engine/agent_runtime/llm_providers/minimax_anthropic.py)（HTTP 超时默认值）、[`backend/config/settings.yaml`](../../../../backend/config/settings.yaml)（`agents.llm.by_service_id`）。

---

## 1. Goal

- 将 AICO / `npc_agent` NLP 路径的 **端到端 tick 延迟** 变为 **可度量、可预算、可回归** 的工程问题，支撑「平均或尾延迟显著高于业务预期」（例如数十秒级）时的 **定位、配置与实现迭代**。
- 建立 **分 phase**（Plan / Do / Check / Act）与 **上游 HTTP** 的耗时视图，使运维与开发能区分「模型慢」「prompt 过大」「工具轮次过多」「重复 DB 访问」等根因。
- 推动 **公共逻辑单点化**（调用方图解析、工具是否可执行、YAML `extra` 布尔解析等），降低不一致与重复 I/O 带来的 **无谓延迟与 bug 面**。

## 2. Non-Goals

- 不替代 **LLM 供应商** 的 SLA，不绑定某一厂商 API 为唯一实现。
- 不在本文 v1 **强制** 流式输出或「先占位后补全」产品形态（可作为 Phase 2+ 产品项）。
- 不在本文中规定 **CampusLibrary（F06）** 或 **图向量检索** 的性能模型（与 F06 互补，可单独 SPEC）。

## 3. 术语与范围

| 术语 | 含义 |
|------|------|
| **tick** | 一次 `run_npc_agent_nlp_tick` 从进入到返回 `FrameworkRunResult` 的完整调用；用户感知为「一次 @aico / aico 答复」。 |
| **phase** | PDCA：`plan`、`do`、`check`、`act`（与 `agent_run_records.phase` 对齐）。 |
| **ReAct round** | 在 `plan` 或 `do` 内，`LlmPDCAFramework._phase_react_loop` 中一次「LLM →（可选）工具 → 观测 → 再 LLM」循环；上限见 `ToolGatherBudgets.max_tool_rounds_per_phase`。 |
| **ToolGather** | 将 LLM 输出的调用计划转为注册表命令执行并拼接观测文本（F08）。 |
| **provider RTT** | 单次 HTTP LLM 请求从发出到收齐响应体的 wall time。 |

## 4. 现状架构与延迟上界（实现摘要）

单次 tick 主链：

`run_npc_agent_nlp_tick` → `LlmPdcaAssistantWorker.create` → `tick` → `LlmPDCAFramework.run` → `_run_inner`。

### 4.1 顺序 LLM 调用（基线）

- **Plan**：`_phase_react_loop`（可含多轮 ReAct）。
- **Do**：`_phase_react_loop`（可含多轮 ReAct）。
- **Check**：单次 `_call_llm`（无 ReAct 循环）；可解析 `RETRY: need_tools=...`。
- **Act**：单次 `_call_llm`（`phase_llm.act` 默认为 skip 时可不调用，见 `phase_llm_resolve._default_phase_config`）。

若 Check 触发 RETRY 且预算允许，会 **再执行一整轮** Plan + Do 的 `_phase_react_loop`（见 `llm_pdca.py` 中 `check_retry_triggered` 分支）。

### 4.2 每 phase 内 ReAct 上界

- `max_tool_rounds_per_phase` 默认 **3**（[`tool_gather.py`](../../../../backend/app/game_engine/agent_runtime/tool_gather.py) `tool_gather_budgets_from_agent_extra`）。
- 每轮至少 **1 次** `_call_llm_dual_track`（或等价 `complete` / `complete_with_tools`）。

故 **仅 Plan+Do 两阶段** 在「每阶段打满 3 轮」且每轮都调用 LLM 时，已有 **6 次** 上游 LLM 调用量级；再加 Check、Act 与可选 RETRY，**串行调用次数** 远高于「4 次 PDCA」的直觉。

### 4.3 HTTP 超时与生成预算

- MiniMax Anthropic 等 HTTP 客户端默认 **`timeout_sec` = 120**（见 `minimax_anthropic.py` 等）；`phase_llm` 可为每 phase 覆盖 `timeout_sec`（`PhaseLlmPhaseConfig` → `LlmCallSpec`）。
- `max_tokens` 较大（如默认 4096）时，生成时间与输出体积上升，与尾延迟正相关。

### 4.4 提示词与观测体积

- Tier-1：`identity_and_invariants_snippet` 与 YAML `system_prompt` 合并（worker 创建路径）。
- Tier-2：Plan 首条 user 含 `world_snapshot`、`tool_manifest_text`、可选 LTM（`memory_context`）。
- Tier-3：工具观测在多轮 ReAct 中追加，受 `tool_gather_max_chars_tick` 等约束。

输入过长会抬高 **TTFT** 与总耗时（业界「有效上下文工程」：把最可行动事实靠近用户指令、压缩低价值重复）。

### 4.5 工具执行

- `gather_tool_observations` **顺序**执行 `plan.commands` 中的命令；多工具时延迟累加。
- 与 F08 一致：授权语义由冻结工具面保证；本 SPEC 关注 **耗时与并发潜力**。

### 4.6 延迟预算表（示意）

以下为上界量级说明，非保证值；实际取决于模型、网络与输入大小。

| 因子 | 默认/典型 | 备注 |
|------|-----------|------|
| Plan LLM 次数 / tick | 1–`max_tool_rounds_per_phase` | 无工具则通常 1。 |
| Do LLM 次数 / tick | 同上 | |
| Check / Act | 各 0–1（act 可 skip） | |
| RETRY 追加 | +Plan+Do 各一轮循环上界 | 受 `max_commands_per_tick` 等约束。 |
| HTTP 超时 / 次 | 默认 120s | 可用 `phase_llm.*.timeout_sec` 下调。 |
| 工具命令 | 顺序执行 | 并行化为 Phase 2 实现项。 |

---

## 5. 根因分类（R1–R7）

| 编号 | 描述 |
|------|------|
| **R1** | 多 phase **串行** LLM；Check RETRY 时 **倍增** Plan+Do。 |
| **R2** | Plan/Do 内 **多轮 ReAct**，每轮至少一次上游调用。 |
| **R3** | 上游模型与 **高默认 HTTP 超时**、大 `max_tokens` 拉长单次 RTT。 |
| **R4** | **提示词与工具观测**体积过大 → TTFT 与生成时间上升。 |
| **R5** | 工具 **顺序**执行，多工具累加延迟。 |
| **R6** | 每 phase `memory.update_run` 等 **同步 I/O**（需 profiling 验证占比）。 |
| **R7** | 同一 tick 内 **重复图解析 / 重复属性读取**（与本文第 7 节重复点 D1、D2 交叉）放大 DB 与 CPU，恶化尾延迟。 |

---

## 6. 业界实践对照（规范性引用，非绑定实现）

- **可观测性**：对每次 tick 记录各 phase wall time、HTTP status、超时次数；对齐 RED 指标思路（请求率、错误率、延迟分布）。
- **编排**：减少无收益 LLM 轮次；在预算内使用更小模型或更短 phase 做 gate（产品化须 ADR）；**deadline** 沿 tick 传递，避免多 phase 各自占满 120s。
- **上下文**：压缩 tool manifest、强调按需 `primer <section>`（见系统 primer 文档）；静态 system 片段的缓存与「断点」思想可与供应商能力对齐，落地另附 ADR。
- **工具**：在 **只读且无副作用** 的前提下探索 **并行** 执行（须不违背 F08 审计与顺序语义约定，见路线图 Phase 2）。
- **产品**：流式首 token、两阶段答复（先短后全）可作为后续产品 SPEC。

---

## 7. 代码重复与收敛（须与实现迭代同步）

F10 要求将下列项以表格维护（重复点 / 涉及文件 / 风险 / 建议收敛形态）。

### 7.1 重复点一览

| ID | 涉及文件（示例） | 风险 | 建议收敛形态 |
|----|------------------|------|----------------|
| **D1** | `npc_agent_nlp.py`、`worker.py` | 同一 invoker 上 **两次** `resolve_caller_node_id` / `location` / 房间展示名解析 | 在 tick 入口构造 **`CallerGraphSnapshot`**（不可变：`caller_node_id`、`caller_location_node_id`、`caller_location_display_name`），传入 worker 与 snapshot/primer 路径，worker 内不再重复解析（除非定义缓存失效条件）。 |
| **D2** | `npc_agent_nlp.py`、`worker.py` | `service_id`、`model_config_ref`、`attrs` 重复解析；worker 再次 `query(Node)` | **`NpcAgentTickInputs`**（或 `AicoTickContext`）：含已加载 `agent`/`attrs`、已解析 `cfg`；非降级路径不重复查库。 |
| **D3** | `llm_pdca.py` | `_gather_tools_after_llm` 与 `_phase_react_loop` 重复 `executor + context` 与 gather 编排 | 与本文第 8 节合并：**`ToolGatherRoute` / `ToolRuntimeView`** 单点解析。 |
| **D4** | `llm_pdca.py` | `_call_llm` 与 `_call_llm_dual_track` 各自 `merge_phase_config` + `to_llm_call_spec` | 私有 **`_spec_for_phase(phase, ctx)`**，行为不变。 |
| **D5** | `worker.py` 等 | YAML `extra` 布尔手写 `str`/`bool` 分支 | **`parse_bool_extra(extra, key, default)`** 小工具，集中解析。 |

### 7.2 根因与重复点交叉

- **R7** 与 **D1、D2**：重复查询直接加重 **R6/R4** 相关成本（DB 与 payload 准备）。

---

## 8. 公共逻辑与工具可用性单点判定

### 8.1 问题

若在 Plan、Do、ReAct 多轮、Check RETRY 等路径上 **分散判断**「是否具备工具执行能力」「executor/context 是否存在」「本轮是否仍允许 gather」，易出现 **不一致**、**难测** 与 **无谓分支成本**。

### 8.2 要求

- 将「本 tick / 本 phase 是否可走工具路径」的 **可复用结论** 收敛到 **单一解析过程**（函数或小型不可变视图）。
- 典型输入：`PreauthorizedToolExecutor`、`ResolvedToolSurface`、`ToolGatherBudgets`、当前 `ToolGatherCounters`、`FrameworkRunContext`（如需要）。
- 典型输出字段（命名示例）：`tools_enabled`、`executor`、`tool_context`、`skip_reason`（仅日志）、`allowed_command_summary`（脱敏摘要）。

### 8.3 与 F08 的关系

- 授权与集合成员语义仍以 **F08 R2**（`build_resolved_tool_surface` + `PreauthorizedToolExecutor`）为真源；单点判定 **不削弱** 授权，只 **集中读取** 已有结构。
- 当前分散点（待收敛）：`llm_pdca.py` 中 `_phase_react_loop`、`_gather_tools_after_llm` 对 `_pre_tool` / `_tool_command_context` 的空检查及后续 `gather_tool_observations` 调用。

### 8.4 验收暗示（代码审查）

- 新增工具门控逻辑 **必须经过** 上述统一入口。
- 单元测试对入口覆盖：**budget 耗尽**、**空 surface**、**缺 `tool_command_context`** 等分支 **一次** 即可，无需在每个 phase 复制用例。

---

## 9. 目标 SLO 与度量

### 9.1 建议 SLO（分级，可部署相关调整）

以下数值为 **建议起点**，上线前须结合 **模型、地域、内网/公网** 校准：

| 环境 | 建议 p95 tick（wall） | 说明 |
|------|------------------------|------|
| 内网 / 低延迟上游 | **≤ 30s** | 同一区域、专线或小包。 |
| 公网 API | **≤ 60s** | 与当前默认 HTTP 超时量级一致时，SLO 应 **低于** 单次调用超时 × 最小必要调用次数，否则无诊断空间。 |

同时跟踪 **p50** 与 **超时率**（HTTP timeout、非 2xx）。

### 9.2 度量字段（可与 F03 文档「AICO 优化可观测」小节日志协同）

- 每个 phase：**开始时间戳、结束时间戳**、**上游一次调用的 RTT**（若一次 phase 内多轮，则多段）。当前实现：`command_trace` 中追加 ``step: phase_timing``（``scope`` 为 ``llm`` / ``tool_gather`` / ``phase_total``，含 ``elapsed_ms``；ReAct 下含 ``round``）。
- 可选：**system+user 字符量估计**或 token 估计（若 provider 不返回，则记录字节长度作 proxy）。
- 写入位置：`command_trace` 扩展字段、或 AICO 专用可观测日志；须 **不泄露** 密钥与完整用户隐私正文（脱敏策略见 F03）。

若当前 schema 不足，在实现 issue 中列明 JSON 字段建议，**本文先约定语义**。

---

## 10. 分阶段路线图

| 阶段 | 内容 |
|------|------|
| **Phase 0** | **仅观测**：补齐各 phase wall time、payload 大小、HTTP 状态；零行为变更。 |
| **Phase 1** | **纯配置**：`phase_llm.*.timeout_sec`、`max_tokens`、减小 `tool_gather_max_rounds_per_phase`、将 `act` 设为 `skip` 或更短 prompt（与现有 `PhaseLlmMode` 语义一致）。 |
| **Phase 1b** | **结构微重构**：D4、D5；单测锁定 LLM 调用参数与行为不变。 |
| **Phase 1c** | **tick 数据单例**：D1+D2；`run_npc_agent_nlp_tick` 构造 `CallerGraphSnapshot` + `NpcAgentTickInputs` 传入 `worker.create`；验收：同 tick 内 `resolve_caller_node_id` 调用次数上界（mock）。 |
| **Phase 2** | **行为与并发**：只读工具 **并行**（须 ADR）、可选 **fast tick** 编排（合并 phase 等）、**D3 + 第 8 节工具单点**；凡改动 `llm_pdca.py` 编排者 **须另附 ADR**。 |

Phase 1 与 Phase 1b/1c 可 **并行开 PR**；Phase 2 依赖 ADR 评审。

---

## 11. 验收清单（文档级）

- [x] 运维能在一次 tick 的日志或 trace 中区分 Plan/Do/Check/Act 各自耗时（``phase_timing``）。
- [x] 配置手册中列出与延迟相关的 `agents.llm` / `extra` / `phase_llm` 键及安全范围（见上文 §13 与 `settings.dev.yaml` 示例）。
- [x] 重复点 D1–D5：D4/D5（``_spec_for_phase``、``parse_bool_extra``）、D1/D2（``NpcAgentTickInputs`` / ``CallerGraphSnapshot``）、D3（``ToolRuntimeView``，见 ADR-F10）已在代码路径落地并配单测。
- [x] 工具单点判定（第 8 节）有单元测试（``test_tool_runtime_view.py``、``test_llm_pdca_framework``）与 ADR-F10。
- [ ] 新 SLO 达成情况在发布说明或运维看板中可回顾（周期复盘）。

---

## 12. 与相关 SPEC 的边界

| 文档 | 边界 |
|------|------|
| **F03** | 实例配置、`tool_allowlist`、可观测日志开关；本文引用其配置形状与日志位置。 |
| **F08** | 工具授权、ToolGather 契约、command_trace 语义；本文不修改其安全模型。 |
| **F09** | L3 管线边界；本文不重新定义四层。 |

---

## 13. 运维调参速查（Phase 1，可选覆盖）

以下键写入 **`agents.llm.by_service_id.<service_id>`**（或与 `settings.*.yaml` 深度合并）。回滚即删除覆盖或恢复默认值。

| 键 / 路径 | 作用 | 建议试算范围 | 风险 |
|-----------|------|----------------|------|
| `max_tokens` | 限制单次生成长度 | 1024–2048 试起 | 过长回答被截断 |
| `extra.tool_gather_max_rounds_per_phase` | Plan/Do 内 ReAct 最大轮数 | 2（默认 3） | 多轮工具场景可能未跑满 |
| `extra.tool_gather_max_commands_tick` | 每 tick 总命令上限 | 保持默认或略降 | 复杂任务工具被截断 |
| `nodes.attributes.phase_llm`（`npc_agent`） | 每 phase 的 `timeout_sec`、`mode: skip` 等 | 见 [`agent_node_phase_llm.py`](../../../../backend/app/game_engine/agent_runtime/agent_node_phase_llm.py) 与 F03 | 与 YAML 合并顺序见 `resolve_agent_llm_config` |

**开发环境示例**：[`backend/config/settings.dev.yaml`](../../../../backend/config/settings.dev.yaml) 对 `aico` 合并了 `max_tokens` 与 `extra.tool_gather_max_rounds_per_phase`；`phase_llm` 请在种子或节点属性中配置（不在 `AgentLlmServiceConfig` 顶层字段）。
