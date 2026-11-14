# F03 — AI-native Quest 世界交互规格

> **Architecture Role：** 定义 CampusWorld 中由世界感知、企业规范和组织经验驱动的人工工作界面。该界面不是传统工单 Inbox，而是 `Situation → Goal → Quest → Objective → Evidence → Outcome → Learning` 闭环的人机协作投影。
>
> **依赖：** [`task F06`](../../../task/SPEC/features/F06_AI_NATIVE_QUEST_RUNTIME_REFACTOR.md)、[`Agent F09`](../../../models/SPEC/features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)、[`Memory F12`](../../../models/SPEC/features/F12_NLP_AGENT_MULTI_TURN_SESSION_MEMORY.md)、[`Frontend SPEC`](../SPEC.md)、[`CampusWorld Next UI`](F01_CAMPUSWORLD_NextUI.md)。

**文档状态：Approved for Implementation（G0 契约已确认；待 G1–G4 实现验收后转 Active）**

交付映射：实施计划 Phase 1 对应 Task Runtime R1 semantic shell；Phase 2–3 中的 governed planning、三平面策略组合和显式自动执行对应 R2；Evidence verification 对应 R3；LearningProposal 发布闭环对应 R4。G0–G4 是跨前后端验收门禁，不是另一套 runtime release 编号。

## 1. 产品判断

传统工作台默认“任务已由流程生成，人只需处理队列”。CampusWorld 的工作来自持续存在的语义世界：Agent 和规则观察世界事实，结合企业规范、流程知识与历史案例形成 Situation；系统提出 Goal 和 Quest；流程和规则决定是否物化 Objective。可被授权自动处理的工作由 Agent 执行，需要人工判断、授权、现实操作或异常接管的工作才进入人工 Feed。

因此 `/works` 的一级对象是 Mission、Situation 与 Decision，而不是待办数量、项目数量或手工新增任务。

```text
World observation
  → Situation assertion（发生了什么、依据是什么）
  → Goal（希望世界变成什么样）
  → Quest / Mission（受治理的行动闭环）
  → Objective（当前需要人推进的目标片段）
  → Evidence / Outcome（如何证明有效）
  → Learning proposal（组织学到了什么）
```

## 2. 设计原则

1. **世界优先。** 每张人工工作卡必须能回溯到 Situation 或明确标识为人工创建。
2. **目标优先。** 主标题展示 Quest；Objective 是当前可行动片段，不能反客为主。
3. **可解释触发。** 展示 hard rule、weak experience、mixed 或 manual，以及置信度和证据来源。
4. **治理可见。** 风险、Policy、Process、QualitySpec 和审批约束在行动前可见。
5. **渐进披露。** 首屏回答“为什么、目标、下一步”；证据和引用按需展开。
6. **完成不等于验收。** Objective 完成后进入验证语义；界面不得暗示整个 Quest 或 Goal 已达成。
7. **命令统一。** 所有动作仍通过 protocol-neutral command/service 执行，前端不复制业务状态机。
8. **事实与记忆分层。** 世界图保存可验证事实与用户明确选择；STM/LTM 保存对话连续性、情境摘要和可检索经验，不能覆盖世界事实。

### 2.1 游戏体验范式

CampusWorld 采用企业语义世界中的游戏体验范式，而不是给传统工作台增加游戏皮肤：

```text
World Pulse（世界发生变化）
  → Discover（发现 Situation）
  → Track Quest（选择当前关注目标）
  → Meet Companion（与场景 Agent/NPC 交流）
  → Act in World（在地图、实体或命令上行动）
  → World Feedback（世界状态、证据与影响即时反馈）
  → Journal（保留行动与学习记录）
```

| 游戏体验模式 | CampusWorld 对应 | 不采用的传统企业模式 |
|---|---|---|
| 世界事件 / environmental storytelling | Situation 在 Map 与 World Pulse 中出现 | 告警表格、消息中心红点堆积 |
| Tracked Quest HUD | 当前 Quest + 单一 Objective + 下一步线索 | KPI Dashboard、四宫格统计卡 |
| Quest Journal | Quest 图、已发现线索、行动与结果历史 | 工单详情页、字段密集表单 |
| NPC / Companion dialogue | Quest 内 Agent 解释、提示、提问与有限行动 | 独立万能 Chatbot |
| Map marker / route | `subjectRef`、影响范围和行动地点 | 从列表跳转业务详情页 |
| Diegetic prompt | 在实体、地点、Agent 附近出现可行动提示 | 固定工具栏塞满操作按钮 |
| Choice + consequence | DecisionOption 明示风险、依据和世界影响 | “提交/审批/驳回”作为主要体验 |
| Quest update feedback | Objective、Evidence、World State 的变化反馈 | 成功 toast 后回到列表 |

企业级不意味着传统企业 UI。权限、审计、流程、规则和证据仍是底层硬约束，但前台只在它们影响当前选择时呈现为门槛、风险、所需线索或后果。

### 2.2 明确禁止的界面回退

- 不以 Inbox、Kanban、工单表格或统计 Dashboard 作为 `/works` 主入口。
- 不以“新建任务”作为默认工作起点；工作从世界变化和规则/流程判断产生。
- 不把所有字段一次性铺开；玩家式渐进披露顺序是“发生了什么 → 当前目标 → 可做什么 → 为什么”。
- 不使用积分、徽章、排行榜、连续签到等浅层游戏化替代真实业务结果。
- 不让独立 AI 助手覆盖 Quest、地图和场景 Agent；交互必须锚定世界对象和当前 Quest。
- 不把自动化处理隐藏掉；Agent 行动以世界反馈和 Journal 记录呈现，而不是后台作业列表。

### 2.3 业界模式依据

- Epic 的官方 Conversations and Quests 示例使用 Quest Manager 管理目标推进、Tracker 只展示当前 Objective，并由不同 NPC Conversation 推进任务；CampusWorld 对应采用 Quest Runtime + Tracked Quest + 场景 Agent。
- Apple 游戏设计指南强调让用户尽快进入体验、针对设备采用自然输入，并保持文本在不同屏幕可读；CampusWorld 保持 Focus 首屏、键鼠/触控一致操作与响应式 HUD。
- Xbox Accessibility Guidelines 将 quest objective、地图、提示和通知视为核心 HUD 信息，并要求强对比及非颜色单通道表达；CampusWorld 的风险、选择和地图热点必须同时提供文本/形状语义。

参考：

- [Epic Games — Conversations and Quests](https://dev.epicgames.com/documentation/fortnite/star-wars-conversations-and-quests-in-fortnite)
- [Apple — Designing for games](https://developer.apple.com/design/human-interface-guidelines/designing-for-games)
- [Xbox Accessibility Guidelines — Contrast](https://learn.microsoft.com/en-us/xbox/accessibility/xbox-accessibility-guidelines/102)
- [Xbox Accessibility Guidelines — Screen narration](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/106)

## 3. 信息架构

| 区域 | 一级内容 | 用户问题 |
|---|---|---|
| Situation Feed | assertion、severity、confidence、trigger provenance、影响范围 | 世界发生了什么，为什么值得关注？ |
| Mission Card | Quest state、risk、Goal、总体进度、治理依据 | 系统正在追求什么结果？ |
| Objective Focus | 当前 Objective、责任、下一步行动、阻塞项 | 此刻需要我做什么？ |
| Evidence Drawer | fact/evidence、质量要求、验证状态、时间窗口 | 凭什么判断，如何证明完成？ |
| Learning Review | outcome、case 对照、改进提案 | 结果怎样，企业应学到什么？ |
| Mission Timeline | 人工与 Agent 的 Action/Run/Evidence 记录 | 谁在何时依据什么处理了什么？ |
| AICO Conversation | 解释、检索、方案比较、命令入口 | 我能否追问、质疑或请求重规划？ |

用户可见命名采用游戏世界语言：顶层历史入口为 `World Journal / 世界日志`，其中选中 Quest 的局部关系图和时间线为 `Quest Journal / 任务日志`；其余术语为 `World Pulse / 世界脉动`、`Tracked Quest / 追踪中的 Quest`、`Companion Agent / 同行 Agent`、`Clue / 线索`、`World Feedback / 世界反馈`。Policy、Evidence、Objective 等精确术语可在展开层保留，避免牺牲审计语义。

R1 在现有 Decision Center 上落地紧凑 HUD，同时提供只读 Quest 关系图 Journal，并物化最小 `observation` 节点以承载可 pin 的事实声明；Evidence Drawer 与验证状态演进在 R3 启用，Learning Review 发布闭环在 R4 启用。缺失字段应隐藏，不得用虚构数据填充。Journal 中尚未物化的 pinned semantic ref 可以作为“未解析引用”叶节点展示，但不得伪装成已验证图事实。

### 3.1 与语义地图、关键信息栏的一致性

`/works` 的 Map、Mission/Decision、Context Summary 是同一 World Interaction read model 的三个投影，不是三套独立工作台：

| 共享语义 | Map | Mission / Decision | Context Summary |
|---|---|---|---|
| 当前权威位置 | `focus_map.currentSpaceId` | 行动发生环境 | `currentSpace` |
| 当前语义焦点 | `selectedEntityId / selectedInspect` | Situation `subjectRef` 关联高亮 | 地图当前焦点摘要 |
| 待处理情况 | event hotspot / `activeEventIds` | Situation Feed | `pendingDecisionCount` |
| 当前行动闭环 | route/event overlay | Quest + Objective | 当前 Mission/Objective 紧凑摘要 |
| Agent | map presence | executor / observer / proposer | nearby/highlighted Agent |

一致性规则：

- 当前空间只以 account `location_id` 的后端聚合结果为权威；三栏不得各自推断位置。
- 地图选中只是交互焦点，不改变 `location_id`，也不自动执行 `go`。
- Situation 主体使用 graph node `subjectRef`；Mission 卡不得以名称字符串猜测地图实体。
- Objective、Quest 和地图热点的状态来自同一轮 interaction state 或带版本的 state patch；前端不得分别修改业务状态。
- 当实体不在当前地图层可见时，定位操作可切换/钻取视图，但不得伪造节点；定位失败保留 Mission 上下文并允许用户查看引用。

### 3.2 双向联动

```text
Mission/Situation "在地图中定位"
  → Map mode
  → semantic-map select(subjectRef)
  → selectedInspect
  → 地图高亮 + inspect sheet + 右侧“地图当前焦点”

Map select(entity)
  → selectedInspect
  → Context Summary 同步实体摘要
  → subjectRef 相同的 Mission/Situation 显示关联高亮
```

联动必须是显式选择或只读聚焦，不得因浏览地图自动 claim/start/complete Objective。用户清除地图选择时，右侧实体焦点和 Mission 关联高亮同时消失，但 Quest/Objective 本身不受影响。

### 3.3 用户场景选择、事实图谱与 Memory

“场景选择”不新增含义模糊的 `scenario` 业务对象，而是复用已经明确的 Situation、Quest、Objective 和 Clue 语义。用户主动选择与事实之间的目标关系如下：

```text
account --TRACKS_QUEST--> quest --RESPONDS_TO--> situation
   +--FOCUSES_ON--------> objective
   +--PINS_CLUE---------> fact/observation/evidence

situation --BASED_ON_FACT--> fact/observation

quest --ASSISTED_BY--> npc_agent
conversation/LTM --graph_node_id/relationship_id--> 上述可见图对象
```

持久化边界：

- `TRACKS_QUEST account -> quest` 表示用户明确加入追踪列表的行动场景；同一账户可以同时追踪多个 Quest，系统推荐不得静默写入该边，也不得因追踪另一个 Quest 自动取消已有追踪。
- `FOCUSES_ON account -> task/objective` 表示多个已追踪 Quest 中唯一的前台行动焦点。它由 `quest focus-objective` 命令替换并审计，其目标必须属于某个已追踪 Quest；该关系决定 HUD 当前 Quest，但不改变 Objective 生命周期、不等价于 claim/start。
- `PINS_CLUE account -> fact/observation/evidence` 表示用户明确保留的事实线索；只有目标已经物化为可读图节点时才能创建。R1 至少支持规范化 `observation` 节点，保存 assertion、source/provenance、observed_at、actor 与初始 `verification_status='unverified'`；后续 Evidence 验证不得覆写原始观察。尚未物化的 semantic ref 只能作为只读引用展示。当前 Quest 的候选 Observation 限于关联 Situation、主体、可见相关实体或范围位置的观察，以及该 Quest 已 pin 的观察，不扫描全局观察图。
- 地图 hover、临时 inspect、面板开合仍属于 UI session state，不写入业务图；account `location_id` 始终是当前位置唯一权威。
- Quest Journal 读取上述边及 `RESPONDS_TO / PURSUES / HAS_OBJECTIVE / BASED_ON_FACT / SUPPORTED_BY / SCOPED_AT / ASSISTED_BY`，形成当前用户可见的受限子图，不遍历全局世界图。

Memory 与世界图采用引用式协作：Quest 对话及操作片段先进入按用户与 Agent 隔离的 STM/raw/episodic 路径；完成、归档或 compaction 后才可异步晋升到 LTM。LTM 可通过 `graph_node_id / relationship_id` 指回 Quest、Situation、事实或用户选择边，但摘要、向量命中和模型推断都不是事实 SSOT。事实详情必须重新按当前权限读取世界图。

### 3.4 World Interaction 契约与并发

稳定响应契约为 `quest-interaction.v1`。后端必须显式返回 `contractVersion`、`capabilities`、账户级 `projectionRevision` 和 `lastEventId`；前端不得从字段是否存在推断能力。核心结构如下：

```typescript
interface QuestInteractionStatePayload {
  contractVersion: 'quest-interaction.v1'
  capabilities: QuestInteractionCapability[]
  projectionRevision: string
  lastEventId?: string
  trackedQuests: TrackedQuestSummary[]
  foregroundQuestId?: string
  questJournal?: { nodes: JournalNode[]; edges: JournalEdge[]; unresolvedRefs: UnresolvedRef[] }
  worldPulse?: WorldPulseItem[]
  worldFeedback?: WorldFeedbackItem[]
}

type QuestInteractionCapability =
  | 'multi_quest_tracking'
  | 'durable_focus'
  | 'observation_clues'
  | 'quest_graph'
  | 'situation_attention'
  | 'structured_conversation'
  | 'world_feedback'

interface TrackedQuestSummary {
  id: string
  title: string
  state: string
  riskLevel: string
  tracking: 'explicit'
  focusedObjectiveId?: string
  recommendedObjectiveId?: string
  situation?: { id: string; assertion: string; triggerKind?: string; confidence?: number; severity?: string; primarySubjectRef?: string; relatedEntityRefs?: string[]; scopedAtRef?: string }
  goal?: { id: string; desiredState: string }
  objectives: Array<{ id: string; title: string; state: string }>
  clues: Array<{ id: string; title: string; assertion: string; verificationStatus: string; sourceRef?: string; observedAt?: string; pinned: boolean }>
  companion?: { id: string; name: string; role: string; isPrimary: true } | null
  companionFallback?: 'aico' | null
  progress: { total_objectives: number; terminal_objectives: number; completed_objectives: number; percent: number; success_percent: number }
}

interface JournalNode { id: string; type: string; label: string; verificationStatus?: string }
interface JournalEdge { id: string; type: string; sourceId: string; targetId: string }
interface UnresolvedRef { ref: string; expectedType?: string; reason: 'not_materialized' | 'not_visible' | 'not_found' }

interface WorldPulseItem {
  id: string
  situationId: string
  severity: string
  assertion: string
  attention: 'new' | 'seen' | 'snoozed' | 'ui_dismissed'
  snoozedUntil?: string
}

interface WorldFeedbackItem {
  id: string
  questId: string
  objectiveId?: string
  actorKind: 'human' | 'agent' | 'system'
  actorId?: string
  status: 'succeeded' | 'failed' | 'blocked' | 'escalated'
  summary: string
  correlationId: string
  occurredAt: string
}

interface QuestMutationEnvelope<T> {
  expectedProjectionRevision: string
  lastEventId?: string
  idempotencyKey: string
  payload: T
}
```

契约规则：

- `trackedQuests` 是显式追踪集合；`foregroundQuestId` 由唯一 `FOCUSES_ON` 所属 Quest 决定。没有焦点时可用最近一次显式追踪作为只读展示默认，但不得创建或改写关系。
- `projectionRevision` 是服务端签发的账户级单调 World Interaction 版本；任何会改变该账户权威位置/Map 语义、可见 Quest、Journal、Pulse、Feedback、协作或对话绑定的成功事务都必须推进它。`lastEventId` 是该投影已包含的最后可见领域事件游标。
- 所有状态变更请求统一携带 `{ expectedProjectionRevision, lastEventId?, idempotencyKey }`。版本过期返回结构化 `stale_projection` 和最新版本提示；服务端不得自动重放有副作用的动作。
- 同一 account 下重复使用 `idempotencyKey` 时，只有 action、目标与规范化 payload 指纹完全一致才可 replay；同 key 不同请求必须返回结构化 `idempotency_conflict`，不得把旧成功结果用于新动作。
- 未产生权威投影变化的幂等 no-op 返回 `changed=false` 且不推进 `projectionRevision`；如需审计“尝试过但无变化”，应使用独立 attempt audit，不得伪造投影版本变化。
- 客户端忽略未知 capability；缺失 capability 时隐藏对应写操作并保留降级读取。未知 major contract version 必须回退到遗留 `activeTask` 路径或显示不支持状态，不得猜测字段语义。
- 旧字段在首个兼容发布周期内继续返回；新实现以 `trackedQuests` 为权威 read projection，不把前端缓存作为业务状态。

## 4. Mission Card 契约

Mission Card 表示 `foregroundQuestId` 指向的 Quest；其他已追踪 Quest 保留在 World Pulse/World Journal 的追踪集合中，不同时争夺 HUD。Mission Card 的最小展示顺序：

1. `questTitle`、Quest state、risk level。
2. Situation assertion、trigger kind、confidence。
3. Goal desired state。
4. Quest 派生进度；该值只作 read projection，不是权威状态。
5. 当前 Objective 标题、状态与下一步命令。
6. governance/process/quality 引用计数；展开后显示 pinned refs。

`TaskCard.questContext` 是前端 read model，不新增业务 SSOT：

```typescript
interface QuestContext {
  state: string
  riskLevel: string
  situation: { assertion: string; triggerKind: string; confidence?: number; severity: string; subjectRef?: string; relatedEntityRefs?: string[]; scopedAtRef?: string } | null
  goal: { desiredState: string } | null
  governanceRefs: string[]
  processRefs: string[]
  qualityRefs: string[]
  caseRefs: string[]
  companion?: { id: string; name: string; role: string; isPrimary: true } | null
  companionFallback?: 'aico' | null
}
```

无 `questId` 的兼容任务可继续显示 Objective 卡，但必须保持为降级体验，不应伪装成 Quest。

## 5. 行动语义

### 5.1 场景与 Objective 聚焦

企业实践中的“订阅/关注当前案件”和游戏中的“追踪 Quest/选择当前 Objective”都具有跨设备连续性、责任上下文和审计价值，因此 Quest 追踪与 Objective 聚焦属于轻量业务状态，而不是纯本地 UI 状态：

- `quest track <quest_id>` 增加一个 `TRACKS_QUEST`，`quest untrack <quest_id>` 只取消指定 Quest 且不替换其他追踪关系；若被取消 Quest 包含当前 focus，必须在同一事务清理该失效 `FOCUSES_ON`。`quest focus-objective` 替换账户唯一的 `FOCUSES_ON`。
- 命令必须校验调用者、Quest 可见性、Objective 的 `HAS_OBJECTIVE` 成员关系，以及聚焦目标是否仍有效。
- 成功写入选择边及 tracking/focus event；并发更新使用服务端 revision 做乐观控制。
- 聚焦只影响 HUD、Journal 默认展开和 Companion 上下文；不得自动认领、启动、完成或批准 Objective。
- 单纯地图选择继续使用临时 UI focus，避免把探索行为误记为业务承诺。

### 5.2 Objective 状态动作

| Objective 状态 | 主动作 | UI 语义 |
|---|---|---|
| `open` + pool | `task claim` | 接受责任，不代表开始执行 |
| `claimed` | `task start` | 开始当前 Objective |
| `in_progress / approved` | `task complete` | 提交 Objective 完成，不代表 Quest 验收 |
| 其他 | `task show` | 查看详情，不猜测非法迁移 |

高风险 Quest、弱经验触发的高影响 Situation 或缺少强制证据时，UI 必须优先呈现审批/补证/质疑操作；不得把“Agent 推荐”渲染为已获授权。

## 6. 人工与 Agent 协作

- Agent 可以提出 Situation、Goal、Plan、Objective 和 LearningProposal。
- Policy/Process 判定可自动执行时，Agent 可认领并完成 Objective，但必须留下 actor、规则/流程版本、Action/Run、Evidence 与结果记录。
- 人可以确认/驳回 Situation、修改目标约束、批准高风险行动、执行现实动作、提交 Evidence、要求重规划。
- UI 必须区分“观察事实”“Agent 推断”“企业强规则”和“人工决定”。
- 不展示完整 chain-of-thought；只展示可审计的 inference summary、引用和决策理由。
- AICO 回答不得代替确定性 Policy gate；命令执行后的状态必须重新从后端聚合。
- 人工 Feed 默认排除无需介入的自动执行项；自动成功、失败和升级记录在 Mission Timeline 中，分别标识“Agent 已处理”“Agent 处理失败”“等待人工接管”。
- Quest decision facade 是对象级治理组合入口，但不是新的万能授权引擎：它组合 Quest/Process/Control 判定与 F16 Agent 行为 `PolicyEngine` 的结构化结果；具体命令仍由 command authorization 做最终强制授权。三个决策平面职责独立、分别留痕，facade 不复制或改写任一规则真源。
- Agent 本身是语义世界节点。其能力、`skill_refs`、策略配置和协作角色可由经过治理的 LearningProposal 形成新版本；Agent 运行时不得把一次对话、LTM 命中或模型结论直接写成正式配置。

### 6.1 长期协作关系

`ASSISTED_BY quest -> npc_agent` 是持久化协作关系，不只是一次对话的展示字段。一个 Quest 可以有多个协作 Agent；关系属性至少表达 `role`、`status`、`is_primary_companion`、`capability_scope`、`valid_from/valid_to`、创建 actor 和 correlation id。

- `ASSISTED_BY` 只声明协作角色，不授予命令权限，也不证明该 Agent 执行过动作。
- 实际执行者仍来自 task/command/Agent run 审计记录；对话者、建议者、审批者和执行者必须可区分。
- 协作 Agent 的加入、角色变化和退出通过命令/service 修改并产生事件；UI 在 Journal 中展示协作历史。
- Companion 优先选择 active 且可见的 primary collaboration；没有合适协作者时才使用明确标注的系统 AICO fallback。
- 非 primary 的 `ASSISTED_BY` Agent 保留为协作者并可在 Journal 中查看，但不冒充当前 Companion。没有可见且 active 的 primary 时，投影返回 `companion: null` 和 `companionFallback: 'aico'`。

### 6.2 Quest 内嵌交互，而非独立助手

AICO 是 Quest Runtime 中 Agent 能力的交互适配器，不应在用户处理工作时表现为一个脱离世界与任务的通用助手。存在 foreground Quest 时，Conversation Zone 切换为 **Quest 协作**：

- 交互身份是 Quest 中的 companion Agent / NPC，可由世界角色、专业 Agent 或流程角色承载。
- 对话默认绑定 `quest_id`、当前 Situation、Goal、Objective、地图语义焦点、pinned Policy/Process/Quality refs 与可见 Evidence。
- Mission Card 提供“询问下一步”“解释依据”等情境入口；用户不需要先打开独立助手再重复描述任务。
- Agent 回答必须区分事实、推断、规则、流程经验和建议，不得把建议伪装成已批准决定。
- 对话中生成的建议可以形成 DecisionOption、补证请求或重规划提案；真正执行仍走 command/service 与 Policy gate。
- Quest 状态、地图焦点或 Objective 迁移后，对话上下文应随 interaction state 刷新；历史回答不得覆盖新状态。
  - 对话身份和默认请求绑定取自 `foregroundQuestId`，不依赖 activeTask 是否存在。没有可执行 Objective 时仍提供 Quest 内嵌对话选项，并明确没有当前行动目标。普通自由追问也使用最新前台 Quest/Objective/revision；取消追踪后回到通用对话，不携带旧 Quest 的隐式绑定。
  - Companion 投影可携带服务端 `collaborationRelationshipId`，本地线程按 Quest + 实际 Agent + 协作关系身份隔离；Agent 或协作关系变化时选择/创建独立线程，不能重新绑定历史线程。Objective 变化可更新本次 request context 而不篡改线程创建审计。相同身份可以恢复本地已有历史；服务端仍重新解析协作关系并拒绝不可读或已归档线程，本地 ID 不授予权限。

推荐体验参考 MUD/MMO 的任务 NPC：角色存在于语义世界并围绕当前事件提供线索、说明和有限行动，而不是悬浮在所有业务之上的万能聊天机器人。游戏化只用于增强情境感，不引入积分或娱乐化外壳。

交互呈现为 NPC dialogue choices，而不是聊天产品的空白输入框优先：

1. Quest Card 先给出 2–4 个与当前状态有关的自然语言选项，例如“接下来该做什么？”“为什么会有这个目标？”“还缺什么线索？”。
2. 选择后进入 Quest dialogue，并保留继续追问的自由输入。
3. Agent 可以反问用户、指出地图目标或提出世界行动；选择行动时展示预期影响和风险。
4. 对话结束不产生“关闭聊天”语义；它是 Quest Journal 的一部分，可随时从当前 Quest 恢复。

兼容切片可以复用现有 AICO thread/SSE 和上下文化查询，但 G2 之前必须把 Quest 上下文升级为结构化 request envelope；prompt 文本只负责表达，不得承担鉴权。界面在 foreground Quest 下隐藏“新建通用对话/切换通用线程”入口：

```typescript
interface QuestConversationContext {
  questId: string
  situationId?: string
  goalId?: string
  objectiveId?: string
  focusedEntityId?: string
  projectionRevision?: string
  lastEventId?: string
}
```

后端必须按调用者权限重新解析这些引用，不能信任前端附带的摘要或使用 prompt 文本作为授权依据。并发控制不得只依赖前端自增值：请求携带后端签发的 opaque projection revision 与最后可见事件 ID；服务端检测过期后要求刷新，绝不自动重放变更命令。

其中 Objective 是 task-backed 业务对象，其可读性必须复用 Task visibility/ACL（含池可见性及参与者权限）；不能套用仅公开/所有者可读的 semantic-node 判定。Quest、Situation、Goal 和 Agent 继续使用各自语义读权限。

Quest 对话线程遵循现有 STM/LTM 作用域，不另造一套 transcript 真源：现有 `agent_node_id` 继续表示实际会话 Agent；conversation thread 新增不可变的 `quest_node_id`、可选 `collaboration_relationship_id` 和创建时 projection revision，不再增加语义重复的 `companion_agent_node_id`。切换 Quest 或实际 Agent 时创建新线程。Quest 完成后线程归档为 Quest Journal 记录，并作为 raw/episodic 学习输入。Memory Thread + STM/LTM 链路是 transcript 真源；现有 `world_conversation_archive` 仅作为兼容读取投影，Quest 生命周期触发的归档由后端执行，不依赖前端 logout。异步 LTM 晋升必须保留 account、Agent、thread、Quest 与图引用；任何组织级经验或 Agent 配置变更仍须形成 LearningProposal 并经过治理，不得从归档对话自动发布。

### 6.3 Choice 与后果真实性

受治理选项的预览是只读、可过期的提示：`gateStatus/gateReasonCode`、风险和证据要求来源于权威版本化图规则。执行时必须重新求值，不能凭预览 clear 或 UI confirmation 直接写入。结果优先通过 `summaryKey/summaryParams` 本地化；未知理由码显示本地化通用提示及理由码，兼容 `summary/label` 仅作 fallback。客户端不把执行成功翻译为 Quest 已验收。

DecisionOption 必须将后果分为三类并显式标注：

- `confirmed`：由规则、当前事实或确定性模拟确认的结果；
- `predicted`：模型或经验预测，必须显示置信度、依据和不确定性；
- `proposed`：尚未执行的计划性影响，不得使用完成时态。

UI 不得把三类内容合并成一段无来源的“AI 后果”。高风险、不可逆或需要审批的选择必须在命令执行前显示 gate、Evidence 要求和受影响实体。

### 6.4 Journal、Pulse 与学习边界

- `Quest Journal / 任务日志` 的关系图只展示已经持久化且授权可读的世界节点/关系，以及明确标识的 unresolved ref；不得为每次命令或模型建议伪造图节点。
- Journal 节点检查是只读局部选择，与持久化 Objective focus、账户位置分离；可展示的边须同时具有可见源/目标节点。地图定位仅使用当前 Quest 明确投影的实体引用，Quest/Task/Policy 等业务语义节点及 unresolved ref 不直接作为地图位置。地图当前选择在对应 Journal 节点上提供文本标记，不能只用颜色表达。
- Action、Run、transition、Policy decision 和结果记录通过可审计时间线叠加到 Journal；只有达到长期语义与审计门槛的产物才按领域契约物化为世界节点。
- World Pulse 的 Situation/Quest 内容从权威图与事件派生，不复制第二份业务记录。高频个人注意力状态由账户级 `situation_attention` 记录保存 `seen_at / snoozed_until / ui_dismissed_at` 等字段；业务上的 dismiss/resolve 仍必须执行 Situation 命令并产生领域事件。
  - 权限过滤后的执行失败/越权/缺证/低置信度记录可形成 Pulse escalation；晚于个人 seen/snooze/UI-dismiss 的新失败必须重新提示，不修改 Situation 业务状态。每 Objective 的最新执行成功可消除该执行失败提示，但不代表 Situation resolved。Feedback 使用真实 transition/event ID 区分同事务同时间的事件，并展示实际主体、理由、关联对象与 correlation；不能泄露不可读 Objective 的失败详情。
- G1–G4 激活只要求 Quest 归档能安全进入 account + Agent 隔离的学习输入，且不能直接修改正式配置。LearningProposal 审批、版本发布和 Agent 配置更新属于后续学习闭环，不阻塞 F03 UI Active。

## 7. 空态、异常与降级

- 协作变更归档与对话 tick 冲突时，mutation 返回 HTTP 409 / `conversation_busy`；事务不提交，前端提示等待本轮结束后人工重试，不自动重放变更，也不把此冲突当成 stale projection。

- 无 Situation 时展示当前世界可探索动作，不制造示例任务。
- Quest 引用节点暂不可解析时保留 pinned ref，并标注为未解析依据。
- 聚合失败时保留错误与重试入口，不回退到静态 Dashboard 假数据。
- 移动端保持 Map 为世界底图；有 foreground Quest 时，以不遮挡关键地图信息的 HUD 优先显示该 Tracked Quest、当前 Objective 和下一步行动，Key Clues 与 Companion 使用可展开层。没有 foreground Quest 时优先呈现 Map + World Pulse。移动端不复制固定纵向工作台。
  - 窄屏层切换属于本地展示状态，不修改 TRACKS_QUEST、FOCUSES_ON、Objective 或位置。任务与线索只展开一层，关闭层仍保留地图；从任务定位地图实体时收起展开层。紧凑 HUD 只读同一 foregroundQuestId 及其 focused/recommended Objective，不取 queue 第一项替代。未展开层从键盘/读屏导航中隐藏；桌面分隔条同时支持键盘方向键与 Home/End。

## 8. 可访问性与文案

- 风险与严重度不能只依赖颜色，必须有文本标签。
- 卡片标题、状态、主动作保持键盘可达。
- 中英文文案均通过 i18n；开发日志保持英文。
- 使用 Mission/使命指用户可理解的 Quest 投影；数据与命令契约仍使用 `quest`。
- 禁止使用“任务完成=问题解决”“AI 已决定”等误导文案。

## 9. 验收场景

1. 关联 Quest 的队列项显示 Situation、Goal、风险、触发依据和当前 Objective。
2. 无 Quest 的遗留任务仍可执行，不展示虚构 Situation/Goal。
3. `claimed → start`、`in_progress/approved → complete` 动作保持既有命令契约。
4. Quest 进度标明为聚合视图；Objective 完成文案不宣称 Quest accepted。
5. 切换“态势/当前使命”只改变视图过滤，不改变后端状态。
6. 中英文界面均无硬编码业务文案。
7. Agent 自动处理不会静默消失：Mission Timeline 可追溯 executor、依据、动作、结果与证据；失败或越界可升级人工处理。
8. Mission 的 `subjectRef` 可定位并选中语义地图实体；地图选择同步到关键信息栏，并高亮关联 Mission。
9. 清除地图选择只清理 UI focus，不改变位置、Situation、Quest 或 Objective 状态。
10. Active Quest 下显示 Quest 协作/同行 Agent，而不是独立助手入口；快捷提问自动携带 Quest 与 Objective 上下文。
11. Quest 对话产生的执行建议必须经过确定性 Policy gate，并通过既有命令或决策动作执行。
12. 用户明确追踪 Quest、聚焦 Objective 和 pin 已物化 Clue 后，选择可跨刷新恢复；推荐、地图 hover 与临时 inspect 不会被误持久化。
13. Quest Journal 展示权限过滤后的 Situation、Goal、Objective、事实/证据、协作 Agent 与行动结果关系图；未物化引用有明确降级标识。
14. `ASSISTED_BY` 可表达多个长期协作角色，但不授予执行权限；对话者、建议者与实际执行者可分别追溯。
15. Quest 对话完成/归档后进入按用户与 Agent 隔离的学习输入路径；未经治理不得改变正式 Agent 配置、Policy、Process 或 Skill。
16. Choice 对 `confirmed / predicted / proposed` 后果使用不同文案和视觉语义，过期 revision 不会自动重放变更动作。
17. 可用性验收采用固定基线：至少 80% 的测试用户在 30 秒内识别“发生了什么/当前目标/下一步”；至少 90% 在无指导情况下完成一次受治理行动；误把 Agent 推荐当授权的比例不超过 5%；过期状态恢复成功率至少 95%；关键路径键盘可操作覆盖率 100%，抽样读屏任务完成率至少 90%。
18. 同一账户可同时恢复多个 `TRACKS_QUEST`；取消其中一个不会影响其他追踪。全账户仍只有一个有效 `FOCUSES_ON`，其所属 Quest 成为 HUD 前台 Quest。
19. R1 的 `observation` Clue 保存原始来源和未验证状态；后续 Evidence 验证产生新记录或状态演进，不改写观察原文。
20. Quest 自动处理前可追溯 Quest 治理、F16 行为策略和 command authorization 三个决策平面；任何一层拒绝都不得执行。
