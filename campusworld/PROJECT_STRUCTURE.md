# CampusWorld 项目目录结构

本文档描述 CampusWorld 项目的实际目录结构。

## 根目录

```
campusworld/
├── CLAUDE.md              # AI/开发者上下文文档（英文）
├── README.md              # 项目主说明（面向访客）
├── PROJECT_STRUCTURE.md    # 本文档
├── CONTRIBUTING.md        # 贡献指南
├── docker-compose*.yml    # Docker 配置
├── scripts/               # 项目脚本
├── docs/                  # 项目文档
├── backend/               # Python 后端
├── frontend/              # Vue3 前端
└── .github/               # GitHub Actions CI/CD
```

## 后端 (backend/)

```
backend/
├── campusworld.py              # 主入口（启动 SSH + FastAPI）
├── app/
│   ├── api/v1/                 # REST API
│   │   ├── api.py              # 路由聚合
│   │   ├── accounts.py          # 账户端点
│   │   └── endpoints/auth.py    # 认证端点
│   ├── core/                   # 核心功能
│   │   ├── settings.py          # Pydantic 配置模型
│   │   ├── config_manager.py    # YAML 配置管理器
│   │   ├── database.py          # SQLAlchemy 连接
│   │   ├── security.py          # 密码加密 / JWT
│   │   ├── authorization.py     # 授权逻辑
│   │   ├── permissions.py       # RBAC 权限系统
│   │   ├── paths.py             # 路径工具
│   │   └── log/                 # 结构化日志（structlog）
│   │       ├── manager.py
│   │       ├── decorators.py    # @log_function_call 等装饰器
│   │       ├── handlers.py      # Handler/Filters/Formatters
│   │       ├── middleware.py    # 请求/响应/错误中间件
│   │       └── context.py
│   ├── models/                  # 纯图数据模型
│   │   ├── base.py              # DefaultObject / DefaultAccount 基类
│   │   ├── user.py              # 用户模型
│   │   ├── accounts.py          # 账户模型
│   │   ├── character.py         # 角色模型
│   │   ├── room.py             # 房间模型
│   │   ├── building.py         # 建筑模型
│   │   ├── world.py            # 世界模型
│   │   ├── campus.py           # 园区模型
│   │   ├── exit.py             # 出口模型
│   │   ├── graph.py            # 图节点/边模型
│   │   ├── factory.py          # 模型工厂（动态发现）
│   │   ├── model_manager.py    # 模型管理器
│   │   └── root_manager.py     # 根节点管理器
│   ├── ssh/                     # SSH 服务器（Paramiko）
│   │   ├── server.py            # SSH 服务器入口
│   │   ├── session.py           # 会话管理
│   │   ├── console.py           # 控制台交互
│   │   ├── input_handler.py    # 输入处理
│   │   ├── protocol_handler.py # 协议处理
│   │   ├── game_handler.py     # 游戏命令处理器
│   │   └── rate_limiter.py      # 速率限制
│   ├── commands/                # 命令系统
│   │   ├── base.py              # BaseCommand 基类
│   │   ├── registry.py          # 命令注册表（自动发现）
│   │   ├── context.py          # CommandContext
│   │   ├── cmdset.py           # 命令集
│   │   ├── init_commands.py    # 命令初始化
│   │   ├── system_commands.py  # 系统命令（look/who 等）
│   │   ├── character.py        # 角色命令
│   │   ├── builder/            # 建造类命令
│   │   │   ├── create_command.py
│   │   │   └── model_discovery.py
│   │   ├── game/               # 游戏命令
│   │   │   └── look_command.py
│   │   ├── admin/              # 管理命令
│   │   └── utils/              # 命令工具
│   ├── game_engine/             # 游戏引擎
│   │   ├── base.py              # 引擎基类
│   │   ├── manager.py           # 引擎管理器
│   │   ├── loader.py            # 内容加载器（自动加载）
│   │   └── interface.py         # 游戏接口
│   ├── games/                   # 游戏内容包
│   │   └── campus_life/        # 校园生活游戏
│   │       ├── game.py
│   │       ├── commands.py
│   │       ├── game_commands.py
│   │       ├── objects.py
│   │       └── scripts.py
│   ├── protocols/               # 协议处理
│   │   ├── base.py             # 协议基类
│   │   ├── http_handler.py     # FastAPI 路由处理
│   │   └── ssh_handler.py     # SSH 命令执行
│   ├── repositories/            # 数据访问层（已创建但核心逻辑在 models 中）
│   └── schemas/                 # Pydantic 请求/响应模型
│       ├── auth.py
│       └── account.py
├── config/                      # YAML 配置文件
│   ├── settings.yaml            # 主配置
│   ├── settings.dev.yaml        # 开发环境
│   ├── settings.prod.yaml       # 生产环境
│   └── tools/                   # 配置工具脚本
├── db/                          # 数据库相关
│   ├── schemas/                 # 数据库 schema 定义
│   ├── seed_data.py            # 种子数据
│   └── init_database.py         # 数据库初始化脚本
├── requirements/                # Python 依赖
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── tests/                       # 后端测试
│   ├── unit/
│   ├── integration/
│   └── README_demo_building.md  # Demo building 生成器文档
├── docs/                        # 后端开发文档
│   ├── look_command_design.md   # look 命令设计文档
│   ├── look_command_usage.md    # look 命令使用指南
│   ├── singularity_room_implementation.md  # 单例房间实现
│   └── examples/
├── scripts/                      # 后端脚本
│   └── database/               # 数据库工具脚本
├── alembic.ini
├── pytest.ini
└── Dockerfile
```

## 前端 (frontend/)

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── main.ts                  # 应用入口
│   ├── App.vue
│   ├── style.css
│   ├── components/
│   │   ├── layout/              # 布局组件
│   │   └── works/               # 业务组件
│   ├── views/
│   │   ├── auth/                # 认证页面
│   │   ├── agents/              # Agent 页面
│   │   ├── discovery/           # 发现页面
│   │   ├── history/             # 历史记录
│   │   ├── spaces/              # 空间页面
│   │   ├── user/                # 用户页面
│   │   └── works/               # 作品页面
│   ├── router/                  # Vue Router 配置
│   ├── stores/                  # Pinia 状态管理
│   ├── utils/                   # 工具函数
│   ├── styles/                  # 样式
│   │   ├── base/
│   │   ├── components/
│   │   └── themes/
│   └── test/                    # 前端测试
├── logs/                        # 前端日志
├── package.json
├── vite.config.ts
├── tsconfig.json
├── Dockerfile
└── .env.example
```

## 文档 (docs/)

```
docs/
├── README.md                    # 文档导航（本文档入口）
├── architecture/README.md       # 系统架构文档
├── configuration.md              # 配置系统说明
├── config-migration.md          # 配置迁移指南
└── conda-setup.md               # Conda 环境设置

# 以下文档待创建（规划中）
├── overview.md                  # 项目概述
├── quickstart.md                # 快速启动详细指南
├── setup.md                     # 环境搭建
├── database/README.md           # 数据库设计
├── api/README.md                # API 设计
├── backend/README.md            # 后端开发指南
├── frontend/README.md           # 前端开发指南
├── testing/README.md            # 测试指南
├── coding-standards.md           # 代码规范
└── deployment/                 # 部署文档
    ├── environments.md
    ├── docker.md
    ├── production.md
    └── monitoring.md
```

## 目录设计原则

### 1. 分层清晰
- API 层 (`api/`) 处理 HTTP 请求
- 模型层 (`models/`) 管理数据结构和关系
- 命令层 (`commands/`) 处理用户输入和业务逻辑
- 协议层 (`protocols/`) 桥接不同通信方式（HTTP/SSH）

### 2. 图数据结构
- 所有实体（Room、Character、User）继承自图节点基类
- 通过关系边（Exit、Relationship）连接
- 支持动态模型发现和扩展

### 3. 命令系统
- 所有命令继承 `BaseCommand`
- 通过命令注册表自动发现
- 支持命令集（CmdSet）组合

### 4. 协议抽象
- HTTP（FastAPI）和 SSH（Paramiko）共享同一游戏引擎
- 协议处理器独立于核心逻辑

## 扩展建议

- 添加微服务支持：拆分 `games/` 为独立服务
- 引入 Kubernetes：基于现有 Docker 配置扩展
- 完善文档：优先补充 docs/ 中规划但未实现的文档