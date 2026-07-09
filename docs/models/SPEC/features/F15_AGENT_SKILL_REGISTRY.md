# F15 — Agent Skill Registry & Injection（L4 经验 Skill 层）

> **Architecture Role：** 落地 [**F09**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md) §6.4 **L4 经验 Skill 层**：定义 Agent 运行时 **经验 Skill 资产**的注册、渐进式加载、按需注入与工具组意图。L4 文本作为 **可选上下文块** 注入 L3 思考管线（`LlmPDCAFramework`）的 prompt 拼接，**不**替代 L2 工具执行、**不**替代 `command_policies` 授权、**不**替代 F07 LTM `memory_context`。

**文档状态：Draft（契约先行；实现按本 SPEC 逐阶段优化）。**

**交叉引用：** [**F09**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)（L1–L4 分层真源）、[**F08**](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md)（Command-as-Tool、`ResolvedToolSurface` 冻结面、`build_llm_tool_manifest`、`prompt_fingerprint`）、[**F02**](F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)（`npc_agent` 节点 attributes）、[**F07**](F07_PER_USER_AGENT_MEMORY_AND_ASYNC_LTM_PROMOTION.md)（LTM 边界）、[**F14**](F14_AGENT_TOOL_ROUTER_PREPLAN.md)（工具路由 lexicon）、[**F16**](F16_AGENT_POLICY_ENGINE.md)（`before_skill_activation` / `before_tool_call` check_point）、[**F17**](F17_AGENT_STATE_MACHINE.md)（`react_turn_schema.selected_skill`）。

**业界对标：** Anthropic **Agent Skills**（filesystem-based，`SKILL.md` + YAML frontmatter，**progressive disclosure** 三级加载，**model-selected** by `description`）；OpenAI Agents SDK（`instructions` + `guardrails` + structured outputs —— guardrail/structured-output 层由本项目 [F16](F16_AGENT_POLICY_ENGINE.md)/[F17](F17_AGENT_STATE_MACHINE.md) 承接，非本 SPEC）。

---

## 1. Goal

- 为 Agent 提供 **可复用** 的经验 Skill 资产：定义态（`SKILL.md` + frontmatter）+ 运行时注册表 + **渐进式加载** + 按需注入 L3 prompt。
- 把 F09 §6.4 「经命令得到 / 指定方式注入」从描述性叙述落实为 **可执行契约**：`SkillRegistry`（加载 frontmatter 清单）→ `SkillRunner`（按激活加载 body）→ `SkillInjection`（注入专门 `skill-context` 段）。
- 引入 `allowed_tool_groups` 作为 Skill 对 L2 工具面的 **声明式意图**（v1 为前向兼容占位，不强制；强制收敛延后，见 §7）。

> **注：** 「可版本化」不在 v1 目标内（`SkillDefinition` 无 `version` 字段，`skill_refs` 不锁版本）；待真实版本化需求出现再加 `version` + `skill_refs` 版本钉（见 Q7）。

---

## 2. Scope / Non-Goals

- **Scope：** `npc_agent`（含 AICO）及未来系统内置 Agent 的 L4 Skill 资产；`prompt` 实现模式的文本注入；**渐进式披露**（L1 清单 + L2 body）。
- **Non-Goals：**
  - **不**引入「定义态 / 运行态两阶段 YAML 转换」（用户决策：Agent/Skill 配置以图节点 attributes + `SKILL.md` 为载体，见 F09 §5）。
  - **不**替代 L2 工具执行；Skill 不直接调用命令，仅收敛工具面意图与注入文本。
  - **不**替代 `command_policies` 授权（F08 §1.3 不变量）。
  - **不**替代 F07 LTM；`memory_context` 与 Skill 文本可并存于同一 tick（F09 §5）。
  - v1 **不**实现 `tool` / `hybrid` 实现模式（仅 `prompt`；`tool`/`hybrid` scaffolded，见 §6）。
  - v1 **不**在 tick 内动态收敛 `ResolvedToolSurface`（冻结面不变量，见 §7）。
  - v1 **不**强制 / 审计 `allowed_tool_groups`（前向兼容占位，见 §7）。
  - v1 **不**含 `input_schema` / `output_schema`（延后到 `tool`/`hybrid` 模式或 [F17](F17_AGENT_STATE_MACHINE.md) 结构化 turn，见 §6）。

---

## 3. 核心定义

### 3.1 Skill 资产形态（单文件 `SKILL.md` + frontmatter）

每条 Skill 是一个 **目录**（`backend/config/skills/<skill_id>/`），含必需的 `SKILL.md` 与可选的 `references/` / `assets/`（v1 prompt 模式不读，为 L3 预留，见 §5.4）。`SKILL.md` 采用 **YAML frontmatter + markdown body** 单文件格式（对标 Anthropic Agent Skills）：

- **frontmatter** = `SkillDefinition` 字段（L1 清单数据源，启动期解析）。
- **body** = prompt 文本（L2，仅激活时注入）。

```
backend/config/skills/retrieval_reasoning/
├── SKILL.md          # REQUIRED: frontmatter (SkillDefinition) + body (prompt text)
└── references/       # OPTIONAL: bundled docs (L3, future tool/hybrid)
```

### 3.2 `SKILL.md` 示例

```markdown
---
name: retrieval_reasoning
description: >-
  Plan and execute read-only retrieval over the live graph (look/find/describe/space)
  to ground factual claims. Use when the user asks about world state, locations,
  entities, or needs verified context before answering.
display_name: 检索推理
category: retrieval
side_effect_level: none
activation_mode: phase_mapped
allowed_in_react_states: [plan, do]
allowed_tool_groups: [read]
implementation:
  mode: prompt
runtime: {}
---

# 检索推理

[Skill body — procedural knowledge / workflow / guidance. Loaded only on activation (L2).
 Recommended ≤ 500 lines / ~5k tokens; move detail to references/.]
```

### 3.3 SkillDefinition 字段（frontmatter 解析为 dataclass）

`backend/app/game_engine/agent_runtime/skills/skill_definition.py`：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `str` | ✅ | 全局唯一 Skill id；lowercase 字母数字 + `_`/`-`，**须匹配目录名**；CampusWorld 约定 snake_case |
| `description` | `str` | ✅ | **what + when-to-use**（含触发短语）；≤1024 字符；L1 清单数据源 + 未来 model 选择信号 |
| `display_name` | `str` | ❌ | 展示名（i18n 由展示层处理；缺省取 `name`） |
| `category` | `Literal` | ❌ | Skill 认知角色分类：`reasoning` / `retrieval` / `analysis` / `observation` / `verifier` / `finalization` / `user_interaction`。**组织性分类轴**：用于审计/trace/同阶段去重（避免同 `category` 多 Skill 重复注入）；**非** 选择信号（选择由 `activation_mode` + `allowed_in_react_states` / `description` 决定，见 §3.3 / Q4） |
| `side_effect_level` | `ToolSideEffectLevel` | ❌ | **Skill 自身**的副作用等级（复用 [F08](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) §1.3 `none`/`read`/`write_low`/`write_high`）；prompt 模式文本注入 = **`none`**；`tool`/`hybrid` 模式下为代码副作用等级。**与 `allowed_tool_groups` 正交**（后者约束 Skill 可引导的工具组） |
| `activation_mode` | `Literal` | ❌ | Skill 选择模式（**显式字段**，便于调试/校验，避免用 `allowed_in_react_states` 存在性隐式编码）：`phase_mapped`（默认；确定性阶段映射，v1 自动注入 body）/ `model_selected`（model 经 [F17](F17_AGENT_STATE_MACHINE.md) `selected_skill` 自选，v1 仅 L1 暴露、body 待 F17） |
| `allowed_in_react_states` | `Tuple[str, ...]` | ❌ | **`activation_mode == phase_mapped` 时必填（≥1）**；**`== model_selected` 时禁止（须缺省）**。取值 v1 = PDCA 阶段名 `plan`/`do`/`check`/`act`（F17 状态机落地后重映射为 `reason`/`select_skill`/`propose_action` 等）。post-F17：`phase_mapped` 模式下转为 model 自选的 **约束校验** |
| `allowed_tool_groups` | `Tuple[str, ...]` | ❌ | 该 Skill 激活时 **声明可用** 的工具组；v1 取值 = `CommandToolSemantics.interaction_profile` 派生（`read`/`mutate`），**前向兼容占位，v1 不强制不审计**（见 §7） |
| `implementation.mode` | `Literal` | ✅ | `prompt` / `tool` / `hybrid`；v1 仅 `prompt` |
| `runtime` | `Dict` | ❌ | `timeout_seconds` / `max_retries` 等（prompt 模式可留空） |

**v1 不含** `input_schema` / `output_schema` / `version`（见 Non-Goals / Q6 / Q7）。

---

## 4. 资产边界（per-type vs per-instance）

| 维度 | 归属 | 载体 | 语义 |
|------|------|------|------|
| **Skill 定义（可复用资产）** | 全局（per-skill，静态） | `backend/config/skills/<id>/SKILL.md` + `SkillRegistry` | "这个 Skill **是什么**"（description、body、组） |
| **Agent 实例引用** | 图节点（per-instance，动态） | `nodes.attributes.skill_refs: List[str]` | "这个 Agent **被允许用哪些 Skill**" |

`skill_refs` 是 Agent 节点上的 **Skill id 列表**；运行时 `SkillInjection` 仅在 `skill_refs` ∩ `SkillRegistry` 内选择。**不**把 Skill 定义塞入图节点（可复用性要求定义与实例分离）。

### 4.1 与既有 `cognition_profile_ref` 的关系

- `cognition_profile_ref`（AICO seed 现存 `pdca_v1`）**当前运行时不读取**（仅 `agent` 命令展示为 `cognition`）。
- v1 引入 `skill_refs` 为 **权威 L4 引用**；`cognition_profile_ref` 保留为 **inert 遗留元数据**，不删除、不读取（surgical 原则；未来迁移再决定，见 Q3）。
- **不**复用 `cognition_profile_ref` 作为 Skill 引用载体（语义拉伸、阻碍后续演进）。

---

## 5. SkillRegistry / SkillRunner / SkillInjection（渐进式披露）

对标 Anthropic Agent Skills 的 **三级渐进式披露**：

| 级别 | 内容 | 加载时机 | token 成本 |
|------|------|---------|-----------|
| **L1 清单** | 该阶段 **eligible 集** 的 `name` + `description`（`activation_mode == model_selected` 或 phase ∈ `allowed_in_react_states`） | 启动期解析 frontmatter；**每阶段注入** user/input context 段 | 低（每 Skill ≤~1.1k 字符） |
| **L2 body** | 匹配 Skill 的 `SKILL.md` 正文（启动期缓存） | **仅匹配阶段**注入 user/input context 段（`phase_mapped` + phase 匹配；`model_selected` 待 F17 model 自选） | 中（≤~5k tokens/Skill） |
| **L3 bundled** | `references/` / `assets/` | 按需（v1 prompt 模式不读；为 `tool`/`hybrid` 预留） | 按需 |

### 5.1 SkillRegistry（`skill_registry.py`）

- **加载时机（v1 快照语义，无 hot reload，D1-a）：** 进程启动时一次性扫描 `backend/config/skills/*/SKILL.md`，**读取完整文件源码**（frontmatter + body），解析 frontmatter 到内存 `SkillDefinition`，**缓存 body 与 `definition_hash`（sha256(完整源码) 截断）到内存**；tick 内仅查询，**不读盘**。参照 `tool_router_rules.yaml` 加载模式。**v1 真无 hot reload** —— frontmatter/body/hash 同源启动期快照，进程运行中编辑 `SKILL.md` **不生效**（L1 manifest + L2 body 均不更新）；编辑生效需 **重建 registry** 或 **重启进程**（见 §12 回归测试语义）。未来 hot reload 见 Q10。
- **API：** `get(skill_id) -> SkillDefinition`、`manifest_for(skill_refs) -> List[SkillDefinition]`（L1，启动期 frontmatter 快照）、`load_body(skill_id) -> SkillBodyLoad`（L2；**从启动期内存缓存的 body + hash 返回**，不读盘——保证 frontmatter/body/hash 同源快照、无 read-gap race、无半热更新）、`contains(skill_id) -> bool`。`definition_hash` = 启动期缓存的 sha256(完整 `SKILL.md` 源码) 截断，与 L1 manifest 同快照。
- **校验：** 启动期校验 `name` 唯一且匹配目录名、`description` 非空（≤1024）、`implementation.mode` 受支持（v1 仅 `prompt`）、`activation_mode` ↔ `allowed_in_react_states` 一致性（`phase_mapped` 必填 ≥1 / `model_selected` 须缺省）；非法定义 **fail-fast**。v1 prompt 模式下 skill 目录含 `references/`/`assets/` 时记录 **warning**（v1 不读 L3，body 须自包含，见 §5.4）。

### 5.2 SkillRunner（`skill_runner.py`）

- `prompt` 模式：`load_body(skill_id)` 从 **启动期内存缓存** 返回 `SkillBodyLoad`（`text` = frontmatter 之后的 markdown 为文本块；`definition_hash` = 同快照的 sha256 截断）（v1 纯静态，无变量插值；模板引擎延后）。**不读盘**——frontmatter/body/hash 同源启动期快照，无半热更新。
- `tool` / `hybrid` 模式：**scaffolded，v1 `raise NotImplementedError`**（见 §6）。
- 输出：`SkillActivation`（`skill_id`、`text`（L2 body）、`allowed_tool_groups`、`category`、`definition_hash`），供 `SkillInjection` 与 [F16](F16_AGENT_POLICY_ENGINE.md) 审计消费。`definition_hash` 取自 **启动期同源快照**（registry 缓存，与 L1 manifest/L2 body 同启动期缓存；见 §5.1），trace provenance（body/frontmatter 修改经重建 registry 可检测，见 §12）。**v1 `allowed_tool_groups` 携带但不消费**（§7.2 占位；F16 `before_tool_call` 落地后消费）。

### 5.3 SkillInjection（`skill_injection.py`）—— 按阶段注入

**核心：按 PDCA 阶段注入，每阶段独立暴露该阶段 eligible 的 Skill 清单（L1）+ 匹配的 body（L2）+ 阶段工具面（F14）。** 不做 tick 级一次性注入。

**每阶段 eligible Skill 集（L1 清单数据源）：**

```
eligible(skill, phase) = (skill.activation_mode == "model_selected") OR (phase ∈ skill.allowed_in_react_states)
```

- `activation_mode == model_selected` 的 Skill **全阶段 eligible**（model 自选语义，见 §3.3 / Q4）。
- `activation_mode == phase_mapped` 的 Skill 仅在 `allowed_in_react_states` 列出阶段 eligible。

**L1 清单块（每阶段注入，eligible 集 → `skill-context` 段）：** 当 `skill_refs` 非空，每阶段将 eligible Skill 的 `name` + `description` 渲染为清单块（对标 Anthropic Agent Skills 的 model-readable manifest —— `description` 即触发信号）。**清单按激活状态分两段**（active vs inactive/selectable），使模型能从清单本身区分哪些 guidance 已生效，避免把 awareness-only Skill 当 active guidance 使用。**模板分版本**（避免 v1 提示模型输出未落地字段，造成调试误判/输出污染）。

**状态判定（v1）：**

- **active** = `activation_mode == phase_mapped` 且 phase ∈ `allowed_in_react_states`（body 已注入，guidance 生效）
- **inactive（awareness-only）** = `activation_mode == model_selected`（v1 body 不注入，仅清单暴露）

**v1 模板**（`selected_skill` 未落地、`model_selected` body 不消费）：

```
## Available Agent Skills

Skills are split by activation status this turn. Active skills' guidance applies; inactive skills are listed for awareness only (not active this turn).

### Active skills
- **<name>** — <description>

### Available but inactive skills
- **<name>** — <description>
```

**post-F17 模板**（`selected_skill` 落地后启用；active/selectable 划分由 [F17](F17_AGENT_STATE_MACHINE.md) 规定）：

```
## Available Agent Skills

### Active skills (guidance applies this turn)
- **<name>** — <description>

### Selectable skills (activate by emitting `selected_skill` in your turn schema, F17)
- **<name>** — <description>
```

- **顺序：** 每段内按 `skill_refs` 声明顺序（确定性、agent 作者可控、fingerprint 稳定）。
- **空段省略：** 某段无条目则不渲染该段标题（避免空 heading）。
- **不含 body 文本**（渐进式披露；body 仅 L2 注入）。
- **`description` 承载 when-to-use 触发信号**（model-selected-by-description 原则；清单行 = `name + " — " + description`，不重复字段名）。

**L2 body 注入（每阶段，仅匹配 Skill）：**

- **v1（确定性阶段映射）：** `activation_mode == phase_mapped` 且 phase ∈ `allowed_in_react_states` 的 Skill，其 body 自动注入为阶段后缀块。**`model_selected` 的 Skill body 在 v1 不自动注入**（model 自选未落地；仅 L1 清单暴露，待 F17 `selected_skill`）。
- **目标（F17，延后）：** model 经 `react_turn_schema.selected_skill` 自选；`phase_mapped` 转为 **约束校验**，`model_selected` = 无约束（自由自选）；`description` 为选择信号（见 Q4）。

**注入点与优先级（`skill-context` 注入 user/input context，与 platform system 隔离）：** Skill 内容经 **专门的 `skill-context` 通道** 注入 **user/input context**，**绝不**进入任何 platform system message。平台 system 段（`llm_pdca.py` `_phase_system` / `_phase_system_core`）仅放 **固定边界声明**（tier-1 primer、安全、command policy guardrails），**不含任何 Skill 文本**；`skill-context` 由每阶段 `SkillInjection.inject(phase, skill_refs)` 产出 = L1 清单块（前缀）+ L2 body 块（后缀），按需注入（非全量），受 F08 prompt 长度上限约束。**优先级：`skill-context` < 平台 system / 安全 / command policy**（Skill 为 advisory 经验/流程指引，不得覆盖 guardrails；对标 OpenAI/Claude Skills 的 provenance 上下文定位，非最高优先级 system 指令；物理隔离由 user/input context 通道保证，不靠 ordering）。**输入序列化顺序 = 平台 system 段 → user/input context 段（`skill-context` L1 → L2，turn 起始）→ user turn payload**。**provider 序列化（统一规则）：** `skill-context` 一律注入 **user/input context 通道**，**任何 provider 不得把 `skill-context` 拼入 system message**——Anthropic：作为 user turn 起始的独立 content block（非 system block）；OpenAI-compatible：注入 user/input context（turn 起始 context block），system message 仅含平台固定边界声明。

**注入与 fingerprint（per-loop-phase，与 [F17](F17_AGENT_STATE_MACHINE.md) §9 对齐）：** 每阶段的 LLM 输入 = 平台 system 段（固定边界）+ user/input context 段（`skill-context` L1 清单 + L2 body）+ 阶段工具面（F14 阶段子集）+ 既有输入 → 属该阶段 LLM 输入。fingerprint 按 loop 阶段计算（非 tick），入参含 `skill_context_text`（该阶段 L1 清单 + L2 body）+ `phase_tool_manifest` + 既有输入；计算移至 `llm_pdca.py` per-phase 路径（`_phase_system` / `_augment_spec_from_ctx`），移除 `npc_agent_nlp.py` tick 级计算。**角色定位（F17 §9 真源）：** fingerprint 为 **输入侧** hash，HTTP 前剥离，**v1 非正确性契约**——当前不驱动任何返回答案的缓存；skill 文本纳入是为 **trace/dedup 完整性** + **前向兼容**（未来若接入 provider prompt-cache / 内部响应缓存，per-phase + `skill_context_text` 即为正确的缓存键派生，无需返工）。即 v1 不以 fingerprint desync 为正确性 bug；但 per-phase 结构本身须正确，避免未来接入时返工。

### 5.4 L3 bundled 资源（预留）

`SKILL.md` body 可引用同目录 `references/*.md` / `assets/*`；v1 prompt 模式 **不读** L3（无 on-demand 文件加载）。**v1 prompt 模式 body 必须自包含**（不得依赖 references/assets 提供上下文，否则运行时静默缺上下文，对标 Claude/OpenAI Skills 的 supporting-files 须由运行时加载而非假设可读）；`tool`/`hybrid` 模式落地时，`SkillRunner` 按 body 指令按需读 L3（对标 Claude `{baseDir}` 模式）。`SkillDefinition` 不携带 L3 列表；L3 由 body 文本引用驱动。**启动校验**：v1 prompt 模式下若 skill 目录含 `references/` 或 `assets/`，记录 **warning**（v1 不读 L3，作者须确认 body 自包含；为 `tool`/`hybrid` 前向预留目录不阻断，见 §5.1 校验 / §12）。

---

## 6. 实现模式（mode）分阶段

| 模式 | v1 | body 来源 | 说明 |
|------|----|----------|------|
| `prompt` | ✅ 落地 | `SKILL.md` body（静态文本） | 文本注入 `skill-context` 段 |
| `tool` | ⏸ Scaffolded | — | Skill = 可调用代码；v1 `SkillRunner` `raise NotImplementedError` |
| `hybrid` | ⏸ Scaffolded | — | prompt + tool 组合；同上 |

`tool` / `hybrid` 的落地需 [F16](F16_AGENT_POLICY_ENGINE.md) `before_skill_activation` 与 [F17](F17_AGENT_STATE_MACHINE.md) 状态机就绪后另行设计；届时引入 `input_schema` / `output_schema`（v1 不含，见 Non-Goals）。

---

## 7. allowed_tool_groups 矩阵

### 7.1 组词汇来源（v1）

`command.group` 在当前代码中为 **空基础设施**（`registry.py` 索引存在但无命令赋值；`BaseCommand` 无 `group` 字段）。为避免新建并行元数据层，v1 **复用 `CommandToolSemantics.interaction_profile` 派生的组名**：

| 组名 | 来源 | 命令示例 |
|------|------|---------|
| `read` | `interaction_profile == 'read'` | `look` / `find` / `describe` / `help` / `whoami` / `space` |
| `mutate` | `interaction_profile == 'mutate'` | `create` / `go` / `enter` / `leave` / `task` / `notice` |

### 7.2 v1 收敛语义（前向兼容占位，**不强制不审计**）

- **冻结面不变量（F08 §5.1）：** `ResolvedToolSurface` 在 `LlmPdcaAssistantWorker.create` 时冻结（`tool_allowlist ∩ get_available_commands`），tick 内 `PreauthorizedToolExecutor` 不再收敛。
- **v1 `allowed_tool_groups` 为声明式占位**：Skill 声明其意图工具组，但 **v1 既不动态收敛冻结面，也不在 trace 审计**。理由：AICO 为只读助手，所有 Skill 均为 `[read]`，二元组 **无判别力**，审计空约束不产生信号。
- **真实价值延迟：** 当引入更细 `tool_group` 分类（如 `info`/`observe`/`identity`/`agent_meta`，Q2）且 [F16](F16_AGENT_POLICY_ENGINE.md) `before_tool_call` 强制落地后，`allowed_tool_groups` 才具收敛/审计意义。
- **未来硬收敛路径：** 若需硬收敛，应在 `build_resolved_tool_surface` 构造时按 `skill_refs` 并集组收敛冻结面（改 F08 §5.1），**非** tick 内动态收敛（Q1）。

### 7.3 与 F14 工具路由的优先级（目标契约）

[F14](F14_AGENT_TOOL_ROUTER_PREPLAN.md) 产出排序后的工具候选；Skill `allowed_tool_groups` 是 F14 候选的 **过滤器**（候选 ∩ Skill 组）。**v1 不强制**（占位），故 v1 F14 建议不受 Skill 组影响；强制落地后，F14 排序、F15 范围过滤，二者正交（F14 选「哪条工具最好」，F15 选「这条工具是否在当前 Skill 范围内」）。见 Q8。

---

## 8. check_point 语义（与 [F16](F16_AGENT_POLICY_ENGINE.md) 分工）

| check_point | 检查内容 | v1 |
|-------------|---------|----|
| `before_skill_activation` | (a) `skill_id ∈ skill_refs`；(b) `phase_mapped`：当前状态 ∈ `allowed_in_react_states`；`model_selected`：无状态约束 | 随 F16 落地（v1 Skill 注入由确定性映射保证，等同隐式校验） |
| `before_tool_call` | 工具 ∈ 当前激活 Skill 的 `allowed_tool_groups` | **v1 不强制**（占位）；强制延后 |

**二者分离**：`before_skill_activation` 是 Skill 激活门（refs + 状态），`before_tool_call` 是工具组门（tool ∈ groups）。勿将工具组审计混入 Skill 激活门。

---

## 9. 与 L3 思考管线的集成（实现锚点）

| 集成点 | 文件:行 | v1 改动 |
|--------|---------|---------|
| PDCA 编排 | `frameworks/llm_pdca.py` `_run_inner` (`699:940`) | **每阶段**（plan/do/check/act）调用 `SkillInjection.inject(phase, skill_refs)` 产出 `skill_context_text`，挂到 `LlmCallSpec`/context（**不**进 `_phase_system`） |
| 平台 system 段 | `llm_pdca.py` `_phase_system` / `_phase_system_core` (`91:93`, `199:203`) | **只保留平台 system**（tier-1 primer、安全、command policy）；**不**拼接任何 Skill 文本 |
| Skill-context 注入（user/input context） | call builder / provider adapter（`llm_pdca.py` call payload 组装点 / `llm_providers/*`） | 把 `skill_context_text`（L1 清单块 + L2 body 块）注入 **user/input context 通道**（turn 起始 content block），**不**进 system message；按 provider 角色序列化（§5.3 统一规则） |
| Fingerprint（per-phase） | `prompt_fingerprint.py` `compute_npc_prompt_fingerprint` (`5:7`) | **改为 per-loop-phase 计算**（非 tick）；入参增 `skill_context_text`（该阶段 L1+L2）+ 既有 `phase_tool_manifest`（F14 阶段子集） |
| Fingerprint 调用点 | `llm_pdca.py` per-phase call 组装 / `_augment_spec_from_ctx` (`271:275`) | **每阶段**计算 fingerprint 并写入 `spec.extra['prompt_fingerprint']`；移除 `npc_agent_nlp.py` tick 级计算 |
| Worker 绑定 | `worker.py` `LlmPdcaAssistantWorker.create` (`104:140`) | 从节点 attrs 读 `skill_refs`，传入 framework |
| 节点 attrs 解析 | `agent_node_phase_llm.py` / 新增 `skill_refs` 解析 | 解析 `attributes.skill_refs: List[str]` |
| 节点种子 | `db/seed_data.py` `ensure_aico_npc_agent` (`286:327`) | AICO seed 增 `skill_refs`（端到端验证） |

**不修改：** `registry.py` 核心逻辑、`resolved_tool_surface.py` 冻结面构造、`command_policies` 授权路径。**`_phase_system`/`_phase_system_core` 不再承载 Skill 文本**（Skill-context 经 user/input context 通道，由 call builder / provider adapter 注入）。

---

## 10. v1 种子 Skill 集

AICO 为只读默认助手（`tool_allowlist` = `help/look/time/version/whoami/primer/find/describe/agent`，全 `read` 组）。v1 种子 3 个通用 Skill，按 PDCA 阶段映射（满足验收「3 个 Skill 端到端通」）：

| skill_id | category | allowed_in_react_states | 映射阶段 | side_effect_level | allowed_tool_groups |
|----------|----------|------------------------|---------|-------------------|---------------------|
| `problem_framing` | `reasoning` | `[plan]` | Plan | `none` | `[read]` |
| `retrieval_reasoning` | `retrieval` | `[plan, do]` | Plan/Do | `none` | `[read]` |
| `final_synthesis` | `finalization` | `[check, act]` | Check/Act | `none` | `[read]` |

3 个 Skill 均为 `prompt` 模式 + `activation_mode: phase_mapped`（默认，确定性阶段映射）；`side_effect_level: none`（Skill 自身为文本注入，无副作用；`allowed_tool_groups: [read]` 表达其引导 read 组工具的意图，v1 占位不强制）。Skill 资产位于 `backend/config/skills/<skill_id>/SKILL.md`。

---

## 11. 与世界包 Skill 概念的边界

HiCampus 世界包存在 `data/concepts/skills.yaml`（schema: `id/world_id/concept_type/name/scope/definition.capability/bindings`），为 **世界语义概念**（包校验 + 快照，**不**入图节点、**不**被 agent tick 消费）。

- **L4 SkillRegistry（本 SPEC）** = 全局 agent 运行时经验 Skill，载体 `backend/config/skills/`。
- **世界包 Skill 概念** = 世界内容资产，载体 `app/games/<world>/data/concepts/skills.yaml`。
- **不同域，不合并**。为避免命名混淆，代码层 L4 类名用 `SkillDefinition` / `SkillRegistry`，文档统一称 **Agent Skill（L4）** vs **世界 Skill 概念**。

---

## 12. Acceptance Criteria

- [ ] `SkillRegistry` 启动期扫描 `config/skills/*/SKILL.md`，解析 frontmatter；非法定义 fail-fast
- [ ] **按阶段注入 L1**：每阶段（plan/do/check/act）`skill-context` 段含该阶段 **eligible 集**（`activation_mode == model_selected` 或 phase ∈ `allowed_in_react_states`）的 `name`+`description` 清单块，按 `skill_refs` 顺序，使用 §5.3 v1 模板
- [ ] **按阶段注入 L2**：仅 `activation_mode == phase_mapped` 且 phase ∈ `allowed_in_react_states` 的 Skill body 被注入；`model_selected` 的 Skill body 在 v1 **不**自动注入（待 F17 model 自选）
- [ ] **启动期校验**：`activation_mode` ↔ `allowed_in_react_states` 一致性（`phase_mapped` 必填 ≥1 / `model_selected` 须缺省）违规 fail-fast
- [ ] **Fingerprint per-loop-phase（trace 完整性，非 v1 正确性契约，对齐 F17 §9）**：fingerprint 按 loop 阶段计算（非 tick），纳入该阶段 `skill_context_text`（L1 清单 + L2 body）+ `phase_tool_manifest`；HTTP 前剥离，v1 不驱动返回答案的缓存——纳入为 trace/dedup 完整性 + 前向兼容（未来接入缓存时无需返工）
- [ ] AICO seed 节点含 `skill_refs: [problem_framing, retrieval_reasoning, final_synthesis]`，端到端 tick 每阶段注入 eligible L1 清单 + 阶段匹配 L2 body
- [ ] `allowed_tool_groups` v1 **不强制、不审计**（冻结面不变量保持；trace 不含 group 违规行）
- [ ] `tool`/`hybrid` 模式 `raise NotImplementedError`
- [ ] trace 记录 `skill_activated`（`{skill_id, phase, states, definition_hash}`）；`definition_hash` = 启动期缓存的 sha256(full `SKILL.md`) 截断，**与 L1 manifest/L2 body 同源快照**（frontmatter/body/hash 同启动期，无半热更新），trace provenance
- [ ] **Skill prompt-injection 边界测试**：验证 L1 清单仅含 eligible 集、L2 body 仅含匹配 Skill、非匹配/非 eligible 文本不进入 `skill-context`；**L1 active 段仅含 `phase_mapped`+phase 匹配、inactive 段仅含 `model_selected`**（状态标记可区分）；空段省略；**平台 system message 不含任何 Skill 文本**（`_phase_system` 仅平台边界）；prompt 长度上限生效
- [ ] **Skill 修改回归测试（重建 registry 后生效，v1 无 hot reload）**：修改 `SKILL.md` frontmatter/body 后 **重建 registry**（或重启），trace 中 `definition_hash` 变化 + fingerprint 输入变化（L1 描述改 → manifest 文本变；L2 body 改 → `skill_context_text` 变）；二者均可验证。**v1 不测运行期 hot reload**（进程运行中改文件 **L1/L2 均不更新**，见 §5.1 / Q10）
- [ ] **L3 bundled 资源告警**：v1 prompt 模式 skill 目录含 `references/`/`assets/` 时启动期记录 warning；body 自包含契约文档化
- [ ] **provider 优先级边界测试（统一 user/input context 规则）**：**所有 provider** `skill_context_text` 注入 user/input context 通道、**不**进 system message——Anthropic 路径 `skill-context` 为 user turn 起始 content block（非 system block）；OpenAI-compatible 路径注入 user/input context、不拼入 system message
- [ ] **Skill 激活评估（v1 确定性）**：golden = phase → expected active skill ids（plan→`[problem_framing, retrieval_reasoning]`、do→`[retrieval_reasoning]`、check→`[final_synthesis]`、act→`[final_synthesis]`）；should-activate（映射阶段→active）与 should-not-activate（非映射阶段→不 active）用例覆盖
- [ ] `cognition_profile_ref` 保留为 inert，不被新路径读取
- [ ] 单元测试位于 `backend/tests/game_engine/`
- [ ] **实施前置（同 PR 必做）**：[**F09**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md) §3 L4 行 / §5 L4 行 / §6.4 / §7 L4 行 已同步本 SPEC（`agent_runtime/skills/` + `config/skills/` + `skill_refs` + `skill-context` 经 user/input context），分层真源无「无单一目录；未来」遗留

---

## 13. Open Questions（待确认 / 后续阶段）

- **Q1（收敛强度）：** `allowed_tool_groups` 何时从占位升级为硬收敛？候选：构造期冻结面收敛 vs F16 `before_tool_call` 强制阻断。**v1 取占位。**
- **Q2（组词汇）：** v1 用 `interaction_profile` 二元组（无判别力）；何时引入更细 `tool_group` 字段（如 `info`/`observe`/`identity`/`agent_meta`）？延后到有 Skill 需要更细粒度时。
- **Q3（`cognition_profile_ref` 处置）：** v1 保留 inert；是否在后续阶段从 seed + `agent` 命令输出移除？延后。
- **Q4（Skill 选择）——方向已定 + 显式 `activation_mode` 字段：** `activation_mode == phase_mapped`（默认）= 确定性阶段映射（v1 自动注入 body；post-F17 转为 model 自选的约束校验）；`== model_selected` = model 经 [F17](F17_AGENT_STATE_MACHINE.md) `selected_skill` 自选（v1 仅 L1 暴露、body 待 F17）。`allowed_in_react_states` 的必填/禁止由 `activation_mode` 决定（见 §3.3）。`description` 为 model 选择信号（已就位）。
- **Q5（fingerprint）——已决（per-loop-phase，Option B 对齐 F17 §9）：** skill 文本（L1+L2）**纳入** fingerprint 哈希，且 **按 loop 阶段计算**（非 tick）。**角色：输入侧 hash，HTTP 前剥离，v1 非正确性契约**（当前不驱动返回答案的缓存；代码现实：fingerprint 当前 vestigial）。纳入为 trace/dedup 完整性 + 前向兼容（修订原 C3 的“正确性不变量/无 desync”框架）。未来若接入 provider prompt-cache / 内部响应缓存（Option A），per-phase + `skill_context_text` 即为正确缓存键，升级为正确性契约。
- **Q6（i18n）：** Skill 文本模板是否走 i18n（`zh-CN`/`en-US`）？v1 单语模板；多语延后。
- **Q7（版本化）：** v1 不含 `version`，`skill_refs` 不锁版本；待真实版本化需求出现再加 `version` + `skill_refs` 版本钉。
- **Q8（F15↔F14 强制优先级）：** v1 不强制（F14 建议不受影响）；`allowed_tool_groups` 强制落地后定义 F14 候选 ∩ Skill 组的过滤契约。
- **Q9（Skill 行为/输出质量 eval）——v1 部分、其余延后：** v1 仅做 **确定性激活评估**（§12 golden：phase→active skill ids，should-/should-not-activate）。**延后**：scenario-based should-trigger/should-not-trigger（post-F17 `selected_skill` model 自选场景）+ 输出质量 **fresh-session golden baseline** 对比（"是否调用"与"调用后输出质量"分离评估，对标 Claude Skills eval）——需 LLM eval harness，待评估基础设施就绪后落地。
- **Q10（hot reload / snapshot 一致性）——v1 已决（D1-a，真无 hot reload）：** v1 启动期缓存完整源码（frontmatter + body + hash 同源快照），`load_body` 从内存返回（不读盘）；运行期改 `SKILL.md` **L1/L2 均不更新**，需重建 registry/重启生效（§5.1）。**未来 hot reload**（同 snapshot + 文件变更检测/版本号）延后到有运行期热更新需求时。

---

## 14. 后续

- ~~实现锚点更新 [**F09**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md) §6.4 / §7 L4 行~~ → **已前移为 §12 实施前置验收**（F09 同步同 PR 必做）。
- `before_skill_activation` / `before_tool_call` check_point 由 [**F16**](F16_AGENT_POLICY_ENGINE.md) 实现（语义见 §8）。
- `react_turn_schema.selected_skill`（model 自选）由 [**F17**](F17_AGENT_STATE_MACHINE.md) 实现；落地后 Q4 收敛。
- `compute_npc_prompt_fingerprint` **改为 per-loop-phase 计算**，扩展 `skill_context_text` 入参（§9 锚点）；移除 `npc_agent_nlp.py` tick 级 fingerprint 计算。**角色对齐 F17 §9**：输入侧、HTTP 前剥离、v1 非正确性契约；未来接入缓存时升级为正确性契约（Option A 路径）。
- Skill 行为/输出质量 eval（scenario-based should-trigger + fresh-session golden baseline）由 Q9 跟踪；post-F17 `selected_skill` 落地后收敛。
