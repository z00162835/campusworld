# Core Module SPEC

> **Architecture Role**: 本模块属于**系统适配层**的公共服务，为整个系统提供配置管理、数据库连接、安全认证和日志等基础能力。所有上层模块都依赖 core 模块的基础设施。

## Module Overview

核心模块（`backend/app/core/`）提供系统基础设施。

```
core/
├── config_manager.py   # YAML 配置管理
├── settings.py         # Pydantic 配置模型
├── database.py        # SQLAlchemy 连接
├── security.py         # JWT/bcrypt 安全
├── authorization.py    # 认证依赖注入
├── permissions.py      # RBAC 权限系统
├── paths.py            # 路径管理
└── log/                # 结构化日志系统
```

## Core Abstractions

### 配置

| 类/文件 | 说明 |
|---|---|
| `get_config()` | 获取全局配置实例 |
| `get_setting(path)` | 获取指定配置项 |
| `Settings` (Pydantic) | 配置模型：App/API/Server/Database/Security/Logging |

### 安全

| 类/文件 | 说明 |
|---|---|
| `create_access_token()` | 创建 JWT Token |
| `verify_password()` | 验证密码 |
| `get_password_hash()` | 哈希密码 |
| `@require_permission()` | 权限检查装饰器 |
| `@require_admin` | 管理员权限装饰器 |

### 日志

| 类/文件 | 说明 |
|---|---|
| `get_logger(name)` | 获取日志器 |
| `LoggerNames` | 预定义日志器名称枚举 |
| `@log_function_call` | 函数调用日志装饰器 |
| `@log_execution_time` | 执行时间日志装饰器 |

## User Stories

1. **配置管理**: 所有服务通过 `get_config()` 获取配置，支持多环境切换
2. **安全认证**: API 请求通过 JWT Token 验证身份，权限不足返回 403
3. **日志追踪**: 所有模块通过 `get_logger()` 记录日志，统一格式便于分析

## Acceptance Criteria

- [ ] `get_config()` 能读取 YAML 配置
- [ ] `create_access_token()` 生成有效的 JWT Token
- [ ] `@require_permission("user.manage")` 正确拦截无权限请求
- [ ] `get_logger(LoggerNames.API)` 返回正确的日志器

## Design Decisions

1. **为何用 YAML 配置**: 结构化配置优于环境变量，支持嵌套和引用
2. **为何用 Pydantic Settings**: 类型安全，自动验证，IDE 支持好
3. **为何用 structlog**: 结构化日志便于查询和分析，支持上下文传播

## Dependencies

- 被所有上层模块依赖（commands/models/game_engine/ssh/protocols）