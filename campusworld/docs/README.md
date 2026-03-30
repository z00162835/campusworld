# CampusWorld 项目文档

CampusWorld 是新一代智慧园区 OS 项目的技术文档中心。

## 已实现的文档

### 快速开始
- [系统架构](./architecture/README.md) — 技术栈、模块设计、性能优化、部署架构
- [配置系统](./configuration.md) — YAML 配置结构说明
- [配置迁移](./config-migration.md) — 从 Pydantic BaseSettings 迁移到 YAML 的完整指南
- [Conda 环境设置](./conda-setup.md) — Conda 环境配置方法

### 后端开发
- [look 命令设计](./backend/docs/look_command_design.md) — 命令架构、核心方法、集成方案
- [look 命令使用](./backend/docs/look_command_usage.md) — 语法、示例、权限控制
- [单例房间实现](./backend/docs/singularity_room_implementation.md) — 默认家位置设计
- [Demo Building 生成器](./backend/tests/README_demo_building.md) — 测试数据生成文档
- [日志系统](../backend/app/core/log/README.md) — structlog 使用指南

### 各模块上下文文档（英文，面向 AI 助手）
- [后端全貌](../backend/CLAUDE.md)
- [核心模块](../backend/app/core/CLAUDE.md)
- [数据模型](../backend/app/models/CLAUDE.md)
- [命令系统](../backend/app/commands/CLAUDE.md)
- [SSH 服务器](../backend/app/ssh/CLAUDE.md)
- [游戏引擎](../backend/app/game_engine/CLAUDE.md)
- [协议处理](../backend/app/protocols/CLAUDE.md)
- [配置构建](../backend/config/CLAUDE.md)
- [数据库模块](../backend/db/CLAUDE.md)
- [前端全貌](../frontend/CLAUDE.md)
- [项目全貌](../CLAUDE.md)

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
- CLAUDE.md 系列文档使用英文，面向 AI 上下文补充
- docs/ 目录文档使用中文，面向开发者阅读