# CampusWorld

一个基于 FastAPI 和 Vue3 的现代化校园世界项目，采用企业级工程化架构设计，借鉴 MUD 游戏世界设计原理构筑世界语义。

## Architectural Vision - 架构愿景

CampusWorld 基于三层架构设计：

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent 服务层 (AI 使能 / Agent 交互)                 │
│         用户/Agent 通过命令系统与 World Semantic 交互                  │
├─────────────────────────────────────────────────────────────────────┤
│                 知识与能力层 (知识服务 / 能力服务)                      │
│    命令系统（commands/）   图数据模型（models/）   游戏引擎（game_engine/）│
├─────────────────────────────────────────────────────────────────────┤
│                    系统适配层 (公共服务 / 设备接入)                     │
│         核心模块（core/）   SSH/协议（protocols/）   配置（config/）   │
└─────────────────────────────────────────────────────────────────────┘
```

5个核心服务：**公共服务**（core/配置/安全）· **知识服务**（models/全图数据）· **能力服务**（game_engine/游戏逻辑）· **AI使能服务** · **Agent服务**

## World Semantic Design - 世界语义设计

CampusWorld 的核心设计理念是"**世界语义驱动**"：

- **万物皆为节点**：User、Character、Room、Building、World 都以 GraphNode 形式存在，通过 type 区分
- **关系即语义**：Exit 连接 Room、Character 位于 Room、User 拥有 Character — 所有关系显式表达为语义边
- **命令即交互**：用户/Agent 通过命令（commands/）操作图数据模型中的实体，类似 MUD 游戏体验
- **知识本体**：全图数据结构构筑知识本体，支持动态模型发现和扩展

## 项目架构

- **后端**: Python 3.9+ + FastAPI + PostgreSQL + Paramiko(SSH)
- **前端**: Vue3 + TypeScript + Vite + Element Plus
- **数据库**: PostgreSQL 13+
- **容器化**: Docker + Docker Compose
- **CI/CD**: GitHub Actions

## 快速开始

### 环境要求

- Python 3.9+
- Node.js 18+
- PostgreSQL 13+
- Docker & Docker Compose

### 启动开发环境

```bash
# 启动完整开发环境(后端+前端+数据库)
cd campusworld
docker compose -f docker-compose.dev.yml up -d

# 后端开发
cd backend
pip install -r requirements/dev.txt

# 方式1: 使用主程序(推荐，含SSH)
python campusworld.py

# 方式2: 使用uvicorn启动API
uvicorn campusworld:app --reload --host 0.0.0.0 --port 8000

# 前端开发
cd frontend
npm install
npm run dev
```

## 项目结构

```
campusworld/
├── CLAUDE.md                    # 本文件
├── backend/                     # Python FastAPI 后端
│   ├── app/
│   │   ├── core/               # 核心模块(配置/日志/数据库/安全)
│   │   ├── ssh/                # SSH服务器和会话管理
│   │   ├── commands/           # 命令系统
│   │   ├── models/             # 数据模型(纯图数据设计)
│   │   ├── game_engine/        # 游戏引擎
│   │   ├── protocols/           # 协议处理
│   │   ├── games/              # 游戏内容
│   │   └── api/                # REST API
│   ├── config/                 # 配置文件
│   ├── db/                     # 数据库脚本
│   ├── scripts/                # 工具脚本
│   ├── tests/                  # 测试
│   └── requirements/           # Python依赖
├── frontend/                   # Vue3 前端
│   ├── src/
│   │   ├── views/             # 页面视图
│   │   ├── components/        # 组件
│   │   ├── styles/            # 样式
│   │   ├── router/            # 路由
│   │   └── stores/            # 状态管理
│   └── package.json
├── docker-compose*.yml         # Docker配置
└── .github/workflows/          # CI/CD配置
```

## 核心模块

### 后端核心 (backend/app/core/)

- **settings.py**: Pydantic配置模型，提供类型安全的配置访问
- **config_manager.py**: 配置管理器，支持YAML配置
- **database.py**: SQLAlchemy数据库连接和会话管理
- **security.py**: 密码加密和JWT令牌处理
- **permissions.py**: 权限系统
- **log/**: 统一日志系统(structlog)

### SSH模块 (backend/app/ssh/)

- **server.py**: 基于Paramiko的SSH服务器实现
- **session.py**: SSH会话管理
- **console.py**: SSH控制台交互
- **input_handler.py**: 输入处理

### 命令系统 (backend/app/commands/)

- **base.py**: 命令基类和上下文
- **registry.py**: 命令注册表
- **builder/**: 建造类命令
- **game/**: 游戏命令(look等)
- **system_commands.py**: 系统命令

### 数据模型 (backend/app/models/)

- **user.py**: 用户模型
- **character.py**: 角色模型
- **room.py**: 房间模型
- **world.py**: 世界模型
- **building.py**: 建筑模型
- **graph.py**: 图结构(世界连接)

### 游戏引擎 (backend/app/game_engine/)

- **base.py**: 引擎基类
- **manager.py**: 引擎管理器
- **loader.py**: 内容加载器
- **interface.py**: 游戏接口

### 前端 (frontend/)

- **Vue 3** + TypeScript + Vite
- **Element Plus** UI组件库
- **Pinia** 状态管理
- **Vue Router** 路由管理

## 开发规范

### Python (后端)

- 使用 `pydantic` 进行数据验证
- 使用 `structlog` 进行结构化日志记录
- 使用 `sqlalchemy` ORM 进行数据库操作
- 命令类需继承 `CommandBase`
- 遵循 PEP 8 编码规范

### TypeScript/Vue (前端)

- 使用 TypeScript 进行类型检查
- 组件使用 Composition API (`<script setup>`)
- 使用 ESLint + Prettier 进行代码格式化
- 遵循 Vue 3 风格指南

### Git 提交规范

```
feat: 新功能
fix: 修复bug
refactor: 重构
docs: 文档更新
test: 测试
chore: 构建/工具链变更
```

## 测试

```bash
# 后端测试
cd backend
pytest

# 前端测试
cd frontend
npm run test

# 前端E2E测试
npm run test:e2e
```

## 配置文件

- `backend/config/settings.yaml` - 主配置文件
- `backend/config/settings.dev.yaml` - 开发环境配置
- `backend/config/settings.prod.yaml` - 生产环境配置
- `frontend/.env` - 前端环境变量

## 常用命令

```bash
# 启动SSH服务器
cd backend
python -m app.ssh.server

# 初始化数据库
python -m db.init_database

# 构建前端
cd frontend
npm run build

# 运行lint
npm run lint
```
