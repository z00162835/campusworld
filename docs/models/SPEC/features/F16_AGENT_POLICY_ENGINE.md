# F16 — Agent Policy Engine（确定性策略引擎）

> **Architecture Role：** 将 Agent 运行时的 **行为安全策略** 从 system_prompt 文本指令迁移到 **确定性引擎**，实现零 Prompt 依赖、check_point 拦截、单一事实来源。收敛既有 `execution_gate` 为 `before_tool_call` 适配器（外部 API 不变）。与 `command_policies`（授权平面）**并存不合并**。

**文档状态：Draft（契约先行；实现按本 SPEC 逐阶段优化）。**

**交叉引用：** [**F08**](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md)（`execution_gate`、`CommandToolSemantics` Tool Profile、`PreauthorizedToolExecutor`）、[**F09**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)（L2/L4 边界）、[**F11**](F11_AGENT_INTENT_CLASSIFIER_RUNTIME.md)（意图分类，与 `before_tool_call` 同向）、[**F14**](F14_AGENT_TOOL_ROUTER_PREPLAN.md)（execution_gate 仍负责最终允许）、[**F15**](F15_AGENT_SKILL_REGISTRY.md)（`before_skill_activation`、`SkillActivation.allowed_tool_groups`）、[**F17**](F17_AGENT_STATE_MACHINE.md)（driver 在 stage 边界咨询 PolicyEngine）、[**F18**](F18_AGENT_QUALITY_GATES.md)（质量/停止 check_point 扩展：`after_state_execute` / `before_terminal` / `per_react_round`；`pause`/`require_approval` 停止决策、输出层脱敏/停止）。

**决策状态：** 本章基于 F15 实现完成后的架构评审，D1–D10 已决策（见 §1.5）。


---

## 1. Goal

- 把 `CAMPUSWORLD_SYSTEM_PRIMER.md` §8–§9 与 `settings.yaml` AICO `system_prompt`/`phase_prompts` 中的 **行为安全规则文本** 迁移到确定性引擎，消除「Prompt 注入依赖」；v1 保留 prompt 文本作为 fallback（`policy.enable_prompt_fallback: true`），实际移除延后到 F18 输出/流式 gate 落地。
- 提供 4 个 check_point 的统一拦截：`before_skill_activation` / `before_tool_call` / `after_tool_observation` / `before_final_answer`。
- 收敛 `execution_gate.py` 为 PolicyEngine 的 `before_tool_call` 适配器，**保持外部 API 与 `GateDecision` 结构稳定**，避免破坏 `PreauthorizedToolExecutor` 与现有测试。
- 通过 `before_tool_call` 硬收敛 F15 `SkillActivation.allowed_tool_groups`（命令所在组 ∉ 当前激活 skill 的 group 并集时拒绝）。

## 1.5 Architectural Decisions（已决策）

| 编号 | 决策 | 结论 | 对 SPEC 的影响 |
|------|------|------|----------------|
| **D1** | 检测器是否允许 LLM 调用 | **A. 纯函数，无 LLM** | v1 所有 detector 为纯函数，复杂语义评估交给 F11/F18 |
| **D2** | `before_skill_activation` 插入位置 | **在 `SkillInjection` 加 hook**；policy 拒绝的 skill 进入 **独立 `Blocked by policy` 段**（v1），明确表达 policy-denied 语义，不混入 F15 `inactive` 段 | 需同步 F15 manifest 模板 + 验收；拒绝信息通过 `policy_decision` trace 保留 |
| **D3** | `allowed_tool_groups` 硬收敛 | **B. 在 `before_tool_call` 硬过滤**，但 **P3 启用** | 命令 tool_group 必须能被当前激活 skill 的 group 并集覆盖；`read` 为父组（含 `observe`/`agent_meta`/`identity`/`communicate`）；数据流见 §4.3 |
| **D4** | `execution_gate` 收敛 | **A. 适配器模式** | `evaluate_execution_gate` 内部委托 `PolicyEngine.evaluate`，对外签名不变 |
| **D5** | `after_tool_observation` 脱敏 | **C. 延迟到 F18 输出层** | v1 `after_tool_observation` 不实现 transform，F18 `before_final_answer` 统一脱敏 |
| **D6** | streaming `before_final_answer` | **在 F18 中考虑** | v1 仅在非流式 Act 路径检查；流式路径已知限制 |
| **D7** | 规则定义语言 | **B. Python dataclass + 代码注册** | v1 平台默认与实例规则均为代码；YAML 节点覆盖延后 |
| **D8** | `require_approval` 语义 | **A. v1 同步降级为 deny** | 保留枚举值，但 `runtime_action='block'`，trace 记录原始 decision |
| **D9** | `policy_decision` trace schema | **兼容现有 schema** | 新增字段可扩展，eval adapter 显式映射 `policy_decision` |
| **D10** | Skill `side_effect_level` 是否约束命令 | **不约束** | Skill 的 `side_effect_level` 仅描述 Skill 自身；命令副作用来自 F08 `CommandToolSemantics` |

## 2. Scope / Non-Goals

- **Scope：** `npc_agent`（含 AICO）agent tick 内的行为策略；`before_skill_activation` / `before_tool_call` 今日落地；`after_tool_observation` 只记录审计、不 transform（D5）；`before_final_answer` 非流式路径拦截（D6）。
- **Non-Goals：**
  - **不**替代 `command_policies`（权限/角色授权平面，`policy.py` / `command_policies` 表）。PolicyEngine 是 **行为平面**（意图/确认/副作用/数据分级），两平面并存（见 §6）。
  - **不**替代 F11 意图分类器；F11 产出 `intent_hint` 软提示，PolicyEngine 在 check_point 做最终拦截。
  - v1 **不**实现跨 tick 异步 `pause`/`resume` 审批工作流（tick 同步不变量，见 §8 / Open Question Q2）。
  - **不**改变 `ResolvedToolSurface` 冻结面构造（F08 §5.1）。
  - v1 **不**实现 LLM-based detector（D1）；所有 detector 为纯函数。
  - v1 **不**实现 `after_tool_observation` 数据脱敏 transform（D5）；脱敏延后到 F18 `before_final_answer`。
  - v1 **不**支持 YAML 节点规则覆盖（D7）；规则通过 Python dataclass + 代码注册。

---

## 3. 核心定义

### 3.0 规则分域（Domain Segmentation）

PolicyEngine 是统一执行器，但其规则注册按 **域（domain）** 划分，不同域关注正交的决策面，各自拥有独立的规则定义、配置命名空间与 check_point 子集。参考 OPA/Rego 的 package 分域、Kubernetes admission webhook 的 by-domain 拆分实践。

**v1 三个域：**

| Domain | 关注面 | CheckPoints | 规则载体 | 配置命名空间 |
|--------|--------|-------------|----------|--------------|
| `skill` | F15 skill 激活合规（phase 映射、group 约束、react state 允许） | `before_skill_activation` | Python dataclass | `policy.skill.*` |
| `gate` | F16 工具执行安全（副作用、数据分级、注入模式、PII） | `before_tool_call`、`after_tool_observation`、`before_final_answer` | Python dataclass | `policy.gate.*` |
| `quality` | F18 质量/停止决策（budget、max_iterations、stagnation、grounding、criteria_coverage、quality_score） | `after_state_execute`、`before_terminal`、`per_react_round` | Python dataclass + YAML DSL（节点覆盖） | `policy.quality.*` / `attributes.success_checks` / `attributes.stop_policy` |

**域边界不变量：**

- 一个 check_point 只属于一个域；不允许跨域注册同一 check_point。
- 域间无共享 detector/evaluator；detector 只读所属域语义的 `PolicyContext` 字段。
- `PolicyEngine.evaluate(check_point, ctx)` 按 check_point → domain 派发，仅运行该域已注册的 detector/evaluator 链；首个非 `allow` 决策短路该域。
- 域间无隐式优先级；同一 tick 内不同 check_point 串行触发，各自独立决策。**跨域仲裁由 driver 层显式组合多 `PolicyDecision`（D1 决策：v1 契约，engine 内部不隐式合并）**——engine 只对单 check_point 单域求值，多 check_point 决策的组合（如 gate 域 `deny` 与 quality 域 `fail` 同 tick 命中时的终态选择）由 driver 按 F17 transition 表显式裁决。

**文件布局（v1）：**

```
backend/app/game_engine/agent_runtime/policy/
├── engine.py              # PolicyEngine: 按 check_point → domain 派发
├── domain.py              # Domain 基类 / DomainRegistry
├── config.py              # PolicyConfig: 加载 backend/config/policy.yaml → 注入 Domain
├── check_points.py        # CheckPoint 常量 + 域归属映射
├── decisions.py           # PolicyDecision
├── context.py             # PolicyContext（统一载体，字段按域分组注释）
└── domains/
    ├── __init__.py
    ├── skill_domain.py    # skill 域: detectors + 平台默认规则
    ├── gate_domain.py     # gate 域: detectors + 平台默认规则
    └── quality_domain.py  # quality 域: evaluators + 平台默认规则（F18 落地）
```

**既有 `detectors.py` 迁移（D3 决策）：** 既有扁平 `detectors.py` 随 quality 域落地一并迁入 `domains/skill_domain.py` / `domains/gate_domain.py`，避免双轨期语义漂移。迁移为纯文件移动 + import 路径更新，**不改 detector 逻辑**；`detectors.py` 在迁移后删除，不留 re-export shim。

**N2 域内 detector 顺序：** 域内 detector 执行顺序由 `Domain.detectors()` 返回顺序决定，迁移时保留既有 `_detectors_from_config` 顺序，确保 reason_code 命中分布 byte-equiv：
- gate 域：`[side_effect_level, data_classification, skill_tool_group]`（`pattern_match`/`pii_scanner` 为 SPEC placeholder，未实现）
- skill 域：`[skill_activation_mode]`

**Domain 接口（`domain.py`）：**

```python
class Domain:
    domain_id: str
    check_points: tuple[str, ...]
    def detectors(self) -> list[Detector]: ...      # skill/gate
    def evaluators(self) -> list[Evaluator]: ...    # quality
    def build_context(self, base: PolicyContext) -> PolicyContext: ...  # 域字段填充
```

`DomainRegistry` 在启动期注册三个域单例；`PolicyEngine` 持有 registry，`evaluate` 按 `check_point → domain` 派发。v1 域实例与 detector 均为代码注册（D7），YAML 节点覆盖延后。

**`build_context` 落地（D2 决策）：** v1 实现 `build_context`——driver 构造域无关的 `base: PolicyContext`（仅含 `check_point` + 跨域公共字段），各域 `build_context` 负责填充本域语义字段（skill 域填 `skill_*`、gate 域填 `command_*`/`side_effect_level`、quality 域填 `draft_text`/`tool_results`/`turn_count` 等）。engine 在派发前依次调用目标域 `build_context`，确保 detector/evaluator 读到的 context 字段已就绪；driver 不再手工拼装全字段 context。

### 3.1 CheckPoint（`check_points.py`）

| CheckPoint | Domain | 触发时机 | 今日可落地 | 依赖 |
|------------|--------|---------|-----------|------|
| `before_skill_activation` | `skill` | Skill body 激活前（F15 `SkillInjection` 内部 hook） | ✅ 是 | [F15](F15_AGENT_SKILL_REGISTRY.md) |
| `before_tool_call` | `gate` | 单次工具执行前 | ✅ 是 | — |
| `after_tool_observation` | `gate` | ToolObservation 生成后 | ⚠️ 仅审计 | v1 不 transform；脱敏由 F18 输出层处理（D5） |
| `before_final_answer` | `gate` | 最终答复发出前（非流式） | ❌ 未落地（P4 pending） | streaming / 非流式完整拦截延后到 [F18](F18_AGENT_QUALITY_GATES.md)（D6） |
| `after_state_execute` | `quality` | `_execute_state` 后、`sm.next` 前 | ✅ P5-A | [F18](F18_AGENT_QUALITY_GATES.md) `stop_evaluator`；决策映射为 `runtime.stop_fail` / `event=stagnation` 供 F17 消费（`enable_stop_dimensions` 门控） |
| `before_terminal` | `quality` | act 锚点 `_detect_tick_emit_deferral` 后、终态前 | ✅ P5-A | [F18](F18_AGENT_QUALITY_GATES.md) `final_success_evaluator`（audit/trace-only，`enable_final_success_gate` 门控） |
| `per_react_round` | `quality` | 内层 ReAct 结构化 turn 校验后 | ✅ P5-A opt-in | [F18](F18_AGENT_QUALITY_GATES.md) `react_turn_success_evaluator`；随 `require_structured_turn`，写 `react_round_decision` payload |

### 3.2 PolicyDecision（`decisions.py`）

```python
@dataclass(frozen=True)
class PolicyDecision:
    decision: Literal[
        'deny', 'allow', 'require_approval', 'allow_with_transform',
        # F18 quality/stop 扩展（见 [F18] §3.4）
        'fail', 'pause', 'final_success', 'replan', 'continue',
    ]
    reason_code: str
    check_point: str
    runtime_action: Literal['block', 'pause', 'transform', 'block_and_rewrite', 'pass']
    transform_applied: Optional[Dict[str, Any]] = None
    evidence: Optional[Dict[str, Any]] = None  # 命中的 detector / 规则 id
    # F18 扩展（可选，向后兼容；见 [F18] §3.4）
    quality_score: Optional[Dict[str, float]] = None   # 分层子分 {surface, process, semantic}
    degraded_action: Optional[str] = None              # pause→block/clarify 记降级动作
```

> **F18 扩展字段说明：** `decision` Literal 后 5 值（`fail`/`pause`/`final_success`/`replan`/`continue`）与 `quality_score` / `degraded_action` 两字段由 [F18](F18_AGENT_QUALITY_GATES.md) §3.4 定义，v1 在 F16 基类一并承载（向后兼容，缺省 `None`）。F16 既有 factory（`allow`/`deny`/`require_approval`）不变；F18 决策 factory（`fail`/`pause`/`final_success`/`replan`/`continue_`）内聚 B5 映射。

**B5 `decision → runtime_action` 派生映射（v1 契约）：** 保留双字段（不合并）——`decision`=语义/审计结果，`runtime_action`=当期命令式行为。F16 既有 factory 与 F18 evaluator 产出 `decision` 时按下表派生 `runtime_action`：

| `decision` | `runtime_action` | 说明 |
|-----------|------------------|------|
| `allow` | `pass` | 正常通过 |
| `deny` | `block` | 阻断 |
| `require_approval` | `block` | D8：v1 同步降级 block，`decision` 保留 `require_approval` 供审计；post-v1 升级 `pause` |
| `allow_with_transform` | `transform` | v2 |
| F18 扩展 `fail` | `block` | 不可恢复终止 |
| F18 扩展 `pause` | `pause` | v1 降级由 `degraded_action` 覆盖 |
| F18 扩展 `final_success`/`continue` | `pass` | 正常通过 |
| F18 扩展 `replan` | `pass` | 由 event 驱动 transition，不阻断 |

运行时消费者统一走 `is_block`/`is_allow`，不直接读 `decision`/`runtime_action` 做控制流（见 §7）。`is_allow` 覆盖 `runtime_action ∈ {pass, transform}`——`allow_with_transform` 仍是「允许」决策（仅附加变形，不阻断）；`is_block` 覆盖 `runtime_action ∈ {block, block_and_rewrite}`。

### 3.3 Detectors / Evaluators（按域注册）

纯函数检测器/评估器，按域注册到 `DomainRegistry`，仅读所属域语义的 `PolicyContext` 字段。**不**读第二个元数据源。

**`skill` 域**（`domains/skill_domain.py`，check_point `before_skill_activation`）：

| Detector | 输入 | 用途 |
|----------|------|------|
| `skill_activation_mode` | `skill_activation_mode` / `current_react_state` | 校验激活模式与 react state 兼容（F15 `allowed_in_react_states`） |

> **注：** `skill_tool_group` detector 运行于 `before_tool_call`（gate 域 check_point），虽读取 skill 元数据，但按「一个 check_point 只属于一个域」不变量归属 **gate 域**（见下表）。其开关 `enable_skill_tool_group_detector` 亦在 gate 域配置下。

**`gate` 域**（`domains/gate_domain.py`，check_points `before_tool_call` / `after_tool_observation` / `before_final_answer`）：

| Detector | 输入 | 用途 |
|----------|------|------|
| `action_type_match` | `interaction_profile` / `side_effect_level` | 校验提议动作类型与 caller ceiling |
| `side_effect_level` | `side_effect_level` | `write_high` → `require_approval`（v1 降级 block） |
| `data_classification` | `data_classification` | `confidential`/`restricted` → `require_approval`（v1 降级 block）；`allow_with_transform` 延后到 F18 输出层落地（D5） |
| `skill_tool_group` | `SkillActivation.allowed_tool_groups` + 命令的 tool group | 命令 tool group ∉ 激活 skill 的 group 并集 → `deny`（D3，默认 off）；运行于 `before_tool_call`，归属 gate 域 |
| `pattern_match` | `user_message` / `args` | Prompt 注入模式 / 越权短语 |
| `pii_scanner` | `ToolObservation` / `final_answer` | v1 规则模式；PII 模式扫描 |

**`quality` 域**（`domains/quality_domain.py`，check_points `after_state_execute` / `before_terminal` / `per_react_round`）：

| Evaluator | 输入 | 用途 |
|-----------|------|------|
| `stop_evaluator` | `runtime.*` / `snapshot.turn_count` / `tool_failure_count` | `budget_exhausted` / `max_iterations_exceeded` / `max_consecutive_tool_failures_exceeded` → `fail` |
| `final_success_evaluator` | act draft / `success_criteria` / grounding | hard gates 通过 → `allow`，否则 `degraded_action` |
| `react_turn_success_evaluator` | structured turn | 结构化 turn 合规校验（随 `require_structured_turn`） |
| `quality_score_evaluator` | draft / obs / criteria | 多维 `QualityScore`（surface/process/semantic/judge），offline-only |

quality 域 evaluator 契约详见 [F18](F18_AGENT_QUALITY_GATES.md) §3。

---

## 4. 与 `execution_gate` 的收敛（适配器契约）

### 4.1 既有 `execution_gate` 现状（`execution_gate.py`）

- `evaluate_execution_gate(*, db_session, command_name, args, context_metadata) -> GateDecision`（`92:112`）。
- 返回 `GateDecision{allow, reason_code, intent, effective_profile, effective_guard, caller_profile, callee_profile}`（`12:20`）。
- `reason_code`：`guard_pass` / `guard_blocked_profile_ceiling` / `guard_blocked_intent` / `guard_blocked_scope` / `guard_blocked_confirmation`。
- 读 `CommandToolSemantics` 的 `interaction_profile` + `invocation_guard`（`69:75`），**未读** `side_effect_level` / `data_classification`。
- 调用方：`PreauthorizedToolExecutor.execute_command`（`resolved_tool_surface.py:84`）；trace 在 `tool_gather.py:226-233`。

### 4.2 收敛契约

- `evaluate_execution_gate` 外部签名 + `GateDecision` 字段 **保持稳定**（适配器，非重写）。既有 `reason_code` 集（`guard_pass` / `guard_blocked_profile_ceiling` / `guard_blocked_intent` / `guard_blocked_scope` / `guard_blocked_confirmation`）**行为不变**；PolicyEngine 否决新增 `guard_blocked_policy`（遵循 `guard_blocked_` 前缀，下游 `tool_gather.py` `startswith('guard_blocked_')` 兼容），详细决策写入 `effective_guard['policy_decision']` + `policy_decision` trace 行。
- 内部委托 `PolicyEngine.evaluate(check_point='before_tool_call', ...)`，映射结果到 `GateDecision`。
- 新增读 `side_effect_level` / `data_classification`（经 `resolve_command_tool_semantics`），用于 `side_effect_level` / `data_classification` detector。
- **保持** `PreauthorizedToolExecutor` 在 `before_tool_call` 内调用（F08 R2：构造面时鉴权等价、tick 内不重复 `authorize_command`）。
- trace：`guard_pass` / `guard_block`（`reason_code` 前缀 `guard_blocked_`）保持；新增 `policy_decision` trace 行（见 §9）。

### 4.3 激活 skill 的 group 数据流（D3 实现协议）

`SkillInjection` 产生 `SkillActivation` 列表后，F16 需要把 **当前 phase 实际激活 skill 的 group 并集** 传入 `before_tool_call`。由于 `evaluate_execution_gate` 外部签名保持不变（`context_metadata`），数据流通过 `CommandContext.metadata` 传递，但 **只传递最小可序列化 DTO，不传递 `SkillActivation` 运行时对象**。

**DTO 结构：**

```python
{
    "active_skill_ids": ["problem_framing", "retrieval_reasoning"],          # 当前 phase 被激活的 skill id 列表
    "active_skill_allowed_tool_groups": ["read", "observe"],                 # 激活 skill 的 allowed_tool_groups 并集
}
```

**数据流步骤：**

1. **`llm_pdca._prepare_skill_context`** 从 `SkillInjectionResult` 构造上述 DTO，写入 `ctx.payload['active_skill_context']`。
2. **`_phase_react_loop`** 构建 `runtime_tool_ctx` 时，把 `ctx.payload['active_skill_context']` 复制到 `runtime_tool_ctx.metadata['active_skill_context']`。
3. **`PreauthorizedToolExecutor.execute_command`** 调用 `evaluate_execution_gate` 时传入该 `metadata`。
4. **`evaluate_execution_gate` 适配器** 从 `context_metadata['active_skill_context']` 读取 `active_skill_allowed_tool_groups`，作为 `PolicyContext` 的一部分委托 `PolicyEngine.evaluate(check_point='before_tool_call', ...)`。

**命令 tool_group 派生：** 从 `resolve_command_tool_semantics(command_name, args=args).tool_groups` 读取（F08 新增字段）。`tool_groups` 为空时，回退到 `interaction_profile` 的 `read`/`mutate` 二元组。

**无激活 skill 时的默认行为：** 若 `active_skill_context` 缺失或 `active_skill_ids` 为空（agent 未配置 `skill_refs` 或当前 phase 无激活 skill），`skill_tool_group` detector 不触发 deny（即不因为 skill group 缺失而阻断），保持与 F15 前向兼容。该默认行为 v1 以代码常量体现，可通过平台默认规则覆盖。

### 4.4 `tool_group` 词汇（v1 细化）

参考 OpenAI function categories、Claude tool policy 与 Palantir ontology 做法，v1 从 F08 的 `read`/`mutate` 二元组扩展到更细的行为分组，但 **保持与 `interaction_profile` 正交**（`tool_group` 是行为分类，`interaction_profile` 保留用于执行 gate 的 ceiling/confirm 语义）。

| `tool_group` | 语义 | 典型命令 / 子命令 |
|--------------|------|-------------------|
| `read` | **父组**：覆盖所有只读信息检索（含 `observe`/`agent_meta`/`identity`/`communicate`）。声明 `allowed_tool_groups: [read]` 的 Skill 默认可引导所有只读命令。 | `help`, `look`, `find`, `describe`, `space`, `time`, `version`, `primer`, `whoami`, `agent list`, `task list`, `notice list` |
| `observe` | 读取动态世界/任务/会话状态 | `task list`, `task show`, `world status`, `agent status` |
| `agent_meta` | Agent 自身元数据与能力查询 | `agent list`, `agent show`, `agent capabilities` |
| `identity` | 用户/账户身份与权限查询 | `whoami` |
| `communicate` | 低副作用的通信/通知读取 | `notice list`, `notice view` |
| `mutate` | 改变世界/图/任务状态 | `go`, `enter`, `leave`, `create`, `task <create/…>`, `agent tool add/del` |
| `admin` | 权限、角色、账户管理（reserved） | （未来） |

**Group 层级与匹配规则：**

- `read` 是 **父组**，包含 `observe`、`agent_meta`、`identity`、`communicate`。
- `mutate` 当前无子组（v1）。
- 命令 group 与 skill `allowed_tool_groups` 匹配时，满足以下任一条件即允许：
  1. 命令的任一 group 精确存在于 skill 的 `allowed_tool_groups` 中；
  2. 命令的任一 group 的父组存在于 skill 的 `allowed_tool_groups` 中。
- 因此 `allowed_tool_groups: [read]` 的 Skill 允许所有 `read`/`observe`/`agent_meta`/`identity`/`communicate` 命令；`allowed_tool_groups: [observe]` 的 Skill 仅允许 `observe` 命令，不允许 `agent_meta` 或 `identity`。

**命令 → group 的解析规则：**

1. 命令/子命令可通过 `CommandToolSemantics.tool_groups` 显式声明一个或多个 group；若声明为空，回退到 `interaction_profile`（`read` → `['read']`，`mutate` → `['mutate']`）。
2. `SubcommandProfileRule` 可覆盖子命令的 `tool_groups`，与 `interaction_profile` 覆盖类似（例如 `task list` 为 `['observe']`，`task create` 为 `['mutate']`）。
3. 未注册命令回退到 `['read']`。

> **v1 实现顺序：** 由于当前 F15 seed skills 仅声明 `allowed_tool_groups: [read]`，group 层级匹配必须在 `tool_group` 硬过滤落地前实现，否则 AICO 的只读能力会误拒绝。因此 `skill_tool_group` detector 的硬过滤为 **P1**（见 §13），在 `read` 父组语义与层级匹配就绪后启用。

---

## 5. 规则来源与加载（按域）

### 5.1 平台默认（按域，独立配置文件 `backend/config/policy.yaml`）

平台默认规则按域以 Python dataclass 形式注册在 `domains/{skill,gate,quality}_domain.py`，配置仅开关/参数化。policy 配置 **独立于** `settings.yaml`，由专用配置文件 `backend/config/policy.yaml` 承载（当前 **不存在**，需新增），由 `PolicyConfig` 加载器（`backend/app/game_engine/agent_runtime/policy/config.py`）在启动期解析并注入 `DomainRegistry`。

**设计理由：** policy 规则（skill/gate/quality 三域开关与阈值）是与应用基础设施配置（DB、auth、logging）正交的关注点，独立文件便于 ops 单独管理、审计 diff、灰度切换，避免与 `settings.yaml` 混杂。

**`backend/config/policy.yaml` 结构（三域顶层键）：**

```yaml
# PolicyEngine 平台默认配置（按域）
skill:
  # skill 域（before_skill_activation check_point）；无开关键（仅 skill_activation_mode detector，常开）

gate:
  enable_side_effect_detector: true
  enable_data_classification_detector: true
  enable_prompt_fallback: true              # pattern_match 命中后降级 rewrite
  enable_skill_tool_group_detector: false   # D3 group 约束 detector（默认 off，前向兼容；运行于 before_tool_call，归属 gate 域）
  # side_effect_level → 默认 decision（由 F08 §1.3 自动推导）
  side_effect_defaults:
    none: allow
    read: allow
    write_low: allow                        # caller require_confirmation_for_mutate 仍生效
    write_high: require_approval             # v1 降级 block

quality:
  enable_quality_score: false               # 多维 QualityScore（offline-only）
  enable_stop_dimensions: false             # stop_evaluator 新维度（stagnation/max_iterations/max_consecutive），P5-A 门控
  enable_final_success_gate: false          # final_success_evaluator 驱动门控（否则 audit/trace-only），P5-A 门控
  max_iterations: 12                        # 总 state transition per tick 上限
  max_consecutive_tool_failures: 3          # 连续工具失败停止阈值
  stagnation_window: 3                      # stagnation 滑动窗口（连续 K round）
```

**`skill` 域：**

无配置开关键（仅 `skill_activation_mode` detector，常开；`_BLOCKED_SKILL_ACTIVATION_MODES` 为空集，前向兼容）。

**`gate` 域：**

| 配置键 | 默认 | 用途 |
|--------|------|------|
| `enable_side_effect_detector` | `true` | 副作用 detector |
| `enable_data_classification_detector` | `true` | 数据分级 detector |
| `enable_prompt_fallback` | `true` | pattern_match 命中后降级 rewrite |
| `enable_skill_tool_group_detector` | `false` | D3 group 约束 detector（默认 off，前向兼容；运行于 `before_tool_call`，归属 gate 域） |

`side_effect_defaults` 由 [F08](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) §1.3 `side_effect_level` 自动推导 gate 默认 decision（`none`/`read`→`allow`、`write_low`→`allow`、`write_high`→`require_approval`，v1 降级 block）。

**`quality` 域（F18 落地）：**

| 配置键 | 默认 | 用途 |
|--------|------|------|
| `enable_quality_score` | `false` | 多维 QualityScore（offline-only） |
| `enable_stop_dimensions` | `false` | stop_evaluator 新维度门控（stagnation / max_iterations / max_consecutive_tool_failures）；off 时 evaluator 返回 `None`，byte-equivalent |
| `enable_final_success_gate` | `false` | final_success_evaluator 驱动门控；off 时 audit/trace-only（`_detect_tick_emit_deferral` 仍为 draft 权威），byte-equivalent |
| `max_iterations` | `12` | 总 state transition per tick 上限 |
| `max_consecutive_tool_failures` | `3` | 连续工具失败停止阈值 |
| `stagnation_window` | `3` | stagnation 滑动窗口（连续 K round） |

quality 域的 `success_checks` / `stop_policy` 节点级覆盖优先级详见 [F18](F18_AGENT_QUALITY_GATES.md) §7。

**加载机制：** `PolicyConfig`（`policy/config.py`）启动期读取 `backend/config/policy.yaml`，按域解析为 dataclass，注入对应 `Domain` 实例；文件缺失或键缺失时回退代码内默认值（保单测无文件可跑）。`config_manager.py` 不再承载 policy 键。

### 5.2 实例规则（v1 代码注册，延后 YAML）

v1 各域实例规则通过 Python dataclass + 代码注册（D7），与平台默认规则共享同一类型系统，启动期加载到 `DomainRegistry`。check_point 按域插入（性能：纯函数，无 DB / 无 LLM）。既有扁平 `detectors.py` 随 quality 域落地迁入 `domains/{skill,gate}_domain.py`（D3，见 §3.0），迁移后 `detectors.py` 删除。

节点级 YAML 规则覆盖按域命名空间组织（`attributes.policy.skill.*` / `attributes.policy.gate.*` / `attributes.policy.quality.*`），延后到有 UI/ops 配置需求时再引入；v1 不实现 `rules_loader` YAML 解析路径。

---

## 6. 两平面边界（不变量）

| 平面 | 职责 | 载体 | 时机 |
|------|------|------|------|
| **授权平面** `command_policies` | 权限/角色能否调用该命令 | `command_policies` 表 + `policy.py` | `authorize_command`（构造冻结面时等价） |
| **行为平面** PolicyEngine | 意图/确认/副作用/数据分级/PII | `policy/` + `safety.rules` + 平台默认 | check_point（tick 内） |

**不合并**：授权是「**能否调**」，行为是「**这次该不该放行/变形**」。PolicyEngine **不**写 `command_policies`，`command_policies` **不**做行为判定。

---

## 7. check_point 在 `llm_pdca.py` 的插入点

> **锚点约定：** 下表以 **函数名** 为锚（不再写死行号），避免 F17 状态机 driver 重构后行号漂移。函数定位以当前 `frameworks/llm_pdca.py` 为准。

| CheckPoint | 插入位置（`llm_pdca.py` 函数） | 今日可落地 | 备注 |
|------------|-------------------------|-----------|------|
| `before_tool_call` | `_phase_react_loop` 工具 gather 前（经 `PreauthorizedToolExecutor` → `execution_gate` 适配器，非直接 `PolicyEngine` 调用） | ✅ 是 | 适配器收敛（D4）；`active_skill_context` 经 `runtime_tool_ctx.metadata` 传入 |
| `after_tool_observation` | `_phase_react_loop` 工具结果组装后 | ⚠️ 仅审计 | v1 不 transform；脱敏由 F18 输出层处理（D5） |
| `before_final_answer` | `_execute_act_state` 最终草稿赋值后 | ❌ 未落地（P4 pending） | v1 代码未插入 `PolicyEngine.evaluate(BEFORE_FINAL_ANSWER)`；`pattern_match` 拦截与 streaming 路径均延后（D6 / P4） |
| `before_skill_activation` | `_prepare_skill_context` 内 `SkillInjection.inject(before_activate=...)` hook | ✅ 是 | policy 拒绝 skill 进 `Blocked by policy` 段（D2），不混入 F15 `inactive` 段 |

`_phase_react_loop` 被 Plan / Do / Check-retry Plan 调用，`before_tool_call` / `after_tool_observation` 在所有 react 入口生效。`_execute_act_state` 为 Act 阶段执行体（F17 driver loop 的 act state handler）。

**B5 trace 序列化修复：** `llm_pdca._prepare_skill_context` 当前硬编码 trace 字段 `'decision':'deny'`/`'runtime_action':'block'`，未序列化真实 `PolicyDecision`（今日无害因 skill detector 只发 deny，但若发 `require_approval` 会误审计）。修复：复用 `execution_gate._policy_decision_to_trace` helper 序列化真实 `PolicyDecision`（含 `decision`/`runtime_action`/`reason_code`/`evidence`）。运行时消费者统一走 `is_block`/`is_allow`，不直接读 `decision`/`runtime_action` 做控制流。

---

## 8. `require_approval` 与 `pause` 语义（v1 同步）

- **今日 tick 同步端到端**（`npc_agent_nlp.py:54-173` blocking）；无 `pause`/`resume`/`pending_approval` 机制。
- v1 `require_approval` decision → **同步降级为 block**：execution_gate 适配器返回 `GateDecision(allow=False, reason_code='guard_blocked_policy')`（与 §4.2 收敛契约一致），详细 `policy_decision` 写入 `effective_guard['policy_decision']`（`resolved_tool_surface.py` / `tool_gather.py:210-233`）；trace 行中 `decision` 字段保留原始 `require_approval` 语义。
- **跨 tick 异步 pause/resume 审批工作流延后**（需 WS `awaiting_approval` 事件 + 持久化 hook，今日不存在）。`StopPolicy.pause`（[F18](F18_AGENT_QUALITY_GATES.md)）在 v1 同样降级为同步 fail/notice。
- **确认信号**：今日 `_is_confirmed` 读 `user_message` 子串 + `confirmed_execute` metadata（`execution_gate.py:60-67`）；生产无 `confirmed_execute` producer。v1 保持子串确认；结构化确认令牌延后（Open Question Q3）。

---

## 9. 可观测性

- 新增 trace 行 `policy_decision`（写入 `command_trace`，F10 审计）：`{step: 'policy_decision', check_point, decision, reason_code, detector, evidence}`。
- 既有 `guard_pass` / `guard_block`（`tool_gather.py:230-233`）保持兼容；eval adapter（`eval/adapters/aico.py`）映射不变。
- 标准化 `TraceEvent.POLICY_DECISION` 由 [F10/F05 可观测性] 标准化阶段统一（本 SPEC 仅定义 trace 行 schema）。

---

## 10. system_prompt 安全文本迁移

迁移目标（**待 F18 输出/流式 gate 落地后从 prompt 移除**，由确定性引擎承接）：

| 来源 | 内容 | 承接 detector |
|------|------|--------------|
| `CAMPUSWORLD_SYSTEM_PRIMER.md` §8 Invariants | 角色不变量、世界状态必须基于工具观测 | `pattern_match`（越权短语）+ `after_tool_observation`（grounding 校验交 F18） |
| `CAMPUSWORLD_SYSTEM_PRIMER.md` §9 Commands | 意图路由（informational → `help`；execute 需显式意图） | `action_type_match` + `pattern_match` |
| `settings.yaml` AICO `system_prompt` (`255:259`) | informational / 确认规则 | 同上 |
| `settings.yaml` AICO `phase_prompts.plan` (`263:271`) | intent 分类 / 确认信号 | 同上 |
| `settings.yaml` AICO `phase_prompts.check` (`302:308`) | informational→execution 升级 fail | `before_final_answer` |

**保留**：`CAMPUSWORLD_SYSTEM_PRIMER.md` 中 **不变量陈述**（角色边界、不泄漏 phase tag）作为 LLM 行为指引；**具体规则条文（§8–§9）的移除为后置验收条件**，需在以下任一条件满足后执行：

1. **非流式模式**：禁用 Do 阶段 prose 流式输出（或所有最终输出都经 Act 阶段 `before_final_answer` gate 后发出）。
2. **F18 落地**：F18 的 pre-flush / `before_final_answer` / `after_tool_observation` 输出层 gate 已覆盖 prompt 规则所防御的缺口。

**v1 策略**：F16 v1 先实现确定性引擎，但 **保留 prompt 安全规则文本作为 fallback**（配置项 `policy.enable_prompt_fallback: true`，默认 `true`）。待 F18 输出/流式 gate 落地后，通过 golden trace 对比验证 AICO 工具选择行为等价，再关闭 fallback 并移除规则条文。

⚠️ **迁移风险：** 今日存在三处意图执行（prompt §9、F11 classifier `llm_pdca.py:712-718`、execution_gate regex `44:58`）。若提前移除 prompt 规则，流式 prose 会绕过 v1 `before_final_answer` gate，造成安全覆盖缺口。

---

## 11. Acceptance Criteria

- [x] `PolicyEngine.evaluate(check_point, context) -> PolicyDecision` 纯函数，无 LLM 调用（D1）
- [x] `evaluate_execution_gate` 外部 API + `GateDecision` 字段稳定，既有 `reason_code` 集行为不变；PolicyEngine 否决新增 `guard_blocked_policy`（`guard_blocked_` 前缀，下游兼容），详细决策写入 `effective_guard['policy_decision']`（D4）
- [x] `before_skill_activation` 在 `SkillInjection` 内 hook，policy 拒绝 skill 进入独立 `Blocked by policy` 段（v1），不混入 F15 `inactive` 段（D2）；需同步 F15 manifest 模板
- [x] `before_tool_call` 读 `side_effect_level`：`write_high` → `require_approval`（v1 同步降级 block）（D8）
- [x] `before_tool_call` 读 `active_skill_context.allowed_tool_groups`，命令 tool group 不在并集时 deny（D3）；数据流协议见 §4.3；层级匹配（`read` 父组）已实现，config toggle `enable_skill_tool_group_detector` 默认 `false`（opt-in）
- [x] `data_classification` `confidential`/`restricted` → `require_approval`（v1 同步降级 block）；`allow_with_transform` 延后到 F18 输出层（D5）
- [ ] Prompt 注入模式被 `before_tool_call` / `before_final_answer` `pattern_match` 拦截
- [x] 策略配置独立于 `settings.yaml`，由专用文件 `backend/config/policy.yaml`（三域顶层键 `skill`/`gate`/`quality`）承载，`policy/config.py` 的 `PolicyConfig` 加载器解析并注入 `DomainRegistry`；`policy.enable_prompt_fallback`（默认 `true`）位于 `gate` 域配置；实例规则用 Python 代码注册（D7）
- [x] `policy_decision` trace 行写入 `command_trace`，兼容现有 schema（D9）
- [ ] `system_prompt` 安全规则文本段 **fallback 可开关**，移除为后置验收条件（需 F18 输出/流式 gate 落地）
- [x] `command_policies` 授权平面不被 PolicyEngine 写入/替代
- [x] Skill `side_effect_level` 不用于约束命令副作用（D10）
- [x] 单元测试位于 `backend/tests/game_engine/`

---

## 12. Open Questions

- **Q1（streaming `before_final_answer`）：** 已决策：延后到 F18（D6）。流式路径引入 pre-flush policy gate 时，需评估首字延迟。
- **Q2（异步审批）：** 已决策：v1 同步降级为 block（D8）；跨 tick pause/resume 何时引入（需 WS 事件 + 持久化）仍待产品排期。
- **Q3（确认令牌）：** 已决策：v1 保留子串确认；结构化 `confirmed_execute` 令牌何时由 UI/会话层产出仍待 UX 设计。
- **Q4（迁移等价性）：** 移除 prompt 安全文本后，如何 golden trace 验证 AICO 工具选择不退化？需回归测试集。待 F16 v1 实现后补充 golden cases。
- **Q5（PII detector 强度）：** 已决策：v1 规则模式（D1）；是否引入扫描库（如 regex PII / 第三方）延后评估。
- **Q6（`before_skill_activation`）：** 已决策：F15 已落地，`before_skill_activation` 在 v1 实现；`SkillActivation.allowed_tool_groups` 在 `before_tool_call` 硬过滤（D3），不再只是警告。

---

## 13. Implementation Phases（v1 窄版实现顺序）

为避免一次性落地过多行为变更，F16 v1 按以下顺序分阶段实现：

| 阶段 | 内容 | 风险/依赖 |
|------|------|-----------|
| **P0** | `PolicyEngine` 纯函数骨架 + `PolicyDecision` / `PolicyContext` / detector 接口；`evaluate_execution_gate` 适配器委托 `PolicyEngine.evaluate(check_point='before_tool_call')` | 保持 `GateDecision` 外部 API 不变；风险低 |
| **P1** | `before_tool_call` 实现 `side_effect_level`（`write_high` → block）和 `data_classification`（`confidential`/`restricted` → block）路径；`policy_decision` trace 写入 | 无需依赖 F15 skill group；与现有 `execution_gate` 行为等价升级 |
| **P2** | `before_skill_activation` hook 接入 `SkillInjection`；policy 拒绝 skill 进入 `Blocked by policy` 段；`policy_decision` trace 记录 | 依赖 F15 manifest 模板已支持 blocked 段（已完成） |
| **P3** | `tool_group` 层级匹配（`read` 父组包含 `observe`/`agent_meta`/`identity`/`communicate`）落地；`skill_tool_group` detector 在 `before_tool_call` 硬过滤 | **必须在 P1 之后**，否则当前 `allowed_tool_groups: [read]` 的 seed skills 会误拒绝 `whoami`/`agent list`/`task list` 等只读命令 |
| **P4** | `pattern_match` detector（Prompt 注入 / 越权短语）在 `before_tool_call` 和 `before_final_answer` 拦截 | 需 golden trace 验证，避免误伤 |
| **P5** | 后置：F18 输出/流式 gate 落地后，关闭 `policy.enable_prompt_fallback` 并移除 prompt 安全规则文本 | 依赖 F18 |

**v1 最小可交付（MVP）：P0 + P1 + P2。** `tool_group` 硬过滤（P3）在 `read` 父组语义与层级匹配实现后再启用。

## 14. 后续

- [F08](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) §execution_gate 标注为「PolicyEngine `before_tool_call` 适配器」。
- [F14](F14_AGENT_TOOL_ROUTER_PREPLAN.md) §「execution_gate 仍负责最终是否允许执行」保持，补充「= PolicyEngine 适配器」。
- `pause` 停止决策与 [F18](F18_AGENT_QUALITY_GATES.md) `StopPolicy.pause` 联动（v1 同步降级）。
