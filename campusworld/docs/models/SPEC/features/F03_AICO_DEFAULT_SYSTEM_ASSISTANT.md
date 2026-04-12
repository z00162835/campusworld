# F03 — 系统默认助手 AICO（`npc_agent` 实例）SPEC

> **Architecture Role：** 定义 CampusWorld **内置单例**助手 **AICO**：图上锚定奇点屋、不可移动、LLM + PDCA；**用户交互入口**（`@` / `@aico`）见 companion [**F04**](F04_AT_AGENT_INTERACTION_PROTOCOL.md)。

**文档状态：Draft — 待人工审核**

**交叉引用：** [`F02`](F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)（`npc_agent` 通用模型）、[`F04`](F04_AT_AGENT_INTERACTION_PROTOCOL.md)（`@` 协议）、[`F01`](../../../database/SPEC/features/F01_TRAIT_CLASS_MASK_FOR_AGENT.md)（trait）、[`F11`](../../../api/SPEC/features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md)（数据访问主体）。

**实现锚点（非 exhaustive）：** [`backend/app/models/things/agents.py`](../../../../backend/app/models/things/agents.py)、[`backend/app/commands/agent_command_context.py`](../../../../backend/app/commands/agent_command_context.py)、[`backend/app/commands/agent_commands.py`](../../../../backend/app/commands/agent_commands.py)（`agent_nlp`）、[`backend/app/game_engine/agent_runtime/`](../../../../backend/app/game_engine/agent_runtime/)（`LlmPdcaAssistantWorker`、`LlmPDCAFramework`）、[`backend/app/constants/trait_mask.py`](../../../../backend/app/constants/trait_mask.py)、[`backend/app/core/settings.py`](../../../../backend/app/core/settings.py) / [`backend/config/settings.yaml`](../../../../backend/config/settings.yaml)（**系统 Agent LLM + 默认 Prompt**）、[`backend/db/ontology/graph_seed_node_types.yaml`](../../../../backend/db/ontology/graph_seed_node_types.yaml)、[`backend/db/seed_data.py`](../../../../backend/db/seed_data.py)（种子落地时）。运行时决策记录见 [`docs/architecture/adr/ADR-F03-AICO-NL-Pipeline.md`](../../../architecture/adr/ADR-F03-AICO-NL-Pipeline.md)。

---

## 1. Goal

- 提供 **系统级默认助手** **AICO**（展示名），帮助用户理解 CampusWorld世界各种知识。
- 以 **单一 `npc_agent` 图节点** 表达实例；**静态配置** 在 `nodes.attributes`（见 §5、附录 A）；记忆与运行过程在 F02 独立表。
- **认知**：`decision_mode: llm`，思维框架 **PDCA**（与 `agent_run_records.phase` 对齐）；工具侧经 **命令注册表** + 授权（与 F02 §6 一致）。
- **可执行命令（`tool_allowlist`）**：与 **默认普通用户** 在会话中可用的 **系统/基础命令集** 对齐（如 **`help`**、**`look`**、**`time`**、**`version`** 等，以注册表与 `command_policies` 为准），并可在白名单中包含 **`agent_capabilities`**、**`agent_tools`** 等 Agent 自省类命令；须与 **服务账号** 权限及策略一致。
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
| `model_config` | object | 否 | — | **可选**；若与 §5.3 YAML 并存，**以 YAML 为主**，图中仅允许 **非密钥** 覆盖或 **引用键**（见 §5.4）。 |
| `model_config_ref` | string | 否 | 见 §5.3 | 指向 YAML 中某 Agent 配置键（如 `aico`），实现时与 `service_id` 默认绑定。 |
| `service_account_id` | integer \| null | 否 | `null` | 指向 `type_code=account` 的节点 id；**未绑定时** 工具执行回退为 invoker 上下文（见 [`agent_command_context.py`](../../../../backend/app/commands/agent_command_context.py)）。 |
| `version` | string | 否 | `"1"` | |

**`tool_allowlist` v1 建议默认值（与「默认 user 可用命令集」对齐，可随命令注册表与策略演进）：**

```json
["help", "look", "time", "version", "agent_capabilities", "agent_tools"]
```

**说明：**

- **`help`**、**`look`**、**`time`**、**`version`** 等对应 [`system_commands.py`](../../../../backend/app/commands/system_commands.py) 中已注册的系统命令，语义上与普通用户会话中 **默认可用** 的基础集一致；**是否**出现在 AICO 的 **有效** 工具列表还受 **`get_available_commands`**（`command_policies` + 服务账号权限）过滤。
- **`agent_capabilities`**、**`agent_tools`** 用于自省与能力查询；若产品希望 AICO 仅回答知识、不自调 `agent_run`，可不在白名单中加入 `agent_run`。
- 后续可追加经策略允许的 **只读图/本体查询** 类命令名；须与 `command_policies` 及服务账号权限一致。

**与 F02 `default_triggers`：** 若需在类型层表达完整触发器模板，可使用 `default_triggers: [{ "kind": "NLP", "config": { } }]`；实例层以 **`trigger_mode`** 为 **摘要字段**，调度与路由逻辑 **以 `trigger_mode` + F04 为准**，避免与 F02 枚举冲突（`NLP` ↔ `nlp` 大小写由实现统一）。

### 5.3 系统配置 YAML 中的 LLM（主配置源）

**原则：** AICO（及未来 **系统内置 Agent**）使用的 **LLM provider、model、API key、temperature** 等，**以** CampusWorld **应用配置 YAML** 为 **主配置源**（例如 [`backend/config/settings.yaml`](../../../../backend/config/settings.yaml)，由 [`config_manager.py`](../../../../backend/app/core/config_manager.py) / [`settings.py`](../../../../backend/app/core/settings.py) 加载；支持 `settings.dev.yaml` / `settings.prod.yaml` 等覆盖）。

**要求：**

1. **按 Agent 区分**：配置以 **`service_id`**（或实现约定的 **逻辑键**）为维度，使 **不同系统 Agent** 可使用 **不同** provider、endpoint、模型名、温度、密钥等。
2. **密钥**：**推荐** `api_key_env: <环境变量名>` 或 `credentials_ref` 指向密钥管理；**禁止**将生产密钥提交进仓库；开发环境可本地覆盖。
3. **与图的关系**：运行时优先从 **YAML** 读取 LLM 参数；**不在** `nodes.attributes` 中存储 **明文 API key**（F02 §8 不变式仍适用）。

**建议 YAML 形状（示例，非最终实现唯一形式）：**

```yaml
# 建议置于 settings.yaml 顶层或 app 下，由实现选型并文档化唯一键名
agents:
  llm:
    # 按 npc_agent.attributes.service_id 索引
    by_service_id:
      aico:
        provider: openai_compatible   # 或 openai、azure_openai 等，实现枚举
        base_url: ""                  # 可选，兼容 OpenAI 兼容网关
        api_key_env: "AICO_OPENAI_API_KEY"   # 推荐：环境变量名
        model: "gpt-4o-mini"
        temperature: 0.2
        max_tokens: 4096
        extra: {}                     # 提供商特定参数
        system_prompt: >-            # 初始系统 Prompt（可与阶段指令分开展示）
          You are AICO, the CampusWorld assistant. ...
        phase_prompts:                # 可选：按 PDCA 阶段注入补充指令
          plan: "..."
          do: "..."
          check: "..."
          act: "..."
        mode_models:                  # 将逻辑 mode 映射到具体 model id
          fast: "gpt-4o-mini"
          plan: "gpt-4o-mini"
          think: "gpt-4o"
        phase_llm:                    # 每阶段：fast | plan | think | skip
          plan: { mode: fast }
          do: { mode: plan }
          check: { mode: skip }       # skip = 该阶段不调用 LLM，trace 记 skipped
          act: { mode: skip }
        use_http_llm: false            # true 且 api_key_env 有值时用 HTTP 客户端
      # 其他系统 Agent 示例：
      # other_sys_agent:
      #   provider: ...
      #   model: ...
```

实现侧在加载 **AICO** 运行时：用 **`service_id=aico`** 读取 `agents.llm.by_service_id.aico`（或等价路径），合并 **Pydantic Settings** 模型字段。

### 5.4 图节点中的覆盖（可选、非密钥）

- **`model_config_ref`**：可指向 YAML 内 **键路径** 或 **逻辑名**（与 `by_service_id` 对齐），便于在 **同一 `service_id`** 下切换配置段（如 `aico` → `aico_preview`）。
- **内联 `model_config`**（F02）：仅允许 **非密钥** 字段（如 `temperature` 覆盖）；若与 YAML 冲突，**SPEC 建议** — **YAML 为默认**，图中覆盖仅用于 **运维微调**（实现需定义优先级并写测试）。

**种子默认值：** 新节点可 **省略** `model_config` 与密钥，仅依赖 §5.3；若需显式占位，见附录 B。

### 5.5 运行时管线（自然语言 + PDCA + 记忆 + LLM）

AICO 的 **可验收执行语义**（与仅声明 `decision_mode: llm` 不同）包含下列 **逻辑阶段**（与 `agent_run_records.phase` 及 F02 `cognition_models[].steps` 对齐）：

1. **输入**：用户自然语言载荷（含 F04 `@aico <payload>` 解析结果）进入 **`FrameworkRunContext.payload`**（建议键 `message` / `text`）。
2. **记忆加载（可选）**：在 **Plan** 之前或之内，由实现从 F02 记忆表检索相关片段（如 **`agent_long_term_memory`** + [`ltm_semantic_retrieval`](../../../../backend/app/services/ltm_semantic_retrieval.py)）；检索结果以 **非密钥短文本** 注入 **`FrameworkRunContext.memory_context`**（不得把长对话堆进 `nodes.attributes`）。
3. **上下文整合**：合并 **系统 Prompt**、**分阶段指令**（见 §5.6）、用户消息、`memory_context`、以及会话/世界辅助字段（由调用方放入 `payload` 或单独上下文字段）。
4. **PDCA + LLM**：按 **Plan → Do → Check → Act** 推进；每阶段由 **`phase_llm.<phase>.mode`** 决定 **fast / plan / think** 路由（映射到 **`mode_models`** 或阶段内 **`model`** 覆盖）或 **`skip`**（不调用 LLM，trace 记 **`skipped`**）。参考实现 **`LlmPDCAFramework`** 对各非 `skip` 阶段调用 **`LlmClient.complete(..., call_spec)`**；默认 **Act** 可为 **`skip`**（仅输出 **Do** 结果）。
5. **生成答复**：面向用户的 **最终自然语言** 作为运行结果返回（与 F04 回显路径对接）。
6. **回馈**：将阶段追踪写入 **`agent_run_records.command_trace`**，必要时追加 **`agent_memory_entries`（raw）** 等（F02 §9）；审计类摘要可经 `append_raw`。

**命令入口（调试/联调）：** `agent_nlp <service_id> <message...>`、`aico <message...>`，以及与 F04 一致的 **`@<handle> <message...>`**（见 [`at_agent_dispatch.py`](../../../../backend/app/commands/at_agent_dispatch.py)、[`npc_agent_nlp.py`](../../../../backend/app/commands/npc_agent_nlp.py)）要求目标节点 **`decision_mode=llm`**，运行时 **`LlmPdcaAssistantWorker`** / **`run_npc_agent_nlp_tick`**。

### 5.6 Prompt 与分阶段注入 — 合并优先级

| 来源 | 内容 | 说明 |
|------|------|------|
| **系统 YAML** `agents.llm.by_service_id.<key>.system_prompt` | 初始系统 Prompt | **主配置源**；`<key>` 默认为 `service_id`，或由 `model_config_ref` 覆盖 |
| **系统 YAML** `agents.llm.by_service_id.<key>.phase_prompts` | `plan` / `do` / `check` / `act` 的阶段性补充指令 | 与 PDCA 阶段名一致；实现可将每阶段合并为「system + 阶段后缀」 |
| **单次 tick 覆盖** `FrameworkRunContext.system_prompt` / `phase_prompts` | 覆盖或追加 | 供 F04 路由层注入会话级覆盖；**同名字段以 tick 覆盖为准** |
| **`FrameworkRunContext.memory_context`** | 检索到的记忆文本 | 仅承载内容，**不**替代系统 Prompt |

图中 **`nodes.attributes`** 可预留 **非密钥** 的 `prompt_overrides`（对象，与 YAML 同形）作为运维微调；与 YAML 冲突时 **YAML 为默认，图中为覆盖**（须单元测试固定优先级）。

---

## 6. 与 F04（`@`）的关系

- 用户侧 **发起与 AICO 的对话**：遵循 [**F04**](F04_AT_AGENT_INTERACTION_PROTOCOL.md)（`@aico <payload>` 或等价形式）。
- **`trigger_mode=nlp`** 表示 **主输入为自然语言**；**`@` 行** 同样视为 NLP 载荷的入口之一（实现可将 `@` 解析后的 `payload` 直接送入 LLM/PDCA 管线）。
- **实现锚点**：`@` 前缀在 [`SSHHandler`](../../../../backend/app/protocols/ssh_handler.py) / [`HTTPHandler`](../../../../backend/app/protocols/http_handler.py) 中优先于普通命令名解析。
- **F03** 只保证存在 **`service_id=aico`** 的图实例及本 SPEC 的配置；**解析、路由、错误码** 以 **F04** 为准。

---

## 7. 验收标准（建议）

- [ ] 存在 **`service_id`=`aico`** 且 **`type_code`=`npc_agent`** 的节点；**`trait_mask=370`**；**`location_id`** 指向奇点屋 room。
- [ ] 奇点屋 `look` 可见 AICO（呈现层）。
- [ ] `attributes` 符合附录 A JSON Schema（或经人工豁免的等价约束）。
- [ ] **`tool_allowlist`** 至少包含 **`help`**、**`look`**、**`time`**、**`version`** 等与默认用户基础集对齐项（经策略与 `get_available_commands` 后仍可对 AICO 生效）。
- [ ] **LLM**：`settings.yaml`（或等价）中存在 **`agents.llm.by_service_id.aico`**（或实现约定的等价键），可配置 **provider、model、api_key（经环境变量或安全引用）、temperature**；图中 **无明文密钥**。
- [ ] **`trigger_mode`** 已设置且 AICO 默认为 **`nlp`**（NLP 触发）。
- [ ] 与 **F04** 联调：`@aico` 能解析到本节点（实现阶段）。
- [ ] **运行时**：`LlmPDCAFramework`（或等价）可对 **NLP 载荷** 执行带 **`agent_run_records`** 追踪的 PDCA；**`agent_nlp`** 或 F04 路由可对 `service_id=aico` 成功返回答复。
- [ ] **Prompt**：YAML 中存在 **`system_prompt`** 与可选 **`phase_prompts`**；或单次 tick 通过 **`FrameworkRunContext`** 注入等效覆盖。
- [ ] **记忆（可选）**：若启用 LTM，Plan 前/内检索注入 **`memory_context`** 的行为与 F02 记忆表一致且有测试。

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
    "model_config": { "type": "object", "description": "可选非密钥覆盖；主 LLM 配置见系统 YAML" },
    "model_config_ref": { "type": "string", "description": "可选，指向 YAML 中 agents.llm.by_service_id 等键" },
    "service_account_id": { "type": ["integer", "null"] },
    "version": { "type": "string" },
    "prompt_overrides": {
      "type": "object",
      "description": "可选；非密钥，形状同 agents.llm.by_service_id 中单服务条目中的 system_prompt / phase_prompts"
    }
  }
}
```

---

## 附录 B — 种子 JSON 示例（单节点片段）

> 仅作文档对齐；**`location_id`** 在真实种子中由查询奇点屋 room id 填充。**LLM** 以 **§5.3 系统 YAML** 为准，图中可 **省略** `model_config` 明文。

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
    "tool_allowlist": ["help", "look", "time", "version", "agent_capabilities", "agent_tools"],
    "model_config_ref": "aico",
    "service_account_id": null,
    "version": "1"
  }
}
```
