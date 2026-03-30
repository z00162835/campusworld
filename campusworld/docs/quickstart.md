# 快速启动

## 环境要求

| 组件 | 版本要求 |
|------|----------|
| Python | 3.11+ |
| Node.js | 18+ |
| PostgreSQL | 13+ |
| Docker & Docker Compose | 最新版 |
| Conda | 可选，推荐用于 Python 环境管理 |

## 方式一：一键初始化（推荐）

```bash
cd campusworld
./scripts/setup.sh
```

该脚本会：
1. 启动 Docker 服务（PostgreSQL、Redis）
2. 创建 Conda 环境并安装 Python 依赖
3. 初始化数据库
4. 启动后端和前端服务

## 方式二：手动启动

### 1. 启动 Docker 服务

```bash
docker compose -f docker-compose.dev.yml up -d
```

验证服务状态：
```bash
docker compose -f docker-compose.dev.yml ps
```

### 2. 配置后端

```bash
cd backend

# 创建 Conda 环境
conda env create -f environment.yml
conda activate campusworld

# 或使用虚拟环境
python -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt

# 复制并编辑环境配置
cp .env.example .env
# 编辑 .env 中的数据库连接信息
```

### 3. 初始化数据库

```bash
cd backend
python -m db.init_database
```

### 4. 启动后端

```bash
# 方式 A：完整启动（含 SSH 服务器，推荐）
python campusworld.py

# 方式 B：仅启动 API 服务
uvicorn campusworld:app --reload --host 0.0.0.0 --port 8000
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

## 访问服务

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 Web | http://localhost:5173 | Vue3 开发服务器 |
| API 文档 | http://localhost:8000/docs | Swagger UI |
| SSH 游戏终端 | ssh localhost -p 2222 | 游戏命令交互 |
| 数据库管理 | http://localhost:8080 | Adminer（可选） |

## 登录凭据

开发环境默认账户：
- 用户名：`admin`
- 密码：`admin123`

## 故障排查

### Docker 服务启动失败

```bash
# 检查 Docker 是否运行
docker info

# 查看日志
docker compose -f docker-compose.dev.yml logs postgres
```

### Python 依赖安装失败

```bash
# 确保使用正确的 Python 版本
python --version  # 应该是 3.11+

# 使用 conda
conda clean --all
conda env update -f environment.yml
```

### 数据库连接错误

```bash
# 检查 PostgreSQL 是否运行
docker compose -f docker-compose.dev.yml ps postgres

# 进入容器检查
docker compose -f docker-compose.dev.yml exec postgres psql -U postgres -d campusworld
```

### SSH 连接失败

```bash
# 检查端口占用
lsof -i :2222

# 使用调试模式启动
python campusworld.py --log-level DEBUG
```

## 下一步

- [配置系统](./configuration.md) — 了解 YAML 配置结构
- [后端开发](../backend/CLAUDE.md) — 后端模块详细说明
- [look 命令使用](../backend/docs/look_command_usage.md) — 游戏终端基础操作