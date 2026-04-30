# CampusWorld

试验性的下一代Campus OS系统，基于原生AI架构，借鉴MUD游戏世界设计，基于图模型驱动理念，构筑物理世界人、物、事、设备、空间等完整的语义孪生世界， CampusWorld系统一切服务皆是Agent，通过AI + 人的设计构筑新的交互体验。

## 技术栈
| 层级 | 技术 |
|------|------|
| 前端 | TypeScript · Vue 3 · Vite · Element Plus · Pinia |
| 后端 | Python 3.11+ · FastAPI · SQLAlchemy |
| 基础设施 | Docker Compose · Redis · PostgreSQL|

## 本地快速启动

```bash
# 一键初始化
./scripts/setup.sh

# 或手动启动
docker compose -f docker-compose.dev.yml up -d

# 后端
cd backend && pip install -r requirements/dev.txt
python campusworld.py          # 系统入口：引擎 + HTTP + SSH

# 前端
cd frontend && npm install && npm run dev
```

本地访问：`http://localhost:3000`（前端） · `ssh localhost -p 2222`（终端）

## 项目结构
- [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) — 详细目录结构说明
- [docs/README.md](./docs/README.md) — 完整文档导航
- [CONTRIBUTING.md](./CONTRIBUTING.md) — 贡献指南

## 许可证

MIT License