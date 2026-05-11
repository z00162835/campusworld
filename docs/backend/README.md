# 后端文档索引

## 关于「backend/docs/」

仓库内 **不存在** `backend/docs/` 目录。根目录 [`docs/README.md`](../README.md) 曾列出 `look_command_design.md`、`look_command_usage.md`、`singularity_room_implementation.md` 等路径，属于 **历史占位**，与当前布局不一致。

后端 **命令契约**、**数据模型** 与 **架构** 的真源已统一到：

| 主题 | 文档 |
|------|------|
| 命令总览 | [`docs/command/SPEC/SPEC.md`](../command/SPEC/SPEC.md) |
| `look`（语法、行为、实现锚点） | [`docs/command/SPEC/features/CMD_look.md`](../command/SPEC/features/CMD_look.md) |
| 数据模型与 SingularityRoom | [`docs/models/SPEC/SPEC.md`](../models/SPEC/SPEC.md)（检索「SingularityRoom」「系统入口」） |
| Agent / 图语义 primer | [`docs/models/SPEC/CAMPUSWORLD_SYSTEM_PRIMER.md`](../models/SPEC/CAMPUSWORLD_SYSTEM_PRIMER.md) |
| 测试工程化 | [`docs/testing/SPEC/SPEC.md`](../testing/SPEC/SPEC.md) |
| 系统架构（接入、Redis、RFC） | [`docs/architecture/README.md`](../architecture/README.md) |

## 与实现对齐的代码锚点（抽查）

- **`look`**：`backend/app/commands/game/look_command.py`、`look_appearance.py`（与 [`CMD_look.md`](../command/SPEC/features/CMD_look.md) 一致）。
- **奇点屋 / 根节点**：`backend/app/models/root_manager.py`、`backend/tests/models/test_singularity_room.py`。

## 仍留在 `backend/` 树内的 Markdown

以下为 **就近 Agent/开发者说明**，尚未迁入 `docs/`：

- `backend/AGENTS.md`
- `backend/app/ssh/CLAUDE.md`
- `backend/app/models/agent_model/**/*.md`（意图分类、tool router 训练与数据说明）

是否逐步迁至 `docs/backend/guides/` 由治理决策（见下文「待决策」）。

---

## 待决策（文档治理）

1. **是否新建 `docs/backend/guides/`**：把 `agent_model` 下训练/README 迁入统一索引，避免与 `docs/models/SPEC/features/F11*.md` 口径分叉。
2. **配置类文档**：`docs/README.md` 曾指向 `configuration.md`、`conda-setup.md` 等；若需面向新人的「配置专章」，应在 `docs/` 下新建并与 [`backend/config/settings.yaml`](../../backend/config/settings.yaml)、根目录 [`CLAUDE.md`](../../CLAUDE.md) 对齐。
3. **日志专页**：`backend/app/core/log/` 无 README；可新增短文说明 structlog 入口与 `LoggerNames`，或仅在 `docs/testing/SPEC` 中链接调试约定。
