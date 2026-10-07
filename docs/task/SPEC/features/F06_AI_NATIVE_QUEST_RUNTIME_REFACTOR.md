# F06 — AI-native Quest Runtime 重构规格

> **Architecture Role：** 将现有 Task System 从“任务状态机 + 池认领”升级为 **受治理的目标驱动行动闭环**。现有 `task` 保留为可分派、可审计的 Objective/Actionable Work Item；新的系统中心上移到 `Situation → Goal → Quest → Objective → Action → Evidence → Outcome → Learning`。
>
> **依赖：** [`SPEC.md`](../SPEC.md) 设计律 D1-D3、[`F01`](F01_TASK_ONTOLOGY_AND_NODE_TYPES.md) 图节点本体、[`F02`](F02_TASK_POOL_AND_CLAIM_PROTOCOL.md) 池认领、[`F03`](F03_TASK_COLLABORATION_WORKFLOW.md) 状态机、[`F04`](F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md) 关系底座、[`F05`](F05_TASK_POOL_FIRST_CLASS_REGISTRY.md) 池治理、[`docs/models/SPEC/features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md`](../../../models/SPEC/features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md) Agent L1-L4 架构。

**文档状态：Draft（重构提案 v1）**

---

## 1. 背景与重构判断

现有 Task System 已完成 Phase B 骨架：`task` 节点、任务池、assignment、transition ledger、outbox、命令族与最小状态迁移。这套设计适合表达“某个主体认领并完成一项工作”。

但在 AI-native 企业设备维护系统中，核心对象不应继续停留在 Work Order / Task。更合适的抽象是：

```text
Observation / Fact
  + Hard Rule Trigger 或 Weak Experience Trigger
  -> Situation Assertion
  -> Goal
  -> Quest
  -> Objective
  -> Action
  -> Evidence
  -> Outcome
  -> Learning
```

其中 `Situation` 是陈述性描述，不是告警、事件或任务；Quest 也不是一个 Task Container，而是：

```text
Governed Goal-directed Learning Loop
```

即“受治理的、目标驱动的、可学习的行动闭环”。

### 1.1 与传统企业系统的边界

| 来源 | 可继承能力 | 不直接继承的部分 |
|---|---|---|
| SAP EAM | Asset / Material / Cost / Resource / Task List / phase / settlement | Work Order 作为唯一中心 |
| Oracle Maintenance | Work Definition / Operation / Resource / decision-centric workspace | 预定义 operation sequence 作为唯一执行路径 |
| Workday | Role / security group / approval / organization semantics | 确定性 Business Process 覆盖所有 runtime 决策 |
| ServiceNow | 通用 Task、CMDB、cross-domain workflow、AI governance/control plane | Record inbox 作为主要用户体验 |
| MUD / MMO Quest | Persistent World、Quest Graph、Trigger、Party、Branch、Event progression | 积分、等级等游戏化外壳 |

CampusWorld 已具备 Persistent Semantic World 的底座，因此任务系统应优先利用“世界模型”，而不是把所有运行时事实塞进 `task.attributes`。

---

## 2. 范围

### 2.1 In-Scope

- 定义 `Situation / Goal / Quest / Objective / Action / Evidence / Outcome / Learning` 的语义边界。
- 定义现有 `task` 与新 `Objective` 的兼容关系。
- 定义 Quest Runtime 与 Policy Runtime / Agent Runtime / World Model 的边界。
- 定义新图节点、关系、关系表的推荐建模方式。
- 定义运行时状态机、重规划、验证、审计与学习闭环。
- 定义从现有 Task System 平滑迁移的分期计划。
- 定义命令层与 World UI 的下一代交互契约。

### 2.2 Non-Goals

- 不引入通用 BPMN 引擎。
- 不让 LLM 直接修改 Policy / SOP / QualitySpec。
- 不把所有 Agent 内部思考步骤持久化为企业级任务。
- 不要求 Phase B/C 既有 `task` 命令立即破坏性迁移。
- 不替代 SAP / Oracle / ServiceNow 等外部系统记录；这些记录作为 Action transaction envelope 或 Evidence source 接入。

---

## 3. 核心语义对象

### 3.1 严格边界

| 对象 | 本质 | 回答的问题 | 生命周期 |
|---|---|---|---|
| `Observation` | 原始事实或事件信号 | 看到/收到什么？ | 短到中 |
| `Situation` | 基于事实与触发依据形成的世界状态陈述 | 当前可以声明什么情况成立？ | 中，可持续演化 |
| `Goal` | 对未来世界状态的期望与评价函数 | 希望世界变成什么样？ | 中到长，稳定 |
| `Quest` | 受治理的行动闭环实例 | 在当前约束和知识下如何干预？ | 中，业务可审计 |
| `Objective` | Quest 内可分派、可验证的业务目标片段 | 哪个子目标需要被推进？ | 中 |
| `Action` | 人/Agent/设备/服务执行的一步操作 | 实际做了什么？ | 短，动态 |
| `Evidence` | 支撑判断的可信证据 | 凭什么说完成/失败/合规？ | 长，审计 |
| `Outcome` | Quest 对世界和业务产生的结果 | 最终效果如何？ | 长，审计/学习 |
| `Learning` | 从结果回流出的组织经验 | 企业学到了什么？ | 长，版本化 |

### 3.2 不再等价的概念

- `Situation != Observation / Alarm / Event`：Observation 是事实信号，Alarm/Event 是发生记录；Situation 是基于事实和触发依据形成的 assertion。
- `Situation != Goal / Task`：Situation 陈述“世界现在处于何种业务状态”，Goal 陈述“世界应变成什么状态”，Task/Objective 是可分派工作。
- `Goal != Action`：`replace bearing` 是动作；`AHU-102 safe operation before 18:00` 才是目标。
- `Quest != Work Order`：Work Order 是某些 Action 的事务外壳；Quest 是跨系统行动闭环。
- `Task != Quest`：现有 `task` 应演进为 Objective 或 Actionable Work Item。
- `Process != Workflow`：Process 是企业行动知识，不必一比一实例化为 runtime graph。

---

## 4. 五个 Plane

Quest Runtime 必须保持五个平面相对独立，避免把企业知识、治理、事实和行动都塞进 `task`。

| Plane | 核心对象 | 职责 |
|---|---|---|
| Reality Plane | Entity / State / Event / Observation | 保存当前世界与历史事实 |
| Intent Plane | Situation / Goal / Risk / Opportunity | 对事实进行业务解释并声明目标 |
| Knowledge & Governance Plane | Policy / Control / ProcessPattern / SOP / QualitySpec / Case | 提供硬约束、质量标准、弱经验和历史案例 |
| Action Plane | Quest / Objective / Plan / Action / Actor / Resource | 组织人、Agent、设备和服务改变世界 |
| Learning Plane | Evidence / Outcome / Lesson / ImprovementProposal | 形成审计证据和组织学习 |

### 4.1 四种企业记忆

| Memory | 内容 | CampusWorld 位置 |
|---|---|---|
| World Memory | 当前世界是什么样 | graph nodes / relationships / state snapshots |
| Normative Memory | 企业规定应该怎样 | Policy / Control / QualitySpec |
| Episodic Memory | 过去发生过什么 | Quest history / Evidence / Outcome / Case |
| Procedural Memory | 企业学会了怎样处理 | ProcessPattern / SOP / Playbook / Skill |

Quest Runtime 位于四种记忆中间，负责将它们组合成当前行动。

---

## 5. 领域模型

### 5.1 `situation` 节点

`situation` 表示“对世界状态的陈述性业务描述”，格式上接近 assertion。它不是 observation、alarm、event，也不是 goal/task。R1 中 Situation 必须同时记录：

- `assertion`：当前声明成立的业务状态。
- `fact_refs` / `evidence_refs`：支持 assertion 的事实或证据引用。
- `trigger_kind` / trigger provenance：说明为什么这些事实被提升为 Situation。

触发来源分为：

| `trigger_kind` | 来源 | R1 约束 |
|---|---|---|
| `hard_rule` | Policy / Control / QualityCriterion / deterministic threshold | 必须 pin `rule_refs`，且必须有事实或证据依据 |
| `weak_experience` | ProcessPattern / SOP / Case / anomaly pattern / Agent inference | 必须记录 `experience_refs` 或 `inference_trace_summary`，且必须有事实或证据依据 |
| `manual` | 人工陈述 | 可无 rule/experience refs，但必须有 assertion 与 actor provenance |
| `mixed` | 事实、强规则、弱经验共同触发 | 必须同时记录 rule provenance 与 weak-experience provenance，且必须有事实或证据依据 |

R1 只保存可审计引用和轻量摘要，不实现完整 Policy Gate、Evidence Verification 或 Learning Loop。弱经验只能提出或更新 Situation，不得直接授权高风险 Quest 执行；强规则触发的 Situation 也不代表行动自动获批，后续仍需 Quest / Policy gate。

建议 `nodes.type_code='situation'`，瘦属性：

| 字段 | 类型 | 含义 |
|---|---|---|
| `current_state` | enum | `asserted / triaged / linked_goal / resolved / dismissed` |
| `state_version` | int | 乐观锁 |
| `title` | string | 简短解释 |
| `assertion` | string | 对世界状态的陈述性描述，必填 |
| `subject_ref` | int/null | 主体节点 id |
| `trigger_kind` | enum | `hard_rule / weak_experience / manual / mixed` |
| `trigger_summary` | string/null | 触发依据摘要 |
| `fact_refs` | array | 事实引用，非人工 Situation 至少与 `evidence_refs` 二选一 |
| `evidence_refs` | array | 证据引用，非人工 Situation 至少与 `fact_refs` 二选一 |
| `rule_refs` | array | 强规则引用；`hard_rule` 和 `mixed` 必填 |
| `experience_refs` | array | 弱经验引用；`weak_experience` 和 `mixed` 可与 inference summary 二选一 |
| `inference_trace_summary` | string/null | Agent/经验推断摘要；弱经验无 experience refs 时必填 |
| `confidence` | number | 当前解释置信度 |
| `severity` | enum | `low / medium / high / critical` |
| `business_impact` | string/object | 业务影响摘要 |
| `temporal_scope` | object | 起止时间或预测窗口 |

关系：

| 边 | 起 -> 止 | 含义 |
|---|---|---|
| `ABOUT` | `situation -> entity` | 涉及的设备/空间/系统 |
| `SUPPORTED_BY` | `situation -> evidence` | 支撑该解释的证据 |
| `TRIGGERED_BY_RULE` | `situation -> policy/control/quality` | 触发该 Situation 的强规则 |
| `TRIGGERED_BY_EXPERIENCE` | `situation -> process/case/pattern` | 触发该 Situation 的弱经验 |
| `RAISES_GOAL` | `situation -> goal` | 由该情况提出目标 |
| `RELATED_TO` | `situation -> situation` | 相关情况 |

语义不变式：

- `Situation` 必须有 `assertion`。
- 非人工 Situation 必须至少有一个 `fact_ref` 或 `evidence_ref`。
- `trigger_kind='hard_rule'` 必须 pin `rule_refs`。
- `trigger_kind='weak_experience'` 必须记录 `experience_refs` 或 `inference_trace_summary`。
- `trigger_kind='mixed'` 必须同时满足强规则与弱经验 provenance。
- 弱经验只能提出/更新 Situation，不得直接触发高风险 Quest 执行。
- 强规则触发的 Situation 不代表自动批准行动，仍需 Quest/Policy gate。

### 5.2 `goal` 节点

`goal` 表示 Desired World State，而不是具体操作。

瘦属性：

| 字段 | 类型 | 含义 |
|---|---|---|
| `current_state` | enum | `proposed / accepted / active / satisfied / abandoned` |
| `state_version` | int | 乐观锁 |
| `title` | string | 目标标题 |
| `desired_state` | jsonb | 指标、阈值、评价函数 |
| `constraints` | jsonb | downtime、成本、安全、时间等约束 |
| `priority` | enum | `low / normal / high / urgent` |
| `deadline_at` | timestamptz | 业务截止时间 |
| `owner_principal` | object | 目标 owner |
| `acceptance_summary` | object | 验收标准摘要 |

关系：

| 边 | 起 -> 止 | 含义 |
|---|---|---|
| `GOAL_FOR` | `goal -> situation` | 目标回应哪个 situation |
| `MEASURED_BY` | `goal -> quality_spec` | 目标的质量/验收标准 |
| `REALIZED_BY` | `goal -> quest` | 哪些 Quest 尝试实现目标 |

### 5.3 `quest` 节点

`quest` 是行动闭环聚合根。它引用政策、流程、质量、案例的版本，而不复制其内容。

瘦属性：

| 字段 | 类型 | 含义 |
|---|---|---|
| `current_state` | enum | `draft / planning / awaiting_decision / executing / verifying / accepted / failed / cancelled / learned / closed` |
| `state_version` | int | 乐观锁 |
| `title` | string | Quest 名称 |
| `situation_id` | int | 主情况 |
| `goal_id` | int | 主目标 |
| `quest_ref` | object | `{key, version}`，可引用 quest template |
| `plan_graph_summary` | object | 计划图摘要 |
| `policy_refs` | array | `policy@version` 引用 |
| `process_refs` | array | `process_pattern@version` 引用 |
| `quality_refs` | array | `quality_spec@version` 引用 |
| `case_refs` | array | 历史案例引用 |
| `risk_level` | enum | 当前风险等级 |
| `progress` | object | Objective 汇总 |
| `outcome_summary` | object | 结果摘要 |

关系：

| 边 | 起 -> 止 | 含义 |
|---|---|---|
| `RESPONDS_TO` | `quest -> situation` | Quest 回应 Situation |
| `PURSUES` | `quest -> goal` | Quest 追求 Goal |
| `HAS_OBJECTIVE` | `quest -> task/objective` | Quest 下的 Objective |
| `GOVERNED_BY` | `quest -> policy/control` | 治理规则 |
| `GUIDED_BY` | `quest -> process_pattern/sop/playbook` | 行动知识 |
| `MEASURED_BY` | `quest -> quality_spec` | 质量标准 |
| `INFORMED_BY` | `quest -> case` | 历史经验 |
| `PRODUCED` | `quest -> evidence/outcome/lesson` | 证据与结果 |

### 5.4 `objective`

Phase-compatible 方案：`Objective` 初期直接复用 `nodes.type_code='task'`。

约定：

- `task.attributes.quest_id` 指向所属 Quest。
- `task.attributes.objective_kind` 表示 `diagnose / stabilize / procure / repair / verify / learn / custom`。
- `task.attributes.required_capabilities` 表示能力要求。
- `task.attributes.acceptance_criteria_refs` 引用质量要求。
- `task.attributes.evidence_requirement_refs` 引用证据要求。

长期方案可以新增 `objective` 节点类型，但不得在未完成迁移前破坏现有 `task` 命令。

### 5.5 `action`

Action 是短生命周期操作，不要求每一步都成为 `task`。

Action 可以落在：

- `task_runs.command_trace`
- `quest_action_records` 关系表
- Agent run records
- 外部系统 transaction reference

持久化规则：

| Action 类型 | 是否企业级持久化 | 说明 |
|---|---|---|
| 改变世界状态 | 是 | 如维修、采购、配置变更 |
| 产生审计要求 | 是 | 如审批、LOTO、隔离验证 |
| 仅 Agent 内部推理 | 否 | 保留 trace 摘要即可 |
| 外部系统事务 | 是 | 保存 transaction envelope ref |

### 5.6 Evidence / Quality / Outcome

Evidence 不应只是附件。它是验证 Goal 的可信事实引用。

建议对象：

| 对象 | 含义 |
|---|---|
| `evidence_requirement` | 需要什么证据 |
| `evidence_record` | 实际收集到的证据 |
| `quality_criterion` | 验收指标 |
| `quality_gate` | 验证关口 |
| `verification_result` | 验证结果 |
| `nonconformance` | 不符合项 |
| `corrective_action` | 纠正措施 |
| `outcome` | Quest 最终结果 |

关键原则：

```text
Complete Objective != Accepted Quest
Accepted Quest == Goal / Quality Criteria satisfied by trusted Evidence
```

---

## 6. 状态机

### 6.1 Situation 状态

```text
detected -> triaged -> linked_goal -> resolved
                  \-> dismissed
```

| 状态 | 含义 |
|---|---|
| `detected` | 由 observation/event 触发，尚未确认业务意义 |
| `triaged` | 已判定值得关注，含 severity / confidence |
| `linked_goal` | 已关联一个或多个 Goal |
| `resolved` | 情况已被处理或不再成立 |
| `dismissed` | 被人工/策略判定为无需处理 |

### 6.2 Goal 状态

```text
proposed -> accepted -> active -> satisfied
                       \-> abandoned
```

Goal 的满足必须由 verifier 基于 evidence 判断，不由 planner 自行声明。

### 6.3 Quest 状态

```text
draft
  -> planning
  -> awaiting_decision
  -> executing
  -> verifying
  -> accepted
  -> learned
  -> closed

executing -> failed
executing -> cancelled
verifying -> executing   # evidence 不足或质量不通过，返工
```

| 状态 | expected roles |
|---|---|
| `draft` | owner |
| `planning` | owner, planner |
| `awaiting_decision` | owner, approver |
| `executing` | owner, executor, supervisor |
| `verifying` | owner, verifier |
| `accepted` | owner |
| `learned` | owner, knowledge_curator |
| `closed` | none |
| `failed` | owner |
| `cancelled` | none |

### 6.4 Objective 状态

Objective 沿用现有 `task` 状态机，但应补齐 Phase C 事件：

```text
draft -> open -> claimed -> in_progress -> pending_review -> approved -> done
                         \-> failed
                         \-> cancelled
```

Quest Runtime 不直接绕过 `task_state_machine` 改写 Objective；它通过命令层或服务层调用现有状态机。

---

## 7. 运行时组件

### 7.1 组件边界

```text
Experience
  Mission Feed / World View / Conversation
        |
        v
Quest Runtime
  Situation Manager
  Goal Manager
  Planner / Replanner
  Scheduler
  Verifier
  Learning Proposer
        |
        +------ Policy Runtime
        |         policy / control / approval / authority / segregation
        |
        +------ Agent Runtime
        |         reason / tool-call / execute / observe
        |
        v
World Model
  graph entities / states / observations / events
        |
        v
Systems of Record / Physical World
  SAP / Oracle / ServiceNow / IoT / BMS / MES / ERP
```

### 7.2 Quest Runtime 循环

```text
Observe -> Interpret -> Define Goal -> Plan -> Gate -> Act -> Verify -> Re-plan -> Learn
```

| Step | 写入对象 |
|---|---|
| Observe | observation / event / evidence |
| Interpret | situation |
| Define Goal | goal |
| Plan | quest + objectives |
| Gate | decision / approval / policy evaluation |
| Act | task transition / action record / external transaction |
| Verify | verification_result / quality_gate |
| Re-plan | plan_graph revision / objective changes |
| Learn | outcome / case / lesson / improvement_proposal |

### 7.3 Policy Runtime

Policy Runtime 控制“AI 可以做什么”，不规定“AI 每一步怎么做”。

它负责：

- who may decide
- who may execute
- what must never happen
- what requires approval
- what evidence is mandatory
- what risk is acceptable
- segregation of duties
- kill switch / hold / escalation

任何 Quest Plan 进入执行前必须通过 deterministic policy gate。

### 7.4 Agent Runtime

Agent 可以：

- 创建 Situation draft。
- 提出 Goal candidate。
- 生成 Quest Plan draft。
- 建议 Objective 分解。
- 执行被授权的 Action。
- 收集 Evidence。
- 提出 LearningProposal。

Agent 不可以：

- 绕过 Policy / Control。
- 自行接受高风险 Quest。
- 自行修改 Policy / SOP / QualitySpec 正式版本。
- 将内部思考步骤全部升级成企业级 Objective。

---

## 8. Invariants

| 编号 | 不变式 |
|---|---|
| QI1 | Quest 必须引用至少一个 Goal；Goal 必须引用或声明 DesiredState。 |
| QI2 | Quest 所有执行型 Objective 必须有 `quest_id` 且由 `HAS_OBJECTIVE` 或等价 FK 关联。 |
| QI3 | `accepted / closed` Quest 必须至少有一个 `verification_result.status='passed'` 或明确的 human override evidence。 |
| QI4 | Policy / Quality / Process 引用必须 pin 到版本；in-flight Quest 不随新版本漂移。 |
| QI5 | Hard Policy / Control 拒绝后，Planner 不得通过改写 Objective 绕过同一约束。 |
| QI6 | Quest Plan 每次重写必须记录 `plan_revision`、actor、reason、correlation_id。 |
| QI7 | Agent 内部 Action 不自动持久化为 Objective；只有改变世界状态、产生审计要求或需要人/Agent/设备认领的 Action 才升级。 |
| QI8 | LearningProposal 不能直接修改正式 Policy / SOP / QualitySpec；必须经治理审批生成新版本。 |
| QI9 | `task.current_state='done'` 不等价于 Quest accepted；Quest acceptance 以 Goal + Evidence + QualityGate 为准。 |
| QI10 | Situation confidence / severity 的自动变更必须保留 evidence 或 inference trace 摘要。 |

---

## 9. 数据模型落地建议

### 9.1 Phase-compatible 最小增量

R1 本轮新增节点类型：

- `situation`
- `goal`
- `quest`

R2+ 再新增：

- `evidence`
- `outcome`
- `process_pattern`
- `quality_spec`
- `policy`
- `case`
- `improvement_proposal`

优先新增关系：

- `ABOUT`
- `SUPPORTED_BY`
- `TRIGGERED_BY_RULE`
- `TRIGGERED_BY_EXPERIENCE`
- `RAISES_GOAL`
- `GOAL_FOR`
- `RESPONDS_TO`
- `PURSUES`
- `HAS_OBJECTIVE`
- `OWNED_BY`
- `SCOPED_AT`

R2+ 再新增或启用：

- `REALIZED_BY`
- `GOVERNED_BY`
- `GUIDED_BY`
- `MEASURED_BY`
- `INFORMED_BY`
- `PRODUCED`

继续复用现有关系表：

- `task_assignments` 用于 Objective 分派。
- `task_state_transitions` 用于 Objective 状态。
- `task_runs` 用于 Objective/Action 执行轨迹。
- `task_outbox` 用于 Objective 事件。

R1 不新增 Quest 专用表。R2+ 关系表建议：

| 表 | 角色 |
|---|---|
| `quest_state_transitions` | Quest 状态审计 |
| `quest_plan_revisions` | plan graph 版本历史 |
| `quest_decisions` | 人/Agent 决策记录 |
| `quest_action_records` | 需要审计的 Action |
| `evidence_records` | 证据记录 |
| `verification_results` | 质量验证结果 |
| `learning_proposals` | 经验改进提案 |

### 9.2 为什么不直接扩展 `task_*` 表

现有 `task_*` 表服务的是 Objective 级别的认领、状态、分派与 outbox。Quest 需要同时管理 Situation、Goal、Policy、Quality、Case、Evidence、Outcome、Learning。如果直接扩展 `task`，会导致：

- `task.attributes` 重新变厚，违反 D2。
- 任务池查询混入 Goal/Quest 语义，破坏热路径。
- Objective 完成与 Quest 验收混淆。
- Agent 内部步骤膨胀为企业任务，形成 Agent Task Explosion。

因此，兼容策略是：

```text
Quest owns semantics.
Task/Objective owns assignment and execution.
Evidence/Quality owns verification.
Knowledge owns reusable process and governance.
```

---

## 10. 命令与 API 草案

### 10.1 命令族

R1 新增 `situation` / `goal` / `quest` 轻量命令族，`task` 命令族保持兼容。

| 命令 | 行为 |
|---|---|
| `situation create --title <T> --assertion <A> [--subject <node_id>] [--trigger-kind hard_rule\|weak_experience\|manual\|mixed] [--fact-ref <R>] [--evidence-ref <R>] [--rule-ref <R>] [--experience-ref <E>] [--confidence <0..1>] [--severity low\|medium\|high\|critical]` | 创建 declarative Situation assertion |
| `situation list [--limit N]` | 列出 Situation |
| `situation show <id>` | 展示 assertion 与 trigger provenance |
| `goal create --title <T> --situation <id> [--priority low\|normal\|high\|urgent]` | 从 Situation 创建 Goal |
| `goal list [--limit N]` | 列出 Goal |
| `goal show <id>` | 展示 Goal |
| `quest create --situation <id> --goal <id> --title <T>` | 创建 Quest draft |
| `quest list [--limit N]` | 列出 Quest |
| `quest show <id>` | 展示 Situation / Goal / Objectives / Evidence / Progress |

R2+ 命令：

| 命令 | 行为 |
|---|---|
| `quest plan <id>` | 生成或刷新 plan draft |
| `quest approve-plan <id>` | 通过 plan gate |
| `quest execute <id>` | 将可执行 objective 发布到池或指派 actor |
| `quest verify <id>` | 运行 verifier / quality gate |
| `quest replan <id> --reason <R>` | 生成新 plan_revision |
| `quest accept <id>` | 在 verification passed 后接受结果 |
| `quest learn <id>` | 生成 learning proposal |
| `quest close <id>` | 关闭 Quest |

### 10.2 `task` 兼容扩展

`task create` 增加：

- `--quest <quest_id>`
- `--scoped-at <node_id>`
- `--objective-kind <kind>`
- `--requires-capability <capability[,capability...]>`
- `--evidence-required <evidence_requirement_id>`（R2+）

`task show` 显示：

- 所属 Quest。
- Objective kind。
- Required capabilities。
- Evidence requirements。
- Quality gate status。

### 10.3 World UI

World UI 应从 Inbox 升级为 Mission / Situation / Decision Feed：

| 区域 | 内容 |
|---|---|
| Situation Feed | 当前需要关注的情况 |
| Mission Card | Quest 进度、风险、下一步决策 |
| Objective Queue | 可执行 Objective，不再作为唯一中心 |
| Evidence Panel | 验证数据、照片、传感器窗口、外部记录 |
| Learning Panel | 结果总结与改进提案 |

UI 文案不得暗示 `task done` 等于业务目标完成。

---

## 11. 示例：AHU 轴承异常

### 11.1 Observation

```json
{
  "asset": "AHU-102",
  "signals": {
    "vibration_rms": 8.1,
    "bearing_temperature": 83
  },
  "observed_at": "2026-10-07T10:15:00+08:00"
}
```

### 11.2 Situation

```json
{
  "title": "AHU-102 suspected bearing degradation",
  "subject_ref": {"node_id": 102, "type_code": "device"},
  "confidence": 0.82,
  "severity": "high",
  "hypotheses_summary": {
    "primary": "bearing_degradation"
  },
  "risk_summary": {
    "risks": ["production_interruption", "secondary_shaft_damage"],
    "window": "24h"
  }
}
```

### 11.3 Goal

```json
{
  "title": "Restore safe operation of AHU-102 before 18:00",
  "desired_state": {
    "metrics": [
      {"name": "vibration_rms", "op": "<", "value": 4.5, "unit": "mm/s"},
      {"name": "bearing_temperature", "op": "<", "value": 70, "unit": "C"}
    ]
  },
  "constraints": {
    "max_production_interruption_minutes": 30,
    "no_safety_policy_violation": true
  },
  "priority": "urgent"
}
```

### 11.4 Quest

```json
{
  "title": "AHU-102 Bearing Degradation Response",
  "policy_refs": ["maintenance_safety@3.2", "loto_control@2.1"],
  "process_refs": ["bearing_degradation_response@4.2"],
  "quality_refs": ["rotating_equipment_post_maintenance@2.4"],
  "case_refs": ["case:AHU-103:2026Q2"],
  "objectives": [
    "diagnose probable failure",
    "determine safe operating window",
    "locate approved replacement or substitute",
    "schedule intervention",
    "repair",
    "verify",
    "update asset knowledge"
  ]
}
```

### 11.5 Acceptance

Quest 可接受的条件：

- vibration RMS 连续 30 分钟低于阈值。
- bearing temperature 连续 30 分钟低于阈值。
- LOTO / safety evidence 完整。
- 维修记录与替换件记录已归档。
- 无 open nonconformance。

---

## 12. 与现有 Task System 的迁移计划

### R0 — Foundation Repair

目标：修正现有任务系统的正确性基础。

- 修正 `task_state_machine.transition()` 的事务边界，确保幂等检查、FOR UPDATE、SSOT 更新、assignment、transition、outbox 在同一事务内。
- 补齐 `task create --scoped-at` 写 `SCOPED_AT`，owner 写 `OWNED_BY` 或等价 assignment/edge。
- World UI 不再生成未实现的 `task start` 动作，或补齐 `start` Phase C 事件。
- 保持 `task` Phase B/C 测试绿色。

### R1 — Semantic Shell

目标：新增 Situation / Goal / Quest 节点与只读展示，不改变 task 热路径。

- 注册节点类型与关系。
- 新增 `quest show/list`、`situation show/list`、`goal show/list`。
- `task` 增加可选 `quest_id`。
- World UI 展示 Mission Card，但执行仍走现有 `task` 命令。

### R2 — Governed Planning

目标：Quest Plan 由 Policy / Process / Quality / Case 约束。

- 新增 `quest_plan_revisions`。
- 新增 deterministic policy gate。
- 引入 `required_capabilities` 到 Objective。
- 将 `task_pools` 查询扩展为 capability-aware candidate pool。

### R3 — Evidence-based Verification

目标：从“点击完成”升级为证据验收。

- 新增 evidence / quality / verification 表。
- `quest verify` 基于 evidence 判断 Goal。
- `quest accept` 要求 verification passed 或 human override。

### R4 — Learning Loop

目标：让 Quest Outcome 回流为组织经验。

- 新增 Case / Lesson / ImprovementProposal。
- Quest close 后生成 outcome。
- LearningProposal 必须人工/治理审核后才能生成新 Process / SOP / QualitySpec 版本。

---

## 13. Acceptance

### 文档级

- [ ] `Situation / Goal / Quest / Objective / Action / Evidence / Outcome / Learning` 边界经评审通过。
- [ ] 明确 `task` 保留为 Objective/Actionable Work Item，Quest 为新行动聚合根。
- [ ] 明确 Process 是企业行动知识，不等价于 Runtime Workflow。
- [ ] 明确 Policy / Control / QualityCriterion 为硬约束，ProcessPattern / SOP / Case 为可偏离的弱经验。
- [ ] 明确 Evidence-based Completion：Quest acceptance 不等于 task done。
- [ ] 明确 Agent 不能绕过 deterministic policy gate，也不能直接修改正式知识版本。

### 实现级 R0

- [ ] `task_state_machine.transition()` 全写路径单事务覆盖。
- [ ] `task create --scoped-at` 落 `SCOPED_AT`；owner 关系/assignment 可审计。
- [ ] World UI 不再指向未实现的 `task start`，或 `start` 已实现。
- [ ] Phase B/C 现有测试仍通过。

### 实现级 R1

- [ ] `situation / goal / quest` 节点类型注册。
- [ ] 关系 `RESPONDS_TO / PURSUES / HAS_OBJECTIVE` 可创建和查询。
- [ ] `task.attributes.quest_id` 与 Quest objective rollup 一致。
- [ ] `quest show` 能展示 situation、goal、objectives、progress。

### 实现级 R2-R4

- [ ] Policy gate 拒绝路径可审计，且 Agent 无法通过 replan 绕过同一 hard constraint。
- [ ] Quest plan revision 单调，含 actor、reason、correlation_id。
- [ ] Evidence requirement 与 verification result 可查询。
- [ ] Quest accepted 需要 verification passed 或 human override evidence。
- [ ] LearningProposal 不直接修改正式 Process / SOP / Policy / QualitySpec。

---

## 14. Open Questions

1. `Objective` 是否长期复用 `task`，还是在 R2 后引入独立 `objective` 节点类型？
2. Policy Runtime 先复用现有 command policy engine，还是引入独立 Quest policy evaluator？
3. QualitySpec 应作为 graph node，还是版本化关系表？
4. Case / Experience 是否归入 CampusLibrary / Knowledge World，还是 Task module 自管？
5. Quest plan graph 是否需要独立 DSL，还是复用 workflow_definition spec 的子集？
6. 外部系统 transaction envelope 的统一 ref schema 如何定义？
7. Mission Feed 是否走现有 WorldInteraction state，还是引入 Quest-specific projection？
