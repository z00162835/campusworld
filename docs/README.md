# CampusWorld 项目文档

CampusWorld 是新一代智慧园区 OS 项目的技术文档中心。

## 已实现的文档

### 快速开始
- [系统架构](./architecture/README.md) — 技术栈、模块设计、性能优化、部署架构
- [快速启动](./quickstart.md) — 环境与 Docker 初始化（若与根目录 `QUICKSTART.md` 并存，以实际维护者更新为准）
- **配置 / Conda**：见根目录 [`CLAUDE.md`](../CLAUDE.md) 与 [`backend/config/settings.yaml`](../backend/config/settings.yaml)；专章文档待补齐时可在此 README 增链。

### 后端开发
- [**后端文档索引（含 backend/docs 迁移说明）**](./backend/README.md) — 命令与模型真源路径、实现对齐锚点
- [`look` 命令契约](./command/SPEC/features/CMD_look.md) — 语法、行为、实现路径（替代历史上计划的 `backend/docs/look_*.md`）
- [数据模型 SPEC / SingularityRoom](./models/SPEC/SPEC.md) — 系统入口空间与图模型（替代历史上计划的 `singularity_room_implementation.md`）
- [奇点屋测试](../backend/tests/models/test_singularity_room.py) — 行为与根节点校验（源码）
- **日志**：实现位于 [`backend/app/core/log/`](../backend/app/core/log/)（`manager.py`）；用法约定见根目录 `CLAUDE.md`「日志系统」

### Agent 上下文文档
- [项目 Agent 指南](../AGENTS.md)
- [后端 Agent 指南](../backend/AGENTS.md)
- [前端 Agent 指南](../frontend/AGENTS.md)
- [文档治理 Agent 指南](./AGENTS.md)
- [HiCampus Agent 指南](../backend/app/games/hicampus/AGENTS.md)

## 规划中的文档

以下文档正在编写或计划中：

| 文档 | 状态 | 说明 |
|------|------|------|
| [overview.md](./overview.md) | 规划中 | 项目完整概述 |
| [quickstart.md](./quickstart.md) | 规划中 | 详细快速启动指南 |
| [setup.md](./setup.md) | 规划中 | 完整环境搭建步骤 |
| database/README.md | 规划中 | 数据库设计详解 |
| api/README.md | 规划中 | API 设计文档 |
| backend/README.md | 规划中 | 后端开发指南 |
| frontend/README.md | 规划中 | 前端开发指南 |
| testing/README.md | 规划中 | 测试指南 |
| coding-standards.md | 规划中 | 代码规范 |
| deployment/ | 规划中 | 部署运维文档 |

## 文档贡献

- 参考根目录 [CONTRIBUTING.md](../CONTRIBUTING.md)
- AGENTS.md 系列文档面向 AI 上下文补充，`CLAUDE.md` 仅作兼容入口
- docs/ 目录文档使用中文，面向开发者阅读
