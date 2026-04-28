# Frontend - CampusWorld 前端应用

> **Architecture Role**: 前端是 **Agent 服务层**的展现层，提供用户与**世界语义**的可视化交互界面。通过 HTTP API 与后端命令系统和知识本体交互，将图数据模型中的实体和关系以 UI 形式呈现。

Vue 3 + TypeScript + Vite 构建的单页应用。

## 技术栈

- **Vue 3** - 渐进式前端框架（Composition API + `<script setup>`）
- **TypeScript** - 类型安全（strict 模式）
- **Vite** - 构建工具
- **Element Plus** - UI 组件库（自动导入）
- **Pinia** - 状态管理
- **Vue Router** - 路由管理（动态导入）
- **Axios** - HTTP 客户端
- **vue-i18n** - 国际化
- **Day.js** - 日期处理（已安装，待使用）

## 项目结构

```
frontend/
├── src/
│   ├── api/                    # API 服务层
│   │   ├── index.ts           # Axios 实例 + 拦截器
│   │   ├── auth.ts            # 认证 API
│   │   └── accounts.ts        # 账户 API
│   │
│   ├── components/            # 组件
│   │   ├── common/           # 通用组件
│   │   │   └── ErrorBoundary.vue
│   │   └── layout/           # 布局组件
│   │       ├── NavBar.vue
│   │       ├── Sidebar.vue
│   │       ├── TabBar.vue
│   │       └── Footer.vue
│   │
│   ├── composables/           # 可复用组合函数
│   │   ├── useAuth.ts        # 认证状态
│   │   ├── useLoading.ts     # 加载状态
│   │   └── useNotification.ts # 通知
│   │
│   ├── locales/              # 国际化
│   │   ├── index.ts          # i18n 配置
│   │   ├── zh.ts             # 中文
│   │   └── en.ts             # 英文
│   │
│   ├── router/               # 路由配置
│   │   └── index.ts          # 路由 + 导航守卫
│   │
│   ├── stores/               # Pinia 状态管理
│   │   ├── auth.ts           # 认证状态
│   │   ├── user.ts          # 用户状态
│   │   └── tabs.ts          # 标签页状态
│   │
│   ├── types/                # TypeScript 类型定义
│   │   ├── index.ts         # 统一导出
│   │   └── auth.ts          # 认证相关类型
│   │
│   ├── utils/               # 工具函数
│   │   └── theme.ts         # 主题管理
│   │
│   ├── views/                # 页面视图
│   │   ├── Home.vue          # 首页/工作台
│   │   ├── NotFound.vue     # 404
│   │   ├── auth/            # 认证
│   │   │   ├── Login.vue
│   │   │   ├── Login.spec.ts
│   │   │   └── Register.vue
│   │   ├── user/            # 用户
│   │   │   └── Profile.vue
│   │   ├── agents/          # 智能体
│   │   ├── spaces/          # 空间
│   │   ├── discovery/       # 发现
│   │   └── history/         # 历史
│   │
│   ├── websocket/            # WebSocket 服务
│   │   ├── index.ts         # WebSocket 管理器
│   │   ├── types.ts        # 类型定义
│   │   └── composables/
│   │       └── useWebSocket.ts
│   │
│   ├── styles/              # 样式文件
│   ├── test/                # 测试配置
│   │   └── setup.ts         # 全局 mocks
│   │
│   ├── App.vue              # 根组件
│   └── main.ts              # 入口文件
│
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
└── vitest.config.ts
```

## 核心架构

### API 服务层 (api/)

Axios 实例配置了请求/响应拦截器：

- **请求拦截器**：自动附加 JWT Bearer Token
- **响应拦截器**：401 时清除 Token

```typescript
// 使用示例
import { authApi } from '@/api/auth'
const response = await authApi.login({ username, password })
```

### 状态管理 (stores/)

使用 Pinia Composition API 风格：

- **auth store**：登录/登出、Token 管理、认证状态
- **user store**：用户资料获取
- **tabs store**：多标签页状态

```typescript
// 使用示例
import { useAuthStore } from '@/stores/auth'
const authStore = useAuthStore()
if (authStore.isAuthenticated) { ... }
```

### 可复用组合函数 (composables/)

封装通用逻辑：

- **useAuth()**：认证状态快捷访问
- **useLoading()**：加载状态管理
- **useNotification()**：ElMessage 包装

### WebSocket 服务 (websocket/)

支持流式交互：

- 自动重连
- 消息处理器注册

```typescript
// 使用示例
import { useWebSocket } from '@/websocket/composables/useWebSocket'
const { status, send, connect, disconnect } = useWebSocket()
```

### 国际化 (locales/)

使用 vue-i18n，支持中英文切换：

```typescript
// 组件中使用
{{ $t('auth.login') }}
// 或 composition API
const { t } = useI18n()
```

## 常用命令

```bash
# 安装依赖
npm install

# 开发模式
npm run dev

# 构建生产
npm run build

# 类型检查
npm run type-check

# 代码检查
npm run lint

# 运行测试
npm run test

# 运行测试(UI模式)
npm run test:ui

# 运行测试(带覆盖率)
npm run test:coverage
```

## 测试配置

- **vitest.config.ts**：vitest 配置（environment、globals、coverage）
- **src/test/setup.ts**：全局 mocks（vue-router、axios、element-plus）

### 测试规范

| 文件 | 说明 |
|------|------|
| `*.spec.ts` | 组件测试 |
| `*.test.ts` | 工具函数测试 |

## 开发规范

- 使用 Composition API (`<script setup>`)
- 组件文件使用 PascalCase
- 类型定义使用 TypeScript
- 使用 ESLint + Prettier 规范代码
- API 调用通过 `@/api/` 服务层，禁止直接使用 axios
- 状态通过 Pinia stores 管理，禁止直接操作 localStorage
- 组件使用 unplugin-vue-components 自动导入

## API 集成

前端通过 Axios 与后端 REST API 通信：

- **基础 URL**：`http://localhost:8000/api/v1`（Vite 代理）
- **认证**：JWT Bearer Token（存储在 localStorage）
- **请求/响应拦截器**：在 `api/index.ts` 中配置

### 关键 API 端点

| 功能 | 方法 | 端点 |
|------|------|------|
| 登录 | POST | `/auth/login` |
| 注册 | POST | `/auth/register` |
| 获取用户资料 | GET | `/accounts/me` |
| 更新用户资料 | PUT | `/accounts/me` |
