# F03 — 系统默认助手 AICO（`npc_agent` 实例）SPEC

> **Architecture Role：** 定义 CampusWorld **内置单例**助手 **AICO**：图上锚定奇点屋、不可移动、LLM + PDCA；**用户交互入口**（`@` / `@aico`）见 companion [**F04**](F04_AT_AGENT_INTERACTION_PROTOCOL.md)。

**文档状态：Draft — 待人工审核**

**交叉引用：** [`F09`](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)（CampusWorld Agent 四层架构 L1–L4）、[`F08`](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md)（Command-as-Tool、ToolGather）、[`F10`](F10_AICO_PERFORMANCE_AND_LATENCY.md)（AICO tick 延迟 SLO、可观测性与实现收敛；**运维调参速查见 F10 第 13 节**）、[`F02`](F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)（`npc_agent` 通用模型）、[`F04`](F04_AT_AGENT_INTERACTION_PROTOCOL.md)（`@` 协议）、[`F07`](F07_PER_USER_AGENT_MEMORY_AND_ASYNC_LTM_PROMOTION.md)（按用户记忆与 LTM 异步晋升，后续迭代）、[`F01`](../../../database/SPEC/features/F01_TRAIT_CLASS_MASK_FOR_AGENT.md)（trait）、[`F11`](../../../api/SPEC/features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md)（数据访问主体）。

**实现锚点（非 exhaustive）：** [`backend/app/models/things/agents.py`](../../../../backend/app/models/things/agents.py)、[`backend/app/commands/agent_command_context.py`](../../../../backend/app/commands/agent_command_context.py)、[`backend/app/commands/agent_commands.py`](../../../../backend/app/commands/agent_commands.py)（`aico`、`agent`、`agent_capabilities`、`agent_tools`）、[`backend/app/commands/npc_agent_nlp.py`](../../../../backend/app/commands/npc_agent_nlp.py)（`run_npc_agent_nlp_tick`）、[`backend/app/game_engine/agent_runtime/`](../../../../backend/app/game_engine/agent_runtime/)（`LlmPdcaAssistantWorker`、`LlmPDCAFramework`、`agent_node_phase_llm`）、[`backend/app/constants/trait_mask.py`](../../../../backend/app/constants/trait_mask.py)、[`backend/app/core/settings.py`](../../../../backend/app/core/settings.py) / [`backend/config/settings.yaml`](../../../../backend/config/settings.yaml)（**连接参数 + 默认 system_prompt / phase_prompts**）、[`backend/app/game_engine/agent_runtime/agent_llm_config.py`](../../../../backend/app/game_engine/agent_runtime/agent_llm_config.py)（`prompt_overrides` 与 **内联 `model_config` 非密钥合并**）、[`backend/db/ontology/graph_seed_node_types.yaml`](../../../../backend/db/ontology/graph_seed_node_types.yaml)、[`backend/db/seed_data.py`](../../../../backend/db/seed_data.py)（种子落地时）。**AICO 优化可观测（专用日志，§5.7）：** [`backend/app/core/log/aico_observability.py`](../../../../backend/app/core/log/aico_observability.py)、[`backend/app/game_engine/agent_runtime/aico_observability_hooks.py`](../../../../backend/app/game_engine/agent_runtime/aico_observability_hooks.py)、配置加载见 [`backend/app/core/config_manager.py`](../../../../backend/app/core/config_manager.py)。运行时决策记录见 [`docs/architecture/adr/ADR-F03-AICO-NL-Pipeline.md`](../../../architecture/adr/ADR-F03-AICO-NL-Pipeline.md)。

---

## 1. Goal

- 提供 **系统级默认助手** **AICO**（展示名），帮助用户理解 CampusWorld世界各种知识。
- **架构位置**：AICO 是 **`npc_agent`** 的默认实例，跨 **L2**（命令工具）、**L3**（LLM + PDCA 等思考管线）、可选 **L4**（经验 Skill）与 **F07** 侧 `memory_context`；**全局四层定义** 见 [**F09**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)，**工具输出进上下文** 见 [**F08**](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md)。
- 以 **单一 `npc_agent` 图节点** 表达实例；**静态配置** 在 `nodes.attributes`（见 §5、附录 A）；记忆与运行过程在 F02 独立表。
- **认知**：`decision_mode: llm`，思维框架 **PDCA**（与 `agent_run_records.phase` 对齐）；工具侧经 **命令注册表** + 授权（与 F02 §6 一致）。
- **可执行命令（`tool_allowlist`）**：v2 Discovery Suite（`help`、`look`、`time`、`version`、`whoami`、`primer`、`find`、`describe`、`agent`、`agent_capabilities`、`agent_tools`），其中 `primer` / `find` / `describe` 为 **v2 新增**、为 LLM 提供 **按需拉取** 的世界本体与图内检索能力。命名与 Evennia 对齐：`find`（别名 `@find`、`locate`）对应 Evennia `@find`；`describe`（别名 `examine`、`ex`）对应 Evennia `examine`。allowlist 中的别名在 `build_resolved_tool_surface` 阶段自动规范化为 primary 名。详见 §5.2 默认值表与 [`F08`](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) §12「工具优先 harness」刷新说明。清单须与 **注册表 + `command_policies` + 服务账号权限** 共同生效。
- **LLM 参数**：**主配置源** 为 CampusWorld **系统级 YAML**（[`settings.yaml`](../../../../backend/config/settings.yaml) 及环境覆盖 `settings.*.yaml`），按 **`service_id`**（如 `aico`）为 **不同系统 Agent** 配置 **provider、model、API key、temperature** 等；**禁止**在图节点 `attributes` 中长期存放明文密钥（见 §5.3）。
- **拓扑**：AICO **实际位置**为 **奇点屋根房间**（`location_id`）；用户可在 **任意位置** 通过 **F04 `@` 协议** 与 AICO 交互（不要求同房间）。
- **触发模式**：实例 **`nodes.attributes`** 须声明 **主触发模式**；AICO 为 **NLP 触发**（自然语言输入，含 **`@aico <payload>`** 与会话内 NL），与 [**F02**](F02_INTELLIGENT_AGENT_SERVICE_TYPE.md) 中 `default_triggers[].kind` 的 **`NLP`** 语义一致（见 §5.2.2 **`trigger_mode`**）。

## 2. Non-Goals

- 不规定 **LLM 提供商 SDK** 的具体实现（仅约定 **配置形状**、加载优先级与密钥来源）。
- 不替代 F04 中 `@` 语法、解析与命令路由的完整规格。
- 不在本 SPEC 中固定 **唯一** 种子迁移策略（`seed_data` / graph seed 二选一由实现选型）。

## 3. 定位与双轨「位置」

| 维度 | 说明 |
|------|------|
| **图锚点** | 实例 `location_id` **固定**为系统 **SingularityRoom** 对应 **room** 节点 id（与账号 `home_id` 锚定的根房间一致；**不写死整数 id**，由初始化/种子解析「`room_type=singularity`」或 RootManager 规则）。 |
| **可观察性** | 用户在 **奇点屋** `look` 时，应能 **看到** AICO（与同房间 `npc_agent` 呈现规则一致）。 |
| **交互** | 用户通过 **`@aico`**（或 F04 规定的等价形式）在 **任意房间/世界上下文** 发起会话，**不**以「与 AICO 同房间」为前置条件（见 F04）。 |

## 4. Trait 与不可移动

- **类型**：`type_code=npc_agent`；`trait_class` 继承类型表（见 F01 / `node_types`）。
- **`trait_mask`（实例）**：在 [`NPC_AGENT`](../../../../backend/app/constants/trait_mask.py)（`498`）基础上 **清除 `MOBILE`（`1<<7`）**，即：

  `trait_mask = NPC_AGENT & ~MOBILE` → **十进制 `370`**。

  **语义**：保留 F01 中与「Agent 本体」相关的位，**去掉可移动**，以便命令层/引擎对「不可搬运」的 NPC 做一致判断（方向移动、拖拽等若存在，应拒绝改变 AICO 的 `location_id`）。

- **不在 `trait_mask` 中编码** PDCA、LLM 或 `tool_allowlist`（与 F02 §7.3 一致）。

## 5. 初始配置数据设计

### 5.1 类型层（`node_types`，`type_code=npc_agent`）

- 属性辞典与 JSON Schema **以 F02 §7、§8 为主**；本 SPEC **不重复**全表。
- **可选扩展（产品需唯一 handle 时）**：在 `schema_definition.properties` 增加 **`handle_aliases`**（`array<string>`），与 `service_id` 联合唯一；若 v1 **仅**用 `service_id` 作为 `@` handle，则 **不新增**该字段（见 F04）。

**实现合并处：** [`graph_seed_node_types.yaml`](../../../../backend/db/ontology/graph_seed_node_types.yaml) 的 `npc_agent` 块。

### 5.2 实例默认值（`nodes` 行 — AICO）

下列为 **种子/迁移** 的 **建议默认**；部署可覆盖非密钥字段。

#### 5.2.1 列级（非 `attributes`）

| 字段 | 默认值 / 规则 |
|------|----------------|
| `name` | `AICO`（或本地化展示名，与产品一致） |
| `type_id` | 指向 `node_types` 中 `type_code=npc_agent` 的行 |
| `is_active` | `true` |
| `trait_mask` | **`370`**（见 §4） |
| `location_id` | 奇点屋 **room** 节点 id（运行时解析，见 §3） |

#### 5.2.2 `nodes.attributes`（静态）

| 属性 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `agent_role` | string | 是 | `narrative_npc` | 助手型叙事 NPC；能力与审计通过 **`service_account_id`** 绑定账号（见 F02/F11）。 |
| `enabled` | boolean | 否 | `true` | |
| `service_id` | string | 是 | `aico` | 全局唯一；**`@` handle 默认**（F04）。 |
| `trigger_mode` | string | 是 | `nlp` | **主触发模式**。AICO 为 **NLP**（自然语言）触发：与 F02 类型层触发种类 **`NLP`** 对齐；与 F04 **`@`**、用户自然语言输入一致。建议取值：`nlp`（小写存图）；扩展 Agent 可用 `command`、`schedule`、`queue` 等（见 F02 `default_triggers[].kind`）。 |
| `decision_mode` | string | 是 | `llm` | |
| `cognition_profile_ref` | string | 否 | `pdca_v1` | 与类型层 `cognition_models` 中 PDCA 条目对齐的引用键（实现约定）。 |
| `tool_allowlist` | array | 否 | 见下段 | 注册表 **命令名** 白名单（与 [`RegistryToolExecutor`](../../../../backend/app/game_engine/agent_runtime/tooling.py) 一致）。 |
| `phase_llm` | object | 否 | 见种子 / §5.5 | **每阶段 PDCA 路由**：键为 `plan` / `do` / `check` / `act`，值为 `{ "mode": "fast" \| "plan" \| "think" \| "skip" }`，可选 `model` / `temperature` 等（与 `PhaseLlmPhaseConfig` 一致）。**实例级配置源**，不放在系统 YAML。 |
| `mode_models` | object | 否 | 见种子 | 将逻辑 mode（`fast` / `plan` / `think`）映射到具体 **model id**；与 `phase_llm` 配合解析 `LlmCallSpec`。 |
| `model_config` | object | 否 | — | **可选**；若与 §5.3 YAML 并存，**以 YAML 为主**，图中仅允许 **非密钥** 字段覆盖（见 §5.4），实现白名单：`temperature`、`max_tokens`、`model`。 |
| `model_config_ref` | string | 否 | 见 §5.3 | 指向 YAML 中某 Agent 配置键（如 `aico`），实现时与 `service_id` 默认绑定。 |
| `prompt_overrides` | object | 否 | — | **非密钥**；`system_prompt` / `phase_prompts` 形状与 YAML 单服务条目一致，合并规则见 §5.6。 |
| `service_account_id` | integer \| null | 否 | `null` | 指向 `type_code=account` 的节点 id；**未绑定时** 工具执行回退为 invoker 上下文（见 [`agent_command_context.py`](../../../../backend/app/commands/agent_command_context.py)）。 |
| `version` | string | 否 | `"1"` | |

**`tool_allowlist` v2 默认值（Discovery Suite — 工具优先 harness）：**

```json
[
  "help", "look", "time", "version", "whoami",
  "primer", "find", "describe",
  "agent", "agent_capabilities", "agent_tools"
]
```

**说明：**

- **`help`**、**`look`**、**`time`**、**`version`**、**`whoami`** 等对应 [`system_commands.py`](../../../../backend/app/commands/system_commands.py) 中已注册的系统命令，语义上与普通用户会话中 **默认可用** 的基础集一致；**是否**出现在 AICO 的 **有效** 工具列表还受 **`get_available_commands`**（`command_policies` + 服务账号权限）过滤。
- **`primer`** — 详见 [`system_primer_command.py`](../../../../backend/app/commands/system_primer_command.py)；以命令形态暴露 CampusWorld 系统本体 [`CAMPUSWORLD_SYSTEM_PRIMER.md`](../../CAMPUSWORLD_SYSTEM_PRIMER.md) 的各语义段（identity / ontology / world / invariants / examples 等），由 [`system_primer_context.py`](../../../../backend/app/game_engine/agent_runtime/system_primer_context.py) 渲染。与 Tier-1 静态 system prompt 协作：`system_prompt` 只放「身份 + 不变量」的精简版，完整设计说明由 agent 主动 `primer <section>` 按需拉取（与 F08 §12.3 对齐）。
- **`find`** — 图节点检索（Evennia `@find` 风格，列表工具）。契约见 [`F01_FIND_COMMAND`](../../../commands/SPEC/features/F01_FIND_COMMAND.md)。别名：`@find`、`locate`。v3 新增 `-n` / `-des` / `-loc` / `-l` / `-a` 与 AND 组合查询。
- **`describe <id | #<id> | name>`** — 同上模块；输出单节点详情 + 出边采样。别名：`examine`、`ex`（Evennia 对齐）。
- **`agent_capabilities`**、**`agent_tools`** 用于自省与能力查询；可按产品需要收紧 **`tool_allowlist`**（不暴露过多注册表命令）。
- 后续可追加经策略允许的 **只读图/本体查询** 类命令名；须与 `command_policies` 及服务账号权限一致。

> **迁移提示**：将现有数据库从 v1 迁移到 v2 时，在 AICO 节点 `attributes.tool_allowlist` 中写入 v2 清单（`help`、`look`、`time`、`version`、`whoami`、`primer`、`find`、`describe`、`agent`、`agent_capabilities`、`agent_tools`）。旧值 `graph_find` 已不再注册，需要替换为 `find`（或 Evennia 风格的 `locate`）。新部署由 `ensure_aico_npc_agent` 直接写入 v2 清单。

**与 F02 `default_triggers`：** 若需在类型层表达完整触发器模板，可使用 `default_triggers: [{ "kind": "NLP", "config": { } }]`；实例层以 **`trigger_mode`** 为 **摘要字段**，调度与路由逻辑 **以 `trigger_mode` + F04 为准**，避免与 F02 枚举冲突（`NLP` ↔ `nlp` 大小写由实现统一）。

### 5.3 系统配置 YAML 中的 LLM（主配置源）

**原则：** AICO（及未来 **系统内置 Agent**）使用的 **LLM provider、model、API key、temperature** 等，**以** CampusWorld **应用配置 YAML** 为 **主配置源**（例如 [`backend/config/settings.yaml`](../../../../backend/config/settings.yaml)，由 [`config_manager.py`](../../../../backend/app/core/config_manager.py) / [`settings.py`](../../../../backend/app/core/settings.py) 加载；支持 `settings.dev.yaml` / `settings.prod.yaml` 等覆盖）。

**要求：**

1. **按 Agent 区分**：配置以 **`service_id`**（或实现约定的 **逻辑键**）为维度，使 **不同系统 Agent** 可使用 **不同** provider、endpoint、模型名、温度、密钥等。
2. **密钥**：**推荐** `api_key_env: <环境变量名>` 或 `credentials_ref` 指向密钥管理；**禁止**将生产密钥提交进仓库；开发环境可本地覆盖。
3. **与图的关系**：运行时优先从 **YAML** 读取 LLM 参数；**不在** `nodes.attributes` 中存储 **明文 API key**（F02 §8 不变式仍适用）。

**建议 YAML 形状（连接 + 默认 Prompt；不含 per-phase 路由）：**

`phase_llm` / `mode_models` **不在此文件配置**，见 §5.2.2 **`nodes.attributes`**（实例级 PDCA 路由）。

```yaml
agents:
  llm:
    by_service_id:
      aico:
        provider: openai_compatible
        base_url: ""
        api_key_env: "AICO_OPENAI_API_KEY"
        model: "gpt-4o-mini"
        temperature: 0.2
        max_tokens: 4096
        extra: {}
        system_prompt: >-
          You are AICO, the CampusWorld assistant. ...
        phase_prompts:
          plan: "..."
          do: "..."
          check: "..."
          act: "..."
        use_http_llm: false
```

实现侧：用 **`service_id`** 与可选 **`model_config_ref`** 读取 `agents.llm.by_service_id.<key>`，再合并 **`nodes.attributes.model_config`**（白名单非密钥字段）、**`prompt_overrides`**（见 [`agent_llm_config.py`](../../../../backend/app/game_engine/agent_runtime/agent_llm_config.py)）。

### 5.4 图节点中的覆盖（可选、非密钥）

- **`model_config_ref`**：可指向 YAML 内 **键路径** 或 **逻辑名**（与 `by_service_id` 对齐），便于在 **同一 `service_id`** 下切换配置段（如 `aico` → `aico_preview`）。
- **内联 `model_config`**：仅允许 **非密钥** 字段，实现白名单：**`temperature`**、**`max_tokens`**、**`model`**（模型 id 字符串）。**YAML 为默认**，节点覆盖在其后合并。
- **`prompt_overrides`**：仅 **`system_prompt`**、**`phase_prompts`**，在 **`model_config` 合并之后**再应用（仍低于单次 tick 覆盖，见 §5.6）。

**种子默认值：** 新节点可 **省略** `model_config` 与密钥，仅依赖 §5.3；**`phase_llm` / `mode_models`** 由种子或运维写入节点属性（见 [`seed_data.py`](../../../../backend/db/seed_data.py) `ensure_aico_npc_agent`）。附录 B 为示例。

### 5.5 运行时管线（自然语言 + PDCA + 记忆 + LLM）

AICO 的 **可验收执行语义**（与仅声明 `decision_mode: llm` 不同）包含下列 **逻辑阶段**（与 `agent_run_records.phase` 及 F02 `cognition_models[].steps` 对齐）：

1. **输入**：用户自然语言载荷（含 F04 `@aico <payload>` 解析结果）进入 **`FrameworkRunContext.payload`**（建议键 `message` / `text`）。
2. **记忆加载（可选）**：当 YAML `agents.llm.by_service_id.<key>.extra.enable_ltm` 为 **true** 时，[`npc_agent_nlp.py`](../../../../backend/app/commands/npc_agent_nlp.py) 调用 [`ltm_semantic_retrieval.build_ltm_memory_context_for_tick`](../../../../backend/app/services/ltm_semantic_retrieval.py)（近期 LTM 摘要拼接；向量语义检索可在有 query embedding 时扩展）；结果以 **非密钥短文本** 注入 **`FrameworkRunContext.memory_context`**。
3. **上下文整合**：合并 **系统 Prompt**、**分阶段指令**（见 §5.6）、用户消息、`memory_context`、以及会话/世界辅助字段（由调用方放入 `payload` 或单独上下文字段）。
4. **PDCA + LLM**：按 **Plan → Do → Check → Act** 推进；每阶段由 **`phase_llm.<phase>.mode`** 决定 **fast / plan / think** 路由（映射到 **`mode_models`** 或阶段内 **`model`** 覆盖）或 **`skip`**（不调用 LLM，trace 记 **`skipped`**）。参考实现 **`LlmPDCAFramework`** 对各非 `skip` 阶段调用 **`LlmClient.complete(..., call_spec)`**；默认 **Act** 可为 **`skip`**（仅输出 **Do** 结果）。
5. **生成答复**：面向用户的 **最终自然语言** 作为运行结果返回（与 F04 回显路径对接）。
6. **回馈**：将阶段追踪写入 **`agent_run_records.command_trace`**，必要时追加 **`agent_memory_entries`（raw）** 等（F02 §9）；审计类摘要可经 `append_raw`。

**用户与联调入口：** **`aico <message...>`**，以及与 F04 一致的 **`@<handle> <message...>`**（见 [`at_agent_dispatch.py`](../../../../backend/app/commands/at_agent_dispatch.py)、[`npc_agent_nlp.py`](../../../../backend/app/commands/npc_agent_nlp.py)）要求目标节点 **`decision_mode=llm`**，运行时 **`LlmPdcaAssistantWorker`** / **`run_npc_agent_nlp_tick`**。

**工具上下文（Command-as-Tool）扩展：** 将注册表命令的可观测输出注入 LLM 上下文的契约见 [**F08**](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md)；**Agent 四层架构** 见 [**F09**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)。

### 5.6 Prompt 与分阶段注入 — 合并优先级

| 来源 | 内容 | 说明 |
|------|------|------|
| **系统 YAML** `agents.llm.by_service_id.<key>.system_prompt` | 初始系统 Prompt | **主配置源**；`<key>` 由 `model_config_ref` 或 `service_id` 解析 |
| **系统 YAML** `agents.llm.by_service_id.<key>.phase_prompts` | `plan` / `do` / `check` / `act` 的阶段性补充指令 | 与 PDCA 阶段名一致；实现将每阶段合并为「system + 阶段后缀」 |
| **`nodes.attributes.model_config`** | `temperature` / `max_tokens` / `model` | 非密钥，白名单字段；在 YAML 之后合并 |
| **`nodes.attributes.prompt_overrides`** | `system_prompt` / `phase_prompts` | 非密钥；在 **YAML + model_config** 之后合并（单元测试见 `test_agent_llm_config.py`） |
| **单次 tick** `FrameworkRunContext.system_prompt` / `phase_prompts` | 会话级覆盖 | **最高优先级**（F04 等调用方注入） |
| **`FrameworkRunContext.memory_context`** | 检索到的记忆文本 | 仅承载内容，**不**替代系统 Prompt |

**PDCA 阶段 LLM 路由**：**`nodes.attributes.phase_llm` / `mode_models`** 为基线；**`FrameworkRunContext.phase_llm_overrides`** 单次 tick 覆盖（见 `merge_phase_config`）。

### 5.7 AICO 优化可观测性（专用日志）

**目标：** 为 **`service_id=aico`** 的 NLP tick（`aico` / `@aico` 与 §5.5 一致）提供可选的 **优化与联调专用** 文件日志，与主应用日志（`project.logs_dir` / `logging.file_name`）**分离**；默认 **关闭**（`enabled: false`）。

**非目标：** 不替代 `monitoring` 指标；不等同于分布式 tracing；不规定外部日志分析产品。

#### 5.7.1 配置契约（系统 YAML）

在 **`agents.llm.by_service_id.aico`** 下与 LLM 字段并列增加 **`observability`** 对象（**不参与** `AgentLlmServiceConfig` 材料化，实现从 YAML 条目中剥离后再解析 LLM，见 `agent_llm_config`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `enabled` | boolean | 是否写入专用日志；默认 `false`。 |
| `log_path` | string | 相对 **backend 根目录** 的文件路径；默认 `logs/agent/aico.log`（物理路径 `backend/logs/agent/aico.log`，与主应用日志同处 `backend/logs/`，便于运维查找）。 |
| `level` | string | 专用 logger 级别：`INFO` = 阶段摘要（hooks）；`DEBUG` = **全链路**（每轮 LLM 的 system/user、`LlmCallSpec`、ToolGather 文本、HTTP 请求/响应 JSON 摘要，与 **`max_phase_output_chars`** 共用长度预算）。 |
| `max_file_size` / `backup_count` | string / int | 与主 `logging` 语义一致，用于该文件的轮转。 |
| `max_phase_output_chars` | int | 阶段输出预览、DEBUG 下 prompt/工具/HTTP JSON 等**长文本**的统一字符上限；`0` 表示不截断（慎用，易含敏感内容）。 |

环境变量覆盖可与现有 `CAMPUSWORLD_*` → 点分键规则对齐（例如 `CAMPUSWORLD_AGENTS_LLM_BY_SERVICE_ID_AICO_OBSERVABILITY_ENABLED`）。

#### 5.7.2 记录范围与隐私

- **挂载：** 配置加载 / 重载时注册专用 logger（`propagate=false`），仅写入上述文件。
- **内容：** 基于 **`AgentTickHooks`**，与 §5.5 **PDCA 阶段**（`plan` / `do` / `check` / `act` 及管线中的 `post`）对齐；记录 **阶段名、correlation、agent 节点 id、各阶段 LLM 输出摘要（可截断）**。实现中 **Act** 步对应 `ThinkingPhaseId.action`（日志字段 `phase=action`），与 YAML **`phase_prompts.act`**、**`PDCAPhase.act`** 语义一致，仅枚举名与字面 **`act`** 不同。
- **跳过 LLM：** 当某阶段 **`phase_llm` 为 `skip`** 时，日志应能区分 **「本阶段未调用 LLM」** 与 **「调用但返回空串」**（例如字段 **`skipped=true/false`**）。
- **用户输入：** 在 **`level: INFO`** 时默认 **不**落盘全文，仅记录 **长度**；**`level: DEBUG`** 且当前 tick 为 **`service_id=aico`** 时，会在 **`aico_llm_call`** 中写入经 **`max_phase_output_chars`** 截断后的 **user 段拼接文本**（含 User message / Plan / Memory 等），仅用于开发联调；其他 `npc_agent` 不因全局 YAML 而写入上述 DEBUG 行。

#### 5.7.3 实现锚点

- [`backend/app/core/log/aico_observability.py`](../../../../backend/app/core/log/aico_observability.py)：`configure_aico_observability_logging`（幂等挂载/卸载文件 handler）。
- [`backend/app/game_engine/agent_runtime/aico_observability_hooks.py`](../../../../backend/app/game_engine/agent_runtime/aico_observability_hooks.py)：`AgentTickHooks` 实现。
- [`backend/app/game_engine/agent_runtime/worker.py`](../../../../backend/app/game_engine/agent_runtime/worker.py)：`LlmPdcaAssistantWorker` 在 **`service_id=aico`** 且 **`observability.enabled`** 时注入 hooks。
- [`backend/app/core/config_manager.py`](../../../../backend/app/core/config_manager.py)：配置加载成功后调用专用日志配置函数。

---

## 6. 与 F04（`@`）的关系

- 用户侧 **发起与 AICO 的对话**：遵循 [**F04**](F04_AT_AGENT_INTERACTION_PROTOCOL.md)（`@aico <payload>` 或等价形式）。
- **`trigger_mode=nlp`** 表示 **主输入为自然语言**；**`@` 行** 同样视为 NLP 载荷的入口之一（实现可将 `@` 解析后的 `payload` 直接送入 LLM/PDCA 管线）。
- **实现锚点**：`@` 前缀在 [`SSHHandler`](../../../../backend/app/protocols/ssh_handler.py) / [`HTTPHandler`](../../../../backend/app/protocols/http_handler.py) 中优先于普通命令名解析。
- **F03** 只保证存在 **`service_id=aico`** 的图实例及本 SPEC 的配置；**解析、路由、错误码** 以 **F04** 为准。

---

## 7. 验收标准（建议）

**自动化（CI / 本地）：** `cd backend && pytest tests/commands/test_agent_f02_commands.py tests/commands/test_npc_agent_nlp.py tests/game_engine/test_agent_llm_config.py tests/game_engine/test_llm_pdca_framework.py`；`python scripts/validate_config.py`。

**手工（SSH 会话，DB 已迁移且已执行种子）：** 奇点屋 `look` 可见 **AICO**；`aico hello` 或 `@aico hello` 成功时 **终端正文为助手自然语言**（`CommandResult.message`）；**`ok` / `phase` / `handle` / `service_id`** 等机读字段在 **`CommandResult.data`**（协议层可一并返回）。未配置可用 HTTP LLM 时见命令 SPEC：**`phase=passthrough`**，正文为回显用户输入。

- [ ] 存在 **`service_id`=`aico`** 且 **`type_code`=`npc_agent`** 的节点；**`trait_mask=370`**；**`location_id`** 指向奇点屋 room。
- [ ] 奇点屋 `look` 可见 AICO（[`look_appearance`](../../../../backend/app/commands/game/look_appearance.py) 将 `npc_agent` 归入人物区）。
- [ ] `attributes` 符合附录 A（或经人工豁免的等价约束）。
- [ ] **`tool_allowlist`** 至少包含 **`help`**、**`look`**、**`whoami`**、**`primer`**、**`find`**、**`describe`** 等（Discovery Suite，经 `command_policies` 后仍可对 AICO 生效）。
- [ ] **LLM**：`settings.yaml` 中存在 **`agents.llm.by_service_id.aico`**；密钥经 **`api_key_env`**；节点 **无明文密钥**。
- [ ] **`trigger_mode=nlp`**。
- [ ] **F04**：`@aico` 解析到本节点（见 F04 SPEC）。
- [ ] **运行时**：`LlmPDCAFramework` + **`agent_run_records`**；**`aico` / `@aico`** 可返回答复。
- [ ] **Prompt**：YAML **`system_prompt` / `phase_prompts`**；合并优先级见 §5.6（**tick > prompt_overrides > model_config > YAML**）。
- [ ] **记忆（可选）**：`extra.enable_ltm: true` 时注入 **`memory_context`**（见 `build_ltm_memory_context_for_tick`）。

---

## 附录 A — `nodes.attributes` JSON Schema（AICO 实例子集）

> 在 F02 §8 全量属性上收紧 **AICO 默认实例** 的校验子集；`$id` 可为实现方内部标识。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "npc_agent.instance.AICO.attributes",
  "type": "object",
  "additionalProperties": true,
  "required": ["agent_role", "service_id", "trigger_mode", "decision_mode"],
  "properties": {
    "agent_role": { "type": "string", "enum": ["narrative_npc", "sys_worker"] },
    "enabled": { "type": "boolean" },
    "service_id": { "type": "string", "const": "aico" },
    "trigger_mode": {
      "type": "string",
      "const": "nlp",
      "description": "AICO 主触发为 NLP；与 F02 default_triggers.kind NLP 对齐"
    },
    "decision_mode": { "type": "string", "enum": ["llm", "rules", "hybrid"] },
    "cognition_profile_ref": { "type": "string" },
    "tool_allowlist": {
      "type": "array",
      "items": { "type": "string" },
      "description": "建议包含 help, look, time, version 及 agent_capabilities, agent_tools 等"
    },
    "model_config": {
      "type": "object",
      "description": "可选非密钥覆盖：temperature、max_tokens、model；主连接配置见系统 YAML"
    },
    "model_config_ref": { "type": "string", "description": "可选，指向 YAML 中 agents.llm.by_service_id 等键" },
    "phase_llm": {
      "type": "object",
      "description": "每阶段 mode：fast|plan|think|skip；可选 per-phase model 等"
    },
    "mode_models": {
      "type": "object",
      "additionalProperties": { "type": "string" },
      "description": "逻辑 mode 到 model id 的映射"
    },
    "service_account_id": { "type": ["integer", "null"] },
    "version": { "type": "string" },
    "prompt_overrides": {
      "type": "object",
      "description": "可选；非密钥，含 system_prompt / phase_prompts"
    }
  }
}
```

---

## 附录 B — 种子 JSON 示例（单节点片段）

> 仅作文档对齐；**`location_id`** 在真实种子中由查询奇点屋 room id 填充。**连接与默认 Prompt** 以 **§5.3 YAML** 为准；**`phase_llm` / `mode_models`** 在节点属性（与种子 `ensure_aico_npc_agent` 一致）。

```json
{
  "name": "AICO",
  "type_code": "npc_agent",
  "trait_mask": 370,
  "location_id": null,
  "attributes": {
    "agent_role": "narrative_npc",
    "enabled": true,
    "service_id": "aico",
    "trigger_mode": "nlp",
    "decision_mode": "llm",
    "cognition_profile_ref": "pdca_v1",
    "tool_allowlist": ["help", "look", "time", "version", "whoami", "primer", "find", "describe", "agent", "agent_capabilities", "agent_tools"],
    "model_config_ref": "aico",
    "mode_models": {
      "fast": "gpt-4o-mini",
      "plan": "gpt-4o-mini",
      "think": "gpt-4o"
    },
    "phase_llm": {
      "plan": { "mode": "fast" },
      "do": { "mode": "plan" },
      "check": { "mode": "skip" },
      "act": { "mode": "skip" }
    },
    "service_account_id": null,
    "version": "1"
  }
}
```
