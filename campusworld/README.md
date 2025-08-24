# CampusWorld

一个基于FastAPI和Vue3的现代化校园世界项目，采用企业级工程化架构设计。

## 项目架构

- **后端**: Python + FastAPI + PostgreSQL
- **前端**: Vue3 + TypeScript + Vite
- **数据库**: PostgreSQL
- **容器化**: Docker + Docker Compose
- **CI/CD**: GitHub Actions
- **测试**: pytest + Jest + Cypress

## 快速开始

### 环境要求

- Python 3.9+
- Node.js 18+
- PostgreSQL 13+
- Docker & Docker Compose

### 开发环境启动

```bash
# 克隆项目
git clone <repository-url>
cd campusworld

# 启动开发环境
docker compose -f docker-compose.dev.yml up -d

# 安装后端依赖
cd backend
pip install -r requirements/dev.txt

# 安装前端依赖
cd ../frontend
npm install

# 启动后端服务
cd ../backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 启动前端服务
cd ../frontend
npm run dev
```

## 项目结构

```
campusworld/
├── backend/                 # Python FastAPI 后端
├── frontend/               # Vue3 前端
├── shared/                 # 共享代码和类型定义
├── docs/                   # 项目文档
├── tests/                  # 集成测试
├── scripts/                # 构建和部署脚本
├── docker/                 # Docker 配置文件
├── .github/                # GitHub Actions CI/CD
├── requirements/            # Python 依赖管理
└── package.json            # Node.js 依赖管理
```

## 开发指南

详细的开发指南请参考 `docs/` 目录下的文档。

## 贡献指南

请参考 `CONTRIBUTING.md` 了解如何贡献代码。

## 许可证

MIT License
