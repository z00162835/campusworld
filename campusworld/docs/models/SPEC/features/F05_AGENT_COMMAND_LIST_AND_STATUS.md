# F05 — `agent` 命令：`list` 与状态查询 SPEC

> **Architecture Role：** 定义 **`agent`** 命令族（子命令扩展位）：首版实现 **`agent list`**（列出对调用方 **可见** 的 `npc_agent`），并支持 **`agent status <service_id>`**（或等价参数）查询实例 **运行状态**。**人类用户**与 **`npc_agent` 调用方**（经 `CommandContext`，含服务账号主体）共用同一命令语义与授权链。

**文档状态：Draft**

**交叉引用：** [`F02`](F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)（`npc_agent`、记忆/运行表）、[`F03`](F03_AICO_DEFAULT_SYSTEM_ASSISTANT.md)（AICO）、[`F04`](F04_AT_AGENT_INTERACTION_PROTOCOL.md)（`@`）、[`F11`](../../../api/SPEC/features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md)（读图范围）、[`docs/commands/SPEC/SPEC.md`](../../../commands/SPEC/SPEC.md)。

**实现锚点（建议）：** [`backend/app/commands/agent_commands.py`](../../../../backend/app/commands/agent_commands.py)、[`backend/app/commands/registry.py`](../../../../backend/app/commands/registry.py)、[`backend/app/commands/policy_store.py`](../../../../backend/app/commands/policy_store.py)、[`backend/app/models/system/agent_memory_tables.py`](../../../../backend/app/models/system/agent_memory_tables.py)（`AgentRunRecord`）、[`backend/app/models/graph.py`](../../../../backend/app/models/graph.py)（`Node`）。

---

## 1. Goal

- 提供 **统一入口** **`agent`**，以 **子命令** 扩展（与 `world`、`notice` 等模式一致），避免继续堆叠无关联的顶层 `agent_*` 命令名（既有 `agent_capabilities` / `agent_tools` / `agent_run` 可逐步迁移为 `agent` 子命令，**非本 SPEC 强制**）。
- **首版必做**：**`agent list`** — 列出当前调用方 **可见** 的 Agent（`type_code=npc_agent`）摘要，含 **状态** 字段。
- **首版必做**：**`agent status <service_id>`** — 查询单个可见 Agent 的 **状态** 与关键展示字段（与 list 中单行语义一致）。
- **调用方**：**终端用户**（SSH/HTTP 同源 `CommandContext`）与 **另一 Agent**（例如通过 `invoke_command_line` 或运行时委派）均可调用；**有效权限** 由 **F11 + `command_policies`** 决定。

## 2. Non-Goals

- 不在首版规定 **完整** `agent` 子命令矩阵（`capabilities` / `tools` / `run` 可仍保留旧名，或后续迁入 `agent`）。
- 不在本 SPEC 定义 **LLM 推理内部** 队列深度；**工作中** 以 **持久化运行表** 为准（见 §5）。

## 3. 命令形态与用法

| 子命令 | 语法 | 说明 |
|--------|------|------|
| **list** | `agent list` | 列出可见 Agent；无额外参数。 |
| **status** | `agent status <service_id>` | 查询 `service_id` 匹配的单个 Agent 状态；`service_id` 与 F02/F03 `attributes.service_id` 一致。 |

- **错误用法**：`agent` 无子命令 → 返回用法（含 `list` / `status`）。
- **数据库**：与现有 Agent 命令一致，需要 **`context.db_session`**；缺失时返回明确错误。

## 4. 可见性（谁能出现在 list / 谁能被 status）

**原则：** 列出的是调用方 **被允许读** 的 `npc_agent` 节点集合，**不是**全库枚举（除非管理员权限）。

**v1 建议规则（实现可收紧，但须在发布说明中写明）：**

1. **节点**：`nodes.type_code = 'npc_agent'` **且** `is_active = true`。
2. **F11 / 读策略**：仅包含当前 **`CommandContext`** 对应主体 **按部署策略允许读取** 的节点（与 F10/F11 对图实例读一致）；若项目尚未对 `npc_agent` 做细粒度 `data_access`，则 **退化为**「已认证用户可读全部活跃 `npc_agent`」，并在 SPEC 验收中标注 **技术债**。
3. **Agent 调用 Agent**：调用方为 **`npc_agent`** 或服务账号时，使用 **同一套** 图读规则（**不**默认赋予超级权限）。

**不包含**：未激活节点、软删；**可选**：`attributes.enabled=false` 仍列出但状态为 **不可用**（见 §5），或从 list 中隐藏 —— **推荐列出** 以便运维感知，由 **状态** 区分。

## 5. 状态模型（三态）

状态为 **产品语义**，须 **可由实现稳定推导**，并 **在 list/status 输出中一致**。

| 状态值（API/机器） | 展示（中文） | 含义 | 推导建议（v1） |
|--------------------|--------------|------|----------------|
| `unavailable` | 不可用 | 不可调度、不应接受新任务 | `nodes.is_active=false` **或** `attributes.enabled=false`（若存在该键） |
| `idle` | 空闲 | 可接受任务，当前无进行中的运行 | `enabled` 且 **无**「进行中」的 `agent_run_records` 行（见下） |
| `working` | 工作中 | 存在未结束的运行 | 存在 **`agent_run_records`** 满足：`agent_node_id` 匹配 **且** `status` 为 **`running`**（或等价）**或** `ended_at` 为空且 `phase` 非终态；具体以 ORM/表定义为准 |

**进行中运行：** 以 [`agent_run_records`](../../../../backend/db/schemas/database_schema.sql)（F02）为准；若表结构仅有 `status`/`phase`，实现应统一 **单一真源**（例如 `status='running'`）。

**边界：** 若数据不一致（无运行表但 Worker 内存忙），**v1 仍以库表为准**；内存态可作为后续增强。

## 6. 输出形状（建议）

### 6.1 `agent list`

- 文本或 JSON（与现有 `agent_capabilities` 风格对齐：**JSON 字符串于 `CommandResult.message`** 亦可）。
- 每项至少：**`service_id`**、**`name`**、**`status`**（三态之一）、**`agent_node_id`**（可选，便于排障）。

示例（逻辑结构）：

```json
{
  "agents": [
    {
      "service_id": "aico",
      "name": "AICO",
      "status": "idle",
      "agent_node_id": 12345
    }
  ]
}
```

### 6.2 `agent status <service_id>`

- 若 **不可见** 或 **不存在**：与现有命令一致，**错误结果**（不泄露无权节点细节）。
- 若可见：返回与 list 单项 **同构** 并可增加 **`detail`**：`phase`（若存在运行中）、`correlation_id`、`updated_at` 等（**不**强制首版）。

## 7. 授权与命令策略

- 注册名建议：**`agent`**（子命令由实现解析 **args[0]**）。
- **`command_policies`**：为 **`agent`**（或 `agent list` / `agent status` 若拆注册）配置所需权限；默认可与 **`agent_capabilities`** 同级或更松（只读）。
- **`authorize_command`**：与 HTTP/SSH 同源（见 F02 命令不变式）。

## 8. 与既有命令的关系

| 现有命令 | 关系 |
|----------|------|
| `agent_capabilities <service_id>` | 偏 **静态能力**；**`agent list`** 偏 **目录 + 动态状态**。可并存。 |
| `agent_tools` | 工具枚举；不变。 |
| `agent_run` | 触发运行；**`working`** 状态应与其写入的 **运行记录** 一致。 |

## 9. 验收标准（建议）

- [ ] `agent list` 在 **有 db_session** 时成功返回 **可见** Agent 列表，每项含 **三态之一**。
- [ ] `agent status <service_id>` 对可见实例返回与 list **一致** 的 `status`。
- [ ] 对 **不可见** `service_id` 返回 **统一错误**（不区分「不存在」与「无权限」，若产品选择如此防枚举）。
- [ ] **`npc_agent`** 作为调用方时命令可执行（权限符合 F11）。
- [ ] 文档与 **`policy_bootstrap`** / 迁移策略对齐（若新增命令名 **`agent`**）。

## 10. 实现阶段（建议）

| 阶段 | 内容 |
|------|------|
| **M1** | 注册 **`agent`**，`list` + `status`；状态推导 **仅依赖** `nodes` + `agent_run_records`。 |
| **M2** | F11 细粒度过滤；与 **`enabled`** 之外的维护模式字段对齐（若有）。 |

---

## 附录 — 与 F03 AICO

- 默认实例 **`service_id=aico`** 应在 **`agent list`** 中对有权限用户可见（若节点可读），状态默认多为 **`idle`** 或 **`unavailable`**（取决于 `enabled` 与运行记录）。
