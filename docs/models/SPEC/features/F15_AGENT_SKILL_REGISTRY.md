# F15 — Agent Skill Registry & Injection（L4 经验 Skill 层）

> **Architecture Role：** 落地 [**F09**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md) §6.4 **L4 经验 Skill 层**：定义 Agent 运行时 **经验 Skill 资产**的注册、加载、按阶段注入与工具组权限矩阵。L4 文本作为 **可选上下文块** 注入 L3 思考管线（`LlmPDCAFramework`）的 prompt 拼接，**不**替代 L2 工具执行、**不**替代 `command_policies` 授权、**不**替代 F07 LTM `memory_context`。

**文档状态：Draft（契约先行；实现按本 SPEC 逐阶段优化）。**

**交叉引用：** [**F09**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)（L1–L4 分层真源）、[**F08**](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md)（Command-as-Tool、`ResolvedToolSurface` 冻结面、`build_llm_tool_manifest`）、[**F02**](F02_INTELLIGENT_AGENT_SERVICE_TYPE.md)（`npc_agent` 节点 attributes）、[**F07**](F07_PER_USER_AGENT_MEMORY_AND_ASYNC_LTM_PROMOTION.md)（LTM 边界）、[**F14**](F14_AGENT_TOOL_ROUTER_PREPLAN.md)（工具路由 lexicon）、[**F16**](F16_AGENT_POLICY_ENGINE.md)（`before_skill_activation` check_point）。

---

## 1. Goal

- 为 Agent 提供 **可版本化、可复用** 的经验 Skill 资产：定义态（YAML）+ 运行时注册表 + 按 PDCA 阶段注入。
- 把 F09 §6.4 「经命令得到 / 指定方式注入」从描述性叙述落实为 **可执行契约**：`SkillRegistry`（加载）→ `SkillRunner`（执行）→ `SkillInjection`（按阶段注入 L3 prompt）。
- 引入 `allowed_tool_groups` 矩阵，作为 Skill 对 L2 工具面的 **声明式收敛意图**，并由 F16 Policy 引擎在 `before_skill_activation` 审计/执行。

## 2. Scope / Non-Goals

- **Scope：** `npc_agent`（含 AICO）及未来系统内置 Agent 的 L4 Skill 资产；`prompt` 实现模式的文本注入。
- **Non-Goals：**
  - **不**引入「定义态 / 运行态两阶段 YAML 转换」（用户决策：Agent/Skill 配置以图节点 attributes + YAML 为载体，见 F09 §5 设计原则）。
  - **不**替代 L2 工具执行；Skill 不直接调用命令，仅收敛工具面意图与注入文本。
  - **不**替代 `command_policies` 授权（F08 §1.3 不变量）。
  - **不**替代 F07 LTM；`memory_context` 与 Skill 文本可并存于同一 tick（F09 §5）。
  - v1 **不**实现 `tool` / `hybrid` 实现模式（仅 `prompt` 模式；`tool`/`hybrid` 为 scaffolded/deferred，见 §6）。
  - v1 **不**在 tick 内动态收敛 `ResolvedToolSurface`（冻结面不变量，见 §7）。

---

## 3. 核心定义

### 3.1 SkillDefinition

每条 Skill 是一个 **可版本化的经验条目**，定义态为 YAML（`backend/config/skills/<skill_id>.yaml`），运行时加载为 `SkillDefinition` dataclass（`backend/app/game_engine/agent_runtime/skills/skill_definition.py`）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `skill_id` | `str` | 全局唯一标识（kebab/snake，跨 Agent 复用） |
| `display_name` | `str` | 展示名（i18n 由展示层处理） |
| `category` | `Literal` | `reasoning` / `retrieval` / `analysis` / `observation` / `verifier` / `finalization` / `user_interaction` |
| `side_effect_level` | `ToolSideEffectLevel` | 复用 [**F08**](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) §1.3 的 `none`/`read`/`write_low`/`write_high`；Skill 本身的副作用等级（prompt 模式默认 `none`） |
| `allowed_in_react_states` | `Tuple[str, ...]` | 允许激活该 Skill 的状态名；**v1 使用 PDCA 阶段名** `plan`/`do`/`check`/`act`（Phase 3 状态机落地后重映射为 `reason`/`select_skill`/`propose_action` 等） |
| `allowed_tool_groups` | `Tuple[str, ...]` | 该 Skill 激活时 **声明可用** 的工具组；v1 取值 = `CommandToolSemantics.interaction_profile` 派生的组名（`read` / `mutate`），见 §7 |
| `implementation.mode` | `Literal` | `prompt` / `tool` / `hybrid`；v1 仅落地 `prompt` |
| `implementation.prompt_ref` | `str` | `prompt` 模式下 Skill 文本模板的相对路径（如 `skills/retrieval_reasoning/SKILL.md`，相对 `backend/config/`） |
| `input_schema` / `output_schema` | `Optional[Dict]` | JSON Schema；`prompt` 模式下为 **声明式契约**（供 F18 Quality Gates 校验与审计），不强制 LLM 输出结构 |
| `runtime` | `Dict` | `timeout_seconds` / `max_retries` 等（v1 prompt 模式可留空） |

### 3.2 Skill YAML 示例

```yaml
# backend/config/skills/retrieval_reasoning.yaml
skill_id: retrieval_reasoning
display_name: 检索推理
category: retrieval
side_effect_level: read
allowed_in_react_states: [plan, do]
allowed_tool_groups: [read]
implementation:
  mode: prompt
  prompt_ref: skills/retrieval_reasoning/SKILL.md
input_schema: {required: [user_intent]}
output_schema: {required: [retrieval_plan, confidence]}
```

---

## 4. 资产边界（per-type vs per-instance）

| 维度 | 归属 | 载体 | 语义 |
|------|------|------|------|
| **Skill 定义（可复用资产）** | 全局（per-skill，静态） | `backend/config/skills/<id>.yaml` + `SkillRegistry` | "这个 Skill **是什么**"（文本、契约、组） |
| **Agent 实例引用** | 图节点（per-instance，动态） | `nodes.attributes.skill_refs: List[str]` | "这个 Agent **被允许用哪些 Skill**" |

`skill_refs` 是 Agent 节点上的 **Skill id 列表**；运行时 `SkillInjection` 仅在 `skill_refs` ∩ `SkillRegistry` 内选择。**不**把 Skill 定义塞入图节点（可复用性要求定义与实例分离）。

### 4.1 与既有 `cognition_profile_ref` 的关系

- `cognition_profile_ref`（AICO seed 现存 `pdca_v1`）**当前运行时不读取**（仅 `agent` 命令展示为 `cognition`）。
- v1 引入 `skill_refs` 为 **权威 L4 引用**；`cognition_profile_ref` 保留为 **inert 遗留元数据**，不删除、不读取（surgical 原则；未来迁移再决定）。
- **不**复用 `cognition_profile_ref` 作为 Skill 引用载体（语义拉伸、阻碍后续演进）。

---

## 5. SkillRegistry / SkillRunner / SkillInjection

### 5.1 SkillRegistry（`skill_registry.py`）

- **加载时机：** 进程启动时一次性加载 `backend/config/skills/*.yaml` 到内存注册表（缓存，参照 `tool_router_rules.yaml` 加载模式）；tick 内仅查询，不读盘。
- **API：** `get(skill_id) -> SkillDefinition`、`all() -> Iterable[SkillDefinition]`、`contains(skill_id) -> bool`。
- **校验：** 加载时校验 `skill_id` 唯一、`category` 合法、`implementation.mode` 受支持（v1 仅 `prompt`）；非法定义启动期 fail-fast。

### 5.2 SkillRunner（`skill_runner.py`）

- `prompt` 模式：渲染 `prompt_ref` 模板为文本块（v1 纯静态文本，无变量插值；模板引擎延后）。
- `tool` / `hybrid` 模式：**scaffolded，v1 raise `NotImplementedError`**（见 §6 Deferred）。
- 输出：`SkillActivation`（含 `skill_id`、`text`、`allowed_tool_groups`、`category`），供 `SkillInjection` 与 F16 审计消费。

### 5.3 SkillInjection（`skill_injection.py`）

- **选择机制（v1）：** **确定性阶段→Skill 映射**。依据当前 PDCA 阶段 + 节点 `skill_refs` + `SkillDefinition.allowed_in_react_states` ∩ `category` 选择 0..N 个 Skill。**LLM 自选 Skill 延后到 Phase 3**（`react_turn_schema.selected_skill`，见 [**F17**](F17_AGENT_STATE_MACHINE.md)）。
- **注入点：** L3 prompt 的 **system 段**（`llm_pdca.py` `_phase_system` / `_phase_system_core` 拼接）。Skill 文本作为 **可选 system 后缀块** 注入，按阶段按需注入（非全量），受 F08 prompt 长度上限约束。
- **注入与 fingerprint：** Skill 文本进入 system 段，**不**进入 `compute_npc_prompt_fingerprint` 哈希输入（`world_snapshot`/`tool_manifest_text`/`user_message`）。fingerprint 是 provider cache key（HTTP 前已被剥离，非正确性契约）；Skill 文本注入不改 fingerprint 输入，**可接受** cache-key 与实际 system 输入的 desync。若后续需精确缓存失效，可扩展 fingerprint 输入（Open Question Q5）。

---

## 6. 实现模式（mode）分阶段

| 模式 | v1 | 说明 |
|------|----|------|
| `prompt` | ✅ 落地 | 文本注入 L3 system 段 |
| `tool` | ⏸ Scaffolded | Skill = 可调用代码；v1 `SkillRunner` raise `NotImplementedError` |
| `hybrid` | ⏸ Scaffolded | prompt + tool 组合；同上 |

`tool` / `hybrid` 的落地需 F16 Policy `before_skill_activation` 与 F17 状态机就绪后另行设计，**不在本 SPEC v1 契约内**。

---

## 7. allowed_tool_groups 矩阵

### 7.1 组词汇来源（v1 决策）

`command.group` 在当前代码中为 **空基础设施**（`registry.py` 索引存在但无命令赋值；`BaseCommand` 无 `group` 字段）。为避免新建并行元数据层，v1 **复用 `CommandToolSemantics.interaction_profile` 派生的组名**：

| 组名 | 来源 | 命令示例 |
|------|------|---------|
| `read` | `interaction_profile == 'read'` | `look` / `find` / `describe` / `help` / `whoami` / `space` |
| `mutate` | `interaction_profile == 'mutate'` | `create` / `go` / `enter` / `leave` / `task` / `notice` |

`skill.allowed_tool_groups` 取值为上述组名的子集。**未来**若引入更细工具组（如 `read_context` / `world_navigation` / `admin`），可在 `CommandToolSemantics` 上新增 `tool_group` 字段（Open Question Q2），届时本节词汇表升级。

### 7.2 收敛语义（v1：声明式 / 审计式，非冻结面收敛）

- **冻结面不变量（F08 §5.1）：** `ResolvedToolSurface` 在 `LlmPdcaAssistantWorker.create` 时冻结（`tool_allowlist ∩ get_available_commands`），tick 内 `PreauthorizedToolExecutor` 不再收敛。
- **v1 不在 tick 内动态收敛冻结面**（破坏不变量且热路径重复鉴权）。`allowed_tool_groups` 在 v1 为 **声明式 + 审计式**：
  - Skill 激活时，`SkillActivation.allowed_tool_groups` 写入 `command_trace`（F10 审计行）。
  - F16 Policy 引擎在 `before_skill_activation` 校验「当前 LLM 提议的工具 ∈ 激活 Skill 的 `allowed_tool_groups`」，**违规记 trace 警告，不强制阻断**（v1；强制阻断延后到 F16 成熟期，见 [**F16**](F16_AGENT_POLICY_ENGINE.md) §check_points）。
- **未来收敛路径：** 若需硬收敛，应在 `build_resolved_tool_surface` 构造时按 `skill_refs` 并集组收敛冻结面（改 F08 §5.1），**非** tick 内动态收敛。此为 Open Question Q1。

---

## 8. 与 L3 思考管线的集成（实现锚点）

| 集成点 | 文件:行 | v1 改动 |
|--------|---------|---------|
| PDCA 编排 | `frameworks/llm_pdca.py` `_run_inner` (`699:940`) | 在 Plan/Do 阶段 `_phase_system` 拼接前调用 `SkillInjection.select(phase, skill_refs)` |
| System 拼接 | `llm_pdca.py` `_phase_system` / `_phase_system_core` (`91:93`, `199:203`) | 追加 Skill 文本块为 system 后缀 |
| Worker 绑定 | `worker.py` `LlmPdcaAssistantWorker.create` (`104:140`) | 从节点 attrs 读 `skill_refs`，传入 framework |
| 节点 attrs 解析 | `agent_node_phase_llm.py` / 新增 `skill_refs` 解析 | 解析 `attributes.skill_refs: List[str]` |
| 节点种子 | `db/seed_data.py` `ensure_aico_npc_agent` (`286:327`) | AICO seed 增 `skill_refs`（端到端验证） |

**不修改：** `registry.py` 核心逻辑、`resolved_tool_surface.py` 冻结面构造、`command_policies` 授权路径。

---

## 9. v1 种子 Skill 集

AICO 为只读默认助手（`tool_allowlist` = `help/look/time/version/whoami/primer/find/describe/agent`，全 `read` 组）。v1 种子 3 个通用 Skill，按 PDCA 阶段映射（满足验收「3 个 Skill 端到端通」）：

| skill_id | category | allowed_in_react_states | 映射阶段 |
|----------|----------|------------------------|---------|
| `problem_framing` | `reasoning` | `[plan]` | Plan |
| `retrieval_reasoning` | `retrieval` | `[plan, do]` | Plan/Do |
| `final_synthesis` | `finalization` | `[check, act]` | Check/Act |

3 个 Skill 均为 `prompt` 模式、`side_effect_level: none`、`allowed_tool_groups: [read]`。Skill 文本模板位于 `backend/config/skills/<skill_id>/SKILL.md`。

---

## 10. 与世界包 Skill 概念的边界

HiCampus 世界包存在 `data/concepts/skills.yaml`（schema: `id/world_id/concept_type/name/scope/definition.capability/bindings`），为 **世界语义概念**（包校验 + 快照，**不**入图节点、**不**被 agent tick 消费）。

- **L4 SkillRegistry（本 SPEC）** = 全局 agent 运行时经验 Skill，载体 `backend/config/skills/`。
- **世界包 Skill 概念** = 世界内容资产，载体 `app/games/<world>/data/concepts/skills.yaml`。
- **不同域，不合并**。为避免命名混淆，代码层 L4 类名用 `SkillDefinition` / `SkillRegistry`，文档统一称 **Agent Skill（L4）** vs **世界 Skill 概念**。

---

## 11. Acceptance Criteria

- [ ] `SkillRegistry` 启动期加载 `config/skills/*.yaml`，非法定义 fail-fast
- [ ] `SkillInjection` 按 PDCA 阶段 + `skill_refs` 选择 Skill，注入 L3 system 段
- [ ] AICO seed 节点含 `skill_refs: [problem_framing, retrieval_reasoning, final_synthesis]`，端到端 tick 注入 3 个 Skill 文本
- [ ] `allowed_tool_groups` 取值限定为 `read`/`mutate`（v1 词汇表）
- [ ] `allowed_tool_groups` 违规记 trace 警告，**不**动态收敛冻结面（冻结面不变量保持）
- [ ] `tool`/`hybrid` 模式 `raise NotImplementedError`
- [ ] `cognition_profile_ref` 保留为 inert，不被新路径读取
- [ ] 单元测试位于 `backend/tests/game_engine/`（非 `tests/test_game_engine/test_agent_runtime/`）

---

## 12. Open Questions（待确认 / 后续阶段）

- **Q1（收敛强度）：** `allowed_tool_groups` 何时从声明式升级为硬收敛？候选：构造期冻结面收敛 vs F16 强制阻断。**v1 取声明式。**
- **Q2（组词汇）：** v1 用 `interaction_profile` 二元组；是否需要更细 `tool_group` 字段（如 `world_navigation`/`admin`）？延后到有 Skill 需要更细粒度时。
- **Q3（`cognition_profile_ref` 处置）：** v1 保留 inert；是否在后续阶段从 seed + `agent` 命令输出移除？延后。
- **Q4（Skill 选择）：** v1 确定性阶段映射；LLM 自选延后到 F17 `selected_skill`。
- **Q5（fingerprint）：** v1 接受 desync；是否扩展 `compute_npc_prompt_fingerprint` 输入含 Skill 文本？需 provider 缓存精确性评估后决定。
- **Q6（i18n）：** Skill 文本模板是否走 i18n（`zh-CN`/`en-US`）？v1 单语模板；多语延后。

---

## 13. 后续

- 实现锚点更新 [**F09**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md) §6.4 / §7 L4 行（从「无单一目录；未来」更新为 `agent_runtime/skills/` + `config/skills/`）。
- `before_skill_activation` check_point 由 [**F16**](F16_AGENT_POLICY_ENGINE.md) 实现。
- `react_turn_schema.selected_skill` 由 [**F17**](F17_AGENT_STATE_MACHINE.md) 实现。
