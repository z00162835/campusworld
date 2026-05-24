# F13 — AICO 命令、交互式会话与流式体验

> **Architecture Role：** 在 [**F03**](F03_AICO_DEFAULT_SYSTEM_ASSISTANT.md)（默认助手 AICO）、[**F04**](F04_AT_AGENT_INTERACTION_PROTOCOL.md)（`@` 协议）、[**F12**](F12_NLP_AGENT_MULTI_TURN_SESSION_MEMORY.md)（会话 STM / 线程目录）之上，规定 **`aico` 命令族** 的交互升级：**REPL（`-i`）**、**线程列表/删除/历史（`-l` / `-d` / `-his`）**、**壳层转义（`!`）**，以及 **`aico` 与 `@aico` 共用的块级流式输出契约**（NDJSON + 能力协商）。**不负责**通用 `npc_agent` Mode B daemon 附身语义扩展（见下文 Non-Goals）。

**文档状态：** Draft

**交叉引用：** [**F08**](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md)（禁止嵌套调度 `aico` NLP）、[**F10**](F10_AICO_PERFORMANCE_AND_LATENCY.md)（tick 延迟与可观测性）、[**F12**](F12_NLP_AGENT_MULTI_TURN_SESSION_MEMORY.md)（STM scope、`agent_conversation_thread`）。

**实现锚点（现状 / 目标）：** [`backend/app/commands/agent_commands.py`](../../../../backend/app/commands/agent_commands.py)（`AicoCommand`）、[`backend/app/commands/npc_agent_nlp.py`](../../../../backend/app/commands/npc_agent_nlp.py)（`run_npc_agent_nlp_tick`）、[`backend/app/game_engine/agent_runtime/aico/profile.py`](../../../../backend/app/game_engine/agent_runtime/aico/profile.py)（AICO 运行时策略）、[`backend/app/game_engine/agent_runtime/conversation_stm_service.py`](../../../../backend/app/game_engine/agent_runtime/conversation_stm_service.py)、[`backend/app/ssh/console.py`](../../../../backend/app/ssh/console.py)（PTY 输入）、[`backend/app/game_engine/agent_runtime/llm_providers/minimax_anthropic.py`](../../../../backend/app/game_engine/agent_runtime/llm_providers/minimax_anthropic.py)（HTTP 流式扩展）、[`backend/config/settings.yaml`](../../../../backend/config/settings.yaml)。

---

## 1. Goal

- **命令面统一**：扩展 `aico` 子命令与 **`@aico`** 共用同一 NLP / 流式语义（见 Decision log **D1**）。
- **交互 REPL**：`aico -i` 进入专用交互页；**Ctrl+Q（`\x11`）** 必须退出并回到系统命令行（**D3**）；**Ctrl+C** 在本模式下表示 **取消当前轮助手生成**（见本文第 17.5 节）。
- **壳层命令**：在 `-i` 内通过 `!<command>` 执行单行注册表命令；**禁止**递归进入 `aico` / `-i`（对齐 F08 不默认递归 NLP）。
- **线程运维**：列表（默认最近 8 条、`-a` 全量）、按 id 删除（二次确认）、按 id 查看历史 transcript（**`aico -his` 默认最近 8 轮、`aico -his … -a` 全量**，见第 7 节与第 17.8 节）。
- **流式体验**：对协商支持的客户端，助手可见正文以 **NDJSON 事件**增量送达；未协商客户端保留 **`CommandResult.message`** 批量语义。
- **持久线程与传输解耦**：对话线程 **独立于**单次 SSH/WebSocket 连接生命周期；用户在新连接上用 `aico -cd` 接续（**D4**）。

## 2. Non-Goals

- **Mode B daemon**：本特性 **不写** `system_shared_exclusive` 附身、抢占锁与 daemon STM 的交互扩展（**D9**）；内置 AICO 以 **per-user assistant** 为准。
- **强取消生成（全局）**：除 **`aico -i` 内 Ctrl+C = 取消当前轮生成**（见第 17.5 节）外，首版 **不**要求任意入口下「全链路、任意 phase 中止远端推理」的完整语义；可与 F12「任意时刻打断」广义 Non-goal 并存。
- **工具观测对用户流式刷屏**：默认 **不**将 ToolGather 原始块写入用户可见流式通道（调试开关另述）。
- **Markdown 终端渲染**：可选产品项，本 SPEC 不强制。

---

## 3. Decision log（已闭合 D1–D11）

| ID | 决策 |
|----|------|
| **D1** | `aico` 与 **`@aico`** 共用 NLP / 流式契约（同一 dispatcher 语义）。 |
| **D2** | **仅方案 A**：客户端（或 SSH 宿主侧）**REPL + 每轮单行命令网关**；**不**在 F13 交付服务端长连接 interactive 子协议（方案 B 另立特性）。 |
| **D3** | **必须**支持 **Ctrl+Q** 退出 `-i`（SSH 与增强 CLI 均验收）。 |
| **D4** | 线程 **持久化**，独立于 SSH session；**STM 与 `transport_session_id`** 跨连接语义须在实现中与 F12 对齐（懒创建 / 合并策略见本文第 8 节）。 |
| **D5** | `aico -d` **二次确认**；**禁止** `--yes` 或等价强制删除标志。 |
| **D6** | 删除线程：LTM 行上 **`conversation_thread_id` → SET NULL**。 |
| **D7** | 流式 wire：**NDJSON**（每行一个 JSON 事件）；WebSocket 可用等价文本帧。 |
| **D8** | **能力协商**；声明流式的客户端 **不得**仅以最终 `message` 作为助手 UI 唯一来源。 |
| **D9** | 与 **Mode B** 无关；F13 仅 **内置 AICO** 场景。 |
| **D10** | `aico -l` **默认 8** 条（按 `last_message_at`）；`aico -l -a` **全量**。 |
| **D11** | 本文件名为规范真源：**`F13_AICO_INTERACTIVE_UPGRADE.md`**。 |

---

## 4. 与 F12 / 流式的关系

- F12 仍将「流式多轮中 **任意时刻用户打断**」列为广义 Non-goal；**本特性收窄**：仅 **`aico` / `@aico` 用户可见答复**要求 **块级流式**（首字节与增量），**不**强制工具轮中途打断或全链路取消令牌。
- STM、`agent_conversation_thread`、compaction 语义仍以 **F12** 与 ADR 为准；F13 **增补**跨 transport 与 `-his` 读路径的 **产品约束**（本文第 8 节）。

---

## 5. Current behavior（基线）

- **`AicoCommand`**：已实现 `-nd`、`-l`、`-cd`、裸消息；**尚未**实现 `-i`、`-d`、`-his`；响应为 **单次 `CommandResult.message`**（无 NDJSON 侧信道）。
- **持久 transcript**：`enable_conversation_stm` 开启且 tick **`ok`** 时，`agent_conversation_stm.messages` **就地追加** user/assistant 对（见 `conversation_stm_service.append_turns_to_messages`）；passthrough **不写** STM。
- **线程目录**：`agent_conversation_thread`；`title_snippet` 由 `touch_thread_metadata` 等在成功 tick 后更新。
- **AICO 运行时策略**：AICO 的 NDJSON tick lifecycle、REPL progress hint 与 observability hooks 由 `AicoRuntimeProfile` 承载；wire shape 与本 SPEC 保持一致。当前实现仍是块级流式/侧信道生命周期，不新增真实 token streaming 或全链路 cancel 能力。

---

## 6. Command surface（须与 `get_usage` 同步）

| 模式 | 语法 | 说明 |
|------|------|------|
| 单轮 | `aico <text...>` | 当前隐式或已绑定线程；助手输出 **流式（协商后）** |
| 新线程 | `aico -nd` · `aico -nd <text>` | 新建线程后可立刻 tick |
| 续线程 | `aico -cd <uuid>` | **持久** thread id；可与当前 SSH **无关**（本文第 8 节） |
| 列表 | `aico -l` · `aico -l -a` | **默认 8** 条 · **`-a` 全量**；**world list** 风格表格 + `data.items` |
| 交互 | `aico -i` · `aico -i <text>` · `aico -i <uuid>` | REPL；可选首条消息或绑定线程后进入；**Ctrl+Q** 退出 |
| 删除 | `aico -d <uuid>` · `aico -d confirm` | **两步确认**（ephemeral + TTL）；删目录行 + 孤儿 STM；LTM **SET NULL** |
| 历史 | `aico -his <uuid>` · `aico -his <uuid> -a` | **批量**文本；**默认最近 8 轮**对话；**`-a`** 输出该线程 id **全部** transcript；数据源见本文第 7 节；非流式 |

**`@aico`**：与上表 NLP/流式语义 **一致**（D1）。

---

## 7. `aico -his` 与持久化

- **展示范围（产品默认）**：`aico -his <uuid>` **默认仅展示该线程下时间上最近的 8 轮对话**；**`aico -his <uuid> -a`** 展示该 uuid **全部**消息（在聚合后的 transcript 上）。**一轮**指一条 `user` 与紧随其后的 `assistant`（若存在）算一轮；尾部不完整轮次仅输出已有消息。与 **`aico -l` 默认 8 / `-a` 全量**（线程列表）并行沿用同一「8 / 全量」心智，但 `-his` 的对象是 **单线程消息**而非线程列表。
- **主数据源**：`agent_conversation_stm.messages`（JSON：`role` / `content` / `ts`），在 STM 开启且成功 tick 写入。
- **非数据源**：`AgentRunRecord.command_trace` 可作运维审计，**不**作为 `-his` 默认可读 transcript（除非产品另行规定）。
- **压缩**：compaction 后列表为 **当前 STM 保留内容**，不是不可变全量日志；须在用户帮助文案中说明。
- **跨 transport**：同一 `conversation_thread_id` 在不同 `transport_session_id` 下可能对应 **多行** STM；`-his` 实现须 **选定一种**：(a) 仅当前 transport 一行；(b) 按 thread 聚合多行按 `ts` 排序。**推荐 (b)** 以匹配 D4「线程持久、换 SSH 续聊」的产品叙述；若选 (a) 须在发行说明中写明限制。**说明与推荐展开见本文第 17.1 节。**

---

## 8. 持久线程 vs SSH 会话（D4）

- **期望**：用户通过 **`aico -cd <uuid>`** 在新 SSH/WS 连接上继续 **同一逻辑对话**。
- **线程表 `transport_session_id`**：实现上 **不得**以「仅创建者 transport」拒绝 **owner + agent** 合法的 `-cd` / tick（列表校验以 **`owner_account_node_id + agent_node_id`** 为主）。
- **STM 唯一键**含 `transport_session_id`：为新连接 **懒创建** `(caller, new_transport, agent, thread_id)` 的 STM 行，或实现 **等价的 transcript 合并展示**；避免用户误以为「换 SSH 丢上下文」。schema 级变更（若有）走迁移与 ADR。

---

## 9. 交互 REPL（方案 A，D2）

- **模型**：宿主进程持有 REPL；**每一轮**用户输入映射为 **一次**现有命令网关调用（与单行 `aico <msg>` 同构）。
- **退出**：**Ctrl+Q（`\x11`）**；可选附加 `/exit`、`quit` 等同义（不改变 Ctrl+Q 为 MUST）。
- **取消生成**：**Ctrl+C** 表示 **取消当前轮正在进行的助手输出**（停止向终端增量写入、中止本轮 tick 侧延续生成）；**不**等同于退出 REPL（见第 17.5 节）。
- **HUD**：进入时打印当前 **`conversation_thread_id`** 与 title（若有）。
- **`!<command>`**：剥离 `!` 后作为 **单行**命令走 `authorize_command` → invoke；**拒绝** `!aico`、`!aico -i` 及可实现列表中的其它递归入口。
- **流式**：每轮流式走本文第 10 节；**reasoning / thinking** 默认 **不**写入用户可见 NDJSON（调试通道另述）。

---

## 10. 流式契约（D7 / D8）

### 10.1 NDJSON 事件

- 每行一个 JSON 对象；**实现冻结**字段：
  - **`kind`**：`delta` | `end` | `error` | `meta`
  - **`delta`**：`text` 字符串片段（助手可见正文增量）
  - **`end`**：可选 `full_text` 或与 `message` 对齐的最终正文校验
  - **`error`**：结构化错误码与可读消息（见 §17.6）
  - **`meta`**：会话/线程绑定、**tick 生命周期**、或其它 **非正文** 元信息（勿含密钥、勿默认携带 tool 原始观测或 reasoning）

**`meta` 字段建议（按用途分层；未列字段保留扩展，客户端 MUST ignore unknown keys）：**

| 字段 | 类型 | 适用 | 说明 |
|------|------|------|------|
| **`kind`** | string | 必填 | 固定为 `meta`。 |
| **`scope`** | string | tick / 正文路由 | **`tick`**：一轮 `w.tick` 生命周期；省略或 **`stream`**：正文流辅助信息（如线程绑定）。 |
| **`phase`** | string | `scope=tick` | **`start`**：即将进入 `LlmPdcaAssistantWorker.tick`；**`complete`**：本轮侧信道 NDJSON 已收尾（见 §10.5）。 |
| **`ok`** | bool | `phase=complete` | 本轮 tick 是否成功（与 `FrameworkRunResult.ok` 对齐）。 |
| **`final_phase`** | string | 可选 | 引擎 phase 枚举（如 `act`）；**SHOULD** 为稳定英文 snake_case，**禁止**承载自由文本长说明。 |
| **`empty_reply`** | bool | 可选 | `ok=true` 但助手正文为空时标 true，便于客户端清状态条。 |
| **`thread_id`** | string (uuid) | 可选 | 当前对话线程；无线程绑定时可省略。 |
| **`correlation_id`** | string | 可选 | 与单次 tick / F10 追踪对齐。 |
| **`trace_id`** | string | 可选 | 分布式追踪 id（若与 `correlation_id` 分离）。 |
| **`model`** | string | 可选 | 模型标识摘要（**禁止** API key）。 |
| **`locale`** | string | 可选 | BCP 47，供客户端选文案。 |
| **`client_hint`** | string | 可选 | **固定枚举**（冻结值见 **§17.12**），供 HUD / 读屏映射；默认路径 **禁止** LLM 生成自由状态句（§16）。在 **`scope=tick` 的 `meta` 上 SHOULD 携带**（H1）。 |

### 10.2 能力协商（D8）

- 客户端在会话或 **每 tick 前置**声明 **`supports_aico_stream`**（或等价 capability 名，实现冻结）。
- **未协商**：服务端 **仅**填充 **`CommandResult.message`**（全文助手答复）。
- **已协商**：助手正文 **必须**经 NDJSON（或 SPEC 等价的 WS 文本帧）送达终端；**不得**要求终端仅靠拼接 `message` 获得流式体验（`message` 可作日志、测试与降级）。

### 10.3 Transport

- **SSH**：增量写入 PTY；约定缓冲策略（按 token / 行 / 定时 flush）避免半行抖动；NDJSON 行须 **完整 `\n` 分隔**。
- **WebSocket / Campus CLI**：文本帧承载 NDJSON 行或与 CLI 协议枚举对齐。

### 10.4 降级

- 流式管道失败时 **降级为批量** `message`；超时遵循 `phase_llm.timeout_sec` 与 F10。

### 10.5 Tick 生命周期 NDJSON（处理中可感知）

**目标**：在助手正文 `delta` 到达之前，客户端即可感知「已进入本轮推理/工具循环」；在正文流结束后有明确「本轮 NDJSON 完结」信号，便于 HUD / 取消态对齐。

**语义边界**：本文 **`tick`** 指 **`LlmPdcaAssistantWorker.tick(...)` 单次调用**（实现锚点：`run_npc_agent_nlp_tick`）。其之前的 STM 锁、LTM 检索、daemon gate 等 **不**发送 `scope=tick` 的 `start`（避免锁失败仍显示「处理中」）。

**MUST（已协商 `supports_aico_stream` 且本轮进入上述 `tick` 调用）**：

1. **Tick 前一行**：在调用 `w.tick` **之前**发送 **一条** `kind=meta` 且 **`scope=tick`**、**`phase=start`** 的行（字段见 §10.1 表）。
2. **Tick 后尾注**：在助手正文 NDJSON 序列的 **`end` 之后**再发送 **一条** `kind=meta` 且 **`scope=tick`**、**`phase=complete`** 的行，并带 **`ok`**；成功时 **`ok=true`**。

**SHOULD**：

- `start` / `complete` 均携带与本 tick 一致的 **`thread_id`**（若有）、**`correlation_id`**。
- `complete` 在 **`ok=true`** 时可带 **`final_phase`**；若正文为空，带 **`empty_reply=true`**。
- `scope=tick` 的 `meta` **SHOULD** 带 **`client_hint`**（枚举与语义见 **§17.12**）；与 `phase`/`ok` 冲突时 **以 `phase`/`ok`/error 为准**。

**失败与悬空禁止**：

- 若已发送 **`phase=start`**，随后 `tick` 抛错或 `ok=false`，**MUST** 在本轮收尾前发送 **`kind=error`**（推荐）或 **`phase=complete`** 且 **`ok=false`**（二选一为主路径，**禁止** silent 结束导致客户端永远停在「处理中」）。与 §17.6 一致。

**排除路径**：

- **Passthrough**（无 HTTP LLM、未进入 `w.tick`）、以及在 **`w.tick` 之前**即返回的门禁错误：**不**发送 `scope=tick` 的 `start` / `complete`。
- **未协商流式**：**不**发送本节 NDJSON；若产品需要人类可读「处理中」，须走 **单独终端提示**（不得冒充协商 NDJSON）。

**与正文流的关系**：正文仍由 **`delta*` + `end`** 承载（可有 **`scope=stream` 或省略 scope** 的 `meta` 作为 thread 绑定，见 §17.3）。客户端 **MUST** 仍将 **拼接助手 UI 正文**限定为 **`delta.text`**；**`scope=tick` 的 `meta` 仅用于状态条或诊断**。

**待闭合细节**（协商载体、完整样例）：见 **§17.2–17.7、17.11**；本节闭合 tick 生命周期；WS 等价帧见 backlog。

---

## 11. `aico -l` 呈现

- 参照 **`world list`**：表头、分隔线、定宽列、`total=` 尾行、`CommandResult.data.items`。
- 建议列：`thread_id`（可缩短显示策略）、`title`、`last_message_at`（可选 `created_at`）。
- **默认 limit=8**；**`-a`** 列出全部（或提高上限至配置上限），调用层扩展 `list_threads_for_owner_agent` 或等价查询。

---

## 12. `aico -d` 删除

1. 校验 **owner** 与 **agent** 与 AICO 节点一致。
2. **二次确认**：`aico -d <uuid>` 写入会话 **`command_ephemeral`** 待删绑定（短时 TTL）；执行 **`aico -d confirm`** 完成删除（第二行无需重复 uuid）。**无** `--yes`。
3. 删除 **`agent_conversation_thread`** 行。
4. 删除所有 **`agent_conversation_stm`** 行满足 `(owner, agent, conversation_thread_id)`（注意 **无 FK** 时需显式删 STM，避免孤儿）。
5. 清理 **`command_ephemeral`** 中该 agent 默认线程键（若删的是当前线程）；清理 **`context.metadata.conversation_thread_id`**。
6. **`agent_long_term_memory.conversation_thread_id`**：**SET NULL**（D6）。

---

## 13. 安全与审计

- `!` 与普通命令 **同一授权链**；流式通道 **不**默认输出未脱敏 tool 观测或 reasoning。
- **`client_hint` / 流式相关 telemetry**（若启用）：**MUST** **脱敏上报**，见 **§17.12.1 H5**。
- 递归禁令：**`!aico`**、**`!aico -i`**（及产品定义的同类前缀）。

---

## 14. 验收要点（测试规划）

- **流式**：mock 多分片 LLM；NDJSON 顺序与拼接全文一致。
- **Tick 生命周期**：已协商流式且进入 `w.tick` 时，`scope=tick` 的 **`start` 在首个 `delta` 之前**、`complete` 在 **`end` 之后**；门禁失败 / passthrough **无** tick `start`；已发 `start` 后失败 **有** `error` 或 `complete ok=false`。
- **`client_hint`**：若出现，**⊆ §17.12 冻结五元**；**H3** 下 **首个 `delta` 后** 由客户端 **本地 streaming 态** 表达，**不**要求 wire 新枚举值。
- **无障碍（H7）**：Web 上 **`client_hint`/生成前 HUD** 对应 **`aria-live="polite"`**（§17.12.3）；**H10** 工程项见 §17.12.4 Todo list。
- **Telemetry（H5）**：若启用埋点，**MUST** 脱敏（§17.12.1 / §13）。
- **`-i`**：Ctrl+Q 退出；Ctrl+C 取消当前轮生成且不退出 REPL；`!help` 类命令成功；`!aico` 拒绝。
- **`-l`**：默认 8 / `-a` 全量；`data.items` schema。
- **`-d`**：二次确认；删除后无孤儿 STM；LTM SET NULL。
- **`-his`**：默认仅最近 8 轮；`-a` 与该线程全部消息一致（在选定 transport / 聚合策略下）。
- **能力协商**：off → 仅 `message`；on → UI **不以** `message` 为唯一增量来源（D8）。

---

## 15. Review 备忘（SPEC 维护）

| 主题 | 说明 |
|------|------|
| HUD | 可选展示流式 capability、模型摘要（对标 IDE agent）；**`client_hint` 枚举与文案映射**见 §17.12 |
| `!` 限制 | 可选：禁止管道、限制行长（与策略一致） |
| 取消 / 协议扩展 | `-i` 下 Ctrl+C 语义见第 17.5 节；跨 transport 的 `aico_stream_cancel` 等见 Phase 2+ |
| `-l` 扩展 | 可选 `snippet` 字段（需 DB/查询支持） |

---

## 16. 业界对标（压缩叙述）

- **方案 A**：终端/IDE coding agent 常见「宿主持 REPL + 每轮无状态 tick」，与 CampusWorld **行模式命令网关**一致。
- **NDJSON**：便于 SSH 调试与多事件类型扩展，与同源的 SSE「分行」思路一致。
- **状态文案为何常常「每次不一样」（如 Claude Code）**：IDE agent 类产品通常将状态条视为 **低优先级 UX**，常见做法是：(1) **由模型或模板 + 随机性**生成短句，避免界面呆板；(2) **内部 phase / tool 种类**变化导致映射到不同英文短语；(3) **版本迭代**调整文案而不保证与客户端缓存一致；(4) **本地化或 A/B** 多套字符串。CampusWorld **默认推荐**（§10.1 `client_hint`）：对用户可见状态优先 **稳定枚举**（再由客户端映射为固定中文），与「每次换一句」的竞品风格区分开，便于测试与无障碍；若产品明确要求「拟人化可变文案」，应 **单列策略**（允许服务端模板池或 LLM），且仍 **禁止**在默认流中泄露 tool 观测或 reasoning。

---

## 17. 待决策项与推荐建议

下列事项在实现前需要 **闭合为 MUST/SHOULD** 或 **单列 ADR**；此处给出 **背景说明** 与 **默认推荐**，便于评审与拆任务。

### 17.1 `aico -his` 跨 transport：单行 STM 还是按 thread 聚合

- **说明**：Mode A 下 STM 键含 `transport_session_id`，同一 `conversation_thread_id` 换 SSH 可能有多行。`-his` 若只读「当前 transport」一行，会与 D4「换连接续聊」叙事冲突；若聚合多行，则需定义排序、去重与边界。
- **推荐**：**按 thread 聚合 (b)**，在同一 owner+agent+thread 下合并所有 STM 行的 `messages`，按消息 `ts` 全局排序后输出；若实现成本过高，可阶段性只做当前 transport，但须在用户可见文案与发行说明中标明「换连接后 `-his` 可能不完整」，并立项补齐。

### 17.2 能力协商：字段名与宣告载体（SSH / WebSocket）

- **说明**：D8 要求客户端声明流式能力，但未规定 **名**（暂定 `supports_aico_stream`）与 **在哪里声明**，易导致 SSH 与 WS 各写一套。
- **推荐**：**冻结 capability 名**为 `supports_aico_stream`（bool）；**SSH**：在会话上下文或首个 REPL 帧写入一次布尔（实现可选用 `GameSession` / channel metadata / 等价单点）；**WebSocket**：在连接握手或首条 envelope 字段携带同一键。**禁止** silent 默认「流式」——未声明则一律走 `message`。

### 17.3 NDJSON 事件 schema 与顺序约束

- **说明**：`delta` / `end` / `error` / `meta` 的组合顺序未钉死时，客户端难以稳健拼装或断线重连。
- **已定（含 §10.5）**：协商路径下一轮助手输出的 **推荐完整序列**：
  1. **可选**：`meta`，**`scope=tick`**，`phase=start`（即将进入 `w.tick`）。
  2. **可选**：`meta`，绑定 **`thread_id`** / **`correlation_id`**（若与 tick 行分拆；亦可合并进单行实现，但 **SHOULD** 保留 `scope` 语义区分）。
  3. **若干** `delta`（正文片段）。
  4. **一条** `end`（可含 `full_text`）。
  5. **可选**：`meta`，**`scope=tick`**，`phase=complete`，**`ok`**。
- **失败**：发 **`error`**，并 **可选** `end`（`partial: true`）；若已发 **`phase=start`**，**禁止**省略收尾事件（见 §10.5）。`correlation_id` **SHOULD** 与 F10 侧单次 tick / trace 对齐。**实现 SHOULD** 在附录或测试夹具中列出 JSON 样例。

### 17.4 TTFS（首字节）与 `meta` 时机

- **说明**：是否强制首包为 `meta` 影响终端 HUD 与排障，也可能拖慢首 token。
- **推荐**：**不**强制首包必须是某种单一 `meta`；**SHOULD** 在首个 **`delta` 之前**至少达成其一：**`scope=tick, phase=start`**（§10.5，给用户「已进入处理」信号），和/或携带 **`thread_id`** 的正文路由 `meta`。纯 passthrough / 未进入 `w.tick` 的路径 **不**发 tick `meta`；日志仍须可追溯。

### 17.5 `-i` 下 Ctrl+C 与 Ctrl+Q 分工（已定）

- **说明**：D3 已定 **Ctrl+Q** 退出 REPL。须在 Unix 终端惯例下区分 **退出交互页** 与 **打断当前轮模型输出**。
- **已定语义**：**Ctrl+Q（`\x11`）**：**MUST** 退出 `-i`，回到普通命令行。**Ctrl+C**：在 `-i` 模式下 **MUST** 表示 **取消当前轮助手生成**（停止继续接收/渲染本轮 NDJSON 增量与尾部 `end`，并向服务端/会话层发出取消意图以使本轮尽快收尾）；**MUST NOT** 单独等同于退出 REPL（避免误触 SIGINT 直接丢会话）。 idle（无生成进行时）下 Ctrl+C 可实现为 noop 或一行提示，但不得退出 `-i`。HUD 或帮助 **MUST** 明示两键分工。
- **实现备注**：取消是否能在所有 provider 上立刻切断上游推理，取决于 HTTP/SDK；产品语义仍以「用户侧停止本轮输出与可接受的收尾」为准，STM 记入策略与 **17.6** 对齐（例如 assistant 截断或占位）。

### 17.6 流式中途失败（已输出部分 `delta`）

- **说明**：网络或服务错误发生在半段 assistant 输出之后，需定义客户端与服务端是否还把本次 tick 记入 STM、`message` 填什么。
- **推荐**：发送 **`error`**（结构化码 + 可读文案）；**可选** `end` + `partial: true`；**STM**：若业务上本轮用户消息已提交，可按策略记入 **assistant 占位或截断全文**（与 F12 compaction 策略对齐），**禁止** silent 丢弃用户侧 turn；验收用例覆盖「error 后 REPL 仍可下一轮」。

### 17.7 裸 NDJSON 与人类可读终端

- **说明**：SSH 直连若把 JSON 行打到 PTY，可读性差；调试又希望可 pipe。
- **推荐**：**Campus CLI / REPL 宿主**负责解析 NDJSON，**仅渲染** `delta.text`；**原生 SSH** 可配置两种模式之一（实现选型）：**(a)** 同样由薄客户端前置解析（推荐统一）；**(b)** 允许裸 NDJSON 作为 debug 模式并在文档标明。无论哪种，**协商客户端**不得依赖肉眼拼接 JSON。

### 17.8 `aico -his` 默认条数与 `-a`（已定）

- **说明**：单线程 transcript 可能极长，需要默认收窄输出又与 `-l` 的「8 / 全量」心智一致。
- **已定语义**：**`aico -his <uuid>`** **默认只输出该线程下时间上最近的 8 轮对话**（「轮」定义见本文第 7 节）。**`aico -his <uuid> -a`** 输出该 uuid 下 **全部**消息（在本文第 7 节数据源与跨 transport 聚合策略之下）。**实现 MUST** 与 `get_usage` 同步。
- **`-a` 仍过大时**：首版 **SHOULD** 在极端体积下给出截断提示或环境可配上限；细分页（如 `--page`）可作为 **Phase 2**，不改变默认 8 轮与 `-a` 全量的产品语义。

### 17.9 `@aico` 是否支持 `-i` 等子命令

- **说明**：D1 要求共用 NLP/流式契约；`@aico` 语法是否与 `aico` 逐字共享 argv 取决于调度入口。
- **推荐**：**语义对齐**：凡 `aico` 支持的子命令与标志，**只要**经同一 dispatcher 解析，**应**对 `@aico` 等价可用；若入口实现受限（例如 `@` 解析不支持复合 argv），须在用户文档列明 **唯一支持形式**（例如仅 `@aico <text>`），并避免两套流式路径。

### 17.10 多 transport 并发写同一 thread

- **说明**：同一账号两条连接同时对同一 `conversation_thread_id` tick，STM append 顺序可能交错。
- **推荐**：**优先复用 F12** 对该 agent/thread（或 tick 管线）的 **串行化或冲突策略**；若无现成约束，则 **SHOULD** 以「单 thread 单次仅一处活跃 tick」拒绝或排队（返回可读错误），并在 SPEC 闭合时改为 MUST。**禁止**未定义交错写入同一 STM 行导致 transcript 乱序。

### 17.11 `CommandResult.message` 与 NDJSON 的单一事实（架构闭合）

- **说明**：计划稿要求避免「双路径分叉」：钩子和同步返回值若各讲一套，客户端与测试会分裂。
- **推荐**：**协商路径**：助手正文增量 **仅以 NDJSON** 为 UI 真相；**`message`** 在同一 tick 末尾 **SHOULD** 填充 **完整助手正文**（与 `end.full_text` 一致），供日志、非流式降级与断言。**未协商路径**：仅 **`message`**。实现不得在协商模式下要求终端只靠轮询 `message` 模拟流式（对齐 D8）。

### 17.12 `client_hint` 枚举 + 客户端固定映射（人工核对记录）

**已定产品方向**：**`client_hint` 稳定枚举 + 各客户端本地固定映射**；服务端 **不**下发自然语言状态句；**禁止**默认路径用 LLM 生成 hint。枚举真源 **SHOULD** 落在实现侧常量（及可选 OpenAPI / JSON Schema）。

#### 17.12.1 决策汇总（已闭合）

| ID | 决策 |
|----|------|
| **H1** | **方案 A**：仅在带 **`scope=tick`** 的 `meta` 上 **`client_hint` SHOULD 出现**；其它 `meta` **可省略** `client_hint`。 |
| **H2** | **服务端可发送的 `client_hint` 枚举（冻结）**：`running` · `finding` · `looking` · `thinking` · `flying`。均为 **机器 token**；用户可见字符串 **仅**由客户端映射表产生。 |
| **H3** | **候选 B**：区分 **「生成前等待」** 与 **「正文流式输出中」**。**不**增加第六个 wire 枚举：在 **首个 `delta` 之前**，HUD 依据服务端下发的 **H2** 五选一更新；自 **首个 `delta`** 起至 **`end`**，客户端进入 **本地「streaming」态**（图标/文案由客户端固定映射，**不**依赖新 hint）。`phase=complete` / `kind=error` 后 HUD 收敛 **以 §17.12.2 为准**。 |
| **H4** | **以 `phase`、`ok`、`empty_reply` 及 `kind=error` 为权威**（与 §10.5 一致）。`client_hint` 与上述字段冲突时 **以 phase / ok / error 为准**；hint 仅表达 **同相位下的展示偏好**（含趣味文案分量）。`empty_reply=true` **不**要求单独 wire 枚举：客户端在 **`complete` + `ok=true`** 时 **SHOULD** 清除「处理中/streaming」HUD。 |
| **H5** | 遇 **未知 `client_hint`**：客户端 **MUST** 忽略 token 本体；**SHOULD** 显示 **固定中性文案**（由客户端选一句，如「状态更新」或「处理中」，与 **H6** 语言表一致）。**telemetry**：若产品启用客户端或服务端埋点，**MUST** **脱敏上报**（**禁止** payload 含用户正文全文、tool 原始观测、session 密钥；可上报计数类或哈希后的 `client_hint` token、布尔 capability、去掉 PII 的 `correlation_id` 前缀等；细则由隐私/安全评审闭合）。未启用埋点则 **无需** 上报。 |
| **H6** | **语言由客户端选择**：映射表按 **客户端 locale** 加载；**首期不强制**用服务端 `meta.locale` 驱动 hint 文案（服务端仍可携带 `locale` 供后续扩展）。 |
| **H7** | **已定**：与 **`client_hint` / 生成前 HUD** 相关的 live region **MUST** `aria-live="polite"`（§17.12.3）；token 去重、首个 `delta` 后与成功收尾规则见同节。 |
| **H8** | **不为 `client_hint` 单独增设调试开关**。仓库内其它 NDJSON / 链路透传调试（若有）**与本条无冲突**；本特性仍 **禁止**把 LLM 自由状态句当默认用户可见流。 |
| **H9** | **无 NDJSON（未协商流式）**：与 hint 相关的 HUD **静默**（**不**展示基于 `client_hint` 的状态条）；**禁止**在未协商路径 **伪造** NDJSON `client_hint` 事件。若需人类可读等待提示，走 **普通终端文案**（产品另述），**不**冒充本协议字段。 |
| **H10** | 见 **§17.12.4**（验收与 CI 原则 + **Todo list**）。 |

#### 17.12.2 H2 语义指引（非 MUST；便于实现一致）

服务端在 **`phase=start` 至首个 `delta` 前** **SHOULD** 发送 **H2 五选一**（可固定为 `running`，或按 **确定性** 规则轮换 / 按内部阶段映射 — **禁止** LLM 选词）：

| `client_hint` | 建议含义（实现可收窄） |
|---------------|------------------------|
| `running` | 已进入本轮 tick，泛义「处理中」。 |
| `finding` | 偏检索 / 记忆 / 上下文装配（若实现能区分）。 |
| `looking` | 偏读取世界 / 图谱 / 清单类准备（若实现能区分）。 |
| `thinking` | 偏已进入模型推理、尚无正文片段。 |
| `flying` | 品牌向轻量占位；**客户端读屏映射允许与 `running` 合并为同一句中性说明**，避免趣味词干扰理解。 |

#### 17.12.3 H7 — 无障碍（a11y）：**polite** 策略（已定）

**问题**：`delta` 可能高频到达；若每次状态变化或每个片段都触发 **aria-live**，读屏会 **打断用户听取正文**，体验差于静默终端。

**已定（Web 客户端）**：

- **`client_hint` / 生成前 HUD**：承载容器 **`aria-live="polite"`**（**MUST**）；**同一 token 连续重复** **不得**触发重复播报（去重：仅 token 变化时更新 live region）。
- **首个 `delta` 起**：进入 **本地 streaming** 时，状态条 **`aria-live="off"`** 或 **仅视觉更新**（**SHOULD**），把朗读焦点让给正文；**禁止**对每个 `delta` 插入 live 播报。
- **成功结束**：`phase=complete` 且 `ok=true` 时，**可选** **`polite` 一次**中性收尾文案或 **静默清除** HUD（二选一由产品定）。
- **失败**：`kind=error` 或 `complete` 且 `ok=false` 时，错误摘要 **仍用 `polite` 至多一次**（与 H7 **统一 polite 策略**）；若后续无障碍评审要求对 **关键错误** 使用 **`assertive`**，可作为实现例外并回写本节。

SSH / 纯终端宿主若无 live region：**等价策略**为不对每一个 `delta` 打印额外状态行；趣味 hint **不得**替代错误正文。

#### 17.12.4 H10 — 验收与 CI：原则与 Todo list

**已定原则**：

- **服务端**：单测或契约 **断言** 发出的 `client_hint` **⊆ {running, finding, looking, thinking, flying}**（若发送）。
- **客户端**：单测 **未知 hint → 中性文案**；**已知 hint → 稳定映射**（golden string 可按 locale 分文件）。
- **顺序**：与 §17.3 / §10.5 一致时，`start` 态可在首 `delta` 前校验。

**Todo list（工程跟踪；闭环后勾掉或移入 PR 描述）**：

- [ ] **T10.1 — CI 双轨镜像**：Python 与 TypeScript（或其它客户端）的 `client_hint` 枚举是否 **同源生成（codegen）** 或在 CI 中 **交叉断言一致**，避免漂移。
- [ ] **T10.2 — fixture 归属**：黄金 NDJSON 序列放在 **backend**、`frontend` 还是 **共享包**；是否 **版本化** wire/API。
- [ ] **T10.3 — E2E 深度**：是否在 Playwright 等中断言 **live region（polite）播报次数**（成本高；可标 **Phase 2**）。

**备注**：若未来产品要求「拟人化可变状态句」，须 **单列特性**（§16），且 **不得**替代默认枚举路径。
