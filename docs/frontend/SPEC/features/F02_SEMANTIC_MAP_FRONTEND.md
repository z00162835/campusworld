# Semantic Map Frontend SPEC

> **Architecture Role**: 语义地图是 CampusWorld `/works` 工作台左侧区域的**只读空间浏览层**。前端负责将后端 `focus_map` / `map_patch` 渲染为可钻取、可选中、可平移缩放的 North-up 视图；**不**直接修改玩家 `location_id`，移动仍由命令层或决策中心推荐触发。

> **SSOT**:
> - 本文件：前端地图组件、store、布局算法、交互与验收。
> - 数据契约：[`frontend/src/types/world.ts`](../../../../frontend/src/types/world.ts)（`FocusMap`、`SemanticMapNode` 等）。
> - 后端生成：[`backend/app/services/world_interaction/semantic_map_service.py`](../../../../backend/app/services/world_interaction/semantic_map_service.py)。
> - REST 端点：[`docs/api/SPEC/SPEC.md`](../../../api/SPEC/SPEC.md) `/semantic-map/*`。
> - 工作台布局与产品约束：[`F01_CAMPUSWORLD_NextUI.md`](F01_CAMPUSWORLD_NextUI.md) §8（产品级摘要；渲染细节以本文件为准）。

## Status

- **Version**: v1.1（补充 §0 设计原则与四层空间语义模型）
- **Owner**: frontend 模块
- **Module key**: `frontend.semantic_map`

## 目录

0. [设计原则与语义模型](#0-设计原则与语义模型)
1. [范围与非目标](#1-范围与非目标)
2. [文件与组件](#2-文件与组件)
3. [API 客户端](#3-api-客户端)
4. [Pinia：`worldMap` store](#4-piniaworldmap-store)
5. [数据模型摘要](#5-数据模型摘要)
6. [视图层级与钻取](#6-视图层级与钻取)
7. [布局模式与渲染](#7-布局模式与渲染)
8. [视口交互](#8-视口交互)
9. [地图内模式](#9-地图内模式)
10. [点击与中央联动](#10-点击与中央联动)
11. [`map_patch` 应用](#11-map_patch-应用)
12. [与 F01 的差异与延期项](#12-与-f01-的差异与延期项)
13. [Acceptance Criteria](#13-acceptance-criteria)

## 0. 设计原则与语义模型

### 0.1 功能定位

语义地图用于**语义世界的可视化**：在同一视图中融合呈现 **空间、人、物、事**，帮助用户理解当前位置、周边实体、邻接关系与待处理语义。

- **空间**：世界—楼栋—楼层—房间四层钻取，及层间/层内连接边。
- **人**：房间 occupant、Agent presence（`roomOccupants`、`agentPresences`）。
- **物**：object / item 分组与成员（logical 侧栏、`groupMembers`）。
- **设备**：device 分组与成员；空间摘要 §3 设备段。
- **事**：任务路线、事件热点、决策联动（`mode: route|event`、`activeEventIds`、决策中心卡片）；**不**单独增加空间层级。

设计参考**游戏地图**的信息分层与钻取惯例（breadcrumb、选中高亮、邻接出口、楼层切换），但**不追求显示特效**。North-up 罗盘、等距楼层 tile、minimap 等视觉手段均服务于**语义可理解**与**易用**，而非装饰性动效。

### 0.2 空间四层模型

语义地图中的**空间**只体现以下 **4 个层次**，不在 UI 上引入额外的空间归纳层：

| 层级 | 用户语义 | 展示要点 |
|------|----------|----------|
| **世界** | 世界入口 | 可见各**楼栋**，以及**楼栋之间的连接空间**（门、桥、广场等 outdoor 锚点与楼栋间边） |
| **楼栋** | 单体建筑 | 进入后**默认显示首层**（最低楼层 / 大堂层）；可通过楼层侧栏选择其他层 |
| **楼层** | 建筑内一层 | 该层房间平面（grid）或列表回退；无平面图时提示「平面图未就绪」 |
| **房间** | 最小空间单元 | 展示**人、物、设备**，以及**与之空间连通的其他空间**（exit 节点、邻接边、摘要 §4） |

Hub / 世界包元数据、outdoor spot 等图节点属于上述层级的**导航与连接表达**，不构成第五层用户可见「空间层」。

### 0.3 各层行为约定

1. **世界层**：从世界入口（菜单「打开全图」或 Hub 钻取）进入后，用户应能一览楼栋布局及楼栋间连接空间；`campus-grid` / `hierarchy` 布局服务于此读图目标。
2. **楼栋 → 楼层**：点击楼栋进入楼层视图时，**默认锚定首层**（后端 `_default_floor_for_building`）；`floorStack` 侧栏可切换至其他楼层。
3. **楼层 → 房间**：点击房间节点或 floor 列表项进入房间层；floor 有 `map_grid_*` 时用等距平面，否则用 `floorRoomList`。
4. **房间层**：画布或侧栏呈现 occupant / device / item 与 exit 邻接；选中后在决策中心 `MapSpaceSummaryCard` 展示与 `space` 命令一致的四段摘要。**不**默认触发玩家移动（`go`）。

### 0.4 技术字段映射

`focus_map.viewLayer` 与产品四层的对应关系（实现细节，不改变 §0.2 的用户模型）：

| 产品层级 | 典型 `viewLayer` / `layout` |
|----------|----------------------------|
| 世界 | `world` / `campus` + `campus-grid` 或 `hierarchy` |
| 楼栋 | `building` + `hierarchy` / `list`（过渡；常直接进入 floor） |
| 楼层 | `floor` + `grid` 或 `list` |
| 房间 | `room` + `logical`（或兼容 `compass` 平面回退） |

`gate` / `bridge` / `plaza` 等节点表示**世界层**上的连接空间；选中后按 room 层展示其空间摘要与邻接，不扩展层级计数。

## 1. 范围与非目标

### In scope

- `/works` 内 `FocusSemanticMap` 面板：区域菜单、breadcrumb、画布、minimap、侧栏面板。
- `useWorldMapStore` 对 `worldSession.interactionState.focus_map` 的读写与 API 编排。
- `semanticMapApi` HTTP 封装。
- `useSemanticMapRender` + `mapLayout.ts` 纯函数布局/投影。
- 选中空间后 `DecisionCenterFlow` 内 `MapSpaceSummaryCard` 展示（`space` 命令 SSOT 四段摘要）。

### Out of scope (deferred)

- F01 §8.2「显示」子菜单（任务目标 / 已发现对象 / 事件热点 / 收起非相关节点）——**未实现**。
- 独立子组件文件（`SpaceNode.vue`、`PathOverlay.vue` 等）——逻辑内联于 `FocusSemanticMap.vue`。
- 玩家自动 `go`、传统详情页跳转、地图内任务路径自动展开全图（产品约束见 F01 §8.6–8.7）。

## 2. 文件与组件

| 路径 | 职责 |
|------|------|
| `frontend/src/components/map/FocusSemanticMap.vue` | 地图 UI 壳：菜单、breadcrumb、画布、toolbar、侧栏、minimap |
| `frontend/src/components/map/MapSpaceSummaryCard.vue` | 决策中心内的空间摘要卡（非地图 pane 内嵌） |
| `frontend/src/composables/useSemanticMapRender.ts` | 节点/边/Agent/minimap/楼层等距 tile 的 computed 渲染模型 |
| `frontend/src/utils/mapLayout.ts` | 方向文案、等距网格、logical/campus 边裁剪、campus 脊线绕行 |
| `frontend/src/stores/worldMap.ts` | 钻取、选中、模式切换、patch、摘要加载 |
| `frontend/src/api/semanticMap.ts` | `/semantic-map/*` 客户端 |
| `frontend/src/types/world.ts` | TypeScript 契约（真源） |

单元测试：`FocusSemanticMap.spec.ts`、`worldMap.spec.ts`、`mapLayout.spec.ts`。

## 3. API 客户端

`semanticMapApi`（[`frontend/src/api/semanticMap.ts`](../../../../frontend/src/api/semanticMap.ts)）：

| 方法 | HTTP | 用途 |
|------|------|------|
| `getFocus` | `GET /semantic-map/focus` | 刷新当前层 `focus_map`（query: `view_layer`, `anchor_id`, `mode`, `selected_entity_id`） |
| `executeAction` | `POST /semantic-map/actions` | `drill` 切换视图层；`select` 高亮实体并返回 `space_summary` |
| `getSpaceSummary` | `GET /semantic-map/space-summary` | 按 `node_id` 拉取 `space` 命令 SSOT 摘要 |
| `query` | `POST /semantic-map/query` | 自然语言/关键词查询，返回 `map_patch` |

首屏 `focus_map` 由 `GET /world-sessions/current` 聚合注入 `worldSession`；地图 store 不单独 bootstrap。

## 4. Pinia：`worldMap` store

状态源：`worldSession.interactionState.focus_map`（computed `map`）。

### 对外 computed

`mode`, `viewLayer`, `breadcrumb`, `floorPlanReady`, `floorRoomList`, `floorStack`, `floorGridBounds`, `roomOccupants`, `nodes`, `edges`, `agentPresences`, `selectedEntityId`, `selectedSpaceSummary`, `mapLoading`。

### 核心 actions

| Action | 行为 |
|--------|------|
| `fetchFocus` | `getFocus` → `applyFocusMap` |
| `drillTo(layer, anchorId?)` | `executeAction(drill)`；清空 `selectedSpaceSummary` |
| `navigateBreadcrumb(crumb)` | 按 `crumb.role`（`hub` / `world` / `campus_spot` / `building` / `floor` / `room`）映射到 `drillTo` |
| `drillToCurrentRoom` | breadcrumb 中 `room` 层或默认 `drillTo('room')` |
| `drillToOutdoorSpot` | `drillTo('room', nodeId)` + `loadSpaceSummary` |
| `selectMapTarget` | `executeAction(select)`；合并 `space_summary` 或 fallback `getSpaceSummary` |
| `handleNodeClick` | 按节点 `type` / 当前 `viewLayer` 分发 drill 或 select（见 §10） |
| `switchMapMode` | 同层 `fetchFocus` 切换 `mode` |
| `applyMapPatch` | 全量 `focus_map` 替换，或 `drillTo` / 高亮 / 路径 / Agent 合并 |
| `searchMap` | `semanticMapApi.query` → `applyMapPatch` |
| `clearMapSelection` | 清除摘要与节点 `active` 高亮（保留 `current`） |
| `reset` | logout 时由 session 清理链调用 |

并发：`beginMapRequest` / `mapRequestSeq` 丢弃过期响应；加载中 `mapLoading` + 画布 `pointer-events: none`。

## 5. 数据模型摘要

完整字段以 [`frontend/src/types/world.ts`](../../../../frontend/src/types/world.ts) 为准。相对 F01 §8.5 的**实现扩展**：

| 字段 / 类型 | 说明 |
|-------------|------|
| `MapViewLayer` | 含 `'world'`（Hub 全图入口层） |
| `MapBreadcrumb.role` | `hub` / `world` / `campus_spot` / … 驱动 breadcrumb 导航 |
| `SemanticMapNode.logicalZone` | `hub` / `occupant` / `device` / `item` / `exit`（logical 房间布局） |
| `SemanticMapNode.groupMembers` | 房间设备/物品分组成员 |
| `SemanticMapNode.mapGridCol/Row/SpanW/SpanH` | 楼层等距平面坐标 |
| `FocusMap.floorStack` | 楼层切换侧栏 |
| `FocusMap.floorGridBounds` | 楼层网格线范围（与 `mapLayout` 常量对齐） |
| `FocusMap.roomOccupants` | 房间 occupant 列表面板 |
| `MapPatch.agentPresences` | patch 级 Agent 合并 |

节点/边数量上限由后端 `display_policy`（`maxMapNodesVisible`、`maxFloorNodesVisible`、`maxCampusNodesVisible` 等）在服务端聚合；前端**不**二次截断。

## 6. 视图层级与钻取

产品上的空间四层（世界 → 楼栋 → 楼层 → 房间）见 [§0.2](#02-空间四层模型)。下表为 `viewLayer` 钻取与布局的技术映射。

| `viewLayer` | 典型 `layout` | 进入方式 |
|-------------|---------------|----------|
| `room` | `logical` | 默认（玩家 `location_id` 所在房间） |
| `floor` | `grid` 或 `list` | 点击 `floor` / floor cluster；breadcrumb |
| `building` | `hierarchy` / `list` | 点击 `building` / building cluster |
| `campus` | `campus-grid` 或 `hierarchy` | 点击 `world` 节点；菜单「打开全图」→ `drillTo('world')` 再 campus |
| `world` | `hierarchy` | Hub 层 outdoor 锚点（gate/bridge/plaza） |

`floorPlanReady === false` 时：显示 `floorPlanNotReady` 提示 + `floorRoomList` 列表（无 canvas）。  
`layout === 'grid'` 且存在 `mapGridCol/Row` 时：等距 tile 画布 + 可选 `floorStack` 侧栏。

Breadcrumb：`navigateBreadcrumb` 必须尊重 `role`（例如 `campus_spot` → `drillToOutdoorSpot`）。

## 7. 布局模式与渲染

渲染入口：`useSemanticMapRender` + `FocusSemanticMap` 模板。

| `layout` | 渲染策略 |
|----------|----------|
| `logical` | Hub 椭圆环（`logicalHubRing`）；hub-and-spoke 边在节点边界裁剪（`trimLogicalRoomEdge`）；`cluster:room:*:device|item` **不**画在画布上，改 dock 到左侧 `room-content-panels`；过滤 `logical_group_*` 边 |
| `grid` | 2:1 等距投影（`gridSpanToIsoTile`）；SVG 网格线 + 伪 3D tile；非 grid 坐标节点仍用 dot 叠加 |
| `campus-grid` | 同语义坐标系；building/outdoor 边 rim 裁剪（`trimCampusGridEdge`）；`campusEdgeKind` 样式；`inter-building` 穿越 outdoor spine 时用二次贝塞尔绕行（`campusEdgeRoute`） |
| `list` / `hierarchy` / `compass` | 平面 `(x,y)` 节点 + SVG 边；compass 仅显示固定北向玫瑰（与 layout 名无关，始终渲染） |

边标签：`formatDirectionLabel` → i18n `worldInteraction.map.direction.*`；锁定边不显示方向标签。

Agent：`agentPresences` 锚定到 `currentSpaceId` 对应节点；无锚点时右下角 floating 徽章。

Minimap：132×88 SVG；节点矩形 + 当前视口框（只读，无 click-to-pan）。

常量（与后端 floor grid 对齐）：`MAP_GRID_CELL_PX=4`, `MAP_GRID_ORIGIN_X/Y=10`（[`mapLayout.ts`](../../../../frontend/src/utils/mapLayout.ts)）。

## 8. 视口交互

| 交互 | 实现 |
|------|------|
| 拖拽平移 | 画布 `mousedown` + window `mousemove` |
| 滚轮缩放 | `wheel` → `zoomBy`；范围 35%–300% |
| Toolbar | 四向 pan、zoom in/out、`resetView` |
| 自适应 | `ResizeObserver` + `fitView`（layout 或数据变化时 `resetView`） |

变换：`translate(pan) scale(fitScale * userZoom)`，`transform-origin: 0 0`。

## 9. 地图内模式

区域菜单暴露：`route`、`agent`；下拉含 `focus`、`event`、`resetView`。另有「打开全图」「回到当前房间」。

| `mode` | UI 效果 |
|--------|---------|
| `focus` | 默认 |
| `route` | `.mode-route` 加粗 `edge.recommended` |
| `agent` | `.mode-agent` Agent 节点外发光 |
| `event` | 样式预留；热点高亮主要由后端 `status` / patch 驱动 |

切换：`switchMapMode` → 同层 `getFocus`。

## 10. 点击与中央联动

`handleNodeClick` 规则（摘要）：

| 节点 / 上下文 | 动作 |
|---------------|------|
| `cluster:room:*` | select 首个 member |
| `cluster:floor:*` | `drillTo('room', drillAnchorId)` |
| 其他 `cluster` | `drillTo('building', drillAnchorId)` |
| `world` | `drillTo('campus', id)` |
| `gate`/`bridge`/`plaza` @ `world` | `drillTo('campus', drillAnchorId)` |
| `hub` | 无操作 |
| `building` | `selectEntity`（drill + space inspect） |
| `floor` | `selectEntity`（drill + space inspect） |
| outdoor spot @ `campus` | `drillToOutdoorSpot` |
| drillable room @ `floor` | `drillTo('room')` 或 outdoor spot 路径 |
| `object` / `device` / `agent` | `selectEntity(..., { viewLayer: 'room' })` |
| `exit` @ `room` | `drillTo('room', id)` |
| 默认 | `selectEntity(id)` |

选中后：`selectedInspect` 驱动地图内 `MapEntityInspectSheet`（互斥单槽）。**不**触发 `go`。

菜单文案键：`worldInteraction.map.*`（en/zh）。

## 11. `map_patch` 应用

`applyMapPatch` 优先级：

1. 若含 `focus_map` → 整包替换。
2. 否则 `viewLayer` → `drillTo`；仅 `mode` → `fetchFocus`。
3. 就地修改：`highlightedNodeIds`（`active` / `current` / `visible`）、`highlightedPath`、`mode`、`agentPresences` 合并。

来源：`POST /semantic-map/query`、全局搜索、`state_patch.map_patch`（WebSocket / 决策查询）。

## 12. 与 F01 的差异与延期项

| F01 描述 | 当前实现 |
|----------|----------|
| §8.2 显示开关菜单 | 未实现 |
| §21 独立 map 子组件目录 | 仅 2 个 Vue 文件；渲染内联 |
| §21 `api/map.ts`、`types/map.ts` | 实际为 `api/semanticMap.ts`、`types/world.ts` |
| §23.5 `POST /map/query` | 应为 `POST /semantic-map/query` |
| `compass` layout 作为 room 默认 | 后端 room 默认 `logical`；`compass` 仍兼容为平面布局 |
| 对象/事件独立 marker 组件 | 通过节点 type + 侧栏/摘要表达 |


## 14. 实体 Inspect 面板

地图画布内底部 dock sheet（`MapEntityInspectSheet`），与 pan/zoom/minimap 共存。

### 14.1 互斥状态机

- Store：`selectedInspect: MapInspectSelection | null`、`loadingInspect`
- `selectEntity` 先清空再请求；成功写入 space（`SpaceSummaryData`）或 entity（`EntityInspectData`）
- `drillTo` / breadcrumb / `clearMapSelection` / 点击 canvas 空白 → 清空
- 搜索 / `map_patch` 高亮 → 同时 `selectEntity`

### 14.2 后端契约

| 路径 | 说明 |
|------|------|
| `POST /semantic-map/actions` `select` | 返回 `focus_map` + `space_summary`（space）或 `entity_inspect`（非 space） |
| `GET /semantic-map/entity-inspect` | refresh；`node_id` 或 `agent_id`（= `agentPresences.agentId`） |

`entity_inspect` 由 `entity_inspect_service` 委托 `LookCommand` 构建；`actions[]` 来自节点 `attributes.capabilities` / `inspect_capabilities`。

### 14.3 Agent inspect

只读摘要；对话 action **deferred**（待 Agent Web 对话 follow-up）。

### 14.4 非目标

- 事件（事）inspect：仍走决策中心 Event 卡
- 决策中心不再承载 `MapSpaceSummaryCard`

## 13. Acceptance Criteria

- [ ] 语义地图遵循 [§0](#0-设计原则与语义模型)：四层空间钻取；世界层可见楼栋与连接空间；进楼栋默认首层；房间层展示人/物/设备及邻接空间。
- [ ] `FocusSemanticMap` 在 floor 无 grid 时显示 list + not-ready 提示；有 grid 时渲染等距 tile + floor stack。
- [ ] logical room：device/item cluster 出现在侧栏 panel，不占画布节点位。
- [ ] campus-grid：spine / inter-building / connector 边样式与绕行曲线可见。
- [ ] breadcrumb 与菜单 drill 不改变玩家 `location_id`（仅 API mock / integration 验证）。
- [ ] 节点点击更新 `MapSpaceSummaryCard`，不 dispatch `go`。
- [ ] `applyMapPatch` 高亮与 `searchMap` 可切换 `viewLayer`。
- [ ] pan/zoom/minimap 在 layout 切换后 `resetView` 不溢出容器。
- [ ] `npm run type-check` 与 `npm run test -- --run` 通过 map 相关 spec。

已实现项勾选见 [`../ACCEPTANCE.md`](../ACCEPTANCE.md) CampusWorld Interaction / Semantic map Phase A–C。
