# 项目概述

## 什么是 CampusWorld

CampusWorld 是新一代智慧园区操作系统，基于原生 AI 架构设计。它借鉴 MUD（Multi-User Dungeon）世界的设计原理，通过全图数据结构构建知识本体，实现物理世界设备、系统、人的语义孪生与交互映射。

## 核心理念

### 世界语义驱动

传统园区系统以功能模块为核心，而 CampusWorld 以"世界"为核心：
- 每个实体（建筑、房间、设备、用户）都是世界中的对象
- 对象之间通过语义关系（出口、包含、从属）连接
- 用户通过命令（类似 MUD ）或者 API 与世界交互

### 模型驱动设计

系统采用图数据模型：
- 所有核心对象继承自统一的图节点基类
- 支持动态模型发现，无需修改核心代码即可扩展
- 关系通过显式的边（Edge）而非外键表达

### 分层架构

```
Agent 服务层（AI 使能/Agent 交互）
    ↓
知识与能力层（知识服务/能力服务）
    ↓
系统适配层（公共服务/设备接入）
```

## 技术架构

### 后端

- **FastAPI**：高性能异步 Web 框架，提供 REST API 和 OpenAPI 文档
- **SQLAlchemy**：Python ORM，支持复杂查询和数据库迁移
- **Paramiko**：SSH 服务器实现，支持终端连接
- **Graph Models**：基于图结构的领域模型（User、Character、Room、Building、World 等）

### 前端

- **Vue 3** + **TypeScript**：类型安全的前端开发
- **Vite**：快速的开发服务器和构建工具
- **Element Plus**：企业级 UI 组件库
- **Pinia**：轻量级状态管理

### 数据层

- **PostgreSQL**：主数据库，支持向量、时序、GIS 扩展
- **Redis**：缓存和会话存储
- **Docker Compose**：开发环境容器化

## 核心模块

| 模块 | 路径 | 说明 |
|------|------|------|
| SSH 服务器 | `backend/app/ssh/` | 基于 Paramiko 的 SSH 服务器，处理终端连接 |
| 命令系统 | `backend/app/commands/` | 继承自 `BaseCommand` 的命令体系，支持自动注册 |
| 引擎 | `backend/app/game_engine/` | 逻辑核心，支持多内容包 |
| 数据模型 | `backend/app/models/` | 纯图数据模型，支持动态发现 |
| 协议处理 | `backend/app/protocols/` | HTTP（FastAPI）和 SSH 的统一接口 |
| 核心模块 | `backend/app/core/` | 配置、日志、安全、数据库连接等基础功能 |

## 与传统园区系统的区别

| 特性 | 传统园区系统 | CampusWorld |
|------|-------------|-------------|
| 数据模型 | 关系型表格，按功能模块隔离 | 图结构，万物互联 |
| 用户交互 | 表单、按钮、API 调用 | 命令（SSH）和 API 双通道 |
| 扩展方式 | 新模块、新表、代码修改 | 新对象类型、新关系、新命令 |
| 设备语义 | 独立设备清单 | 设备作为世界对象，参与空间拓扑 |

## 文档导航

- [快速开始](./quickstart.md) — 环境搭建和启动
- [系统架构](./architecture/README.md) — 详细技术架构说明
- [配置系统](./configuration.md) — YAML 配置管理
- [后端开发](../backend/CLAUDE.md) — 后端模块详细说明
- [前端开发](../frontend/CLAUDE.md) — 前端模块详细说明