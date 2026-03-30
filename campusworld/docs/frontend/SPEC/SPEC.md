# Frontend SPEC

> **Architecture Role**: 前端是 **Agent 服务层**的展现层，提供用户与**世界语义**的可视化交互界面。通过 HTTP API 与后端命令系统和知识本体交互，将图数据模型中的实体和关系以 UI 形式呈现。

## Module Overview

前端（`frontend/`）是 Vue 3 + TypeScript 构建的单页应用。

> **注**：CampusWorld 是智慧园区 OS，前端是用户与园区空间交互的可视化界面。

## 技术栈

| 技术 | 说明 |
|------|------|
| Vue 3 | 渐进式前端框架 |
| TypeScript | 类型安全 |
| Vite | 构建工具 |
| Element Plus | UI 组件库 |
| Pinia | 状态管理 |
| Vue Router | 路由管理 |
| Axios | HTTP 客户端 |
| Day.js | 日期处理 |

## 项目结构

```
frontend/
├── src/
│   ├── views/          # 页面视图
│   ├── components/    # 共享组件
│   ├── styles/        # 样式系统
│   ├── router/        # 路由配置
│   ├── stores/        # Pinia 状态
│   └── utils/         # 工具函数
```

## 页面结构

| 页面 | 路径 | 说明 |
|------|------|------|
| Home | `/` | 首页 |
| Login | `/auth/login` | 登录 |
| Register | `/auth/register` | 注册 |
| Agents | `/agents` | Agent 管理 |
| Spaces | `/spaces` | 空间浏览 |
| Works | `/works` | 工作台 |
| Discovery | `/discovery` | 发现 |
| History | `/history` | 历史记录 |
| Profile | `/user/profile` | 用户资料 |

## Core Abstractions

### API 集成

```typescript
// API 客户端配置
const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  timeout: 10000,
})

// 请求拦截器：添加 JWT Token
api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
```

### 状态管理

```typescript
// tabs store 示例
interface Tab {
  id: string
  title: string
  closable: boolean
}
```

## User Stories

1. **用户登录**: 用户通过 Login 页面登录，获取 JWT Token 后访问受保护资源
2. **空间浏览**: 用户通过 Spaces 页面浏览园区空间，查看空间详情和出口
3. **工作台**: 用户通过 Works 页面管理自己的物品和状态

## Design Decisions

1. **为何用 Composition API**: `<script setup>` 语法简洁，逻辑复用方便
2. **为何用 Pinia**: 比 Vuex 更轻量，TypeScript 支持更好
3. **为何用 Element Plus**: 企业级 UI 组件，开箱即用

## Dependencies

- 依赖 `backend/app/api/v1/`（REST API）
- 依赖 `backend/app/core/security.py`（JWT 认证）