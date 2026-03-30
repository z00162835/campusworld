# Backend - CampusWorld 后端服务

> **Architecture Role**: 后端覆盖**系统适配层**（core/配置/安全/SSH协议）和**知识与能力层**（commands/命令系统 · models/全图数据模型 · game_engine/游戏引擎），为 Agent 服务层提供世界语义交互的能力底座。

FastAPI + PostgreSQL + SSH 的后端服务，提供游戏逻辑、SSH终端和REST API。

## 模块结构

```
backend/
├── app/
│   ├── core/              # 核心模块
│   │   ├── config_manager.py    # 配置管理
│   │   ├── database.py          # 数据库连接
│   │   ├── security.py          # 安全认证
│   │   ├── permissions.py       # 权限系统
│   │   ├── settings.py          # Pydantic配置
│   │   └── log/                 # 日志系统
│   │
│   ├── ssh/                # SSH服务器模块
│   │   ├── server.py            # Paramiko SSH服务器
│   │   ├── session.py           # 会话管理
│   │   ├── console.py           # 终端控制台
│   │   └── input_handler.py     # 输入处理
│   │
│   ├── commands/           # 命令系统
│   │   ├── base.py             # 命令基类
│   │   ├── registry.py         # 命令注册表
│   │   ├── builder/             # 建造命令
│   │   ├── game/                # 游戏命令
│   │   └── admin/               # 管理命令
│   │
│   ├── models/             # 数据模型
│   │   ├── user.py             # 用户
│   │   ├── character.py        # 角色
│   │   ├── room.py             # 房间
│   │   ├── world.py            # 世界
│   │   ├── building.py         # 建筑
│   │   ├── exit.py             # 出口
│   │   └── graph.py             # 图结构
│   │
│   ├── game_engine/        # 游戏引擎
│   │   ├── manager.py          # 引擎管理
│   │   ├── loader.py           # 内容加载
│   │   └── interface.py       # 接口定义
│   │
│   ├── protocols/          # 协议处理
│   │   ├── http_handler.py     # HTTP处理
│   │   └── ssh_handler.py      # SSH处理
│   │
│   ├── games/              # 游戏内容
│   │   └── campus_life/       # 校园生活游戏
│   │
│   └── api/                # REST API
│       └── v1/
│           ├── endpoints/     # API端点
│           └── accounts.py     # 账户API
│
├── config/                 # YAML配置文件
│   ├── settings.yaml
│   ├── settings.dev.yaml
│   └── settings.prod.yaml
│
├── db/                     # 数据库脚本
│   ├── init_database.py
│   └── schemas/
│
└── requirements/           # 依赖管理
    ├── base.txt
    └── dev.txt
```

## 核心功能

### 1. SSH终端服务
- 基于 Paramiko 实现SSH服务器
- 支持交互式命令输入
- 会话管理和认证

### 2. 命令系统
- 抽象命令基类 `BaseCommand`
- 命令上下文 `CommandContext`
- 命令结果 `CommandResult`
- 命令注册表自动发现

### 3. 数据模型
- 纯图数据设计 (Graph-based)
- 世界/房间/角色/建筑关系
- 图结构管理世界连接
- 模型工厂 `model_factory`

### 4. 游戏引擎
- 内容自动加载
- 游戏状态管理
- 命令系统集成
- `GameEngineManager` 统一管理

### 5. 日志系统
- 基于 structlog + Python logging
- 多模块日志分类 (LoggerNames)
- 上下文日志支持

## 入口文件

### campusworld.py

主程序入口:

```python
from campusworld import CampusWorld

app = CampusWorld()
app.start()  # 启动所有服务
app.start_ssh()  # 仅启动SSH
```

## 依赖

主要依赖见 `requirements/base.txt`:
- fastapi==0.116.1
- sqlalchemy==2.0.23
- paramiko==4.0.0
- pydantic==2.5.0
- structlog==23.2.0

## 开发

```bash
# 安装依赖
pip install -r requirements/dev.txt

# 启动后端API
uvicorn campusworld:app --reload

# 启动主程序(含SSH)
python campusworld.py

# 启动SSH服务器
python -m app.ssh.server

# 运行测试
pytest
```

### 测试配置

- **pytest.ini**: `backend/pytest.ini` 定义测试路径、markers、覆盖率配置
- **fixtures**: `backend/tests/conftest.py` 提供共享测试 fixtures

### 测试命令

```bash
pytest                           # 运行所有测试
pytest -m unit                   # 仅运行单元测试
pytest -m integration            # 仅运行集成测试
pytest --cov=app --cov-report=xml  # 带覆盖率
```

### 测试分类

| 标记 | 说明 |
|------|------|
| `@pytest.mark.unit` | 单元测试，隔离组件测试 |
| `@pytest.mark.integration` | 集成测试，需要数据库/服务 |
| `@pytest.mark.ssh` | SSH 模块测试 |
| `@pytest.mark.models` | 数据模型测试 |
| `@pytest.mark.commands` | 命令系统测试 |

## 配置

配置通过 `config/settings.yaml` 管理，支持多环境配置。核心配置项:

- `database.*`: 数据库连接
- `security.*`: JWT/密码配置
- `ssh.*`: SSH服务器配置
- `logging.*`: 日志配置
