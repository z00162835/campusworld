# F07 — 按用户区隔的 Agent 记忆与 LTM 异步晋升

> **文档状态：Deferred（后续迭代，不在当前 AICO 基础能力计划内实施）**  
> **架构角色：** 将 **原生对话记忆（raw / run 审计）** 与 **长期记忆（LTM）** 从「仅按 `agent_node_id` 隔离」升级为 **按用户（或稳定账号主体）与 agent 二元组隔离**；并由 **异步处理路径** 将 raw 对话 **压缩 / 摘要 / 合并** 写入 LTM，供后续 tick 检索注入。  
> **交叉引用：** [`F02_INTELLIGENT_AGENT_SERVICE_TYPE.md`](F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)（`npc_agent`、记忆表语义）、[`F02_LTM_VECTORS_AND_MEMORY_LINKS.md`](F02_LTM_VECTORS_AND_MEMORY_LINKS.md)（向量与 LTM 链接）、[`F03_AICO_DEFAULT_SYSTEM_ASSISTANT.md`](F03_AICO_DEFAULT_SYSTEM_ASSISTANT.md)（AICO）、[`F04_AT_AGENT_INTERACTION_PROTOCOL.md`](F04_AT_AGENT_INTERACTION_PROTOCOL.md)（`@`）、[`F05_AGENT_COMMAND_LIST_AND_STATUS.md`](F05_AGENT_COMMAND_LIST_AND_STATUS.md)（`agent` 命令）、[`F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md`](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)（Agent 四层架构；**LTM 与 F09 L4 Skill 的边界** 见该文 §5）。  
> **实现锚点（现状）：** [`backend/app/models/system/agent_memory_tables.py`](../../../../backend/app/models/system/agent_memory_tables.py)、[`backend/app/game_engine/agent_runtime/memory_port.py`](../../../../backend/app/game_engine/agent_runtime/memory_port.py)、[`backend/app/services/ltm_semantic_retrieval.py`](../../../../backend/app/services/ltm_semantic_retrieval.py)、[`backend/scripts/promote_raw_to_ltm.py`](../../../../backend/scripts/promote_raw_to_ltm.py)（占位未实现）。

---

## 1. 目标

1. **原生记忆按用户区隔**  
   SSH（及同源 `CommandContext`）用户与 AICO（及未来同类助手）对话时，**写入** `agent_memory_entries` / `agent_run_records` 等 raw 路径的数据必须能按 **调用方主体**（建议：与图账号节点或 `CommandContext.user_id` 对齐的稳定键）与 **`agent_node_id`** 联合作用域查询，**禁止**多用户共享同一 AICO 节点下的单一记忆池。

2. **长期记忆按用户区隔**  
   `agent_long_term_memory`（及 `agent_long_term_memory_links`）的读写与检索（含 [`build_ltm_memory_context_for_tick`](../../../../backend/app/services/ltm_semantic_retrieval.py) 类入口）必须在 **同一用户 + 同一 agent** 范围内进行，与 F02 扩展文档中「agent 隔离」正交补充 **用户隔离**。

3. **LTM 异步晋升**  
   由 **后台异步工作者**（线程 / 队列 / 定时批处理等产品选定实现）消费已落库的 raw 片段，经 **摘要、去重、合并策略** 后写入或更新 LTM；占位脚本 [`promote_raw_to_ltm.py`](../../../../backend/scripts/promote_raw_to_ltm.py) 由本特性替换为可运行管线或与运行时任务合并。  
   **不要求**在同步 `aico` tick 内完成完整压缩，以避免阻塞交互路径。

---

## 2. 非目标（本 SPEC 不包含）

- 不规定具体 **embedding 模型** 或 **摘要提示词**（可与 F02 向量文档、运维配置协同）。  
- 不替代 **图本体**（`nodes` / `relationships`）；LTM 仍为推理与检索辅助层。  
- **不与**「AICO 基础能力」短期计划耦合：终端纯文本呈现、无 LLM 直通、瘦 PDCA、系统侧 YAML 初始化加载等见独立实施计划，**记忆多租户与本特性一并后续交付**。
- **架构边界**：本 SPEC 的 **LTM / `memory_context` 注入** **不是** [**F09**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md) 中的 **L4 经验 Skill**；二者可并存于同一 tick，划界见 F09 §5。

---

## 3. 现状缺口（验收基线）

- 记忆表与 `SqlAlchemyMemoryPort` 仅以 **`agent_node_id`** 为作用域；**无**用户维度列。  
- `AgentMemoryEntry.session_id` 可选，但当前框架路径 **未**稳定传入可用于「用户级」隔离的标识。  
- `build_ltm_memory_context_for_tick` 仅按 `agent_node_id` 拉取 LTM。  
- **无**已接入进程的异步 LTM 晋升实现；`promote_raw_to_ltm` 为占位。

---

## 4. 设计要点（后续细化）

| 方向 | 说明 |
|------|------|
| **主体键** | 在相关表上增加与 **账号 / 用户图节点** 一致的外键或稳定字符串键（如 `account_node_id` / `principal_id`）；迁移需幂等、可回填策略单独约定。 |
| **调用链** | `CommandContext` → `run_npc_agent_nlp_tick` / `MemoryPort` / `FrameworkRunContext` 全链路携带该键；所有 SELECT/INSERT 带 `(agent_node_id, principal)` 条件。 |
| **异步任务** | 输入：未晋升或待合并的 raw 行（可按用户 + agent 分区）；输出：LTM 行 + 可选向量回填（F02）；失败重试与幂等键待定。 |
| **隐私与安全** | 管理端导出、跨用户检索默认拒绝；与 F11 数据访问策略对齐。 |

---

## 5. 与「AICO 基础能力」计划的关系

当前聚焦 **AICO 基本能力**（交互呈现、无 LLM 行为、瘦 PDCA、系统配置初始化加载等）的仓库内实施计划 **刻意不包含** 本章所列 schema 与异步管线；待基础能力稳定后，以 **本 F07 文档** 为需求与验收提纲 **单独立项** 实施。
