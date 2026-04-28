# Spaces 主页面需求规格 (SPEC)

> **版本**: v0.1.0
> **日期**: 2026-04-12
> **状态**: 初稿

---

## 1. 概述

### 1.1 页面目的

Spaces 页面为用户提供虚拟世界中的语义空间查询与管理界面。用户可通过本页面浏览、搜索和筛选不同层次的空间实体（世界、建筑、楼层、房间），了解其全局语义描述和空间结构。

### 1.2 核心功能

- **层次化空间浏览**：通过 Tab 切换 World / Building / Floor / Room 四个语义视图
- **统一搜索**：跨所有空间层次的关键字搜索
- **条件过滤**：每个视图支持特定筛选条件
- **视图模式切换**：支持列表视图和卡片视图两种展示模式
- **空间详情**：点击空间实体查看详细信息

### 1.3 用户交互流程

```
用户进入 Spaces 页面
    │
    ├─► 默认显示 World 视图 (Tab 1)
    │       │
    │       ├─► 输入关键字 → 即时搜索/过滤
    │       │
    │       ├─► 选择筛选条件 → 列表/卡片更新
    │       │
    │       └─► 点击实体 → 查看详情/操作
    │
    ├─► 切换到 Building 视图 (Tab 2)
    │       │
    │       ├─► 可按 world 筛选
    │       ├─► 可按 building_type 筛选
    │       └─► ... 同上
    │
    ├─► 切换到 Floor 视图 (Tab 3)
    │       │
    │       ├─► 可按 building 筛选
    │       ├─► 可按 floor_number 筛选
    │       └─► ... 同上
    │
    └─► 切换到 Room 视图 (Tab 4)
            │
            ├─► 可按 floor 筛选
            ├─► 可按 room_type 筛选
            └─► ... 同上
```

---

## 2. 信息架构

### 2.1 空间层次定义

| 层次 | 类型代码 (type_code) | 说明 | 父级 |
|------|---------------------|------|------|
| World (世界) | `world` | 完整虚拟世界，包含多个建筑 | 无 |
| Building (建筑) | `building` | 建筑全局描述 | 属于某个 World |
| Floor (楼层) | `building_floor` | 楼层全局语义 | 属于某个 Building |
| Room (房间) | `room` | 房间空间语义 | 属于某个 Floor |

### 2.2 实体数据结构

> **后端确认**: 所有空间类型共用 `trait_class = SPACE`，`trait_mask = 516` (SPATIAL | LOAD_BEARING)

#### World (世界)
```typescript
interface World {
  id: number
  uuid: string
  type_code: 'world'
  name: string
  description: string
  is_active: boolean
  is_public: boolean
  access_level: string
  attributes: {
    world_type: string        // world, campus, sandbox
    theme: string             // 主题风格
    genre: string             // 类型
    max_players?: number
    is_private: boolean
    status: 'online' | 'offline' | 'maintenance'
  }
  tags: string[]
  created_at: string
  updated_at: string
}
```

#### Building (建筑)
```typescript
interface Building {
  id: number
  uuid: string
  type_code: 'building'
  name: string
  description: string
  is_active: boolean
  is_public: boolean
  attributes: {
    uns: string               // 统一编号
    building_type: string     // 教学楼, 宿舍, 食堂, 图书馆...
    building_status: string    // 正常, 维修中, 关闭
    building_code: string
    building_area: number      // 面积
    building_floors?: number   // 楼层数
    world_id?: number         // 所属世界
  }
  tags: string[]
  created_at: string
  updated_at: string
}
```

#### Floor (楼层)
```typescript
interface Floor {
  id: number
  uuid: string
  type_code: 'building_floor'
  name: string
  description: string
  is_active: boolean
  attributes: {
    floor_number: number      // 楼层编号 (1, 2, -1...)
    floor_type: string        // 普通, 地下, 屋顶
    building_id: number       // 所属建筑
    floor_area?: number       // 楼层面积
  }
  tags: string[]
}
```

#### Room (房间)
```typescript
interface Room {
  id: number
  uuid: string
  type_code: 'room'
  name: string
  description: string
  is_active: boolean
  attributes: {
    room_code: string         // 房间编号
    room_type: string         // 教室, 办公室, 实验室...
    room_floor: number        // 所在楼层
    room_area?: number        // 房间面积
    room_capacity?: number    // 容纳人数
    room_exits?: string[]     // 出口方向列表
    building_id?: number       // 所属建筑
    floor_id?: number         // 所属楼层
  }
  tags: string[]
}
```

---

## 3. UI/UX 设计

### 3.1 页面布局

```
┌──────────────────────────────────────────────────────────────────┐
│  [Sidebar]  │  [Main Content Area]                              │
│              │                                                      │
│  Logo       │  ┌──────────────────────────────────────────────┐  │
│  ─────────  │  │  Spaces                              [Search] │  │
│  Nav Items  │  │  ────────────────────────────────────────────│  │
│  - Works    │  │                                              │  │
│  - Spaces ◄ │  │  [World] [Building] [Floor] [Room]   [≡][☷] │  │
│  - Agents   │  │  ───────────────────────────────────────────│  │
│  - History  │  │                                              │  │
│              │  │  Filter Chips / Dropdowns                    │  │
│              │  │  ────────────────────────────────────────────│  │
│              │  │                                              │  │
│              │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐        │  │
│              │  │  │  Card   │ │  Card   │ │  Card   │        │  │
│              │  │  │         │ │         │ │         │        │  │
│              │  │  │  Icon   │ │  Icon   │ │  Icon   │        │  │
│              │  │  │  Name   │ │  Name   │ │  Name   │        │  │
│              │  │  │  Desc   │ │  Desc   │ │  Desc   │        │  │
│              │  │  └─────────┘ └─────────┘ └─────────┘        │  │
│              │  │                                              │  │
│              │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐        │  │
│              │  │  │  Card   │ │  Card   │ │  Card   │        │  │
│              │  │  │         │ │         │ │         │        │  │
│              │  │  └─────────┘ └─────────┘ └─────────┘        │  │
│              │  │                                              │  │
│              │  │  ───────────────────────────────────────────│  │
│              │  │  [Load More / Pagination]                   │  │
│              │  └──────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 组件结构

```
Spaces.vue (页面容器)
├── SpaceHeader (页面头部)
│   ├── Title
│   ├── GlobalSearch (统一搜索输入)
│   └── ViewModeToggle (列表/卡片切换)
├── SpaceTabs (Tab 切换)
│   ├── WorldTab
│   ├── BuildingTab
│   ├── FloorTab
│   └── RoomTab
├── FilterBar (筛选栏，根据当前 Tab 显示不同筛选器)
│   ├── WorldFilters (world_type, status)
│   ├── BuildingFilters (world, building_type, status)
│   ├── FloorFilters (building, floor_type)
│   └── RoomFilters (floor, room_type)
├── SpaceContent (内容区)
│   ├── CardGridView (卡片网格视图)
│   │   └── SpaceCard (空间卡片)
│   │       ├── CardIcon
│   │       ├── CardTitle
│   │       ├── CardDescription
│   │       └── CardMeta
│   └── ListTableView (列表视图)
│       └── SpaceRow (空间行)
│           ├── Name
│           ├── Type
│           ├── Status
│           └── Actions
└── SpaceDetailDrawer (详情抽屉)
    ├── DetailHeader
    ├── DetailAttributes
    ├── DetailDescription
    └── DetailActions
```

### 3.3 视图模式

#### 3.3.1 卡片视图 (默认)

- 响应式网格布局：`repeat(auto-fill, minmax(280px, 1fr))`
- 卡片包含：
  - **图标区域**：根据类型显示不同图标
    - World: 🌍 或 globe 图标
    - Building: 🏢 或 building 图标
    - Floor: 📑 或 layers 图标
    - Room: 🚪 或 door 图标
  - **标题**：实体名称
  - **描述**：简短描述 (最多 2 行，超出省略)
  - **标签**：显示最多 3 个标签
  - **状态指示**：在线/离线/维护状态

#### 3.3.2 列表视图

- Element Plus `el-table` 实现
- 列定义：
  | 列 | 宽度 | 说明 |
  |----|------|------|
  | 名称 | 200px | 实体名称，可点击查看详情 |
  | 类型 | 120px | 类型标签 |
  | 状态 | 100px | 状态徽章 |
  | 标签 | flex | 标签列表 |
  | 操作 | 120px | 查看详情按钮 |

### 3.4 筛选器设计

#### World 视图筛选器
| 筛选项 | 类型 | 选项 |
|--------|------|------|
| World Type | 单选下拉 | All, Campus, World, Sandbox |
| Status | 多选下拉 | Online, Offline, Maintenance |
| Public/Private | 单选下拉 | All, Public, Private |

#### Building 视图筛选器
| 筛选项 | 类型 | 选项 |
|--------|------|------|
| World | 单选下拉 | 动态获取所有 World |
| Building Type | 单选下拉 | All, 教学楼, 宿舍, 食堂, 图书馆, 办公楼, 体育馆 |
| Status | 多选下拉 | 正常, 维修中, 关闭 |

#### Floor 视图筛选器
| 筛选项 | 类型 | 选项 |
|--------|------|------|
| Building | 单选下拉 | 动态获取所有 Building |
| Floor Type | 单选下拉 | All, 普通, 地下, 屋顶 |

#### Room 视图筛选器
| 筛选项 | 类型 | 选项 |
|--------|------|------|
| Floor | 单选下拉 | 动态获取所有 Floor |
| Room Type | 单选下拉 | All, 教室, 办公室, 实验室, 会议室, 卫生间, 走廊 |
| Has Capacity | 复选框 | 仅显示有容量信息的房间 |

---

## 4. 功能规格

### 4.1 核心功能

#### F1: Tab 切换
- 点击 Tab 切换语义视图
- 切换时重置筛选条件和搜索词
- 保留用户偏好的视图模式 (卡片/列表)
- URL 可通过 query 参数反映当前 Tab: `/spaces?view=building`

#### F2: 统一搜索
- 输入框支持关键字搜索
- 搜索延迟 300ms 防抖 (debounce)
- 搜索范围：name, description, tags
- 搜索 API 参数：`name_like=${keyword}`
- 搜索框支持清空 (X 按钮)

#### F3: 条件过滤
- 每个 Tab 有专属筛选器
- 筛选器级联：选择 World 后，Building 筛选器只显示该 World 下的 Building
- 筛选条件通过 URL query 参数同步: `/spaces?view=building&world_id=1&building_type=教学楼`
- 筛选器有"重置"按钮一键清空

#### F4: 视图模式切换
- 切换按钮位于页面右上角
- 图标按钮：☷ (卡片) / ≡ (列表)
- 记住用户偏好 (localStorage)

#### F5: 分页加载
- 默认每页 24 条
- 卡片视图：无限滚动加载 (Load More)
- 列表视图：标准分页器 (el-pagination)
- 跳转到指定页

#### F6: 查看详情
- 点击卡片/行打开详情抽屉 (el-drawer)
- 抽屉显示完整实体信息
- 包含操作按钮：查看位置、编辑（需权限）、刷新

### 4.2 数据交互

#### API 端点
```
GET /api/v1/graph/nodes
    ?type_code={type_code}
    &name_like={keyword}
    &is_active=true
    &is_public={filter}
    &offset={offset}
    &limit={limit}
    &tags_any={tags}
```

#### 权限要求
- 所有操作需要 `graph.read` 权限
- 编辑操作需要 `graph.write` 权限

### 4.3 状态管理

```typescript
// stores/spaces.ts
interface SpacesState {
  // 当前视图
  activeTab: 'world' | 'building' | 'floor' | 'room'

  // 搜索和筛选
  searchKeyword: string
  filters: {
    world_id?: number
    building_id?: number
    floor_id?: number
    world_type?: string
    building_type?: string
    floor_type?: string
    room_type?: string
    status?: string[]
    is_public?: boolean
  }

  // 数据
  nodes: Record<string, SpaceNode[]>  // 按类型缓存
  totalCounts: Record<string, number>

  // UI 状态
  viewMode: 'card' | 'list'
  loading: boolean
  currentPage: number
  pageSize: number

  // 详情
  selectedNode: SpaceNode | null
  detailDrawerVisible: boolean
}
```

---

## 5. 组件清单

### 5.1 页面组件

| 组件 | 文件 | 说明 |
|------|------|------|
| SpacesPage | `views/spaces/Spaces.vue` | 页面容器 |
| SpaceHeader | `components/spaces/SpaceHeader.vue` | 页面头部 |
| SpaceTabs | `components/spaces/SpaceTabs.vue` | Tab 切换 |
| FilterBar | `components/spaces/FilterBar.vue` | 筛选栏容器 |
| SpaceContent | `components/spaces/SpaceContent.vue` | 内容区容器 |
| SpaceDetailDrawer | `components/spaces/SpaceDetailDrawer.vue` | 详情抽屉 |

### 5.2 子组件

| 组件 | 文件 | 说明 |
|------|------|------|
| WorldCard | `components/spaces/cards/WorldCard.vue` | World 卡片 |
| BuildingCard | `components/spaces/cards/BuildingCard.vue` | Building 卡片 |
| FloorCard | `components/spaces/cards/FloorCard.vue` | Floor 卡片 |
| RoomCard | `components/spaces/cards/RoomCard.vue` | Room 卡片 |
| SpaceTable | `components/spaces/SpaceTable.vue` | 列表视图表格 |
| GlobalSearch | `components/spaces/GlobalSearch.vue` | 搜索输入框 |
| ViewModeToggle | `components/spaces/ViewModeToggle.vue` | 视图切换按钮 |
| FilterChips | `components/spaces/FilterChips.vue` | 筛选标签组 |
| Pagination | `components/spaces/SpacePagination.vue` | 分页器 |

### 5.3 组件接口

```typescript
// SpaceCard.vue props
interface SpaceCardProps {
  node: SpaceNode
  type: 'world' | 'building' | 'floor' | 'room'
}

// SpaceTable.vue props
interface SpaceTableProps {
  nodes: SpaceNode[]
  loading: boolean
}

// FilterBar.vue emits
interface FilterBarEmits {
  (e: 'update:filters', filters: FilterState): void
  (e: 'reset'): void
}

// SpaceDetailDrawer.vue props
interface SpaceDetailDrawerProps {
  visible: boolean
  node: SpaceNode | null
}
```

---

## 6. 类型定义

### 6.1 类型文件位置
`src/types/space.ts`

### 6.2 完整类型定义

```typescript
// 空间节点基础类型
interface SpaceNode {
  id: number
  uuid: string
  type_code: string
  name: string
  description: string
  is_active: boolean
  is_public: boolean
  access_level: string
  attributes: Record<string, any>
  tags: string[]
  created_at: string
  updated_at: string
}

// World 类型扩展
interface World extends SpaceNode {
  type_code: 'world'
  attributes: {
    world_type: 'campus' | 'world' | 'sandbox'
    theme: string
    genre: string
    max_players?: number
    is_private: boolean
    status: 'online' | 'offline' | 'maintenance'
  }
}

// Building 类型扩展
interface Building extends SpaceNode {
  type_code: 'building'
  attributes: {
    uns: string
    building_type: string
    building_status: string
    building_code: string
    building_area: number
    building_floors?: number
    world_id?: number
  }
}

// Floor 类型扩展
interface Floor extends SpaceNode {
  type_code: 'building_floor'
  attributes: {
    floor_number: number
    floor_type: 'normal' | 'basement' | 'rooftop'
    building_id: number
    floor_area?: number
  }
}

// Room 类型扩展
interface Room extends SpaceNode {
  type_code: 'room'
  attributes: {
    room_code: string
    room_type: string
    room_floor: number
    room_area?: number
    room_capacity?: number
    room_exits?: string[]
    building_id?: number
    floor_id?: number
  }
}

// 筛选状态
interface FilterState {
  world_id?: number
  building_id?: number
  floor_id?: number
  world_type?: string
  building_type?: string
  floor_type?: string
  room_type?: string
  status?: string[]
  is_public?: boolean
}

// 视图模式
type ViewMode = 'card' | 'list'

// Tab 类型
type SpaceTab = 'world' | 'building' | 'floor' | 'room'
```

---

## 7. API 集成

### 7.1 Trait 系统 (性能优化)

后端使用 **Trait Mask** 位掩码系统实现高性能的空间过滤。所有空间类型共用 `trait_class = SPACE`，通过 `trait_mask` 进行快速过滤。

#### Trait 常量定义
文件位置：`backend/app/constants/trait_mask.py`

| Trait | Bit | Value | 说明 |
|-------|-----|-------|------|
| SPATIAL | bit 2 | 4 | 具有物理位置 |
| LOAD_BEARING | bit 9 | 512 | 结构/承重属性 |

**空间类型 composite mask = SPATIAL | LOAD_BEARING = 516**

#### Trait 过滤优势
- 使用 SQL `&` (位与) 运算符，O(1) 时间复杂度
- `trait_mask` 是 `BIGINT` 列，可建数据库索引
- 避免扫描 JSONB 属性的昂贵查询
- 单次查询可通过位运算组合多个 trait

### 7.2 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/graph/nodes` | GET | 全局节点查询 |
| `/api/v1/graph/nodes/{id}` | GET | 获取单个节点 |
| `/api/v1/worlds/{world_id}/nodes` | GET | 世界范围内的节点 |

### 7.3 查询参数

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `type_code` | string | 节点类型 | `world`, `building`, `building_floor`, `room` |
| `name_like` | string | 名称模糊搜索 (ILIKE) | `?name_like=meeting` |
| `trait_class` | string | Trait 类过滤 | `?trait_class=SPACE` |
| `required_any_mask` | int | 任一位命中 (OR) | `?required_any_mask=516` |
| `required_all_mask` | int | 全位命中 (AND) | `?required_all_mask=516` |
| `is_active` | bool | 是否激活 | `?is_active=true` |
| `is_public` | bool | 是否公开 | `?is_public=true` |
| `tags_any` | string | 标签过滤 (逗号分隔) | `?tags_any=hicampus,spatial` |
| `offset` | int | 分页偏移 | `?offset=0` |
| `limit` | int | 每页数量 (默认100) | `?limit=24` |

### 7.4 空间类型查询示例

```bash
# 获取所有 World
GET /api/v1/graph/nodes?type_code=world&trait_class=SPACE

# 获取所有 Building
GET /api/v1/graph/nodes?type_code=building&trait_class=SPACE

# 获取所有 Floor
GET /api/v1/graph/nodes?type_code=building_floor&trait_class=SPACE

# 获取所有 Room
GET /api/v1/graph/nodes?type_code=room&trait_class=SPACE

# 搜索 Room (名称包含 "meeting")
GET /api/v1/graph/nodes?type_code=room&name_like=meeting&limit=24

# 获取特定世界的 Building
GET /api/v1/graph/nodes?type_code=building&is_active=true&limit=1000
```

### 7.5 API 模块
文件位置：`src/api/spaces.ts`

```typescript
import apiClient from './index'
import type { SpaceNode, FilterState } from '@/types/space'

// Trait mask 常量 (与后端 backend/app/constants/trait_mask.py 对齐)
export const TRAIT_MASK = {
  SPATIAL: 4,
  LOAD_BEARING: 512,
  SPACE: 4 | 512, // 516
} as const

export interface SpaceListParams {
  type_code: 'world' | 'building' | 'building_floor' | 'room'
  name_like?: string
  trait_class?: string          // 默认 'SPACE'
  required_any_mask?: number   // 默认 516 (SPACE)
  is_active?: boolean
  is_public?: boolean
  tags_any?: string
  world_id?: number            // attributes.world_id
  building_id?: number         // attributes.building_id
  floor_id?: number            // attributes.floor_id
  offset?: number
  limit?: number
}

export interface SpaceListResponse {
  items: SpaceNode[]
  page: {
    total: number
    offset: number
    limit: number
  }
}

export const spacesApi = {
  // 获取空间列表 (默认使用 SPACE trait 过滤)
  getSpaces: (params: SpaceListParams) =>
    apiClient.get<SpaceListResponse>('/graph/nodes', {
      params: {
        trait_class: 'SPACE',
        required_any_mask: TRAIT_MASK.SPACE,
        limit: 24,
        ...params,
      }
    }),

  // 获取单个空间详情
  getSpace: (nodeId: number) =>
    apiClient.get<SpaceNode>(`/graph/nodes/${nodeId}`),

  // 获取特定类型的所有节点 (用于筛选器下拉,不分页)
  getNodesByType: (typeCode: string, params?: Partial<SpaceListParams>) =>
    apiClient.get<SpaceListResponse>('/graph/nodes', {
      params: {
        type_code: typeCode,
        trait_class: 'SPACE',
        required_any_mask: TRAIT_MASK.SPACE,
        limit: 1000,
        is_active: true,
        ...params,
      }
    }),
}
```

### 7.6 API 错误处理

```typescript
// 响应拦截器已处理 401
// 空间 API 错误映射
const SPACE_ERROR_MESSAGES: Record<number, string> = {
  400: 'Invalid filter parameters',
  401: 'Authentication required',
  403: 'Permission denied',
  404: 'Space not found',
  500: 'Server error loading spaces',
}
```

---

## 8. i18n 国际化

### 8.1 中文语言文件
`src/locales/zh.ts`

```typescript
export default {
  spaces: {
    title: '空间',
    tabs: {
      world: '世界',
      building: '建筑',
      floor: '楼层',
      room: '房间',
    },
    search: {
      placeholder: '搜索空间名称、描述或标签...',
    },
    filters: {
      worldType: '世界类型',
      buildingType: '建筑类型',
      floorType: '楼层类型',
      roomType: '房间类型',
      status: '状态',
      public: '公开/私有',
      reset: '重置',
    },
    viewMode: {
      card: '卡片视图',
      list: '列表视图',
    },
    card: {
      viewDetail: '查看详情',
      online: '在线',
      offline: '离线',
      maintenance: '维护中',
    },
    table: {
      name: '名称',
      type: '类型',
      status: '状态',
      tags: '标签',
      actions: '操作',
    },
    detail: {
      title: '空间详情',
      attributes: '属性',
      description: '描述',
      tags: '标签',
      createdAt: '创建时间',
      updatedAt: '更新时间',
      close: '关闭',
    },
    pagination: {
      loadMore: '加载更多',
      total: '共 {total} 条',
    },
    empty: {
      title: '暂无数据',
      description: '尝试调整筛选条件',
    },
    loading: '加载中...',
  },
}
```

---

## 9. 路由配置

### 9.1 路由定义

```typescript
// router/index.ts
{
  path: '/spaces',
  name: 'Spaces',
  component: () => import('@/views/spaces/Spaces.vue'),
  meta: {
    title: 'Spaces',
    requiresAuth: true,
  },
}
```

### 9.2 URL 参数同步

| 参数 | 说明 | 示例 |
|------|------|------|
| view | 当前 Tab | `?view=building` |
| keyword | 搜索关键字 | `?keyword=campus` |
| world_id | 世界筛选 | `?world_id=1` |
| building_id | 建筑筛选 | `?building_id=5` |
| floor_id | 楼层筛选 | `?floor_id=10` |
| page | 当前页码 | `?page=2` |

---

## 10. 验收标准

### 10.1 功能验收

- [ ] 用户可切换 World/Building/Floor/Room 四个 Tab
- [ ] 每个 Tab 显示对应类型的空间列表
- [ ] 搜索框可跨名称、描述、标签搜索
- [ ] 筛选器根据 Tab 显示对应筛选条件
- [ ] 筛选器支持级联选择
- [ ] 可切换卡片视图和列表视图
- [ ] 点击卡片/行可打开详情抽屉
- [ ] URL 参数与页面状态同步
- [ ] 分页/加载更多正常工作

### 10.2 UI 验收

- [ ] 页面布局与设计稿一致
- [ ] Tab 切换动画流畅
- [ ] 卡片悬停有视觉反馈
- [ ] 列表/卡片切换无闪烁
- [ ] 加载状态有骨架屏或 Spinner
- [ ] 空状态有友好提示
- [ ] 响应式布局正常 (桌面/平板)

### 10.3 性能验收

- [ ] 首屏加载 < 2s
- [ ] Tab 切换 < 300ms
- [ ] 搜索防抖 300ms
- [ ] 列表滚动流畅 (60fps)

---

## 11. 已确认事项

| 项目 | 确认内容 |
|------|---------|
| type_code | `world`, `building`, `building_floor`, `room` |
| World | `world_type` (virtual/physical/mixed), `status` (active/offline/maintenance) |
| Building | `building_status` (active/maintenance/closed), `building_type` (academic/administrative/residential/research) |
| Room `room_type` | `normal`, `home`, `special`, `classroom`, `office`, `lab`, `singularity` |
| Floor `floor_type` | `normal`, `basement`, `mezzanine`, `rooftop` |
| Building-World 约束 | 通过 `attributes.world_id` 关联 Building 所属 World |
| 编辑功能 | 需要，需 `graph.write` 权限 |
| 空间详情 | 使用 el-drawer 抽屉 |

---

## 12. 文件清单

### 12.1 新增文件

```
frontend/src/
├── api/
│   └── spaces.ts                    # 空间 API 模块
├── components/spaces/
│   ├── SpaceHeader.vue              # 页面头部
│   ├── SpaceTabs.vue                # Tab 切换
│   ├── FilterBar.vue                # 筛选栏容器
│   ├── SpaceContent.vue             # 内容区容器
│   ├── SpaceDetailDrawer.vue        # 详情抽屉
│   ├── GlobalSearch.vue             # 搜索输入框
│   ├── ViewModeToggle.vue           # 视图切换
│   ├── FilterChips.vue              # 筛选标签
│   ├── SpacePagination.vue           # 分页器
│   ├── SpaceTable.vue               # 列表视图表格
│   └── cards/
│       ├── WorldCard.vue
│       ├── BuildingCard.vue
│       ├── FloorCard.vue
│       └── RoomCard.vue
├── stores/
│   └── spaces.ts                    # 空间状态管理
├── types/
│   └── space.ts                     # 空间类型定义
├── views/
│   └── spaces/
│       └── Spaces.vue               # 页面入口
└── locales/
    ├── zh.ts                       # 中文语言 (更新)
    └── en.ts                       # 英文语言 (更新)
```

### 12.2 修改文件

| 文件 | 修改内容 |
|------|---------|
| `router/index.ts` | 可能需要添加子路由 |
| `stores/auth.ts` | 确保 API 权限 |
| `components/layout/Sidebar.vue` | 确保 Spaces 导航正确 |

---

## 13. 技术参考

### 13.1 参考实现

- `views/Home.vue` - 页面结构和布局参考
- `components/works/Dashboard.vue` - 卡片网格布局参考
- `stores/user.ts` - Store 模式参考
- `api/auth.ts` - API 模块模式参考

### 13.2 依赖组件

- Element Plus: el-tabs, el-table, el-card, el-input, el-select, el-drawer, el-pagination, el-empty, el-loading
- VueUse: useDebounceFn (搜索防抖)
- 图标: Globe, OfficeBuilding, List, Grid, Search, Filter
