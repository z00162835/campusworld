# CampusWorld 项目文档

CampusWorld 技术文档的**唯一入口**（所有契约与索引均在仓库根目录下的 `docs/` 树内；**不设** `docs/backend/`、`backend/docs/` 等并行文档根）。

---

## 快速开始

- [系统架构](./architecture/README.md) — 技术栈、多端接入、Redis/可观测性说明、RFC（如 `campus` CLI）
- [快速启动](./quickstart.md) — 环境与 Docker 初始化（与根目录 `QUICKSTART.md` 若并存，以维护者最近一次更新为准）
- **配置 / Conda**：根目录 [`CLAUDE.md`](../CLAUDE.md)、[`AGENTS.md`](../AGENTS.md)、[`backend/config/settings.yaml`](../backend/config/settings.yaml)

---

## 后端：契约真源与实现对齐

### 关于历史上「backend/docs/」占位

仓库内 **不存在** `backend/docs/`。旧导航中的 `look_command_design.md`、`look_command_usage.md`、`singularity_room_implementation.md` 等路径无效。下列 SPEC 与源码为当前真源：

| 主题 | 文档 |
|------|------|
| 命令总览 | [command/SPEC/SPEC.md](./command/SPEC/SPEC.md) |
| `look` | [command/SPEC/features/CMD_look.md](./command/SPEC/features/CMD_look.md) |
| 数据模型与 SingularityRoom | [models/SPEC/SPEC.md](./models/SPEC/SPEC.md)（检索「SingularityRoom」「系统入口」） |
| Agent / 图语义 primer | [models/SPEC/CAMPUSWORLD_SYSTEM_PRIMER.md](./models/SPEC/CAMPUSWORLD_SYSTEM_PRIMER.md) |
| 测试工程化 | [testing/SPEC/SPEC.md](./testing/SPEC/SPEC.md) |
| 系统架构 | [architecture/README.md](./architecture/README.md) |

### 代码锚点（抽查）

- **`look`**：`backend/app/commands/game/look_command.py`、`look_appearance.py`（与 CMD_look 契约一致）
- **奇点屋 / 根节点**：`backend/app/models/root_manager.py`、`backend/tests/models/test_singularity_room.py`
- **日志**：`backend/app/core/log/manager.py`；约定见根目录 `CLAUDE.md`

### 仍留在 `backend/` 树内的 Markdown（就近说明）

未单独拆文件；若增删请同步对应 SPEC：

- `backend/AGENTS.md`
- `backend/app/ssh/CLAUDE.md`
- `backend/app/models/agent_model/**/*.md`（训练/数据说明；与 `docs/models/SPEC/features/F11*.md` 等勿口径分叉）

---

## Agent 上下文（指向根与子模块）

- [项目 Agent 指南](../AGENTS.md)
- [后端 Agent 指南](../backend/AGENTS.md)
- [前端 Agent 指南](../frontend/AGENTS.md)
- [HiCampus Agent 指南](../backend/app/games/hicampus/AGENTS.md)

---

## 文档治理（SPEC 与 Agent）

以下内容原独立见于 `docs/AGENTS.md`，现并入本 README，**避免多处「文档说明文档」**。

### Source of Truth

- 模块契约：`docs/<module>/SPEC/SPEC.md`
- 特性契约：仅 `docs/<module>/SPEC/features/`
- 验收：`docs/<module>/SPEC/ACCEPTANCE.md`（若存在）
- 待办 / 延期：`docs/<module>/SPEC/TODO.md`

### 规则

- 不得在 `features/` 外平行放置特性 SPEC。
- 模块 `SPEC.md` 只链接与摘要，不粘贴完整特性正文。
- 行为变更须在同一变更中更新最近模块 SPEC 或显式标注漂移。
- 实现代码避免 `Fxx` 标签；契约文档可使用特性命名。
- 文档须可执行：优先不变量、验证步骤与链接；架构若未落地标 RFC。
- 示例路径与命令须与仓库一致。

---

## 模块索引（节选）

| 域 | 入口 |
|----|------|
| 命令 | [command/SPEC/SPEC.md](./command/SPEC/SPEC.md) |
| 模型 | [models/SPEC/SPEC.md](./models/SPEC/SPEC.md) |
| 前端 | [frontend/SPEC/SPEC.md](./frontend/SPEC/SPEC.md) |
| 测试 | [testing/SPEC/SPEC.md](./testing/SPEC/SPEC.md) |
| HiCampus | [games/hicampus/SPEC/SPEC.md](./games/hicampus/SPEC/SPEC.md) |
| campus_life（遗留包叙述） | [games/campus_life/SPEC/SPEC.md](./games/campus_life/SPEC/SPEC.md) |

---

## 规划与缺口

| 条目 | 状态 | 说明 |
|------|------|------|
| [overview.md](./overview.md) | 按需 | 项目概述 |
| [quickstart.md](./quickstart.md) | 已有文件 | 详细快速启动；与根 `QUICKSTART.md` 是否合并待统一维护策略 |
| setup.md | 缺 | 完整环境搭建 |
| database/README.md | 缺 | DDL 见 [`backend/db/schemas/database_schema.sql`](../backend/db/schemas/database_schema.sql) |
| api/README.md | 缺 | API 契约（`backend/AGENTS.md` 曾引用，落地后补） |
| frontend/README.md | 缺 | 前端开发指南（现有 `frontend/SPEC/SPEC.md`） |
| coding-standards.md | 缺 | 代码规范 |
| deployment/ | 缺 | 部署运维 |

**待决策**：配置专章、日志专页是否新增为 `docs/configuration.md` 等单文件（仍在唯一 `docs/` 树下）。

---

## 文档贡献

- [CONTRIBUTING.md](../CONTRIBUTING.md)
- 面向人类的较长说明以 `docs/` 为准；根目录 `AGENTS.md` / `CLAUDE.md` 面向 Agent 执行约束。
- `docs/` 正文默认中文。
