# CampusWorld 快速启动指南

本指南将帮助您快速启动 CampusWorld 项目，包括环境搭建、依赖安装和项目运行。

## 🚀 快速启动 (推荐方式)

### 1. 一键初始化

```bash
# 克隆项目
git clone <your-repository-url>
cd campusworld

# 运行初始化脚本 (自动完成所有设置)
./scripts/setup.sh
```

### 2. 启动服务

初始化完成后，按照提示启动服务：

```bash
# 启动后端服务（推荐：引擎 + HTTP/WebSocket + SSH，与 HiCampus / world 命令一致）
cd backend
conda activate campusworld
python campusworld.py

# 新开终端，启动前端服务
cd frontend
npm run dev
```

### 3. 访问应用

- **前端应用**: http://localhost:3000
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/api/v1/docs
- **数据库管理**: http://localhost:8080

## 🔧 手动设置 (可选)

如果您想手动控制每个步骤，可以按照以下方式：

### 1. 环境要求检查

确保您的系统已安装：
- Miniconda (Python 3.9+)
- Node.js 18+
- Docker & Docker Compose
- Git

### 2. 启动基础设施

```bash
# 启动数据库和缓存服务
docker compose -f docker-compose.dev.yml up -d
```

### 3. 后端设置

```bash
cd backend

# 创建 conda 环境
conda env create -f environment.yml
conda activate campusworld

# 安装依赖
pip install -r requirements/dev.txt

# 创建环境配置
cp .env.example .env
# 编辑 .env 文件（`CAMPUSWORLD_*` 前缀），用于覆盖 YAML 配置

# 初始化 / 迁移数据库（默认 migrate：建表 + schema 补丁 + 可选种子）
python -m db.init_database
# 显式：python -m db.init_database migrate
# 危险重建（仅 PostgreSQL，会清空 public）：需 CAMPUSWORLD_ALLOW_DB_RESET=true 且加 --i-understand
# CAMPUSWORLD_ALLOW_DB_RESET=true python -m db.init_database reset --i-understand
# scripts/setup.sh 本地自动化：RESET_DB=1（会导出 CAMPUSWORLD_ALLOW_DB_RESET 并调用 reset --i-understand）

# 诊断 seed/建表状态（只读）
python scripts/diagnose_seed_state.py

# 启动服务（系统入口：主程序）
conda activate campusworld
python campusworld.py
```

**系统入口说明**：请使用 **`python campusworld.py`**。主程序会依次拉起 **引擎（GameLoader）**、**HTTP/WebSocket**（FastAPI，见 `app.api.http_app`）、**SSH**。默认 **`game_engine.load_installed_worlds_on_start: true`**：会在启动时对 **`world_runtime_states` 中已 `install` 的世界**执行 `load_game`（重启后保留安装状态并自动进内存）。首次使用仍需 **`world install <world_id>`**（例如 `hicampus`）写入安装状态。可选 **`game_engine.auto_load_discovered_on_start`**（或旧键 **`auto_load_on_start`**）用于额外按「磁盘发现的包」装载，与 install 状态无关。

### 4. 前端设置

```bash
cd frontend

# 安装依赖
npm install

# 创建环境配置
cp .env.example .env
# 编辑 .env 文件，配置 API 地址等

# 启动服务
npm run dev
```

## 📋 环境配置

### 后端环境变量 (.env)

```bash
# CampusWorld Backend Environment Variables (override YAML)
ENVIRONMENT=development

# 安全配置
CAMPUSWORLD_SECURITY_SECRET_KEY=dev-secret-key-change-in-production

# 数据库配置（覆盖 backend/config/settings*.yaml）
CAMPUSWORLD_DATABASE_HOST=localhost
CAMPUSWORLD_DATABASE_PORT=5433
CAMPUSWORLD_DATABASE_NAME=campusworld_dev
CAMPUSWORLD_DATABASE_USER=campusworld_dev_user
CAMPUSWORLD_DATABASE_PASSWORD=campusworld_dev_password

# Redis 配置
CAMPUSWORLD_REDIS_HOST=localhost
CAMPUSWORLD_REDIS_PORT=6380
CAMPUSWORLD_REDIS_PASSWORD=

# 日志配置
CAMPUSWORLD_LOGGING_LEVEL=DEBUG
```

### 前端环境变量 (.env)

```bash
# CampusWorld Frontend Environment Configuration
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_TITLE=CampusWorld
VITE_APP_VERSION=0.1.0
```

## 🐳 Docker 方式启动

如果您更喜欢使用 Docker：

```bash
# 启动开发环境
docker compose -f docker-compose.dev.yml up -d

# 启动生产环境
docker compose up -d
```

## 🧪 验证安装

### 1. 检查后端服务

```bash
# 检查 API 健康状态
curl http://localhost:8000/api/v1/health

# 检查 API 文档
open http://localhost:8000/api/v1/docs
```

### 2. 检查前端服务

```bash
# 检查前端页面
open http://localhost:3000
```

### 3. 检查数据库

```bash
# 访问数据库管理界面
open http://localhost:8080
```

## 🌍 安装 HiCampus 世界（可选）

HiCampus 是内置示例世界包，目录为 `backend/app/games/hicampus/`。在 SSH/终端中使用 **`look`**、方向键移动（`n`/`u` 等）浏览房间与物品时，依赖图数据库中的房间与出口；因此需要 **PostgreSQL** 已启动且已完成库初始化，且包内 [`backend/app/games/hicampus/manifest.yaml`](backend/app/games/hicampus/manifest.yaml) 中 **`graph_seed: true`**（默认如此：安装世界时会将包快照写入图库）。若无 PostgreSQL、仅做 API 调试，可将 `graph_seed` 改为 `false`，此时 **`world install` 仍可能成功**，但世界内浏览/移动通常不可用。

**前置条件**

- 后端已按上文配置数据库并完成 `python -m db.init_database`（或等价迁移流程）。
- 引擎与 SSH 随 **`python campusworld.py`** 启动；文档与脚本均以该命令为唯一推荐的后端入口。详情见根目录 [`CLAUDE.md`](CLAUDE.md)。

**步骤**

1. 使用具备 **`admin.world.manage`** 的账号接入 **SSH 会话**（或项目提供的同名命令通道）。
2. 执行 **`world install hicampus`**；可选 **`world status hicampus`** 查看是否已加载。
3. 用户登录后位于 **奇点屋**：执行 **`look`** 应看到入口 **hicampus**；**`enter hicampus`** 进入门户厅（`hicampus_gate`）。
4. **示例深链路**（图种子成功后）：`n`（连桥）→ `n`（广场）→ `n`（F1 首层交通核）→ `w`（首层卫生间，可看物品）→ `e` 返回 → `u`（二层交通核）→ `n`（会议室，可看物品）。
5. 可选：**`world validate hicampus`** 做拓扑检查。

架构说明、manifest 与特性文档：根目录 [`CLAUDE.md`](CLAUDE.md)（「世界内容包」「安装 HiCampus 世界」）、[`docs/games/hicampus/SPEC/SPEC.md`](docs/games/hicampus/SPEC/SPEC.md)。

## 🔍 常见问题

### 1. 端口冲突

如果遇到端口冲突，可以修改配置文件：

- **后端端口**: 修改 `backend/.env` 中的端口配置
- **前端端口**: 修改 `frontend/vite.config.ts` 中的端口配置
- **数据库端口**: 修改 `docker-compose.dev.yml` 中的端口映射

### 2. 数据库连接失败

```bash
# 检查数据库服务状态
docker compose -f docker-compose.dev.yml ps

# 重启数据库服务
docker compose -f docker-compose.dev.yml restart postgres_dev
```

### 3. 依赖安装失败

```bash
# 清理并重新安装后端依赖
cd backend
conda env remove -n campusworld -y
conda env create -f environment.yml
conda activate campusworld
pip install --upgrade pip
pip install -r requirements/dev.txt

# 清理并重新安装前端依赖
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## 📚 下一步

启动成功后，您可以：

1. **阅读文档**: 查看 `docs/` 目录下的详细文档；架构与世界语义见根目录 `CLAUDE.md`
2. **安装示例世界**: 按需按上文「安装 HiCampus 世界」在终端中加载 HiCampus 包
3. **探索代码**: 了解项目结构和代码组织
4. **运行测试**: 执行测试套件验证功能
5. **开始开发**: 根据需求进行功能开发

## 🆘 获取帮助

如果遇到问题：

1. 查看项目文档
2. 搜索 GitHub Issues
3. 在 GitHub Discussions 中提问
4. 联系项目维护者

---

**提示**: 首次启动可能需要几分钟时间，请耐心等待所有服务启动完成。
