# CampusWorld UI 交互优化 SPEC

## 0. 文档元信息

| 字段     | 内容                                                                                                                                                                   |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 文档类型   | Frontend Interaction UI Feature SPEC                                                                                                                                 |
| 推荐路径   | `docs/frontend/SPEC/features/F01_CAMPUSWORLD_NextUI.md`                                                                                                  |
| 所属模块   | `docs/frontend/SPEC/`                                                                                                                                                |
| 所属阶段   | Phase 1 / 下一代UI MVP                                                                                                                                                |
| 涉及前端   | `frontend/src/views`、`frontend/src/components`、`frontend/src/stores`、`frontend/src/api`、`frontend/src/router`、`frontend/src/websocket`、`frontend/src/types`          |
| 涉及后端   | `backend/app/commands`、`backend/app/api`、`backend/app/protocols`、`backend/app/services`、`backend/app/schemas`、`backend/app/game_engine`、`backend/app/games/hicampus` |
| 技术栈约束  | Vue 3、TypeScript、Vite、Element Plus、Pinia、Vue Router、Axios、WebSocket                                                                                                  |
| 后端协作约束 | FastAPI API adapter、protocol-neutral command layer、world runtime、Agent runtime、HiCampus world package                                                                |
| 核心体验   | 低信息负担、决策中心、轻量语义地图、状态摘要、区域菜单、可查询、可解释、可点击完成主流程                                                                                                                         |
| 非目标    | 传统后台 Dashboard、全量地图大屏、全量日志刷屏、强依赖聊天输入、复杂 3D、完整 IoT 平台                                                                                                                 |

## 0.1 实施阶段（与代码真源）

**当前里程碑（Phase 1）** 以真实用户任务队列为决策中心数据源（与 Task SPEC §1.5 可见性谓词一致，实现 SSOT：`backend/app/services/task/task_visibility_sql.py`，供 `task list` 与 `user_task_queue` 共用），不以 UI 侧 `task create` 或固定 HiCampus 八步点击脚本驱动。Admin 首次登录 `/works` 预期：奇点屋语义地图、`task_assignments` 直接指派的待办任务、Context 含当前位置与 `lastHandledTask`。

**HTTP 真源路径**（实现与 [`ACCEPTANCE.md`](../ACCEPTANCE.md) 一致，取代下文 §23/§32 中的 `mvp/world/enter`、`GET decision-center` 单数路径等旧示例）：

| 用途 | 路径 |
|------|------|
| 首屏聚合 | `GET /api/v1/world-sessions/current` |
| 进入/离开世界 | `POST /api/v1/world-sessions/enter-world` / `leave-world` |
| 决策动作 | `POST /api/v1/decision-center/actions` |
| 决策查询 | `POST /api/v1/decision-center/query` |
| 语义地图焦点 | `GET /api/v1/semantic-map/focus` |
| 语义地图动作 | `POST /api/v1/semantic-map/actions`（`drill` / `select`） |
| 空间摘要 | `GET /api/v1/semantic-map/space-summary` |
| 语义地图查询 | `POST /api/v1/semantic-map/query` |
| 全局搜索 | `POST /api/v1/world-search` |
| 历史摘要 | `GET /api/v1/world-history/summary` |

**反模式**：在 `world_interaction` 聚合层扫描房间设备并调用 `task create` 生成决策事件。

**延后（Phase 3+）**：Agent 主动关注项、EventTriage L2、WebSocket 实时 patch、成就 Toast、HiCampus 完整演示路径、`QuestCompletionCard`。

## 0.2 App 壳层（过渡实现真源）

多 Tab 产品形态下，已登录应用使用 **双层顶栏**，与 §5.1 单页 `WorldTopBar` 愿景并存；以本节与 [`ACCEPTANCE.md`](../ACCEPTANCE.md) 为准。

```text
┌─────────────────────────────────────────────────────────────┐
│ App NavBar（`NavBar.vue`）                                     │
│  CampusWorld ▾ 应用导航          ……          设置 ▾          │
├─────────────────────────────────────────────────────────────┤
│ TabBar（全宽，无左侧 Sidebar）  Works │ Spaces │ …            │
├─────────────────────────────────────────────────────────────┤
│ Tab 内容（全宽）                                               │
│   /works → WorldTopBar + WorldShell（三栏）                    │
│   /spaces、/agents 等 → 各 legacy 视图                         │
└─────────────────────────────────────────────────────────────┘
```

| 区域 | 组件 | 职责 |
|------|------|------|
| 应用导航 | CampusWorld 下拉（`AppNavMenu`） | Works → Spaces → Agents → Discovery → History；`openAppTab(route)`；默认 Tab 为 Works（`/works`） |
| 账号与会话 | **App NavBar 右侧「设置」** | **账号设置**（`/profile` Tab）、**退出登录**；**不**放入 CampusWorld 应用导航下拉 |
| Guest / 当前身份 | **设置** 与 Profile 页 | §6.8 `UserSessionMenu` 能力归 **设置菜单 + Profile**；本阶段 **不** 在 `WorldTopBar` 显示 Guest ▾ |
| 世界交互顶栏 | `WorldTopBar`（仅 `/works` Tab 内） | 世界切换、搜索/命令、Focus/Map 视图；**不** 重复「CampusWorld」品牌文案 |
| 已废弃 | 固定左侧 `Sidebar.vue` | 由 CampusWorld 下拉替代 |

---

# 1. 背景

CampusWorld 当前定位是一个世界语义化的 Campus OS。系统通过图模型描述人、空间、设备、任务、Agent 等实体，通过命令系统提供协议无关的交互能力，通过 HTTP、SSH、WebSocket 等不同协议适配到外部入口。

现有前端已经具备传统 Web 应用基础结构，包括登录、空间、Agent、发现、历史、工作台等页面方向。但第一阶段 MVP 不应继续强化传统“页面导航 + 查询 + 列表 + 详情”的后台体验，而应形成 CampusWorld 自己的下一代UI风格：

```text
用户进入一个物理+数字融合的语义世界；
系统主动整理和推荐当前最重要的信息和任务；
统一语义地图帮助用户理解空间和Agent（NPC）；
中央区域聚焦帮助用户处理任务与决策；
用户大部分流程可通过点击完成；
通过一个统一的交互框采用自然语言用于查询、解释和搜索，而不是主流程负担。
```

因此，本 SPEC 的目标是定义 CampusWorld 下一代 UI 交互优化方案，使其既符合当前项目架构，又能体现“下一代 Campus OS”的产品感。

---

# 2. 总体设计目标

## 2.1 用户 30 秒理解目标

用户进入 MVP 后，30 秒内必须理解：

1. 我在哪个世界。
2. 我当前在哪个空间。
3. 当前需要关注哪些信息和任务。
4. 下一步建议做什么。
5. 为什么建议这样做。
6. 相关 Agent 在哪里。
7. 地图和任务如何联动。
8. 如果想知道更多，可以搜索、点击快捷查询或展开区域菜单。

## 2.2 低交互目标

用户完成第一阶段核心演示流程时，不应强制输入自然语言。
用户是被信息和任务主动驱动的，用户通过信息和任务作为入口可以通过点击简单完成任务。

> **Phase 1 实施说明**：当前里程碑验收为 admin @ 奇点屋 + **用户任务队列**待办（见 §0.1），**不要求**完成下列 HiCampus 空间链路与投影仪报修演示；该路径归入 Phase 3 HiCampus 全量演示。

如果用户主动进行探索处理，**Phase 3+ 参考演示**最多可包含以下点击：

1. 进入 HiCampus。
2. 前往长桥。
3. 前往中心广场。
4. 前往 F3 培训中心。
5. 查看 F3-101 投影仪。
6. 处理已存在的报修任务（非 UI 触发 `task create`）。

自然语言输入可以作为：

1. 查询入口。
2. 解释入口。
3. 搜索入口。
4. 与 Agent 深入交流入口（未来可以提供附身到Agent能力将信息视角转换为Agent）。
5. 命令入口。

## 2.3 信息减负目标

默认界面不展示全部信息。

默认只展示：

1. 当前焦点摘要。
2. 当前任务。
3. 最多 2 个待决策事件。
4. 最多 3 个推荐动作。
5. 当前相关地图区域。
6. 最多 3 个高亮 Agent。
7. 当前状态摘要。
8. 异常或阻塞信息。

更多信息通过：

1. 顶部全局搜索。
2. 区域菜单。
3. 快捷查询。
4. 展开详情。
5. 历史抽屉。
6. 底部命令栏。

---

# 3. 核心交互原则

## 3.1 顶部极简，区域自治

顶部状态栏不再承担大量信息展示，只保留全局锚点和全局入口。

区域菜单负责各区域内部功能：

| 区域    | 负责内容                    |
| ----- | ----------------------- |
| 顶部状态栏 | 产品、世界、全局搜索、全局视图模式、用户、异常 |
| 地图区域  | 地图模式、路线、Agent、事件、居中、全图  |
| 决策中心  | 待处理、当前任务、已处理、稍后、排序      |
| 状态摘要  | 展开、快捷查询、刷新、固定           |
| 底部工具  | 命令、历史、日志、调试             |

## 3.2 决策中心优先于聊天流

中央区域不是聊天窗口，而是“决策中心 + 任务行动流”。

优先级为：

```text
阻塞事件 > 待决策事件 > 当前任务 > 下一步推荐 > 快捷查询 > 自然语言输入
```

## 3.3 地图服务当前决策

地图不是全量展示园区所有信息，而是支持当前决策。

地图默认回答：

1. 我在哪？
2. 下一步去哪？
3. 目标在哪？
4. 相关 Agent 在哪？
5. 路线是什么？

## 3.4 对话能力保留但弱化主流程负担

用户不应为了完成 MVP 流程而必须问：

```text
我下一步做什么？
这里有什么？
我该去哪？
```

系统应主动给出下一步。

用户可以在需要解释时点击：

```text
为什么？
```

或使用查询入口。

## 3.5 后端仍是事实来源

前端不能自行伪造世界状态、任务状态、Agent 位置或命令执行结果。

所有关键状态来自：

1. 后端 session。
2. world runtime。
3. command execution。
4. Agent presence。
5. task / quest service。
6. decision center service。
7. semantic map service。

---

# 4. 与当前前端架构的关系

## 4.1 当前路径保留

当前已有页面路径不直接废弃：

| 当前路径                   | 处理方式                                 |
| ---------------------- | ------------------------------------ |
| `/works`               | 作为新 MVP 主入口承载 `WorldInteractionView` |
| `/spaces`              | 保留为传统空间浏览或降级为开发/详情页面                 |
| `/agents`              | 保留为 Agent 管理或列表页面                    |
| `/discovery`           | 保留为发现页，后续可接世界事件推荐                    |
| `/history`             | 保留为历史页，MVP 中主要通过底部历史抽屉访问             |
| `/profile`             | 保留用户资料                               |
| `/login` / `/register` | 保留认证流程                               |

## 4.2 `/works` 页面升级

`/works` 从传统 Dashboard 升级为：

```text
CampusWorld 主世界交互界面
```

组件：

```text
WorldInteractionView
```

## 4.3 当前组件方向兼容

现有规划组件可映射为：

| 现有组件方向         | MVP 新组件 / 过渡实现                              |
| -------------- | ----------------------------------------------- |
| NavBar         | 保留；CampusWorld 下拉应用导航 + 右侧「设置」（账号/退出）     |
| Sidebar        | **移除**；五项导航迁入 CampusWorld 下拉（§0.2）          |
| TabBar         | 保留；全宽；菜单项各开独立 Tab                           |
| NavBar（愿景对照） | `/works` Tab 内另设 `WorldTopBar`（世界/搜索/视图）   |
| Dashboard      | `DecisionCenterFlow` + `ContextSummaryPanel` |
| ChatInput      | `DecisionQueryBox`                           |
| TodoList       | `ActiveTaskCard` / `DecisionEventList`       |
| AgentsActivity | `AgentSummaryList` / `AgentAvatarNode`       |
| History 页面     | `HistorySummaryDrawer` / `/history`          |
| Spaces 页面      | `SpaceNode` / `FocusSemanticMap` / `/spaces` |
| Agents 页面      | `AgentMapPresence` / `/agents`               |

---

# 5. 总体页面布局

## 5.1 桌面默认布局

**过渡实现（真源）**：见 §0.2（App NavBar + TabBar + Tab 内 `/works` 三栏）。下列单页愿景仍描述 **World 内容区** 内部结构。

```text
┌──────────────────────────────────────────────────────────────┐
│ WorldTopBar（/works Tab 内）                                  │
│ {世界/位置} ▾              ⌘ 搜索或命令       Focus ▾ Map ▾   │
├──────────────────────┬──────────────────────────┬────────────┤
│ FocusSemanticMap      │ DecisionCenterFlow       │ Context    │
│ 地图                   │ 决策中心                   │ 摘要       │
├──────────────────────┴──────────────────────────┴────────────┤
│ BottomUtilityDrawer：命令 / 历史，默认折叠                       │
└──────────────────────────────────────────────────────────────┘
```

账号、Guest、退出登录在 **App NavBar → 设置**（§0.2），不在此 `WorldTopBar` 行。

## 5.2 默认区域比例

| 区域   |  比例 | 说明            |
| ---- | --: | ------------- |
| 地图区域 | 30% | 当前区域、路径、Agent |
| 决策中心 | 50% | 主交互焦点         |
| 状态摘要 | 20% | 当前上下文         |
| 底部工具 |  折叠 | 命令、历史、调试      |

## 5.3 全局视图模式

顶部 `ViewModeSwitcher` 控制整体布局。

| 模式        |  地图 | 决策中心 | 状态摘要 | 底部工具      |
| --------- | --: | ---: | ---: | --------- |
| `Focus`   | 30% |  50% |  20% | 折叠        |
| `Map`     | 55% |  35% |  10% | 折叠        |
| `History` | 20% |  40% |  10% | 30% 历史    |
| `Debug`   | 25% |  35% |  15% | 25% 命令/日志 |

默认模式：

```text
Focus
```

Focus 模式下语义地图 pane **默认收起**（44px collapsed strip）；切换到 `Map` 时前端展开地图 pane；切回 `Focus` 时再次收起。`display_policy.mapDefaultCollapsed` 为 `true`，与 `contextDefaultCollapsed` 对齐首屏侧栏收拢。

---

# 6. 顶部状态栏 SPEC

## 6.1 组件名称

```text
WorldTopBar
```

## 6.2 顶部职责

分两层（§0.2）：

**App NavBar**

1. 产品锚点与应用导航（CampusWorld 下拉：Works / Spaces / …）。
2. **用户账号与会话**（右侧「设置」：账号设置、退出登录）。

**WorldTopBar**（`/works` Tab 内）

1. 世界锚点（当前世界/位置，enter/leave）。
2. 全局搜索或命令入口。
3. 世界视图模式（Focus / Map）。
4. （可选）连接/异常提示；**不含** Guest ▾ / 账号设置。

## 6.3 顶部常驻元素

App NavBar：

```text
CampusWorld ▾                    设置 ▾
```

WorldTopBar（`/works`）：

```text
{世界名/位置} ▾      ⌘ 搜索或命令      Focus ▾   Map ▾
```

## 6.4 顶部不展示内容

以下内容不得常驻顶部：

1. 当前地点详情。
2. 当前任务完整进度。
3. Agent 数量。
4. 待处理事件数量，除非 urgent。
5. 地图内部模式。
6. 历史列表。
7. 命令日志。
8. WebSocket 文本状态。
9. 当前空间对象数量。
10. 普通系统事件。

## 6.5 ProductWorldSwitcher

显示：

```text
CampusWorld · HiCampus ▾
```

点击菜单：

```text
当前世界
- HiCampus

世界操作
- 查看世界说明
- 重新进入世界
- 打开演示模式
- 返回首页
```

## 6.6 GlobalCommandSearch

显示：

```text
⌘ 搜索空间、Agent、任务或输入命令
```

支持输入：

```text
F3
Agent 都在哪里？
刚才发生了什么？
/go north
```

结果以浮层展示，不跳传统结果页。

## 6.7 ViewModeSwitcher

显示：

```text
Focus ▾
```

选项：

```text
Focus
Map
History
Debug
```

注意：

`ViewModeSwitcher` 控制全局布局，不控制地图内部模式。

## 6.8 UserSessionMenu

**过渡实现**：挂在 **App NavBar 右侧「设置」**（`NavBar.vue`），**不**在 `WorldTopBar` 显示 Guest ▾。

触发：

```text
设置 ▾
```

菜单（当前实现）：

```text
账号设置          → /profile Tab
退出登录
```

愿景扩展（Guest、当前 Session、演示重置等）仍归 **设置** 子菜单或 Profile 页，不迁入 CampusWorld 应用导航下拉。F01 文案中的 Guest ▾ 指上述 **设置入口** 所承载的身份/会话能力，而非世界顶栏独立按钮。

## 6.9 SystemStatusIndicator

正常时弱化为小点或隐藏：

```text
●
```

异常时显示：

```text
连接异常
```

或：

```text
需要处理
```

点击异常提示后：

1. `连接异常` 打开连接状态菜单。
2. `需要处理` 聚焦中央决策中心。

---

# 7. 区域菜单统一规范

## 7.1 区域菜单形式

每个主要区域顶部都有轻量菜单：

```text
区域标题      主操作      次操作      ⋯
```

例如：

```text
语义地图      路线      Agent      ⋯
```

```text
决策中心      待处理      当前任务      ⋯
```

```text
状态摘要      展开      ⋯
```

## 7.2 区域菜单规则

1. 区域菜单只控制本区域。
2. 主操作最多 2 个。
3. 低频操作进入 `⋯`。
4. 更多菜单最多 3 组。
5. 每组最多 5 项。
6. 菜单操作如影响其他区域，必须轻量反馈。
7. 区域菜单不能导致顶部信息膨胀。

---

# 8. 地图区域 SPEC

## 8.1 组件名称

```text
FocusSemanticMap
```

## 8.2 地图区域菜单

默认：

```text
语义地图      路线      Agent      ⋯
```

更多菜单：

```text
地图模式
- 当前焦点
- 路线
- Agent
- 事件

显示
- 显示任务目标
- 显示已发现对象
- 显示事件热点
- 收起非相关节点

操作
- 回到当前位置
- 打开全图
- 重置地图视图
```

## 8.3 地图内部模式

| 模式      | 说明              |
| ------- | --------------- |
| `focus` | 当前地点、邻近空间、下一步目标 |
| `route` | 当前任务路线或搜索路线     |
| `agent` | 已发现 Agent 分布    |
| `event` | 事件热点与关联对象       |

## 8.4 地图默认显示限制

| 类型       | 默认最大数量 |
| -------- | -----: |
| 空间节点     |      7 |
| 高亮 Agent |      3 |
| 事件热点     |      2 |
| 推荐路径     |      1 |
| 对象标记     |      3 |

超过数量使用聚合标记：

```text
+4 空间
+3 Agent
+8 对象
```

## 8.5 地图数据结构

真源：`frontend/src/types/world.ts` 与 `backend/app/services/world_interaction/semantic_map_service.py` 返回的 `focus_map` / `map_patch`。

```ts
export type MapViewLayer = 'room' | 'floor' | 'building' | 'campus'

export interface SemanticMapNode {
  id: string
  name: string
  type:
    | 'gate'
    | 'bridge'
    | 'plaza'
    | 'building'
    | 'room'
    | 'floor'
    | 'outdoor'
    | 'cluster'
    | 'service'
    | 'hidden'
  x: number
  y: number
  status:
    | 'unknown'
    | 'visible'
    | 'discovered'
    | 'current'
    | 'active'
    | 'locked'
    | 'warning'
  semanticTags: string[]
  activeAgentIds: string[]
  activeEventIds: string[]
  objectIds: string[]
  buildingId?: string
  floorId?: string
  floorNumber?: number
  drillAnchorId?: string   // cluster 钻取锚点
  overflowCount?: number   // floor cluster 溢出房间数
}

export interface SemanticMapEdge {
  id: string
  from: string
  to: string
  label?: string
  direction?: string
  status: 'available' | 'locked' | 'recommended' | 'visited' | 'cross-building'
  targetLabel?: string
  crossBuilding?: boolean
  campusEdgeKind?: 'spine' | 'inter-building' | 'connector'  // viewLayer=campus only
}

export interface AgentMapPresence {
  agentId: string
  name: string
  role: string
  currentSpaceId: string
  status: 'idle' | 'waiting' | 'talking' | 'moving' | 'working' | 'offline'
  currentIntent?: string
  currentTask?: string
  lastSeenAt: string
  visibility: 'visible' | 'discovered' | 'hidden'
}

export interface FocusMap {
  mode: 'focus' | 'route' | 'agent' | 'event'
  viewLayer?: MapViewLayer
  orientation?: 'north-up'
  layout?: 'compass' | 'grid' | 'campus-grid' | 'hierarchy' | 'list' | 'logical'
  breadcrumb?: Array<{ layer: string; id: string; name: string }>
  neighborLinks?: Array<{ direction: string; targetId: string; targetName: string; summary: string }>
  floorPlanReady?: boolean
  floorRoomList?: Array<{ id: string; name: string; status: SemanticMapNode['status'] }>
  nodes: SemanticMapNode[]
  edges: SemanticMapEdge[]
  agentPresences: AgentMapPresence[]
  highlightedPath: string[]
  currentSpaceId: string | null
  selectedEntityId: string | null
  loading: boolean
}
```

`layout` 与 `viewLayer` 组合约定（North-up）：

| `layout` | 典型 `viewLayer` | 含义 |
| -------- | ---------------- | ---- |
| `compass` | `room` | 焦点邻域罗盘 |
| `logical` | `room` | 房间 hub-and-spoke |
| `grid` | `floor` | 楼层 `map_grid_*` 等距平面 |
| `campus-grid` | `campus` | 园区 `campus_grid_*` 鸟瞰（与 floor `grid` 分离） |
| `hierarchy` / `list` | `building` / fallback | 竖排或列表回退 |

Campus 层边：`campusEdgeKind=spine`（户外脊线）、`inter-building`（楼栋间）、`connector`（广场/户外 ↔ 楼栋）。

```ts
export interface MapPatch {
  mode?: FocusMap['mode']
  viewLayer?: MapViewLayer
  anchorId?: string
  highlightedNodeIds?: string[]
  highlightedPath?: string[]
  visibleNodeIds?: string[]
  focus_map?: FocusMap
}
```

`DISPLAY_POLICY` 扩展：`maxFloorNodesVisible`（默认 24，超出以 `cluster` 节点聚合）、`maxCampusNodesVisible`（默认 40，超出按楼栋 cluster）、`maxEventHotspotsHighlighted`（event 模式高亮上限）。

## 8.6 地图点击行为

| 点击对象  | 响应             |
| ----- | -------------- |
| 当前空间  | 中央显示空间摘要（与 `space` 命令四段一致） |
| 可达空间  | 高亮目标 + 中央显示连接与空间摘要；**不**默认触发移动或「前往」 |
| 楼栋/楼层/cluster | 钻取切换 `viewLayer`（`POST /semantic-map/actions` `drill`）；不改玩家 `location_id` |
| Agent | 地图模式高亮；必要时中央显示 Agent 摘要卡 |
| 对象    | 中央显示对象发现卡      |
| 事件热点  | 中央显示事件决策卡      |
| 聚合标记  | 钻取到对应楼栋层      |

地图点击不得跳传统详情页。玩家移动仅由决策中心任务推荐或命令栏 `go` 触发。

`focus_map` 扩展字段：`viewLayer`、`orientation: north-up`、`breadcrumb`、`neighborLinks`、`floorPlanReady`（floor 层无 grid 时为 false）。

## 8.7 地图与中央联动

当中央决策卡显示“前往长桥”时：

1. 地图高亮当前位置。
2. 地图高亮长桥。
3. 地图显示路线边。
4. 地图不自动展开全图。

当用户点击地图菜单 `Agent` 时：

1. 地图切换 Agent 模式。
2. 状态摘要更新关键 Agent。
3. 中央区域只在必要时显示提示，不刷屏。

---

# 9. 决策中心 SPEC

## 9.1 组件名称

```text
DecisionCenterFlow
```

## 9.2 区域菜单

默认：

```text
决策中心      待处理      当前任务      ⋯
```

更多菜单：

```text
查看
- 只看待处理
- 只看当前任务
- 查看已处理
- 查看稍后项

排序
- 按优先级
- 按时间
- 按任务相关性

操作
- 清除已处理
- 打开决策历史
```

## 9.3 中央区域结构

```text
region-menu（固定）
task-zone（三态：收起标题 / 分屏可拖拽默认约 35% / 最大化隐藏对话内容）
  task-zone-header（待办与决策 + 待处理徽标）
  task-zone-body
    FocusSummary（severity 左色条 + 标题 + 短摘要）
    DecisionEventList（左色条；Impact/Recommendation 默认折叠）
    ActiveTaskCard（进度/状态 pill，非告警色条）
    NextBestAction（主行动；边框/hover 强调，非独立巨型 CTA）
zone-divider / fold-hinge（区域分界 + 三态切换；分屏态可垂直拖拽，>4px 视为拖拽否则点击切换；拖至顶≈最大化、拖至底≈收起）
conversation-zone（flex:1，独立滚动；较深背景、较低信息密度；最大化时隐藏）
  conversation-zone-header（对话与查询 + 模式副文案）
  AicoThreadToolbar（仅 AICO 模式）
  DecisionConversationThread
DecisionQueryBox（固定底部）
```

样式 token（`frontend/src/styles/themes/variables.css`）：`--decision-pane-bg`、`--decision-task-surface`、`--decision-chat-well`、`--decision-divider-bg`、`--decision-severity-stripe-width` 等。视觉为 **CampusWorld 工作台** 分区，仅借鉴低阅读负担/主行动突出等交互原则，**不得**做成车机/HMI 界面。

`viewFilter` 仅过滤 **待处理事件列表**；`ActiveTaskCard` 与 `NextBestAction` 不受 Tab 切换隐藏。

## 9.4 查询模式

| 模式 | 传输 | 说明 |
|------|------|------|
| `command` | `POST /decision-center/query` 同步 | `/` 前缀走命令执行并返回 `state_patch`；纯文本走 world-search，透传 `results[]` |
| `aico` | `POST /decision-center/query/stream` SSE | 禁止同步 `/query`（HTTP 400）；**provider 真流式** `delta`（任意产生用户向 prose 的 LLM 调用，含 Plan react 末轮）；`scope=activity` meta（`working` / `tool` / `writing` / `rewrite`），**不展示** PDCA 阶段名；`scope=tick` 仅 `start`/`complete`；响应头 `Cache-Control: no-cache`、`X-Accel-Buffering: no`；队列轮询 ≤50ms；空闲 `: ping`；前端分块 flush（≥32 字或 16ms）；`rewrite` 清空当前助手气泡；支持 **Stop** |

会话消息上限 50 条（FIFO）；`logout` 将 AICO 线程与 Command 会话归档至 `POST /world-history/conversations/archive`。

## 9.5 渲染优先级

1. 阻塞用户行动的事件。
2. 高优先级异常。
3. 当前任务下一步。
4. Agent 明确建议。
5. 新发现的重要信息。
6. 普通状态变化。
7. 会话线程与输入框。

---

# 10. FocusSummary SPEC

## 10.1 作用

一句话说明当前状态和推荐方向。

## 10.2 数据结构

```ts
export interface FocusSummary {
  title: string
  summary: string
  currentSpaceId: string
  currentTaskId?: string
  severity: 'normal' | 'info' | 'warning' | 'critical'
  primaryAction?: DecisionOption
}
```

## 10.3 示例

```text
你在 HiCampus 大门

AICO 正在入口处，当前探索任务建议你前往中心广场。
```

---

# 11. DecisionEventCard SPEC

## 11.1 作用

把需要用户判断或处理的事件卡片化。

每张卡必须回答：

1. 发生了什么？
2. 为什么重要？
3. 建议做什么？
4. 可以执行什么？
5. 可以稍后处理吗？

## 11.2 数据结构

```ts
export interface DecisionEvent {
  id: string
  title: string
  summary: string
  type:
    | 'navigation'
    | 'agent_suggestion'
    | 'task_update'
    | 'service_request'
    | 'object_discovery'
    | 'warning'
    | 'system'
  priority: 'urgent' | 'important' | 'normal' | 'low'
  status: 'new' | 'seen' | 'resolved' | 'dismissed' | 'snoozed'
  source: 'system' | 'agent' | 'world' | 'quest' | 'command'
  impact: string
  recommendation: string
  options: DecisionOption[]
  explanation?: string
  relatedEntities: EntityReference[]
  createdAt: string
}

export interface DecisionOption {
  id: string
  label: string
  style: 'primary' | 'secondary' | 'safe' | 'danger' | 'quiet'
  actionType:
    | 'execute_command'
    | 'open_map'
    | 'open_detail'
    | 'ask_explanation'
    | 'snooze'
    | 'dismiss'
    | 'start_task'
    | 'continue_task'
    | 'search'
  command?: string
  intent?: string
  targetEntityId?: string
  requiresConfirmation: boolean
}

export interface EntityReference {
  id: string
  type: 'space' | 'agent' | 'object' | 'task' | 'event' | 'command'
  label: string
}
```

## 11.3 卡片格式

```text
标题

一句话摘要。

影响：
说明这件事对当前任务或用户行动有什么影响。

建议：
系统推荐用户怎么做。

[主操作] [次操作] [稍后]
```

## 11.4 示例

```text
下一步：前往中心广场

中心广场连接 F1-F6，也是前往 F3 培训中心的中转点。

影响：
到达中心广场后，你可以继续前往 F3 并发现更多 Agent。

建议：
现在通过长桥前往中心广场。

[前往长桥] [查看路线] [稍后]
```

## 11.5 规则

1. 每张卡片 5 秒内可理解。
2. 主操作只能有 1 个。
3. 次操作最多 2 个。
4. 解释默认折叠。
5. 已解决后自动收起。
6. 非紧急卡允许稍后。
7. 重复事件必须合并。
8. 不展示技术日志。

---

# 12. ActiveTaskCard SPEC

## 12.1 作用

显示当前主任务和下一步。

## 12.2 数据结构

```ts
export interface TaskCard {
  id: string
  title: string
  summary: string
  status: 'not_started' | 'active' | 'blocked' | 'completed'
  progress: number
  currentStep: TaskStep
  nextBestAction: DecisionOption
  alternativeActions: DecisionOption[]
  blockers?: TaskBlocker[]
}

export interface TaskStep {
  id: string
  title: string
  shortInstruction: string
  status: 'locked' | 'active' | 'completed'
  targetSpaceId?: string
  targetAgentId?: string
  targetObjectId?: string
  expectedAction?: string
}

export interface TaskBlocker {
  id: string
  reason: string
  resolutionAction?: DecisionOption
}
```

## 12.3 默认 MVP 任务

任务名：

```text
第一次探索 CampusWorld
```

步骤：

1. 进入 HiCampus。
2. 观察入口。
3. 前往长桥。
4. 到达中心广场。
5. 前往 F3 培训中心。
6. 查看 F3-101 投影仪。
7. 创建模拟报修。
8. 查看完成总结。

## 12.4 示例

```text
第一次探索 CampusWorld

进度：2/5
当前步骤：前往中心广场

你已经到达长桥。下一步建议继续前往中心广场。

[继续前往中心广场] [查看路线] [为什么？]
```

---

# 13. NextBestAction SPEC

## 13.1 作用

当没有高优先级待处理卡片时，仍给出明确下一步。

## 13.2 规则

推荐动作优先级：

1. 当前任务下一步。
2. 当前决策事件主操作。
3. 当前空间推荐出口。
4. 当前 Agent 建议。
5. 默认探索动作。

## 13.3 示例

```text
下一步建议：前往长桥

这是去中心广场和 F3 培训中心的第一步。

[前往长桥] [查看路线] [为什么？]
```

---

# 14. 查询与解释入口 SPEC

## 14.1 组件名称

```text
DecisionQueryBox
```

## 14.2 定位

输入框是查询、解释、搜索和命令入口，不是主流程必需入口。

占位文案：

```text
搜索或询问任务、事件、Agent、空间...
```

## 14.3 快捷查询

组件：

```text
QuickQueryChips
```

默认最多展示 4 个：

```text
[我现在要处理什么？]
[为什么建议这样做？]
[Agent 都在哪里？]
[刚才发生了什么？]
```

## 14.4 支持输入

```text
F3 在哪里？
Agent 都在哪里？
刚才发生了什么？
为什么建议去中心广场？
/go north
```

## 14.5 结果呈现

查询结果不得刷成长聊天流，应显示为轻量结果卡：

```text
为什么建议去中心广场？

中心广场连接 F1-F6，也是前往 F3 培训中心的中转点。

[继续前往长桥] [查看路线]
```

---

# 15. 状态摘要 SPEC

## 15.1 组件名称

```text
ContextSummaryPanel
```

## 15.2 区域菜单

默认：

```text
状态摘要      展开      ⋯
```

更多菜单：

```text
显示
- 当前位置
- 当前任务
- 关键 Agent
- 待处理事件

快捷查询
- 我现在在哪里？
- 当前任务是什么？
- Agent 都在哪里？
- 刚才发生了什么？

操作
- 刷新摘要
- 固定当前摘要
```

## 15.3 数据结构

```ts
export interface ContextSummary {
  currentSpace: {
    id: string
    name: string
    oneLineSummary: string
  }
  nearbyAgents: {
    total: number
    highlighted: AgentSummary[]
  }
  activeTask: {
    id: string
    title: string
    currentStep: string
    progress: number
  }
  pendingDecisionCount: number
  suggestedQueries: QueryHint[]
}

export interface AgentSummary {
  id: string
  name: string
  role: string
  status: AgentMapPresence['status']
  locationName: string
}

export interface QueryHint {
  label: string
  query: string
  scope?: 'task' | 'map' | 'agent' | 'history' | 'world'
}
```

## 15.4 默认示例

```text
当前位置
HiCampus 大门
你在园区入口，AICO 正在附近。

当前任务
第一次探索 · 1/5
下一步：前往中心广场

关键 Agent
AICO · 导览 · 在大门

快速查询
[这里有什么？]
[Agent 都在哪里？]
[刚才发生了什么？]
```

---

# 16. 底部工具区 SPEC

## 16.1 组件名称

```text
BottomUtilityDrawer
```

## 16.2 默认状态

默认折叠：

```text
命令 / 历史 / 日志 ︿
```

展开后：

```text
工具      命令      历史      日志      ⋯
```

## 16.3 Tabs

| Tab  | 说明             |
| ---- | -------------- |
| `命令` | MUD / CLI 命令输入 |
| `历史` | 历史摘要和事件分组      |
| `日志` | 原始事件，开发用       |
| `调试` | Debug 模式可见     |

## 16.4 命令栏支持

```text
/look
/whereami
/go north
/enter F3
/inspect projector_f3_101
/ask AICO 怎么去 F3？
/history
```

## 16.5 历史摘要分组

| 分组       | 示例             |
| -------- | -------------- |
| 位置变化     | 大门 → 长桥 → 中心广场 |
| Agent 对话 | AICO 给出 F3 路径  |
| 任务进度     | 完成 3/5         |
| 对象发现     | 发现 F3-101 投影仪  |
| 服务动作     | 创建模拟报修         |

---

# 17. 全局搜索 SPEC

## 17.1 组件名称

```text
GlobalCommandSearch
```

## 17.2 搜索范围

1. 空间。
2. Agent。
3. 对象。
4. 当前任务。
5. 历史事件。
6. 决策事件。
7. 命令。
8. Agent 回复。

## 17.3 搜索结果示例

搜索：

```text
F3
```

结果：

```text
F3 培训中心
建筑 · 位于中心广场东侧
Agent：培训服务 Agent
对象：F3-101 投影仪

[规划路线] [在地图上显示] [查看相关任务]
```

## 17.4 结果行为

| 动作         | 结果                    |
| ---------- | --------------------- |
| 规划路线       | 地图切换 Route 模式，中央生成路线卡 |
| 在地图上显示     | 地图高亮目标                |
| 查看相关任务     | 中央聚焦任务卡               |
| 与 Agent 对话 | 中央显示 Agent 摘要和查询入口    |

---

# 18. Agent UI SPEC

## 18.1 Agent 呈现原则

Agent 是世界实体，不是单纯聊天对象。

每个 Agent 必须有：

1. 名称。
2. 角色。
3. 位置。
4. 状态。
5. 能力摘要。
6. 推荐交互。
7. 地图呈现。

## 18.2 MVP Agent

| Agent ID       | 名称         | 角色          | 初始位置                 | 能力                   |
| -------------- | ---------- | ----------- | -------------------- | -------------------- |
| `aico`         | AICO       | 系统导览 Agent  | `hicampus_gate`      | 世界介绍、路径引导、当前空间解释     |
| `map_spirit`   | 地图精灵       | 地图 Agent    | `central_plaza`      | 地图说明、建筑说明、Agent 位置解释 |
| `training_bot` | 培训服务 Agent | 教学/培训 Agent | `f3_training_center` | F3 介绍、培训服务、设备说明      |
| `repair_bot`   | 报修服务 Agent | 运维 Agent    | `f6_service_center`  | 模拟报修、设备状态解释          |

## 18.3 Agent 摘要卡

点击地图上的 Agent 后，在中央显示：

```text
AICO

角色：系统导览 Agent
位置：HiCampus 大门
状态：等待提问

它可以帮助你理解当前位置、规划路线、解释任务。

[询问这里有什么] [让 AICO 规划路线] [稍后]
```

## 18.4 Agent 状态

| 状态        | 地图表现    |
| --------- | ------- |
| `idle`    | 静态头像    |
| `waiting` | 轻微呼吸高亮  |
| `talking` | 对话气泡脉冲  |
| `moving`  | 路径移动动画  |
| `working` | 工具/任务标记 |
| `offline` | 灰色标记    |

---

# 19. 信息与事件分流 SPEC

## 19.1 事件分类

| 类型                  | 进入中央区域 | 说明         |
| ------------------- | ------ | ---------- |
| `decision_required` | 是      | 需要用户处理     |
| `task_relevant`     | 是      | 影响当前任务     |
| `contextual`        | 合并摘要   | 当前上下文变化    |
| `background`        | 否      | 进入历史       |
| `debug`             | 否      | 仅 Debug 模式 |

## 19.2 合并示例

原始事件：

```text
space.entered: long_bridge
map.node.discovered: central_plaza
quest.updated: step_2
agent.presence.updated: aico waiting
```

中央区域应合并为：

```text
你已到达长桥

中心广场已在前方点亮，这是当前探索任务的下一步目标。

[继续前往中心广场] [查看路线] [稍后]
```

## 19.3 去重规则

必须合并：

1. 同一目标路径建议。
2. 同一任务步骤更新。
3. 同一 Agent 连续状态变化。
4. 同一空间重复观察。
5. 同一对象重复发现。

---

# 20. 游戏化交互 SPEC

## 20.1 游戏感来源

1. 进入世界仪式。
2. 地图节点点亮。
3. 任务推进。
4. Agent 遭遇。
5. 对象发现。
6. 决策卡行动。
7. 成就提示。
8. 完成总结。
9. 命令彩蛋。
10. 世界事件反馈。

## 20.2 进入世界仪式

用户点击进入后展示：

```text
正在连接 CampusWorld...
正在加载 HiCampus 语义世界...
正在定位入口...
你已抵达：HiCampus 大门
```

时长建议：1 至 2 秒。

## 20.3 成就

| 成就 id                  | 名称       | 触发条件          |
| ---------------------- | -------- | ------------- |
| `first_entry`          | 初入世界     | 首次进入 HiCampus |
| `first_decision`       | 第一次决策    | 执行第一个决策动作     |
| `first_move`           | 迈出第一步    | 第一次移动         |
| `first_agent_contact`  | 遭遇 Agent | 第一次与 Agent 交互 |
| `found_f3`             | 找到 F3    | 到达 F3         |
| `first_service_action` | 服务已触发    | 创建模拟报修        |
| `quest_complete`       | 探索完成     | 完成默认任务        |

---

# 21. 前端文件结构建议

## 21.1 Views

```text
frontend/src/views/
├── Home.vue                      # 可继续作为 /works 容器，或迁移为 WorldInteractionView
├── WorldInteractionView.vue       # 新主世界交互页
├── DemoSummaryView.vue
├── auth/
├── spaces/
├── agents/
├── discovery/
├── history/
└── user/
```

## 21.2 Components

```text
frontend/src/components/
├── shell/
│   ├── WorldShell.vue
│   ├── WorldTopBar.vue
│   ├── ViewModeSwitcher.vue
│   ├── GlobalCommandSearch.vue
│   └── ConnectionStatusIndicator.vue
├── decision/
│   ├── DecisionCenterFlow.vue
│   ├── DecisionCenterMenu.vue
│   ├── FocusSummary.vue
│   ├── DecisionEventList.vue
│   ├── DecisionEventCard.vue
│   ├── ActiveTaskCard.vue
│   ├── NextBestAction.vue
│   ├── QuickQueryChips.vue
│   ├── DecisionQueryBox.vue
│   └── ResolvedEventsDrawer.vue
├── map/
│   ├── FocusSemanticMap.vue
│   ├── MapRegionMenu.vue
│   ├── SpaceNode.vue
│   ├── AgentAvatarNode.vue
│   ├── ObjectMarker.vue
│   ├── EventPulse.vue
│   ├── PathOverlay.vue
│   └── MiniMapLegend.vue
├── context/
│   ├── ContextSummaryPanel.vue
│   ├── ContextSummaryMenu.vue
│   ├── CurrentSpaceSummary.vue
│   ├── AgentSummaryList.vue
│   ├── TaskProgressMini.vue
│   └── SuggestedQueryList.vue
├── utility/
│   ├── BottomUtilityDrawer.vue
│   ├── BottomUtilityMenu.vue
│   ├── CommandBar.vue
│   ├── HistorySummaryDrawer.vue
│   └── DebugLogPanel.vue
├── game/
│   ├── EntrySequence.vue
│   ├── AchievementToast.vue
│   ├── DiscoveryToast.vue
│   └── QuestCompletionCard.vue
└── shared/
    ├── EntityChip.vue
    ├── StatusDot.vue
    ├── TypeIcon.vue
    ├── ProgressiveDisclosure.vue
    └── MoreActionsMenu.vue
```

## 21.3 Stores

```text
frontend/src/stores/
├── auth.ts
├── session.ts
├── decisionCenter.ts
├── worldMap.ts
├── contextSummary.ts
├── agents.ts
├── tasks.ts
├── search.ts
├── history.ts
├── commands.ts
└── connection.ts
```

## 21.4 API

```text
frontend/src/api/
├── client.ts
├── decisionCenter.ts
├── world.ts
├── map.ts
├── search.ts
├── history.ts
├── commands.ts
└── session.ts
```

## 21.5 Types

```text
frontend/src/types/
├── decision.ts
├── map.ts
├── context.ts
├── agent.ts
├── task.ts
├── search.ts
├── history.ts
├── command.ts
└── common.ts
```

---

# 22. Pinia Store SPEC

## 22.1 decisionCenter store

```ts
export interface DecisionCenterState {
  focus: FocusSummary | null
  decisionEvents: DecisionEvent[]
  activeTask: TaskCard | null
  nextBestAction: DecisionOption | null
  quickQueries: QueryHint[]
  loading: boolean
  error: string | null
}
```

Actions：

```ts
loadDecisionCenter(): Promise<void>
executeDecisionOption(eventId: string, optionId: string): Promise<void>
queryDecisionCenter(query: string): Promise<void>
dismissDecision(eventId: string): Promise<void>
snoozeDecision(eventId: string): Promise<void>
applyStatePatch(patch: StatePatch): void
```

## 22.2 worldMap store

```ts
export interface WorldMapState {
  mode: 'focus' | 'route' | 'agent' | 'event'
  nodes: SemanticMapNode[]
  edges: SemanticMapEdge[]
  agentPresences: AgentMapPresence[]
  highlightedPath: string[]
  currentSpaceId: string | null
  selectedEntityId: string | null
  loading: boolean
}
```

Actions：

```ts
loadFocusMap(): Promise<void>
switchMapMode(mode: WorldMapState['mode']): void
highlightPath(spaceIds: string[]): void
highlightAgent(agentId: string): void
handleMapEntityClick(entityId: string): Promise<void>
applyMapPatch(patch: FocusMapPatch): void
```

## 22.3 contextSummary store

```ts
export interface ContextSummaryState {
  summary: ContextSummary | null
  expandedSections: string[]
  loading: boolean
}
```

Actions：

```ts
loadContextSummary(): Promise<void>
toggleSection(sectionId: string): void
runQuickQuery(query: string): Promise<void>
applyContextPatch(patch: Partial<ContextSummary>): void
```

---

# 23. 后端 API 协作 SPEC

## 23.1 进入世界

> **已实施**：见 §0.1，`GET /api/v1/world-sessions/current` 返回首屏聚合；下列为早期草案。

### `POST /api/v1/mvp/world/enter`（草案，勿实现）

用途：

进入世界并返回首屏低负担数据。

响应：

```json
{
  "success": true,
  "data": {
    "session": {},
    "decision_center": {},
    "focus_map": {},
    "context_summary": {},
    "quick_queries": [],
    "display_policy": {}
  },
  "error": null
}
```

## 23.2 获取决策中心

### `GET /api/v1/decision-center?session_id={session_id}`

返回：

1. 当前焦点。
2. 待决策事件。
3. 当前任务。
4. 下一步动作。
5. 快捷查询。

## 23.3 执行决策动作

### `POST /api/v1/decision-center/action`

请求：

```json
{
  "session_id": "sess_001",
  "decision_event_id": "dec_001",
  "option_id": "go_bridge"
}
```

响应：

```json
{
  "success": true,
  "data": {
    "result": {
      "summary": "你已前往长桥。",
      "status": "completed"
    },
    "state_patch": {
      "current_space_id": "long_bridge",
      "resolved_decision_event_ids": ["dec_001"],
      "new_decision_events": [],
      "active_task": {},
      "map_patch": {},
      "context_summary": {}
    }
  },
  "error": null
}
```

## 23.4 查询决策中心

### `POST /api/v1/decision-center/query/stream`（仅 `mode=aico`）

请求体可选 **`thread_id`**（与前端 `activeAicoThreadId` 对齐）：同一 **user + thread_id** 的新 query **自动 cancel** 仍在进行的 stream（服务端 registry；前端 Stop / 发送前 cancel 为双保险）。

SSE：`data: {json}\n\n`，`kind` 为 `meta` / `delta` / `end` / `error` / `cancelled` / `state_patch`。首条 HTTP `meta` 含 `scope=stream` 与 `stream_id`。tick 内 `meta` 含 `scope=tick`、`phase`（`plan`/`do`/`check`/`action`）、可选 `client_hint`。Act 开始前 UI 清空当前 assistant 气泡再流式终稿。`error.code=llm_timeout` 时前端展示 i18n 超时文案（zh「模型响应超时，请稍后重试」/ en「Model response timed out. Please try again.»）。`error.code=draft_incomplete` 时展示 i18n 未完成回答文案（zh「未能完成回答，请稍后重试或换一种问法」/ en「Could not complete the answer…»）。响应头：`Cache-Control: no-cache`、`X-Accel-Buffering: no`。代理需关闭缓冲（Nginx `proxy_buffering off`）。

**Stop / 发送（方案 A）**：流式进行中 **Stop** 与 **发送** 同时可用；**发送** = 停止当前 stream 并提交新 query（不禁用发送按钮）。

### `POST /api/v1/decision-center/query/stream/cancel`

请求：`{ "stream_id": "<from meta>" }`。

### `POST /api/v1/world-history/conversations/archive`

`logout` 前打包 `aico_threads[]` 与 `command_conversation[]`。

### `POST /api/v1/decision-center/query`

请求：

```json
{
  "session_id": "sess_001",
  "query": "为什么建议去中心广场？",
  "scope": "auto"
}
```

响应：

```json
{
  "success": true,
  "data": {
    "answer": "中心广场连接 F1-F6，是前往 F3 培训中心的中转点，也是多个 Agent 的活动区域。",
    "related_decision_events": ["dec_001"],
    "related_task_id": "first_enter_campusworld",
    "suggested_actions": [
      {
        "label": "继续前往长桥",
        "actionType": "execute_command",
        "command": "go north"
      }
    ]
  },
  "error": null
}
```

## 23.5 查询地图

### `POST /api/v1/map/query`

请求：

```json
{
  "session_id": "sess_001",
  "world_id": "hicampus",
  "query": "Agent 都在哪里？",
  "mode": "auto"
}
```

响应：

```json
{
  "success": true,
  "data": {
    "mode": "agent",
    "answer": "当前已发现 4 个 Agent：AICO 在大门，地图精灵在中心广场，培训服务 Agent 在 F3，报修 Agent 在 F6。",
    "map_patch": {
      "focus_mode": "agent",
      "highlighted_agent_ids": ["aico", "map_spirit", "training_bot", "repair_bot"],
      "visible_space_ids": ["hicampus_gate", "central_plaza", "f3_training_center", "f6_service_center"]
    }
  },
  "error": null
}
```

## 23.6 搜索

### `POST /api/v1/search`

请求：

```json
{
  "session_id": "sess_001",
  "world_id": "hicampus",
  "query": "F3",
  "types": ["space", "agent", "object", "event", "task"]
}
```

## 23.7 历史摘要

### `GET /api/v1/history/summary?session_id={session_id}`

返回历史分组摘要。

---

# 24. 后端服务建议

为支撑 UI，建议新增或复用以下服务：

```text
backend/app/services/
├── decision_center_service.py
├── event_triage_service.py
├── task_decision_service.py
├── recommendation_service.py
├── information_orchestrator.py
├── context_summary_service.py
├── semantic_map_service.py
├── map_focus_service.py
├── agent_presence_service.py
├── semantic_search_service.py
└── history_summary_service.py
```

职责：

| 服务                        | 职责               |
| ------------------------- | ---------------- |
| `DecisionCenterService`   | 生成中央决策中心数据       |
| `EventTriageService`      | 事件分类、过滤、合并       |
| `TaskDecisionService`     | 根据任务生成下一步        |
| `RecommendationService`   | 生成推荐动作和解释        |
| `InformationOrchestrator` | 编排首屏低负担信息        |
| `ContextSummaryService`   | 生成状态摘要           |
| `SemanticMapService`      | 生成语义地图           |
| `MapFocusService`         | 控制地图显示范围         |
| `AgentPresenceService`    | 管理 Agent 位置和状态   |
| `SemanticSearchService`   | 搜索空间、Agent、对象、历史 |
| `HistorySummaryService`   | 生成历史摘要           |

---

# 25. State Patch SPEC

## 25.1 数据结构

```ts
export interface StatePatch {
  currentSpaceId?: string
  resolvedDecisionEventIds?: string[]
  newDecisionEvents?: DecisionEvent[]
  activeTask?: TaskCard
  focusSummary?: FocusSummary
  mapPatch?: FocusMapPatch
  contextSummary?: Partial<ContextSummary>
  agentPresencePatch?: AgentMapPresence[]
  historyAppend?: HistoryEvent[]
  achievements?: Achievement[]
  displayPolicy?: DisplayPolicy
}

export interface FocusMapPatch {
  mode?: 'focus' | 'route' | 'agent' | 'event'
  visibleNodeIds?: string[]
  highlightedNodeIds?: string[]
  highlightedAgentIds?: string[]
  highlightedPath?: string[]
  eventPulseIds?: string[]
}

export interface DisplayPolicy {
  maxDecisionEventsVisible: number
  maxActionsPerCard: number
  maxMapNodesVisible: number
  maxAgentsHighlighted: number
  contextDefaultCollapsed: boolean
  mapDefaultCollapsed: boolean
  historyDefaultCollapsed: boolean
}
```

## 25.2 默认 display policy

```json
{
  "maxDecisionEventsVisible": 2,
  "maxActionsPerCard": 3,
  "maxMapNodesVisible": 7,
  "maxAgentsHighlighted": 3,
  "contextDefaultCollapsed": true,
  "mapDefaultCollapsed": true,
  "historyDefaultCollapsed": true
}
```

---

# 26. WebSocket SPEC

## 26.1 事件类型

```ts
export type WorldSocketEventType =
  | 'decision.created'
  | 'decision.resolved'
  | 'task.updated'
  | 'space.entered'
  | 'agent.presence.updated'
  | 'map.node.discovered'
  | 'map.path.highlighted'
  | 'achievement.unlocked'
  | 'object.discovered'
  | 'history.updated'
  | 'system.error'
```

## 26.2 消息格式

```json
{
  "event_id": "evt_001",
  "type": "agent.presence.updated",
  "timestamp": "2026-05-31T10:00:00Z",
  "session_id": "sess_001",
  "world_id": "hicampus",
  "payload": {
    "agentId": "aico",
    "currentSpaceId": "hicampus_gate",
    "status": "talking",
    "currentTask": "回答路径问题"
  }
}
```

## 26.3 前端处理

| 事件                       | 前端行为         |
| ------------------------ | ------------ |
| `decision.created`       | 重要时显示决策卡     |
| `decision.resolved`      | 移除已处理卡       |
| `task.updated`           | 更新任务卡        |
| `space.entered`          | 更新当前地点、地图、任务 |
| `agent.presence.updated` | 更新地图 Agent   |
| `map.node.discovered`    | 点亮地图节点       |
| `map.path.highlighted`   | 显示路径         |
| `achievement.unlocked`   | 显示成就         |
| `object.discovered`      | 生成对象发现卡或历史摘要 |
| `history.updated`        | 更新历史摘要       |
| `system.error`           | 显示错误卡或状态提示   |

---

# 27. 路由集成 SPEC

## 27.1 路由建议

保留现有路由，并对 `/works` 进行升级：

```ts
{
  path: '/works',
  name: 'Works',
  component: () => import('@/views/WorldInteractionView.vue'),
  meta: { title: 'Works', requiresAuth: true }
}
```

新增可选演示总结页：

```ts
{
  path: '/demo/summary',
  name: 'DemoSummary',
  component: () => import('@/views/DemoSummaryView.vue'),
  meta: { title: '演示总结', requiresAuth: true }
}
```

## 27.2 认证约束

1. 继续使用当前路由守卫。
2. 未登录访问 `/works` 时跳转登录。
3. 登录后回到安全 redirect。
4. access token 不应持久化到 localStorage/sessionStorage。
5. logout 后立即清空用户相关 store。

---

# 28. UI 文案规范

## 28.1 首页文案

```text
CampusWorld
进入一个由 Agent 编排的园区语义世界
```

价值点：

```text
看见空间、Agent 与任务
系统主动整理你需要关注的事情
通过点击、查询和对话完成行动
```

主按钮：

```text
进入 HiCampus
```

## 28.2 中央区域文案

不推荐：

```text
你可以问我下一步做什么。
```

推荐：

```text
下一步建议：前往长桥。
[前往长桥] [查看路线] [为什么？]
```

不推荐：

```text
请输入你想查询的问题。
```

推荐：

```text
还想了解：
[Agent 都在哪里？] [当前任务是什么？] [刚才发生了什么？]
```

## 28.3 错误文案

不推荐：

```text
COMMAND_FAILED
```

推荐：

```text
这一步暂时无法执行，因为当前空间没有通往 F3 的直接路径。
[查看路线] [返回当前任务] [稍后]
```

---

# 29. 响应式 SPEC

## 29.1 桌面优先

优先支持：

1. 1440px。
2. 1280px。
3. 1024px。

## 29.2 窄屏顶部

```text
CampusWorld     ⌘     ☰
```

点击 `☰` 打开全局菜单：

```text
HiCampus
Focus 模式
Guest

全局
- 搜索 / 命令
- 切换视图
- 重新开始演示

区域
- 地图
- 决策中心
- 状态摘要
- 历史
```

## 29.3 窄屏顺序

```text
顶部
决策中心
地图摘要
状态摘要
底部工具
```

地图默认折叠为：

```text
地图：当前位置 → 长桥 → 中心广场
[展开地图]
```

---

# 30. MVP 演示流程验收

## 30.1 零输入主流程

用户不输入任何文字，完成：

```text
打开 /works
→ 进入 HiCampus
→ 查看当前任务
→ 点击前往长桥
→ 点击继续前往中心广场
→ 点击前往 F3
→ 点击查看投影仪
→ 点击创建模拟报修
→ 查看完成总结
```

## 30.2 演示完成后显示

```text
任务完成

你已经完成一次从入口到 F3 的探索，并触发了模拟服务动作。

完成内容：
1. 进入 HiCampus
2. 到达中心广场
3. 找到 F3
4. 查看设备
5. 创建模拟报修

[查看探索总结] [继续探索 Agent] [重新开始]
```

---

# 31. 前端测试验收

必须覆盖：

1. 顶部常驻元素不超过 5 个。
2. `/works` 渲染 `WorldInteractionView`。
3. 首屏展示决策中心。
4. 当前任务卡可见。
5. 下一步推荐可见。
6. 用户不输入文字可执行主流程。
7. 点击决策动作后卡片更新。
8. 已处理事件自动收起。
9. 地图默认节点不超过 7 个。
10. 地图 Agent 不超过默认高亮数量。
11. 点击 Agent 节点生成摘要卡。
12. 地图菜单能切换 Agent / Route 模式。
13. 状态摘要默认简洁。
14. 决策中心 task-zone 与 conversation-zone 分区；会话区可独立滚动。
15. Command 查询结果可展开（默认 120px）；展示 `results[]` 或完整 `command_result.message`。
16. AICO 模式 HTTP SSE：**LLM provider 真流式** `delta`（Act / 符合条件的 Do 末轮）+ `scope=tick` 阶段 meta 状态行；响应头 `Cache-Control: no-cache`、`X-Accel-Buffering: no`；loading 时 **Stop** 可中止（客户端 + 服务端 cancel）。
17. AICO 支持新对话与线程切换；Command 单线程无切换器。
18. `logout` 后 `GET /world-history/summary` 可见归档的 AICO / Command 会话摘要。
19. 搜索 F3 能返回路线动作（Command 同步查询路径）。
20. 历史默认折叠。
21. 命令栏默认折叠。
22. WebSocket 更新 Agent 状态后地图变化（Phase 2+）。
23. 错误显示为可读卡片。
24. 窄屏下顶部压缩为 `CampusWorld / ⌘ / ☰`（Phase 2+）。

---

# 32. 后端协作验收

必须满足（路径以 §0.1 为准）：

1. `GET /api/v1/world-sessions/current` 返回首屏聚合数据（含 `focus_map`、`context_summary`、`decision_center`）。
2. 决策中心事件来自用户任务队列，而非 UI 触发的 `task create`。
3. `POST /api/v1/decision-center/actions` 能执行决策动作（经 command layer）。
4. `POST /api/v1/decision-center/query` 支持 Command 同步查询（含 `state_patch`）；`mode=aico` 返回 400 并提示流式端点。
5. `POST /api/v1/decision-center/query/stream` + cancel 支持 AICO SSE。
6. `POST /api/v1/world-history/conversations/archive` 支持 logout 会话归档。
7. `POST /api/v1/semantic-map/query` 能返回地图 patch。
8. `POST /api/v1/world-search` 能搜索空间、Agent、对象、命令等。
9. `GET /api/v1/world-history/summary` 能返回历史分组摘要（含归档会话）。
10. `context_summary` 可含 `lastHandledTask`（最近 done/cancelled 过渡）。
11. 后端命令系统仍是动作执行事实入口。
12. UI 层不得复制命令行为。
13. 世界包数据不得硬编码到前端。
14. Agent 位置和状态来自后端。
15. 任务状态来自后端。
16. 重复事件能合并。
17. 背景事件不进入中央区域。
18. 错误不泄露 traceback。

---

# 33. Definition of Done

本 UI 交互优化完成定义：

1. `/works` 成为 CampusWorld 主世界交互界面。
2. 顶部状态栏极简，只保留全局锚点和入口。
3. 地图、决策中心、状态摘要、底部工具各自有区域菜单。
4. 顶部不展示当前地点、任务详情、Agent 数量和日志。
5. 中央区域以决策事件、当前任务、下一步动作为主。
6. 自然语言输入是查询与解释入口，不是主流程必需入口。
7. 用户无需输入文字即可完成第一阶段 MVP 主流程。
8. 地图默认只显示当前相关空间、Agent 和路径。
9. Agent 在地图上有位置和状态。
10. 状态摘要默认简洁，只展示当前关键上下文。
11. 搜索能召回空间、Agent、对象、任务和历史。
12. 历史和命令默认折叠。
13. 事件经过过滤、合并和摘要后再展示。
14. 推荐动作可一键执行。
15. 推荐动作可解释。
16. 异常和阻塞事件能上浮到中央或顶部。
17. 组件结构符合当前 Vue 3 + Pinia + Router 架构。
18. API 调用集中在 `frontend/src/api/`。
19. 用户状态集中在 Pinia stores。
20. 后端动作通过 command layer 执行。
21. 新用户 30 秒内能知道：我在哪、要处理什么、下一步做什么。
22. 3 分钟内可完成完整演示。
23. UI 不呈现传统后台风格。
24. CampusWorld 的“下一代园区语义世界入口”体验成立。
