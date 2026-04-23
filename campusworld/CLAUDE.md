# CampusWorld

下一代智慧园区OS系统，采用企业级工程化架构设计，借鉴 MUD 游戏世界设计原理构筑世界语义。

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

**Agent 运行时四层架构（L1–L4）**（类型与数据、命令工具、思考模型、经验 Skill）的规范叙述见 [`docs/models/SPEC/features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md`](docs/models/SPEC/features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)。

### 世界内容包（HiCampus 与 `world install`）

可安装世界以 `backend/app/games/<world_id>/` 为内容根目录，由 **GameLoader**（[`game_engine/loader.py`](backend/app/game_engine/loader.py)）发现与装载；`world install` / `uninstall` / `reload`（[`commands/game/world_command.py`](backend/app/commands/game/world_command.py)）维护运行时并与奇点屋入口可见性同步。包内 [`manifest.yaml`](backend/app/games/hicampus/manifest.yaml) 中的 **`graph_seed`** 为 `true` 时，快照经 [`game_engine/graph_seed/`](backend/app/game_engine/graph_seed/) 写入 **PostgreSQL**（需已完成相关库迁移），命令层 `look`、方向移动等依赖图中的 **room** 与 **`connects_to`**；无 PostgreSQL 的环境应将 `graph_seed` 设为 `false`，否则安装可能失败。用户登录后默认落在 **奇点屋**，再 `enter <world_id>` 进入世界。

**世界内位置（Evennia 式）**：账号节点（`type_code=account`）的 **`location_id` 指向当前所在房间图节点**（含 HiCampus 包内 room）；`home_id` 仍锚定奇点屋根房间。`attributes.active_world` / `world_location` 作跨世界桥与拓扑校验的辅助字段，与 `location_id` 同步更新。从奇点屋 `enter` 另一世界前须 **`leave`（或 `ooc`）** 回到根房间；进入世界时出生点须已在图中（`world_entry_service` 解析的 `spawn_key` 对应 `package_node_id`）。实现见 [`app/ssh/game_handler.py`](backend/app/ssh/game_handler.py)、[`app/commands/game/direction_command.py`](backend/app/commands/game/direction_command.py)、[`app/commands/game/look_command.py`](backend/app/commands/game/look_command.py)。

**奇点屋世界入口（Evennia Exit）**：与图种子中的 **`type_code=world` 元数据节点**分离，使用专用 **`type_code=world_entrance`** 节点挂在根房间（`location_id` = 奇点屋），由 [`world_entry_service.sync_world_entry_visibility`](backend/app/game_engine/world_entry_service.py) 在 `world install` / `uninstall` 时维护；节点描述即世界门面，`look` 在 **「出口（世界）」** 区块列出（见 [`look_appearance.py`](backend/app/commands/game/look_appearance.py)）。`enter <world_id>` 只解析 `world_entrance`。属性可含 **`destination_node_id`**（gate 房间图 id，与 Evennia 的 `destination` 对齐）。**`look` 当前房间唯一由 `location_id` 解析**，不再使用 `active_world`+`world_location` 作为 `look` 回退路径。

操作步骤见下文 **「安装 HiCampus 世界」**；更短的清单见 **[`QUICKSTART.md`](QUICKSTART.md)**「安装 HiCampus 世界」。

## World Semantic Design - 世界语义设计

CampusWorld 的核心设计理念是"**世界语义驱动**"：

- **万物皆为节点**：User、Character、Room、Building、World 都以 GraphNode 形式存在，通过 type 区分
- **关系即语义**：Exit 连接 Room、Character 位于 Room、User 拥有 Character — 所有关系显式表达为语义边
- **命令即交互**：用户/Agent 通过命令（commands/）操作图数据模型中的实体，类似 MUD 游戏体验
- **知识本体**：全图数据结构构筑知识本体，支持动态模型发现和扩展
- **可安装世界包**：例如 `app/games/hicampus/`，由 `GameLoader` 发现，`world install <world_id>` 加载；用户始终在系统 **奇点屋** 落地，再经入口进入世界（参见下文「安装 HiCampus 世界」）。

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

### Python 执行环境（Conda `campusworld`）

**后端与本地 pytest 默认假定使用 Conda 环境 `campusworld` 中的解释器与依赖。** 在 `base`、系统 Python 或未安装 `requirements` 的环境中直接运行 `pytest` / `python campusworld.py`，容易出现 **`ModuleNotFoundError`、pytest 未安装、依赖或 Python 次版本与仓库不一致** 等问题，易被误判为项目代码故障。

- **推荐**：先 `conda activate campusworld`，再进入 `backend` 执行 `pip install`、`pytest`、`python campusworld.py`。
- **无需持久激活时**：在 `backend` 目录下使用 `conda run -n campusworld pytest …` 或 `conda run -n campusworld python campusworld.py`（与下文「测试」一节一致）。
- **CI**：流水线应使用与 `requirements` 声明一致的 Python 版本；若 CI 使用 Conda，环境名可与本地对齐为 `campusworld` 或等价锁定文件。

### 启动开发环境

```bash
# 启动完整开发环境(后端+前端+数据库)
cd campusworld
docker compose -f docker-compose.dev.yml up -d

# 后端开发（建议在 conda activate campusworld 之后）
cd backend
pip install -r requirements/dev.txt

# 后端系统入口（游戏引擎 + HTTP/WebSocket + SSH）
python campusworld.py

# 前端开发
cd frontend
npm install
npm run dev
```

### 安装 HiCampus 世界（可选）

HiCampus 为内置示例世界包（`app/games/hicampus/`）。完整空间、`look` 与方向移动依赖图数据中的房间与 `connects_to` 边，因此一般需要 **PostgreSQL** 且在 [`app/games/hicampus/manifest.yaml`](backend/app/games/hicampus/manifest.yaml) 中启用 **`graph_seed: true`**（安装/重载世界时把包快照幂等写入图库；无数据库的测试环境可改为 `false`，此时仅注册运行时，世界内浏览/移动不可用）。

1. 启动后端（含游戏引擎），确保 DB 已迁移。
2. 在 SSH 会话或具备 **`admin.world.manage`** 的上下文中执行：`world install hicampus`。
3. 用户登录后位于奇点屋：`look` 应可见入口 **hicampus**；`enter hicampus` 进入门户厅（`hicampus_gate`）。
4. **示例深链路**（种子成功后）：`n`（连桥）→ `n`（广场）→ `n`（F1 首层交通核）→ `w`（首层卫生间，可见物品）→ `e` 返回交通核 → `u`（二层交通核）→ `n`（会议室，可见物品）。
5. 可选：`world validate hicampus`（拓扑检查）。更细的特性与契约见 [`docs/games/hicampus/SPEC/`](docs/games/hicampus/SPEC/SPEC.md)。**修改 HiCampus 包内 YAML 后的再生成命令**见 [`backend/app/games/hicampus/package/README.md`](backend/app/games/hicampus/package/README.md)。

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

### 代码注释与特性文档（全局）

- **不要在实现代码中**用 **`F02`、`F03`… 等特性编号**、SPEC 章节号（如 `§5.4`）或「某特性 §x」来标注注释、模块/类 docstring、用户可见文案或**业务标识符命名**；特性目标、范围与验收应写在 **`docs/**/SPEC/`**、ADR 或 issue / 待办清单中。
- 代码里只写 **行为、不变量、边界条件、调用约定**；若必须指向文档，用 **目录级** 指引（例如「见 `docs/models/SPEC/features/`」），避免把带特性编号的文件名写进核心业务逻辑（脚本占位说明等可保留仓库内真实路径，但仍避免在注释里堆叠 `Fxx` 标签）。

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

测试工程化基于 pytest (后端) 和 vitest (前端)，详见 `docs/testing/SPEC/SPEC.md`。

**后端 pytest 必须使用与仓库一致的 Python 依赖环境。** 项目约定本地使用 **Conda 环境 `campusworld`**（见上文「Python 执行环境（Conda `campusworld`）」）：先 `conda activate campusworld`，再进入 `backend` 运行 `pytest`；否则极易因错用 `base`/系统 Python 而失败。不激活时务必使用 **`conda run -n campusworld pytest …`**（工作目录为 `backend`），勿在无 `pytest` 或未装 `requirements` 的解释器上直接执行 `pytest`。

**锁与死锁**：需真实 PostgreSQL 的集成用例应避免多连接对多行以不一致顺序加锁、在持锁事务中长时间阻塞；审查清单见 `docs/testing/SPEC/SPEC.md` 中「集成测试、行锁与死锁风险」。

```bash
# 后端测试（须在 conda campusworld 环境中，或改用 conda run -n campusworld）
cd backend
pytest                          # 运行所有测试
pytest -m unit                  # 仅运行单元测试
pytest -m integration           # 仅运行集成测试
pytest tests/models/            # 按模块运行测试
pytest tests/ssh/               # SSH 模块测试
pytest tests/services/           # 服务层测试
pytest --cov=app --cov-report=xml  # 带覆盖率

# 前端测试
cd frontend
npm run test                    # 运行测试
npm run test:coverage           # 带覆盖率
```

### 测试目录结构

```
backend/tests/
├── conftest.py              # 共享 fixtures
├── core/                    # 核心模块测试
│   └── test_database.py     # 数据库兼容性测试
├── models/                  # 数据模型测试
│   ├── test_singularity_room.py
│   └── test_demo_building.py
├── ssh/                     # SSH 模块测试
│   ├── test_session.py
│   ├── test_game_handler.py
│   └── test_entry_router.py
├── commands/                # 命令系统测试
│   └── test_enter_world.py
├── game_engine/             # 游戏引擎测试
│   └── test_campus_life.py
└── services/                # 服务层测试
    ├── test_bulletin_board_service.py
    └── test_system_bulletin_manager.py
```

### 测试分类

| 类型 | 标记 | 说明 |
|------|------|------|
| Unit | `@pytest.mark.unit` | 隔离的组件测试 |
| Integration | `@pytest.mark.integration` | 需要数据库/服务 |
| SSH | `@pytest.mark.ssh` | SSH 模块测试 |
| Models | `@pytest.mark.models` | 数据模型测试 |
| Commands | `@pytest.mark.commands` | 命令系统测试 |
| Services | `@pytest.mark.services` | 服务层测试 |
| Game | `@pytest.mark.game` | 游戏引擎测试 |

### Fixtures

共享 fixtures 定义在 `backend/tests/conftest.py`，包括：
- `mock_db_session` - 模拟数据库会话
- `mock_user_node` - 模拟用户节点
- `mock_user_node_with_world` - 模拟有世界恢复状态的用户
- `mock_admin_node` - 模拟管理员用户节点
- `mock_ssh_session` - 模拟 SSH 会话
- `mock_ssh_client` - 模拟 Paramiko SSH 客户端
- `sample_room` / `sample_character` / `sample_world` - 示例数据 fixtures
- `mock_command_context` - 模拟命令执行上下文
- `mock_game_handler` - 模拟游戏处理器
- `mock_entry_router` - 模拟入口路由器

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

# Rules
1. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.
Before implementing:

State your assumptions explicitly. If uncertain, ask.
If multiple interpretations exist, present them - don't pick silently.
If a simpler approach exists, say so. Push back when warranted.
If something is unclear, stop. Name what's confusing. Ask.
2. Simplicity First
Minimum code that solves the problem. Nothing speculative.

No features beyond what was asked.
No abstractions for single-use code.
No "flexibility" or "configurability" that wasn't requested.
No error handling for impossible scenarios.
If you write 200 lines and it could be 50, rewrite it.
Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

3. Surgical Changes
Touch only what you must. Clean up only your own mess.

When editing existing code:

Don't "improve" adjacent code, comments, or formatting.
Don't refactor things that aren't broken.
Match existing style, even if you'd do it differently.
If you notice unrelated dead code, mention it - don't delete it.
When your changes create orphans:

Remove imports/variables/functions that YOUR changes made unused.
Don't remove pre-existing dead code unless asked.
The test: Every changed line should trace directly to the user's request.

4. Goal-Driven Execution
Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

"Add validation" → "Write tests for invalid inputs, then make them pass"
"Fix the bug" → "Write a test that reproduces it, then make it pass"
"Refactor X" → "Ensure tests pass before and after"
For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

These guidelines are working if: fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.