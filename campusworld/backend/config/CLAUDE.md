# Build & Config - 构建与配置

> **Architecture Role**: 本模块属于**系统适配层**的配置管理能力，为各层服务提供可插拔的 YAML 配置底座。所有服务（SSH · API · 数据库 · 引擎）通过统一的配置管理器获取配置，实现环境间的平滑切换。

项目构建、Docker 和配置文件说明。

## 配置文件

### YAML 配置

```
config/
├── settings.yaml        # 主配置
├── settings.dev.yaml    # 开发环境
├── settings.prod.yaml  # 生产环境
├── settings.test.yaml  # 测试环境
└── tools/             # 配置工具
    ├── config_tool.py
    └── config_usage_analyzer.py
```

### 配置结构

```yaml
app:
  name: CampusWorld
  version: 0.1.0
  debug: true
  environment: development

server:
  host: 0.0.0.0
  port: 8000
  workers: 1
  reload: true

database:
  host: localhost
  port: 5432
  name: campusworld
  user: postgres
  password: ${DB_PASSWORD}

security:
  secret_key: ${SECRET_KEY}
  algorithm: HS256
  access_token_expire_minutes: 11520

ssh:
  enabled: true
  port: 2222
  host_key_path: ssh_host_key

logging:
  level: INFO
  console_output: true
```

### 环境变量

```bash
# backend/.env
DB_PASSWORD=your_db_password
SECRET_KEY=your_secret_key
REDIS_PASSWORD=your_redis_password
```

## Docker 构建

### docker-compose.yml

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DB_PASSWORD=${DB_PASSWORD}

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"

  db:
    image: postgres:13
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

### 开发环境

```bash
# 启动完整开发环境
docker compose -f docker-compose.dev.yml up -d

# 启动所有服务
docker compose up -d

# 查看日志
docker compose logs -f

# 停止
docker compose down
```

## 构建命令

### 后端

```bash
cd backend

# 安装依赖
pip install -r requirements/base.txt
pip install -r requirements/dev.txt

# 运行（系统入口）
python campusworld.py

# 测试
pytest

# 打包
python -m build
```

### 前端

```bash
cd frontend

# 安装依赖
npm install

# 开发
npm run dev

# 构建
npm run build

# 测试
npm run test

# Lint
npm run lint
```

## CI/CD

GitHub Actions 工作流在 `.github/workflows/ci.yml`:

```yaml
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: |
          cd backend && pip install -r requirements/dev.txt
          pytest
```

## 环境说明

| 环境 | 配置 | 用途 |
|------|------|------|
| development | settings.dev.yaml | 本地开发 |
| production | settings.prod.yaml | 生产部署 |
| test | settings.test.yaml | 自动化测试 |
