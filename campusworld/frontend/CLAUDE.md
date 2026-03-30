# Frontend - CampusWorld 前端应用

> **Architecture Role**: 前端是 **Agent 服务层**的展现层，提供用户与**世界语义**的可视化交互界面。通过 HTTP API 与后端命令系统和知识本体交互，将图数据模型中的实体和关系以 UI 形式呈现。

Vue 3 + TypeScript + Vite 构建的单页应用。

## 技术栈

- **Vue 3** - 渐进式前端框架
- **TypeScript** - 类型安全
- **Vite** - 构建工具
- **Element Plus** - UI组件库
- **Pinia** - 状态管理
- **Vue Router** - 路由管理
- **Axios** - HTTP客户端
- **Day.js** - 日期处理

## 项目结构

```
frontend/
├── src/
│   ├── views/               # 页面视图
│   │   ├── Home.vue         # 首页
│   │   ├── auth/           # 登录/注册
│   │   │   ├── Login.vue
│   │   │   └── Register.vue
│   │   ├── agents/         # 智能体
│   │   ├── spaces/        # 空间
│   │   ├── works/         # 工作台
│   │   │   ├── Dashboard.vue
│   │   │   ├── ChatInput.vue
│   │   │   ├── TodoList.vue
│   │   │   └── AgentsActivity.vue
│   │   ├── history/       # 历史
│   │   ├── discovery/     # 发现
│   │   └── user/          # 用户
│   │       └── Profile.vue
│   │
│   ├── components/        # 公共组件
│   │   ├── layout/        # 布局组件
│   │   │   ├── NavBar.vue
│   │   │   ├── Sidebar.vue
│   │   │   ├── Footer.vue
│   │   │   └── TabBar.vue
│   │   └── works/         # 工作组件
│   │
│   ├── styles/           # 样式文件
│   │   ├── base/         # 基础样式
│   │   ├── components/   # 组件样式
│   │   └── themes/        # 主题
│   │
│   ├── router/           # 路由配置
│   │   └── index.ts
│   │
│   ├── stores/           # Pinia状态管理
│   │   └── tabs.ts
│   │
│   ├── utils/            # 工具函数
│   │   └── theme.ts
│   │
│   ├── test/             # 测试配置
│   │   └── setup.ts
│   │
│   ├── App.vue            # 根组件
│   └── main.ts            # 入口文件
│
├── package.json
├── vite.config.ts
├── tsconfig.json
└── vitest.config.ts
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

# 格式化代码
npm run format
```

## 开发规范

- 使用 Composition API (`<script setup>`)
- 组件文件使用 PascalCase
- 类型定义使用 TypeScript
- 使用 ESLint + Prettier 规范代码

## API 集成

前端通过 Axios 与后端 REST API 通信:

- 基础URL: `http://localhost:8000/api/v1`
- 认证: JWT Bearer Token
- 请求/响应拦截器已配置
