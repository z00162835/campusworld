# F06 — AI-native Quest Runtime 重构规格

> **Architecture Role：** 将现有 Task System 从“任务状态机 + 池认领”升级为 **受治理的目标驱动行动闭环**。现有 `task` 保留为可分派、可审计的 Objective/Actionable Work Item；新的系统中心上移到 `Situation → Goal → Quest → Objective → Action → Evidence → Outcome → Learning`。
>
> **依赖：** [`SPEC.md`](../SPEC.md) 设计律 D1-D3、[`F01`](F01_TASK_ONTOLOGY_AND_NODE_TYPES.md) 图节点本体、[`F02`](F02_TASK_POOL_AND_CLAIM_PROTOCOL.md) 池认领、[`F03`](F03_TASK_COLLABORATION_WORKFLOW.md) 状态机、[`F04`](F04_TASK_RELATIONAL_SUBSTRATE_AND_OBSERVABILITY.md) 关系底座、[`F05`](F05_TASK_POOL_FIRST_CLASS_REGISTRY.md) 池治理、[`docs/models/SPEC/features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md`](../../../models/SPEC/features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md) Agent L1-L4 架构。

**文档状态：Approved for Implementation（R0 与部分 R1 已实现；新增 R1 及 R2–R4 待实施验收）**

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

本规格中的 `Situation / Goal / Quest / Objective / Action / Evidence / Outcome / Learning`
以及它们引用的 `Policy / Control / QualitySpec / ProcessPattern / Case` 都属于语义世界对象。
“是否在 R1 注册为 `nodes.type_code`”只是分期落地差异，不表示对象在世界模型之外。R1 对尚未物化为节点的对象使用可审计、可版本 pin 的 semantic ref 作为桥接；一旦对应节点类型存在，引用应优先解析到语义世界节点。

---

## 2. 范围

### 2.1 In-Scope

- 定义 `Situation / Goal / Quest / Objective / Action / Evidence / Outcome / Learning` 的语义边界。
- 定义现有 `task` 与新 `Objective` 的兼容关系。
- 定义 Quest Runtime 与 Quest governance、F16 behavior policy、command authorization、Agent Runtime、World Model 的边界。
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

### 4.2 世界事实、用户选择与 Agent Memory 的边界

CampusWorld 采用“世界即外化记忆 + Agent 内化记忆”的组合，不把所有内容塞入 LTM：

- 可验证的世界事实、Situation/Quest 主链路、用户明确的 Quest/Objective/Clue 选择使用 graph nodes/relationships 持久化，并受图权限约束。
- 对话连续性、个人偏好解释、情境摘要和历史 episode 使用按 account + Agent 隔离的 STM/LTM；LTM 通过 `graph_node_id / relationship_id` 引用图对象，不能覆盖图事实。
- 用户推荐、模型预测和向量召回都不是事实；重新用于计划或执行前必须按当前权限解析图对象并校验版本。
- Quest 对话归档可以成为 episodic/LTM 晋升输入，但不得直接发布为企业 Process/Policy/Skill，也不得直接修改 Agent 节点配置。

用户场景选择复用现有语义对象，不新增通用 `scenario` 节点：多个 `TRACKS_QUEST account -> quest` 表示用户追踪的行动闭环集合，唯一 `FOCUSES_ON account -> task/objective` 表示当前前台业务焦点，`PINS_CLUE account -> fact/observation/evidence` 表示用户明确保留的已物化事实线索。推荐、地图 hover 与临时 inspect 不创建这些边。

`PINS_CLUE` 的身份按 `account + quest + clue` 确定：同一账户可将同一线索分别 pin 到多个 Quest；对一个 Quest unpin 不得影响其他 Quest 的 pin。

---

## 5. 领域模型

### 5.0 `observation` 节点

`observation` 是带来源的世界陈述输入，不等价于已验证 Fact/Evidence。R1 物化它是为了让 Situation provenance 与用户 `PINS_CLUE` 指向真实图节点，而不是悬空字符串。

| 字段 | 类型 | 约束 |
|---|---|---|
| `assertion` | string | 必填；原始观察陈述，创建后不可原地改写 |
| `source_ref` | string | 必填；传感器、系统记录、人工输入或外部事件引用 |
| `provenance` | object | 必填；source kind、采集方式及可用 correlation/trace id |
| `observed_at` | datetime | 必填；业务观察发生时间，不使用写库时间替代 |
| `actor_id` | node id | 必填；记录该 Observation 的 human/Agent/system principal |
| `subject_ref` | node id/null | 可选；观察所指向的可读世界对象 |
| `verification_status` | enum | R1 固定初始为 `unverified`；R3 的支持/反驳/失效通过 Evidence/verification 记录表达 |

去重只能依据受治理的 source identity/idempotency key，不能对自然语言 assertion 做模糊合并。更正应创建新 Observation，并以 `provenance.corrects_observation_id` 指回被更正记录，保留原始审计链。

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

R1 只保存可审计引用和轻量摘要，不实现完整 Policy Gate、Evidence Verification 或 Learning Loop。这里的引用仍是语义世界引用：目标节点类型已存在时应指向 graph node；目标节点类型尚未落地时，可用 `namespace:key@version` 或等价稳定 ref 临时承接。弱经验只能提出或更新 Situation，不得直接授权高风险 Quest 执行；强规则触发的 Situation 也不代表行动自动获批，后续仍需 Quest / Policy gate。

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
| `BASED_ON_FACT` | `situation -> fact/observation` | assertion 基于的事实或观测 |
| `SUPPORTED_BY` | `situation -> evidence` | 支撑该解释的证据 |
| `TRIGGERED_BY_RULE` | `situation -> policy/control/quality` | 触发该 Situation 的强规则 |
| `TRIGGERED_BY_EXPERIENCE` | `situation -> process/case/pattern` | 触发该 Situation 的弱经验 |
| `RAISES_GOAL` | `situation -> goal` | 由该情况提出目标 |
| `RELATED_TO` | `situation -> situation` | 相关情况；R2+ 启用，R1 不注册/不创建 |

语义不变式：

- `Situation` 必须有 `assertion`。
- 非人工 Situation 必须至少有一个 `fact_ref` 或 `evidence_ref`。
- `trigger_kind='hard_rule'` 必须 pin `rule_refs`，R1 enforcement 使用 `namespace:key@version` 格式。
- `trigger_kind='weak_experience'` 必须记录 `experience_refs` 或 `inference_trace_summary`；存在 `experience_refs` 时，R1 enforcement 使用 `namespace:key@version` 格式。
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
| `desired_state` | string/object | 必填；指标、阈值、评价函数；R1 命令仅接收自然语言 string，结构化 object 仅保留给服务/API 或 R2+ GoalSpec |
| `constraints` | jsonb | downtime、成本、安全、时间等约束 |
| `priority` | enum | `low / normal / high / urgent` |
| `deadline_at` | timestamptz | 业务截止时间 |
| `owner_principal` | object | 目标 owner |
| `acceptance_summary` | string/null | 验收标准摘要；R1 命令仅接收自然语言 string，结构化 object 留 R2+ |

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
| `plan_graph_summary` | string/object | 计划图摘要；R1 命令仅接收自然语言 string，结构化 object 留 R2+ 版本化 plan graph |
| `policy_refs` | array | `namespace:key@version` policy 引用 |
| `process_refs` | array | `namespace:key@version` process/process_pattern 引用 |
| `quality_refs` | array | `namespace:key@version` quality/quality_spec 引用 |
| `case_refs` | array | `namespace:key@version` 历史案例引用 |
| `risk_level` | enum | 当前风险等级 |
| `progress` | object | Objective 汇总 runtime snapshot/cache；非 SSOT，可由 `HAS_OBJECTIVE` + task states 重建 |
| `outcome_summary` | object/null | 结果摘要；R1 创建时为空，Quest 验证/关闭阶段再写入 |

关系：

| 边 | 起 -> 止 | 含义 |
|---|---|---|
| `RESPONDS_TO` | `quest -> situation` | Quest 回应 Situation |
| `PURSUES` | `quest -> goal` | Quest 追求 Goal |
| `REALIZED_BY` | `goal -> quest` | 目标被哪些 Quest 尝试实现；R1 创建 Quest 时直接写入 |
| `HAS_OBJECTIVE` | `quest -> task/objective` | Quest 下的 Objective |
| `GOVERNED_BY` | `quest -> policy/control` | 治理规则 |
| `GUIDED_BY` | `quest -> process_pattern/sop/playbook` | 行动知识 |
| `MEASURED_BY` | `quest -> quality_spec` | 质量标准 |
| `INFORMED_BY` | `quest -> case` | 历史经验 |
| `PRODUCED` | `quest -> evidence/outcome/lesson` | 证据与结果 |
| `ASSISTED_BY` | `quest -> npc_agent` | Quest 的长期协作 Agent；关系本身不授予执行权限 |

用户选择关系：

| 边 | 起 -> 止 | 含义 |
|---|---|---|
| `TRACKS_QUEST` | `account -> quest` | 用户明确追踪的 Quest；每个 account 可有多个 active Quest，但同一 account+Quest 至多一个 active 边 |
| `FOCUSES_ON` | `account -> task/objective` | 多个已追踪 Quest 中账户唯一的前台 Objective 聚焦；不改变 Objective 状态 |
| `PINS_CLUE` | `account -> fact/observation/evidence` | 用户 pin 的已物化事实线索；R1 至少支持 canonical `observation`，未物化 semantic ref 不得伪造边 |

`ASSISTED_BY` 允许一个 Quest 对应多个 Agent，通过关系 attributes 表达 `role / status / is_primary_companion / capability_scope / valid_from / valid_to / actor / correlation_id`。协作关系与实际 Action executor 分离；执行者必须由命令、task run 或 Agent run 审计记录证明。

R1 `Quest -> Objective` 出边建议保持在 1-50 条的人工可审计范围内；超过该规模时应拆分为多个 Quest 或在 R2+ 引入 plan shard / batch objective，避免形成 supernode 并拖慢 Mission Card、relationship traversal 与 review UI。

`progress` 采用方案 B：保留在 `node_types.schema_definition.properties` 中作为 runtime/dynamic snapshot 字段，但它不是 Quest 的权威状态。当前 R1 实现把 progress 作为 `show_quest` 派生视图返回，不在创建 Quest 时写入持久 SSOT；后续 Mission Card / 列表性能需要缓存时，可以写入 `quest.attributes.progress`，但该字段必须可丢弃、可重建，并以 `HAS_OBJECTIVE` + task states 的现算结果为权威来源。业界对照：

- ServiceNow Task 共享基础 task 字段，但 SLA/escalation 等运行视图由规则动态填充，说明“列表/看板视图字段”和业务记录 SSOT 可以分离。
- Jira work item 以 status/resolution 表达完成语义，进度通常由 workflow category、resolution 或 agile board/report 派生，不把“百分比进度”作为 issue 的核心一致性字段。
- Temporal 明确区分 visibility store 与 authoritative workflow state；visibility 适合列表和过滤，单个 workflow 的权威状态仍通过 describe/query 获取。
- SAP maintenance order 更强调系统状态、变更文档和结算/释放等审计状态，进度性汇总通常来自 order/operation 状态与报表，而不是覆盖 order header 的单一 SSOT 百分比。

落地约束：

- R1 创建 Quest 时不得写入 progress 快照，避免把空进度误当作 SSOT。
- `show_quest` 返回的 progress 以现算结果为准；若 attributes 中存在 progress cache，也必须被现算结果覆盖。
- R2+ 若启用缓存写入，刷新责任应归属 Objective 状态变更路径、read-side projection updater 或一致性 worker；漂移处理以现算重建为准。
- 一致性巡检发现 progress cache 与现算结果不一致时，应记录 drift 并重建/刷新 cache，不得反向修改 Objective 状态。

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
asserted -> triaged -> linked_goal -> resolved
                  \-> dismissed
```

| 状态 | 含义 |
|---|---|
| `asserted` | 基于事实与触发依据形成陈述性 Situation，尚未完成业务分诊 |
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

R1 写入不可变核心的 `Observation` 记录，以及 `Situation / Goal / Quest` 的初始状态（`asserted / proposed / draft`）与主链路关系；不实现 semantic shell 的状态转移 ledger，`linked_goal / active / executing` 等生命周期推进由 R2+ 状态机补齐。

### 6.4 Objective 状态

Objective 沿用现有 `task` 状态机，但应补齐 Phase C 事件：

```text
draft -> open -> claimed -> in_progress -> pending_review -> approved -> done
                         \-> failed
                         \-> cancelled
```

Quest Runtime 不直接绕过 `task_state_machine` 改写 Objective；它通过命令层或服务层调用现有状态机。

R1 不再把 `claimed -> done` 作为长期例外。已落地优化方案：

1. 补齐最小 `task start` 事件与命令，严格走 `claimed / rejected -> in_progress`，沿用现有 workflow seed 中的 `start` 定义。
2. World UI 对 `claimed` 任务生成 `task start`，对 `in_progress / approved` 任务生成 `task complete`。
3. 移除 seed 中 `complete.from` 的 `claimed`，恢复为 `in_progress / approved -> done`。
4. 测试同步覆盖 `claim -> start -> complete`，并断言 `claim -> complete` 返回稳定错误。

该方案保持完整协作流语义，避免继续扩大 direct-complete 依赖。

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
        +------ Quest Decision Facade
        |         Quest governance + F16 behavior decision
        |         command authorization at execution
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

### 7.2.1 Objective 物化与自动执行决策

Situation 成立不等于必须生成一条人工任务。Planner 必须基于 pinned Process / Policy / Control 判断行动是否需要物化为 Objective，以及由人还是 Agent 执行：

```text
Situation + Goal + Process/Policy evaluation
  ├─ 无需行动                    → 不生成 Objective，记录 evaluation
  ├─ 可自动处理且已授权          → 生成或绑定 Objective → Agent 执行 → 记录 Action/Run/Evidence
  ├─ 需要人工判断/授权/现实操作   → 生成人工 Objective → Mission Feed
  └─ 自动处理异常或越界          → 暂停/升级为人工 Objective
```

物化条件至少包括：需要责任归属、改变世界状态、产生审计要求、跨系统事务、人工判断、审批或不可自动恢复的异常。纯 Agent 内部推理不得生成 Objective。

自动执行约束：

- 自动化资格必须由确定性的 Policy/Control 与 Process capability 共同判定，不能仅凭 LLM 建议。
- Agent 必须以明确 principal 执行现有 command/service，不得绕过 Objective 状态机和 Policy gate。
- 自动处理同样必须记录 actor、触发依据、pinned 规则/流程版本、输入事实、命令或工具调用摘要、状态迁移、结果、Evidence、时间和 correlation/trace id。
- 自动成功进入验证，不直接宣称 Goal satisfied；自动失败、低置信度、证据不足、越权或 kill switch 命中必须转人工接管。
- UI 的默认人工 Feed 只展示需人工介入项；Agent 自动处理记录进入 Mission 时间线/活动流，并提供“Agent 已处理”的可审计标识。
- 首期使用显式编排器调用既有 command/service；“模型动态生成任意执行拓扑”不进入当前实施范围，后续须单独通过安全与治理评审。

### 7.3 Policy composition

Quest 执行不新增一个覆盖全系统的 Policy 真相源。对象级 Quest decision facade 负责组合 Quest/Process/Control 治理判定；Agent 参与时调用 F16 行为 `PolicyEngine`；真正执行命令时仍由 command authorization 做最终强制授权。三层分别回答“业务上是否允许此目标/动作”“本次 Agent 行为是否应放行”“该 principal 是否有权调用命令”，并分别留痕。

它负责：

- who may decide
- who may execute
- what must never happen
- what requires approval
- what evidence is mandatory
- what risk is acceptable
- segregation of duties
- kill switch / hold / escalation

任何 Quest Plan 进入执行前必须通过适用的确定性 Quest 治理与 F16 行为 gate；任何实际命令还必须再次通过 command authorization。任一层拒绝即不得执行。

R2 采用 Quest decision facade：输入 Quest/Objective、目标对象、actor/Agent、风险、pinned Policy/Process 版本、Evidence 要求和当前世界状态，显式组合 Quest governance decision 与适用的 F16 `PolicyDecision`，但不复制两个规则仓库。Planner 与 Agent 只消费结构化组合结果，不各自实现授权逻辑；command authorization 仍在执行点独立求值。每一层 decision 均记录输入对象引用、规则版本、结论、理由码、有效期/revision 与 correlation id。

#### 有限确定性治理与事务执行契约

- Quest 以 `governance_mode=enforced` 显式启用确定性执行；必须处于 `executing` 且 `execution_hold=false`。未启用的历史 Quest 保留人工命令兼容性，但 Agent 不得以 legacy 模式绕过治理。启用前必须完成全部写入方迁移；启用后，Objective 状态机拒绝没有执行器签发许可的直接写入。
- `policy` / `control` / `process_pattern` 是图节点，不是旁路规则仓库。来源按完整 `semantic_ref` 精确解析，必须唯一、可读、`publication_state=published`，且 `version` 等于引用中的具体版本；`latest/head/current/*` 不可执行。已发布定义必须不可变；修订发布新版本，不能原地修改已 pin 的版本。本求值器不承担发布授权，也不自动安装企业规则。
- 定义 `schema_version=1`：Process 仅含 `schema_version, command_templates`，模板为有限注册 command，参数仅替换当前 `quest_id/objective_id`。Policy/Control 仅含 `schema_version, allowed_process_refs, risk_ceiling, min_confidence, requires_approval, allow_automatic, required_evidence_refs`；布尔、风险和置信度严格校验，未知字段或未支持的 Goal constraints / quality_refs 必须 fail closed。一个请求必须唯一匹配一个 Process 版本，任何适用 Control 均不可被其他 allow 覆盖。审批要求只产生阻断/待审批，UI 确认不等于审批通过。
- 单次求值最多 32 个 Policy、16 个 Process、每 Process 32 个模板、每 Policy 64 个证据引用；超限拒绝，不静默截断。证据必须是可读、已物化且 `verified/supported` 的 observation/fact/evidence，并以 `SUPPORTED_BY/BASED_ON_FACT` 关联当前 Quest、Objective 或 Situation。绑定关系存在不等于验证通过。
- 执行输入同时携带 Quest/Objective `state_version` 和 UI `projectionRevision`；前者用于领域乐观锁，后者仅是投影/交互游标，不能相互替代。组合结果绑定原始 Quest、Objective、主体、Agent、命令、规则版本和 correlation，不能跨请求移用。
- 只执行显式声明支持托管 DB 事务的已注册命令分支；当前支持 `look`、`task claim/start/complete`。最终仍调用 registry command authorization，Agent 使用真实 Agent Principal，不冒充人类。状态机写入要求执行点签发的一次性许可，绑定主体、Quest、Objective、命令事件、领域版本和同一事务；客户端 metadata 不能授予许可。受治理 Objective 的创建需后续已批准规划能力，不接受自由创建旁路。
- 锁顺序为账户 projection cursor（按 ID）→ Quest/Objective 节点（按 ID）→ 成员关系；执行期间锁定已读取治理来源/证据。幂等 key 在同一主体和 Objective 范围内 replay，不重复命令或审计；复用 key 改变业务请求必须冲突。动作失败、取消、超时或 kill switch 先回滚动作 savepoint，再保存失败审计；外层调用方负责 commit。
  - 选项预览与能力编译不得提前持有行锁；否则同一请求中先 SHARE 后 UPDATE 会破坏上述锁序。HTTP 预览只使用非加锁图源，执行器在完成账户/对象锁定后使用新的加锁治理源重新求值，不复用预览结论。模板仅允许普通 `{quest_id}` / `{objective_id}`，拒绝属性/下标访问、转换标记和格式规格；编译和执行共用同一渲染规则，非法模板稳定拒绝而不是返回服务器异常。
- 复用 `task_runs` / `task_events` 保存三平面决策、实际主体、执行结果与 correlation；Agent 同时写 `AgentRunRecord`，向受影响账户推进投影。执行成功仅表示 command completed，不能据此标记 Quest accepted。SQL 超时和 cooperative cancellation 有界保护 DB 动作；外部 I/O 补偿、CPU 强制抢占和任意动态执行拓扑不在该执行器承诺范围内。

### 7.4 Agent Runtime

Agent 可以：

- 提出 Situation assertion。
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

### 7.4.1 Agent 在语义世界中的学习

Agent 是 `npc_agent` 图节点，也是学习闭环中的 actor 和被配置对象：

1. Agent 观察可见世界事实，并在其 account/Agent scope 内形成 raw、episodic 与 LTM 记忆。
2. Agent 可基于 Quest Outcome、Evidence、人工反馈和历史 Case 提出 LearningProposal。
3. 经治理批准后，LearningProposal 生成新版本的 Process/SOP/Skill、能力声明或 Agent 配置引用。
4. 受控命令将批准版本关联到具体 Agent 节点（例如更新 `skill_refs` 或策略 profile revision），保留旧版本、actor、reason 与回滚信息。
5. 下一次 tick 重新加载当前有效配置和图事实；Agent 不得将一次模型输出或 LTM 条目直接提升为正式配置。

因此“每个 Agent 的设置基于学习”表示配置由可追溯学习产物演进，而不是 Agent 无审计地自我改写。学习后的能力仍须逐动作经过 Quest governance、适用的 F16 behavior policy 与最终 command authorization。

---

## 8. Invariants

| 编号 | 不变式 |
|---|---|
| QI1 | Quest 必须引用至少一个 Goal；Goal 必须声明非空 DesiredState。 |
| QI2 | Quest 所有执行型 Objective 必须有 `quest_id` 且由 `HAS_OBJECTIVE` 或等价 FK 关联。 |
| QI3 | `accepted / closed` Quest 必须至少有一个 `verification_result.status='passed'` 或明确的 human override evidence。 |
| QI4 | Policy / Quality / Process / Case / Experience 引用必须 pin 到版本；R1 使用 `namespace:key@version` enforcement；in-flight Quest 不随新版本漂移。 |
| QI5 | Hard Policy / Control 拒绝后，Planner 不得通过改写 Objective 绕过同一约束。 |
| QI6 | Quest Plan 每次重写必须记录 `plan_revision`、actor、reason、correlation_id。 |
| QI7 | Agent 内部 Action 不自动持久化为 Objective；只有改变世界状态、产生审计要求或需要人/Agent/设备认领的 Action 才升级。 |
| QI8 | LearningProposal 不能直接修改正式 Policy / SOP / QualitySpec；必须经治理审批生成新版本。 |
| QI9 | `task.current_state='done'` 不等价于 Quest accepted；Quest acceptance 以 Goal + Evidence + QualityGate 为准。 |
| QI10 | Situation confidence / severity 的自动变更必须保留 evidence 或 inference trace 摘要。 |
| QI11 | 用户的 Quest/Objective/Clue 明确选择必须通过命令写图并可审计；推荐和临时 UI focus 不得静默持久化。 |
| QI12 | LTM、对话摘要或模型推断不得覆盖图事实；使用其行动前必须重新解析并鉴权引用对象。 |
| QI13 | `ASSISTED_BY` 只表达协作，不授予执行权；实际执行 actor 必须来自命令/run 记录。 |
| QI14 | Agent 配置只能由获批学习产物通过受控命令更新；Agent 不得从对话或 LTM 直接自我修改正式配置。 |
| QI15 | 一个账户可有多个 active `TRACKS_QUEST`，但同一 account+Quest 不得重复；全账户至多一个 active `FOCUSES_ON`，且其 Objective 必须属于某个已追踪 Quest。 |
| QI16 | World Interaction revision 由服务端按账户单调推进；过期 mutation 不得自动重放或产生副作用。 |
| QI17 | Quest 治理、F16 行为策略和 command authorization 保持独立规则真源；组合 facade 不得把任一层的 allow 当作绕过其他层的授权。 |

---

## 9. 数据模型落地建议

### 9.1 Phase-compatible 最小增量

所有核心对象都在 CampusWorld 语义世界内建模；R1 与 R2+ 的区别是**节点类型物化进度**，不是对象归属边界。

R1 图节点完整性契约：

- `Situation / Goal / Quest` 必须是 `nodes` 实例，分别使用 `type_code='situation' / 'goal' / 'quest'`，并在 `node_types.schema_definition.properties` 注册 service 写入的全部 attributes。
- `Situation / Goal / Quest` 创建时必须写 `OWNED_BY semantic_node -> actor`（system actor 例外），attributes 中的 `actor_provenance/created_by` 只是审计摘要，不替代图边。
- R1 创建下游语义节点时必须校验调用者可读上游节点：`goal create` 要求 actor 可读对应 Situation，`quest create` 要求 actor 可读对应 Situation 与 Goal；`task.admin` 与 system 可跨 owner 读取。
- `Objective` 必须是 `nodes.type_code='task'`，通过 `HAS_OBJECTIVE quest -> task` 与 `task.attributes.quest_id` 双向可审计关联。
- 核心语义连接必须优先表达为 `relationships` 边：`ABOUT / RAISES_GOAL / GOAL_FOR / RESPONDS_TO / PURSUES / HAS_OBJECTIVE / OWNED_BY / SCOPED_AT`。不得只在 attributes 中保存主链路而不写边。
- 用户与协作语义使用 `TRACKS_QUEST / FOCUSES_ON / PINS_CLUE / ASSISTED_BY`；关系变更必须携带 actor、时间与 correlation metadata。一个账户可追踪多个 Quest，`FOCUSES_ON` 仍是账户唯一前台焦点。`PINS_CLUE` 仅在事实/观测/证据目标节点已物化且可读时创建。
- R1 物化最小 canonical `observation`：原始 assertion、source/provenance、`observed_at`、actor 和初始 `verification_status='unverified'` 必须可审计，后续验证不得覆写原始观察。尚未物化的 `Fact / Evidence / Policy / Control / QualitySpec / ProcessPattern / Case` 可先以 pinned semantic ref 保存在 attributes；当目标节点类型存在且 ref 可解析时，semantic ref resolver 应补写对应语义边，如 `BASED_ON_FACT / SUPPORTED_BY / TRIGGERED_BY_RULE / TRIGGERED_BY_EXPERIENCE / GOVERNED_BY / GUIDED_BY / MEASURED_BY / INFORMED_BY`。
- `node_types.trait_class` 与 `relationship_types.trait_class` 必须为 `TASK`，实例写入依赖图层 trait 同步机制继承检索语义；按 TASK trait 检索时必须同时按 `type_code` 缩小范围，避免把 semantic shell 节点误当作可分派 task。

| 对象 | 语义世界归属 | R1 持久化方式 | 目标形态 |
|---|---|---|---|
| `Situation` | 是 | `nodes.type_code='situation'` | graph node |
| `Observation` | 是 | `nodes.type_code='observation'`，保留原始来源且初始未验证 | graph node；R3 由 Evidence/verification 评价 |
| `Goal` | 是 | `nodes.type_code='goal'` | graph node |
| `Quest` | 是 | `nodes.type_code='quest'` | graph node |
| `Objective` | 是 | 复用 `nodes.type_code='task'` | 继续复用 task，或长期迁移为独立 objective node |
| `Action` | 是 | `task_runs.command_trace` / Agent run / external transaction ref；必要时未来进入 `quest_action_records` | action record 或 graph node，由审计等级决定 |
| `Evidence` | 是 | `fact_refs` / `evidence_refs` 语义引用 | `evidence` / `evidence_record` node 或专用记录 |
| `Outcome` | 是 | `outcome_summary` / 未来记录 | `outcome` node 或专用记录 |
| `Learning` | 是 | 未来 `learning_proposals` | `improvement_proposal` / `lesson` node |
| `Policy / Control / QualitySpec / ProcessPattern / Case` | 是 | `rule_refs` / `policy_refs` / `process_refs` / `quality_refs` / `case_refs` 语义引用 | graph node + versioned artifact |

R1 本轮新增并注册的节点类型：

- `situation`
- `observation`
- `goal`
- `quest`

R2+ 再补齐语义世界节点类型：

- `evidence`
- `outcome`
- `process_pattern`
- `quality_spec`
- `policy`
- `case`
- `improvement_proposal`

优先新增关系：

- `ABOUT`
- `BASED_ON_FACT`
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
- `REALIZED_BY`
- `GOVERNED_BY`
- `GUIDED_BY`
- `MEASURED_BY`
- `INFORMED_BY`
- `PRODUCED`
- `TRACKS_QUEST`
- `FOCUSES_ON`
- `PINS_CLUE`
- `ASSISTED_BY`

其中 `BASED_ON_FACT / SUPPORTED_BY / TRIGGERED_BY_RULE / TRIGGERED_BY_EXPERIENCE / GOVERNED_BY / GUIDED_BY / MEASURED_BY / INFORMED_BY` 在 R1 由 semantic ref resolver 在目标节点已存在时补边；`REALIZED_BY` 是 `Goal -> Quest` 结构性反向边，R1 在创建 Quest 时直接写入；`PRODUCED` 在 R1 仅注册关系类型，证据、结果和学习产物的生成由 R2+ 启用。

Semantic ref resolver 的 R1 解析顺序：

1. 显式节点引用：`123` / `node:123` / `#123`。
2. 精确属性引用：`semantic_ref` / `ref` / `source_ref` / `external_ref` 等于完整 ref。
3. `key/code + version` 候选；带 namespace 的 ref 必须匹配目标 `type_code` 或精确属性引用，不得退化为任意同名 key。
4. 多候选或未解析时保留原始 ref 字符串，不阻断创建，并写 debug 日志用于审计排查。

继续复用现有关系表：

- `task_assignments` 用于 Objective 分派。
- `task_state_transitions` 用于 Objective 状态。
- `task_runs` 用于 Objective/Action 执行轨迹。
- `task_outbox` 用于 Objective 事件。

R1 不新增 Quest 生命周期专用表；允许新增共享投影并发基础设施：账户级 `world_interaction_revisions`（或等价单调版本存储）必须在影响可见投影的事务中推进。G3/R2 可新增 `situation_attention`，以 account+Situation 唯一键保存高频 seen/snooze/UI-dismiss 状态；它不是 Situation 业务状态或图事实真源。

R2+ 关系表建议：

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

R1 新增 `observation` / `situation` / `goal` / `quest` 轻量命令族，`task` 命令族保持兼容。改变用户 Quest 选择投影的交互 mutation（`track / untrack / focus-objective / pin-clue / unpin-clue / set-collaborator / remove-collaborator`）必须接受 expected revision 与 idempotency key，并返回新 revision/event id。创建 Observation、Situation、Goal、Quest 的语义命令不属于该交互 mutation envelope；若其结果影响账户可见投影，适配层仍须推进对应投影 revision。

| 命令 | 行为 |
|---|---|
| `observation record --assertion <A> --source-ref <R> --observed-at <T> [--subject <node_id>]` | 创建 canonical Observation；保留 actor/provenance，初始 `verification_status=unverified`，后续验证不得覆写 assertion/source |
| `situation create --title <T> --assertion <A> [--subject <node_id>] [--trigger-kind hard_rule\|weak_experience\|manual\|mixed] [--fact-ref <R>] [--evidence-ref <R>] [--rule-ref <R>] [--experience-ref <E>] [--confidence <0..1>] [--severity low\|medium\|high\|critical]` | 创建 declarative Situation assertion；`rule-ref / experience-ref` 使用 `namespace:key@version` |
| `situation list [--limit N]` | 列出 Situation |
| `situation show <id>` | 展示 assertion 与 trigger provenance |
| `goal create --title <T> --situation <id> --desired-state <state> [--priority low\|normal\|high\|urgent]` | 从 Situation 创建 Goal；R1 命令层 `desired-state` 为 string |
| `goal list [--limit N]` | 列出 Goal |
| `goal show <id>` | 展示 Goal |
| `quest create --situation <id> --goal <id> --title <T> [--policy-ref <R>] [--process-ref <R>] [--quality-ref <R>] [--case-ref <R>] [--plan-graph-summary <S>]` | 创建 Quest draft；治理/经验 ref 使用 `namespace:key@version`，R1 命令层计划摘要为 string |
| `quest list [--limit N]` | 列出 Quest |
| `quest show <id>` | R1 展示 Situation / Goal / Objectives / Evidence refs / Progress；完整 Evidence 节点视图留 R2+ |
| `quest track <id> --if-revision <R>` | 幂等增加该 account+Quest 的 active `TRACKS_QUEST`，不替换其他追踪 |
| `quest untrack <id> --if-revision <R>` | 仅失活指定 Quest 的 tracking；若它包含当前 focus，同时清理失效 focus 并在同一事务推进 revision |
| `quest focus-objective <quest_id> <task_id> --if-revision <R>` | 校验 Quest 已追踪及 `HAS_OBJECTIVE` 后替换账户唯一 `FOCUSES_ON`；不改变 Objective lifecycle |
| `quest pin-clue <quest_id> <node_id> --if-revision <R>` | 对可读、已物化 observation/fact/evidence 幂等创建 `PINS_CLUE` |
| `quest unpin-clue <quest_id> <node_id> --if-revision <R>` | 失活调用者对应 Clue pin，不修改目标事实 |

交互 mutation 的幂等 key 必须绑定 action、目标与规范化 payload 指纹；同 key 不同请求返回冲突。未改变任何关系的 no-op 返回 `changed=false`，且不得推进账户投影 revision。

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

R1 `task show` 展示 `evidence_requirement_refs`，`quality_gate_status` 标注为 `R2+`；完整 Evidence / QualityGate 节点视图由 R2+ `quest verify` 接入。

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
  "policy_refs": ["policy:maintenance_safety@3.2", "policy:loto_control@2.1"],
  "process_refs": ["process:bearing_degradation_response@4.2"],
  "quality_refs": ["quality:rotating_equipment_post_maintenance@2.4"],
  "case_refs": ["case:AHU-103-2026Q2@1"],
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
- World UI 对 `claimed` 任务生成已实现的 `task start` 动作，对 `in_progress / approved` 任务生成 `task complete`。
- 保持 `task` Phase B/C 测试绿色。

### R1 — Semantic Shell

目标：新增 Observation / Situation / Goal / Quest 节点、受限 Quest 关系图与用户选择/协作边，不改变 task 状态热路径。

- 注册节点类型与关系。
- 新增 `quest show/list`、`situation show/list`、`goal show/list`。
- `task` 增加可选 `quest_id`。
- World UI 展示 Mission Card，但执行仍走现有 `task` 命令。
- `quest track/untrack` 维护可并存的多个 `TRACKS_QUEST`，取消指定 Quest 不影响其他追踪；`quest focus-objective` 维护账户唯一 `FOCUSES_ON`。它们是可审计的业务上下文命令，但不得隐式 claim/start/complete Objective。
- 最小 `observation` 节点保存不可被后续验证覆写的 assertion 与 provenance，供 R1 `PINS_CLUE` 使用；完整 Evidence/verification 留在 R3。
- Quest Journal 返回权限过滤后的 Situation、Goal、Objective、可解析事实/证据与协作 Agent 子图；Action/Run/Outcome 审计记录作为时间线叠加，只有按领域契约物化后才进入图。未物化 ref 以只读 unresolved leaf 降级。
- Quest 对话归档保留 Quest/Agent/thread 图引用，作为后续 episodic/LTM 晋升输入。

### R2 — Governed Planning

目标：Quest Plan 由 Policy / Process / Quality / Case 约束。

- 新增 `quest_plan_revisions`。
- 新增 deterministic policy gate。
- 新增组合 Quest governance、F16 behavior policy 与最终 command authorization 的 decision facade，并用显式 orchestrator 执行已注册 command/process capability；全动态执行图延后。
- 引入 `required_capabilities` 到 Objective。
- 将 `task_pools` 查询扩展为 capability-aware candidate pool。

### R3 — Evidence-based Verification

目标：从“点击完成”升级为证据验收。

- 新增 evidence / quality / verification 表。
- Evidence/verification 对 Observation 做支持、反驳或失效评价，不修改原始 assertion/provenance。
- `quest verify` 基于 evidence 判断 Goal。
- `quest accept` 要求 verification passed 或 human override。

### R4 — Learning Loop

目标：让 Quest Outcome 回流为组织经验。

- 新增 Case / Lesson / ImprovementProposal。
- Quest close 后生成 outcome。
- LearningProposal 必须人工/治理审核后才能生成新 Process / SOP / QualitySpec 版本。
- 获批 LearningProposal 可通过受控命令更新 Agent 的 `skill_refs`、能力或 policy profile revision；禁止 Agent 直接自改节点配置。

---

## 13. Acceptance

### 文档级

- [x] `Situation / Goal / Quest / Objective / Action / Evidence / Outcome / Learning` 边界经评审通过。
- [x] 明确 `task` 保留为 Objective/Actionable Work Item，Quest 为新行动聚合根。
- [x] 明确 Process 是企业行动知识，不等价于 Runtime Workflow。
- [x] 明确 Policy / Control / QualityCriterion 为硬约束，ProcessPattern / SOP / Case 为可偏离的弱经验。
- [x] 明确 Evidence-based Completion：Quest acceptance 不等于 task done。
- [x] 明确 Agent 不能绕过 Quest governance、F16 behavior gate 或 command authorization，也不能直接修改正式知识版本。

### 实现级 R0

- [x] `task_state_machine.transition()` 全写路径单事务覆盖。
- [x] `task create --scoped-at` 落 `SCOPED_AT`；owner 关系/assignment 可审计。
- [x] World UI 不再指向未实现的 `task start`，且 `start` 已实现。
- [x] Phase B/C 现有测试仍通过。

### 实现级 R1

以下实现项已落地；PostgreSQL 端到端验收单独跟踪，未通过前不得将 F03 G1 标记为验收完成。

- [x] `situation / goal / quest` 节点类型注册。
- [x] 关系 `RESPONDS_TO / PURSUES / HAS_OBJECTIVE` 可创建和查询。
- [x] `task.attributes.quest_id` 与 Quest objective rollup 一致。
- [x] `quest show` 能展示 situation、goal、objectives、progress。
- [x] `observation` 节点及 provenance 契约可创建、读取并作为 `PINS_CLUE` 目标（服务/命令测试通过）。
- [x] 多个 `TRACKS_QUEST` 可并存，通过账户 revision 行锁与服务检查防止 account+Quest 重复 active 边；`FOCUSES_ON` 全账户唯一并校验 Objective 属于已追踪 Quest（服务测试及数据库约束定义检查通过；数据库端到端验收另列）。
- [x] `ASSISTED_BY` 多 Agent 关系、账户级 projection revision 与权限过滤 Journal 子图已实现并有针对性测试。
- [ ] PostgreSQL 端到端验收：运行 `backend/tests/integration/test_quest_interaction_runtime.py`，验证 graph mutation、权限过滤、协作与投影。

### 实现级 R2-R4

- [ ] Policy gate 拒绝路径可审计，且 Agent 无法通过 replan 绕过同一 hard constraint。
- [ ] Quest plan revision 单调，含 actor、reason、correlation_id。
- [ ] Evidence requirement 与 verification result 可查询。
- [ ] Quest accepted 需要 verification passed 或 human override evidence。
- [ ] LearningProposal 不直接修改正式 Process / SOP / Policy / QualitySpec。

---

## 14. Open Questions

已定边界：Quest decision facade 组合 Quest governance 与适用的 F16 行为决策，实际命令继续由现有 command authorization 做最终强制检查；三者保留独立规则真源和审计记录。

首个验证场景使用隔离的只读规则/流程 fixture 和已有注册能力，不向生产发布虚构企业规则。组合结果的通过仅表示 `ready_for_command_authorization`，不是执行授权。有限图源求值、UI choice 调用与持久化审计已进入实现；真实 Agent worker、完整规划/生命周期、发布治理和数据库验收仍以执行清单为准，不据此关闭 R2 整体验收。

已定投影：Mission Feed 继续由现有 WorldInteraction state 聚合 Quest interaction projection，不新增并行的 Quest-specific 前端状态真源。

1. `Objective` 是否长期复用 `task`，还是在 R2 后引入独立 `objective` 节点类型？
2. QualitySpec 应作为 graph node，还是版本化关系表？
3. Case / Experience 是否归入 CampusLibrary / Knowledge World，还是 Task module 自管？
4. Quest plan graph 是否需要独立 DSL，还是复用 workflow_definition spec 的子集？
5. 外部系统 transaction envelope 的统一 ref schema 如何定义？
