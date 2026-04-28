# CampusWorld

新一代智慧园区 OS，基于原生 AI 架构，借鉴 MUD 世界设计原理构筑世界语义，基于模型驱动理念，采用全图数据结构实现物理世界设备、系统、人的语义孪生并实现与物理世界与系统的交互。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11+ · FastAPI · SQLAlchemy · Paramiko (SSH) · PostgreSQL |
| 前端 | Vue 3 · TypeScript · Vite · Element Plus · Pinia |
| 基础设施 | Docker Compose · Redis · GitHub Actions |

## 快速启动

```bash
# 一键初始化（推荐）
./scripts/setup.sh

# 或手动启动
docker compose -f docker-compose.dev.yml up -d

# 后端
cd backend && pip install -r requirements/dev.txt
python campusworld.py          # 系统入口：引擎 + HTTP + SSH

# 前端
cd frontend && npm install && npm run dev
```

访问：`http://localhost:5173`（前端）· `http://localhost:8000/docs`（API 文档）· `ssh localhost -p 2222`（终端）

## 项目结构

- [CLAUDE.md](./CLAUDE.md) — 开发者完整上下文（模块路径、命令、配置）
- [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) — 详细目录结构说明
- [docs/README.md](./docs/README.md) — 完整文档导航
- [CONTRIBUTING.md](./CONTRIBUTING.md) — 贡献指南

## 许可证

MIT License