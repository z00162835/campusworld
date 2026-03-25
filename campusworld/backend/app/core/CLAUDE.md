# Core Module - 后端核心模块

提供应用程序的基础设施支持，包括配置管理、数据库、安全认证和日志系统。

## 模块组成

### 配置管理

**config_manager.py**
- 从 YAML 文件加载配置
- 支持多环境配置 (dev/prod/test)
- 提供配置热重载
- 统一配置访问接口

**settings.py**
- Pydantic 配置模型
- 类型安全的配置访问
- 配置验证和默认值
- 包含: App/API/Server/Database/Security/Logging 等配置类

### 数据库

**database.py**
- SQLAlchemy 引擎创建
- SessionLocal 会话管理
- 连接池配置
- 数据库初始化函数

**models/base.py**
- 基础模型类
- 时间戳自动填充
- 软删除支持

### 安全认证

**security.py**
- JWT 令牌生成和验证
- 密码哈希 (bcrypt)
- 密码验证
- Token 过期处理

**permissions.py**
- 基于角色的权限系统
- 权限检查装饰器
- 用户组支持

### 日志系统

**log/** (基于 structlog + Python logging)
- `manager.py`: LoggingManager 日志管理器
- `context.py`: LoggingContext 日志上下文
- `decorators.py`: log_function_call 装饰器
- `handlers.py`: 自定义处理器(RotatingFileHandler, TimedRotatingFileHandler, DatabaseHandler, EmailHandler)
- `filters.py`: 多种过滤器(SensitiveDataFilter, LevelFilter, ModuleFilter等)
- `formatters.py`: 格式化器
- `middleware.py`: LoggingMiddleware 中间件

**LoggerNames** 预定义日志器:
- `ROOT`, `APP`, `SSH`, `GAME`, `DATABASE`, `API`
- `AUTH`, `CORE`, `UTILS`, `TESTS`, `PERFORMANCE`
- `AUDIT`, `SECURITY`, `COMMAND`, `PROTOCOL`, `SESSION`

### 其他

**paths.py**
- 应用路径管理
- 动态路径解析

**auth.py**
- 认证依赖注入
- 当前用户解析
- OAuth 支持

## 使用示例

```python
from app.core.config_manager import get_config, get_setting
from app.core.database import SessionLocal, get_db
from app.core.security import create_access_token, verify_password
from app.core.log import get_logger, LoggerNames

# 配置
config = get_config()
setting = get_setting('app.name')

# 数据库
db = SessionLocal()
# ... 使用 db
db.close()

# 日志
logger = get_logger(LoggerNames.API)
logger.info("message", key="value")
```

## 配置项

主要配置在 `backend/config/settings.yaml`:

```yaml
app:
  name: CampusWorld
  version: 0.1.0

database:
  host: localhost
  port: 5432
  name: campusworld

security:
  secret_key: "your-secret-key"
  algorithm: HS256
  access_token_expire_minutes: 11520

ssh:
  host_key_path: ssh_host_key
  port: 2222
```
