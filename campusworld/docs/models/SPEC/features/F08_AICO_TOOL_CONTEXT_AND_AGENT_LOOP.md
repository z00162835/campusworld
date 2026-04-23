# F08 — AICO 工具调用与命令上下文（Command-as-Tool）

> **Architecture Role：** 在 **F03** 所定义的默认助手 **AICO** / 通用 **`npc_agent`**（`decision_mode: llm`）NLP 路径上，规定 **通过命令注册表执行受控命令、将可观测输出作为 LLM 上下文** 的契约；补齐「世界语义经命令取得 → 再经 LLM 组织答复」的设计初衷，并与 **F04**（`@`）、**F05**（`agent` 状态）及命令授权模型对齐。整体 **Agent 四层架构** 的 **规范真源** 见 [**F09**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)。

**文档状态：Draft**

**交叉引用：** [**F09**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)（CampusWorld Agent 四层架构：L1–L4、映射与边界）、[**F03**](F03_AICO_DEFAULT_SYSTEM_ASSISTANT.md)（AICO 实例、`tool_allowlist`、PDCA + LLM 基线）、[**F02**](F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)（`npc_agent`、运行记录）、[**F04**](F04_AT_AGENT_INTERACTION_PROTOCOL.md)（`@<handle>`）、[**F05**](F05_AGENT_COMMAND_LIST_AND_STATUS.md)（Agent 列表/状态）、[**F06**](F06_CAMPUSLIBRARY_KNOWLEDGE_WORLD.md)（CampusLibrary 知识检索，与本特性互补）。

**实现锚点：** `[backend/app/commands/npc_agent_nlp.py](../../../../backend/app/commands/npc_agent_nlp.py)`（`run_npc_agent_nlp_tick`）、`[backend/app/game_engine/agent_runtime/frameworks/llm_pdca.py](../../../../backend/app/game_engine/agent_runtime/frameworks/llm_pdca.py)`（`LlmPDCAFramework`、`_phase_react_loop`、`_call_llm_dual_track`）、`[backend/app/game_engine/agent_runtime/worker.py](../../../../backend/app/game_engine/agent_runtime/worker.py)`（`LlmPdcaAssistantWorker`）、`[backend/app/game_engine/agent_runtime/resolved_tool_surface.py](../../../../backend/app/game_engine/agent_runtime/resolved_tool_surface.py)`（`build_resolved_tool_surface`、`PreauthorizedToolExecutor`）、`[backend/app/game_engine/agent_runtime/tool_gather.py](../../../../backend/app/game_engine/agent_runtime/tool_gather.py)`（`gather_tool_observations`、`parse_tool_invocation_plan_from_text`、`ToolGatherBudgets`）、`[backend/app/game_engine/agent_runtime/tool_calling.py](../../../../backend/app/game_engine/agent_runtime/tool_calling.py)`（`ToolSchema`、`ToolCall`、`ToolResult`、`ConversationTurn`、`CompleteWithToolsResult`，**provider-agnostic tool_use 协议**）、`[backend/app/game_engine/agent_runtime/aico_world_context.py](../../../../backend/app/game_engine/agent_runtime/aico_world_context.py)`（`build_ontology_primer`、`build_world_snapshot`、`build_llm_tool_manifest`）、`[backend/app/game_engine/agent_runtime/llm_client.py](../../../../backend/app/game_engine/agent_runtime/llm_client.py)`（`LlmClient.supports_tools`、`complete_with_tools`）、`[backend/app/game_engine/agent_runtime/tooling.py](../../../../backend/app/game_engine/agent_runtime/tooling.py)`（`RegistryToolExecutor`、`ToolRouter`）、`[backend/app/commands/agent_command_context.py](../../../../backend/app/commands/agent_command_context.py)`（`command_context_for_npc_agent`）、`[backend/app/commands/system_primer_command.py](../../../../backend/app/commands/system_primer_command.py)`（`primer` 系统命令）、`[backend/app/commands/graph_inspect_commands.py](../../../../backend/app/commands/graph_inspect_commands.py)`（`find` / `describe` 系统命令）、`[backend/app/commands/invoke.py](../../../../backend/app/commands/invoke.py)`（进程内命令网关语义）。**本 SPEC 为需求与契约；实现决策见 [ADR-F08-Tool-Gather](../../../../architecture/adr/ADR-F08-Tool-Gather.md)。**

---

## 1. Goal

- 定义 **Command-as-Tool**：在单次 **`aico` / `@<handle>`** tick（或实现约定的有限步扩展）内，经 **`RegistryToolExecutor`** + **`ToolRouter`**（`tool_allowlist`）+ **`command_context_for_npc_agent`** 执行 **已注册命令**，将 **`CommandResult.message`** 及实现白名单允许的 **`CommandResult.data`** 子集，规范化为 **`ToolObservation`** 文本，注入后续 **LLM** 阶段，使助手答复 **以世界中真实命令输出为依据**，而非仅凭模型先验。
- **工具语义面向 Agent**：注册表中的命令名与参数应对 Agent **可读、可组合**（例如 `help`、`look`、自省类 `agent_tools`）；候选集、组合策略与 **PDCA 各阶段是否调用工具** 由本节与 §6 规定 **策略位**（实现可配置，初稿给出 **v1 默认建议**）。
- **执行路径**：工具调用等价于「在 **同一进程** 内完成与 SSH 会话 **相同鉴权链** 的命令执行」（`authorize_command`、策略表达式、`command_policies`），**不是**由外部客户端再开一条 HTTP/SSH 去执行字符串；语义上与用户手工输入 `look` 一致，调用方为实现内的 **`CommandContext`**（见 §7）。
- 与 **F03** §5.5 **上下文整合** 的关系：**`memory_context`（LTM）** 与 **ToolObservation（命令观测）** 为两类注入源；合并顺序与优先级见 §6。

### 1.1 在整体 Agent 架构中的位置

本 SPEC（Command-as-Tool、ToolGather、**AICO** 在 L3′/L4′ 的特化）建立在 **`npc_agent` 四层架构**之上。**L1–L4 定义、双视角图示、与 F02–F08 及 F07 的映射与边界** 的 **规范真源** 见 [**F09 — CampusWorld Agent 四层架构**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)；本文 **不重复** 全表与各层长文补充。

### 1.2 AICO 特化（L3′ / L4′）

- **AICO 与公共框架**：**AICO** 仍属 **`npc_agent` + F03** 默认实例，应 **复用** L1–L3 的 **公共能力**（tick 入口、Worker、框架协议、工具执行与运行记录等）。**禁止**将 **仅适用于 AICO** 的 L3 策略偏好、L4 经验包选择与 **通用 `npc_agent`** 无差别混写在同一实现单元中。
- **AICO 特化须有独立实现单元**：在 **L3′（AICO 思考管线特化）** 与 **L4′（AICO 经验/Skill 组合）** 上应有 **独立模块或子包**（如 `aico/` 编排器、AICO 专属 `preflight`、默认 prompt 与工具偏好），**调用** 公共 L2/L3 API，**不**复制 L1 数据语义或绕过 **`authorize_command`**。公共实现 **不**硬编码 `aico`（种子、默认 YAML 键等约定处除外）。
- **验收暗示**：能区分「改 L1 本体」「改 L2 命令工具」「改 L3 通用思考框架」与「仅改 AICO 的 L3′/L4′」；测试可对通用 `npc_agent` 与 **`service_id=aico`** 分别覆盖。

---

## 2. Non-Goals

- 不将 **某一厂商** 的 Function Calling / JSON Schema 定为 **唯一** 互操作格式（实现可选用结构化计划、或宿主解析的轻量协议，见 §7）。
- 不要求 **v1** 即支持「流式多轮对话中任意时刻用户中断」的完整交互模型（可与 F04 会话产品迭代对齐）。
- **不替代** **[F06](F06_CAMPUSLIBRARY_KNOWLEDGE_WORLD.md)** 的图/向量检索；**CampusLibrary** 与 **命令工具上下文** 互补：前者偏静态/入库知识，后者偏 **当前会话与世界状态** 的可观测文本。

---

## 3. 业界对齐（参考，非规范性依赖）

以下仅作 **产品/架构对标**，实现以 CampusWorld **命令注册表与授权** 为准。


| 范式                                                  | 可借用的思想                                                 |
| --------------------------------------------------- | ------------------------------------------------------ |
| **Claude Code 类助手**                                 | 受控能力集、步骤可审计、每步结果以 **人类可读摘要** 进入后续推理。                   |
| **OpenClaw / 仓库级 coding agent 生态**（名称与仓库链接待人工确认后替换） | **Observe → Act** 短循环、**步数/时间上限**、失败时重试或降级为「无工具纯 LLM」。 |


---

## 4. 核心术语


| 术语                   | 含义                                                                                      |
| -------------------- | --------------------------------------------------------------------------------------- |
| **ToolObservation**  | 单次命令执行后，经规范化模板拼接的 **文本块**（含命令名、参数摘要、stdout 等价 `message`、可选 `data` 摘要），供注入 LLM `user` 侧。 |
| **tool_trace**       | 本 tick 内所有工具调用的有序列表；应写入 **`agent_run_records.command_trace`**（与 F02 运行记录一致），供排障与审计。     |
| **preflight_policy** | **可选** 的确定性规则（不经 LLM）：例如对「帮助体系介绍」类意图先执行 **`help help`** 再进入 Do；由产品/运维配置或代码策略表实现。        |
| **llm_tool_plan**    | **Plan 阶段** LLM 输出的 **结构化计划**（如受限 JSON：待执行命令列表及参数）；解析失败时 **降级**（见 §7）。                  |


---

## 5. 与 F03 PDCA 的关系

### 5.1 实现要点（与 §5.2 对齐）

- **F03** 约定 **`tool_allowlist`** 与注册表工具面；**`agent_tools`** 可列出白名单内工具。
- **初始化冻结权限面**：`LlmPdcaAssistantWorker.create` 构建 **`ResolvedToolSurface`**（`tool_allowlist` ∩ `get_available_commands(tool_ctx)`，并移除默认禁止项如 **`aico`**），运行时由 **`PreauthorizedToolExecutor`** 执行命令（集合成员校验 + `execute`，避免 tick 内热路径重复 `authorize_command`；权限与策略的交集在构造面时一次性等价于原链）。
- **ToolGather**：对 LLM 输出中解析到的 **`llm_tool_plan`（JSON，`commands` 数组，0..N 条）** 顺序执行，生成 **ToolObservation**，写入 **`command_trace`**；**各 PDCA 阶段**在阶段 LLM 调用之后均可解析并执行一批命令（多工具、多阶段），再注入**后续**阶段 LLM 的 `user` 侧（见 `llm_pdca.py`）。
- **上限**：`agents.llm` 的 `extra` 可选键 `tool_gather_max_commands_tick`、`tool_gather_max_chars_tick`、`tool_gather_max_commands_phase`、`tool_gather_max_rounds_per_phase`（见 `tool_gather.py`）。

### 5.2 方案 A（v1 编排说明）

1. **Plan（LLM）**：输出自然语言与/或 **`llm_tool_plan`** JSON；若 **`phase_llm.plan` = skip**，可为空计划。
2. **ToolGather（Plan）**：对解析到的每条命令，在 **冻结权限面**内执行；汇总为 **ToolObservation**。
3. **Do（LLM）**：`user` 含 **用户消息**、**Plan 输出**、**Plan 阶段 ToolObservation**、**`memory_context`**（见实现拼接顺序）。
4. **ToolGather（Do / Check）**：对 Do、Check 阶段 LLM 输出中若含 JSON 计划，同样可执行并注入后续阶段（**Act** 阶段默认不再从 LLM 输出追加工具执行，以避免与「润色-only」冲突；可配置迭代）。

### 5.3 方案 B（**后续**）

多轮 **LLM ↔ 工具**：直到模型输出 **`FINAL`** 或明确表示无需再调用工具。更接近深度 **agent 循环**，复杂度高；**v1 可不采纳**。

```mermaid
flowchart LR
  userMsg[UserMessage]
  planLLM[PlanPhase_LLM]
  toolExec[ToolGather_Registry]
  doLLM[DoPhase_LLM]
  checkLLM[CheckPhase_LLM]
  actLLM[ActPhase_LLM]
  userMsg --> planLLM
  planLLM --> toolExec
  toolExec --> doLLM
  doLLM --> checkLLM
  checkLLM --> actLLM
```



---

## 6. 各 LLM 阶段与工具策略（v1 建议）

以下策略为 **初稿默认**，人工审核后可改为「配置驱动」或「仅 AICO 默认」。


| 阶段             | 是否使用工具            | 说明                                                                                                       |
| -------------- | ----------------- | -------------------------------------------------------------------------------------------------------- |
| **Plan**       | **可选**            | 输出 **`llm_tool_plan`**（推荐）或纯文本计划；**不直接执行**命令，除非实现将「解析 + 执行」合并为同一子阶段（不推荐）。                                |
| **ToolGather** | **必执行（当有合法计划项时）** | 非 LLM 阶段；执行 0..N 条命令，受 **上限** 约束（§8）。                                                                    |
| **Do**         | **间接**            | 基于 **ToolObservation** 生成草稿答复；**本阶段不再默认执行新命令**（避免与方案 B 混淆）。                                              |
| **Check**      | **通常否**           | 以 Do 草稿与 F03 **check** prompt 为主；若需二次核对世界状态，实现可选用 **只读** 命令（如 `look`），须在 **tool_allowlist** 与策略中显式允许并计次。 |
| **Act**        | **否**             | 润色最终用户可见文本；不引入新观测。                                                                                       |


**候选与组合：**

- **候选工具集** = **`ToolRouter.filter(RegistryToolExecutor.list_tool_ids(...))`**，与 **F03** `tool_allowlist` 一致。
- **组合**：允许多条命令顺序执行（如 `help help` → `agent_tools aico`）；**顺序**由 Plan 或 **preflight_policy** 决定；总条数与总字符 **封顶**（§8）。

**终止条件：**

- ToolGather 在 **N 条命令执行完毕**、**超限时截断**、或 **命令失败**（按策略：中止 tick / 跳过该条 / 将错误文本写入 ToolObservation）时结束。

---

## 7. 工具选择与参数、调用形态

- **v1 无原生 function-calling 时**：推荐 **Plan 输出受限 JSON**（示例形状，非最终 schema）：
  ```json
  {
    "commands": [
      { "name": "help", "args": ["help"] },
      { "name": "look", "args": [] }
    ]
  }
  ```
  解析失败时：**降级** 为仅 LLM、或执行 **单条安全默认**（如仅 `help`），行为由实现与 **preflight_policy** 共同定义。
- **调用形态**：与「用户在 SSH 输入 `look`」**语义等价**，但在实现上为 **进程内直接调用** `Command.execute`（经 `RegistryToolExecutor`），**不**经过外部客户端；须完整走 **`authorize_command`** 与 **`command_context_for_npc_agent`**（含 **`service_account_id`** 时的服务账号权限）。
- **预留**：若 LLM 提供商支持 **tool_calls**，实现可选用 **结构化 tool_calls** 与上述 JSON 计划 **二选一**，本 SPEC 不强制唯一路径。

---

## 8. 安全与不变量

- **禁止默认递归**：工具上下文中 **不得** 默认再次调度 **`aico` / `@` NLP**（避免无限嵌套）；若未来允许「子助手 tick」，须单独 **深度上限** 与 **标识符**。
- **每 tick 上限**：**最大命令条数**、**ToolObservation 总字符**、**wall-clock 时间**；超限截断并记入 **tool_trace**。
- **`CommandResult.data`**：仅允许 **白名单键** 进入 ToolObservation（防泄漏大图 JSON、内部 id）；默认可仅使用 **`message`**。
- **授权**：与 **`authorize_command`**、**`command_policies`**、F11 数据访问策略 **一致**；**不**因「Agent 调用」绕过审计。

---

## 9. 可观测性

- **`agent_run_records.command_trace`**：每条记录建议包含：`command_name`、`args` 摘要、`success`、`message_len`、可选 **内容哈希**（非存全文）。
- 日志与排障：工具失败原因应可区分 **授权拒绝**、**未知命令**、**业务 Error** 与 **系统异常**（与 SSH **System Error** 分层）。

---

## 10. 验收标准（建议）

**人工 / SSH（DB 已迁移且种子就绪）：**

- 对「介绍 `help` 命令本身」类问题，在启用本特性的构建上，**至少一次** 将 **`help`（或等价）命令输出** 纳入 **Do 阶段上下文**，最终 **`CommandResult.message`** 为自然语言答复（非未捕获的网络 DNS 类 **System Error** 裸传；该类错误应在 LLM 前或工具层被处理/降级）。
- **`agent_tools <service_id>`** 所列工具与 **`tool_allowlist`**、策略过滤一致。

**自动化（方向性，实现可后置）：**

- 与 **`tests/commands/test_registry_tool_executor_auth.py`** 授权语义一致：工具执行路径 **不拓宽** 权限。
- 与 **`tests/commands/test_npc_agent_nlp.py`** 等 mock 路径兼容：可在 mock LLM 下断言 **ToolObservation** 注入 **Do** 的输入拼接（具体断言由实现 PR 补充）。

---

## 11. 与 F03 / ADR 的后续动作（非本文件范围）

- 实现采纳后，建议新增 **ADR**（例：ADR-F08-AICO-Tool-Context）描述 **ToolGather** 插入点与与 **`LlmPDCAFramework`** 的代码级决策。
- **F03** 可在 §5.5 保持摘要，以 **指向本 SPEC** 为 **扩展来源**（见 F03 交叉引用）。

---

## 附录 A — `ToolObservation` 文本模板（示例）

```
--- tool_observation begin ---
[1] command=help args=[help]
ok=true
message:
<CommandResult.message 原文或截断>
--- tool_observation end ---
```

截断策略与编码由实现定义，须符合 §8 上限。

---

## 12. v2 刷新 — 工具优先 harness（2026-04）

原 §5–§9 保留为 **v1 基线**。本节描述 **v2 刷新**，其动机是：观测日志表明 Plan 阶段的 LLM 很少主动调用命令、对世界本体认识不足；借鉴业界（Anthropic effective context engineering、OpenAI tools、长时 agent 的 ReAct 循环）后，做以下系统性调整。**v2 与 v1 在协议/数据面向后兼容**，行为变化均为「增强」。

### 12.1 Provider-agnostic Tool Calling 抽象

工具调用从「实现即 JSON-in-text」升级为「协议中立的 neutral primitives」：

- 公共数据类型定义在 [`tool_calling.py`](../../../../backend/app/game_engine/agent_runtime/tool_calling.py)：`ToolSchema`、`ToolCall`、`ToolResult`、`ConversationTurn`（`TextTurn | ToolResultsTurn`）、`CompleteWithToolsResult`。
- `LlmClient` 协议（[`llm_client.py`](../../../../backend/app/game_engine/agent_runtime/llm_client.py)）新增两个可选方法：
  - `supports_tools() -> bool` —— 客户端是否理解上述 primitives（默认 `False`）。
  - `complete_with_tools(*, system, turns, tools, call_spec) -> CompleteWithToolsResult` —— 原生 `tool_use` / `tools` 通道。
- **任何 provider** 都可以在适配层把 neutral primitives 映射到厂商线路（见 `minimax_anthropic.py` 对 Anthropic `tool_use` 的映射）。**framework 不感知厂商**。

**Dual-track 调度**（`LlmPDCAFramework._call_llm_dual_track`）：

1. 若 `supports_tools()` 返回 `True` 且当前有 schemas，走 `complete_with_tools`，返回 `(text, tool_calls)`。
2. 否则走既有 `complete(system, user)` 文本通道；`_tool_calls_from_text` 解析 `{"commands": [...]}` JSON 作为 fallback。
3. 两条通道的后续执行与观测注入完全一致，**不**引入双份代码路径。

### 12.2 多轮 ReAct（per-phase）

- `ToolGatherBudgets.max_tool_rounds_per_phase` 默认从 `1` 升为 `3`（`tool_gather.py::tool_gather_budgets_from_agent_extra`）。
- `LlmPDCAFramework._phase_react_loop` 在 **同一 PDCA 阶段** 内执行「LLM → 工具 → 观测 → LLM ...」直到：
  a) LLM 不再要求工具；
  b) 达到 `max_tool_rounds_per_phase`；
  c) 触达 `max_commands_per_tick` 或 `max_chars_observations_per_tick`。
- 每一轮的观测以 `ToolResultsTurn` 追加到会话 turns 列表；fallback 通道把它们序列化为 `Tool observations:` 文本块。
- 该改动使 AICO 可以在单个 Plan 中「先 `look`、再 `find`、再下结论」而不是一次只能调一个工具。

### 12.3 Tier-ized Context（分层上下文拼装）

按 Anthropic "place the most actionable facts nearest the user instruction" 的建议分层：

| Tier | 内容 | 位置 | 生命期 |
|---|---|---|---|
| **1（静态）** | 身份、不变量、工具契约 | **system_prompt**（`settings.yaml` + `identity_and_invariants_snippet()` 可选前置） | 整个 tick 稳定 |
| **2（每 tick）** | `World snapshot`（身份/当前房间/已安装世界）+ `Tools available`（manifest 文本/schemas） | **Plan 阶段首个 user turn** | 仅 Plan；Do/Check/Act 不重复 |
| **3（按需）** | 完整 primer、房间详情、命令参数说明等 | **工具调用返回值**（`primer <section>`、`describe <id>`、`find ...`，契约见 [F01](../../../commands/SPEC/features/F01_FIND_COMMAND.md)） | 只在被调用时产生 |

**拼装入口**：
- 静态：`settings.yaml` 的 `agents.llm.by_service_id.aico.system_prompt` + `phase_prompts`（v2 已全面重写）。
- Tier-2：`LlmPdcaAssistantWorker.create` 在 worker 生命期内计算 `build_llm_tool_manifest(surface, command_registry, session=...)`；每 tick `run_npc_agent_nlp_tick` 计算 `build_world_snapshot_from_session(...)`，二者通过 `payload.world_snapshot` / `payload.tool_manifest_text` 传入，由 `_assemble_plan_user` 组装。
- Tier-3：由 LLM 自行决定是否调用 `primer` / `find` / `describe` / `look` 等 **新增工具**，其输出自然成为下一轮 ReAct 的观测。

### 12.4 Check 阶段守门与 `RETRY` 信号

Check 阶段不再只做「通过/不通过」标签，而引入可选 **重试信号**：

- Check 输出中若出现 `RETRY: need_tools=<a,b,c>`（单行，tool 名用逗号分隔，匹配 `_CHECK_RETRY_RE`），framework 解析为 `["a", "b", "c"]`。
- 若 `tool_gather_counters` 仍在预算内，framework 追加一条「Guardrail note: 要求调用 <tools>」的提示再跑一次 Plan → Do（每 tick 最多一次，避免无限递归）。
- 该信号与失败标签共存：Check 仍可同时给出「error」语义；二者在 `command_trace` 中以 `check_retry_triggered` 条目显式记录。

### 12.5 默认工具面扩展 — Discovery Suite

`ensure_aico_npc_agent`（[`seed_data.py`](../../../../backend/db/seed_data.py)）默认 `tool_allowlist` 扩为：

```
help, look, time, version, whoami,
primer, find, describe,
agent, agent_capabilities, agent_tools
```

- `primer` — 从 `docs/models/SPEC/AICO_SYSTEM_PRIMER.md` 分节检索系统本体；Tier-3 主力。
- `find` — Evennia `@find` 风格的图检索（列表工具）。v3 支持 `-n` / `-des` / `-t` / `-loc` / `-l` / `-a` 与 AND 组合查询。**完整契约与性能策略见** [`F01_FIND_COMMAND`](../../../commands/SPEC/features/F01_FIND_COMMAND.md)。别名：`@find`、`locate`。
- `describe <id | #<id> | name>` — 单节点详情（属性预览 + 出边采样），对应 Evennia `examine`。别名：`examine`、`ex`。

三者均 **只读**、**不递归 AICO**、与既有 `authorize_command` 路径一致。审计与权限不变。

### 12.6 Primer 作为 SSOT

- Primer 文件：[`docs/models/SPEC/AICO_SYSTEM_PRIMER.md`](../../AICO_SYSTEM_PRIMER.md)。
- 九个语义段（Identity / Structure / Ontology / World / Actions / Interaction / Memory / Invariants / Examples），每段可独立注入或经 `primer <section>` 命令按需拉取。
- 验证脚本：[`backend/scripts/validate_system_primer.py`](../../../../backend/scripts/validate_system_primer.py) —— 检查段完整性、占位符、命令/节点类型引用的存在性。
- 编辑该文件后：建议同步运行 `pytest tests/commands/test_primer_command.py`，并在开发 loop 中依赖 `primer_reload_if_stale` 动态重载。

### 12.7 Golden 行为测试

[`tests/game_engine/test_aico_harness_golden.py`](../../../../backend/tests/game_engine/test_aico_harness_golden.py) 覆盖：

1. Tier-ized ordering — Plan user turn 中 World snapshot / Tools / Memory / User message 顺序。
2. JSON fallback — 无 `supports_tools` 的客户端走文本通道 + JSON 解析。
3. Native tool_use — 实现 `complete_with_tools` 的客户端收到 schemas，ToolResultsTurn 在下一轮注入。
4. Multi-round ReAct — 连续工具调用在预算内循环、预算外终止。
5. Check RETRY — Check 返回 `RETRY: need_tools=...` 时 Plan/Do 再跑一次且恰一次；Check 不含 RETRY 时不重跑。

### 12.8 与 v1 的兼容性

- 旧 provider 无需改动：`LlmClient.supports_tools()` 默认 `False`，framework 走 v1 JSON 通道。
- 旧 `tool_allowlist`（仅 `help/look/whoami`）继续可用；`build_llm_tool_manifest` 对缺失命令节点仅是忽略。
- 旧 `phase_llm` 配置保持语义；`act` 仍默认 `skip`。
- 观测日志 schema 不变，仅增加 `round`、`channel`（`text|tool_use`）、`tool_call_count`、`check_retry_triggered` 等可选字段。