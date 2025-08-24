# CampusWorld 配置系统

CampusWorld 采用基于 YAML 的配置管理系统，提供灵活的配置管理和环境分离。

## 🏗️ 配置架构

### 1. 配置文件结构

```
backend/
├── config/
│   ├── settings.yaml          # 基础配置文件
│   ├── settings.dev.yaml      # 开发环境配置
│   ├── settings.test.yaml     # 测试环境配置
│   └── settings.prod.yaml     # 生产环境配置
├── app/core/
│   ├── config_manager.py      # 配置管理器
│   ├── settings.py            # Pydantic配置模型
│   └── config.py              # 配置接口（向后兼容）
```

### 2. 配置层次

- **基础配置** (`settings.yaml`): 包含所有环境的通用配置
- **环境配置** (`settings.{env}.yaml`): 覆盖特定环境的配置
- **环境变量**: 最高优先级，可以覆盖任何配置文件中的值

## 📋 配置领域

### 应用配置 (app)

```yaml
app:
  name: "CampusWorld"
  version: "0.1.0"
  description: "A modern campus world application"
  debug: false
  environment: "development"
```

### API配置 (api)

```yaml
api:
  v1_prefix: "/api/v1"
  title: "CampusWorld API"
  description: "CampusWorld REST API Documentation"
  docs_url: "/docs"
  redoc_url: "/redoc"
  openapi_url: "/openapi.json"
```

### 服务器配置 (server)

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  workers: 1
  reload: true
  access_log: true
```

### 安全配置 (security)

```yaml
security:
  secret_key: "your-secret-key-here"
  algorithm: "HS256"
  access_token_expire_minutes: 11520  # 8 days
  refresh_token_expire_days: 30
  password_min_length: 8
  bcrypt_rounds: 12
```

### 数据库配置 (database)

```yaml
database:
  engine: "postgresql"
  host: "localhost"
  port: 5432
  name: "campusworld"
  user: "campusworld_user"
  password: "campusworld_password"
  pool_size: 20
  max_overflow: 30
  pool_pre_ping: true
  pool_recycle: 300
  echo: false
```

### Redis配置 (redis)

```yaml
redis:
  host: "localhost"
  port: 6379
  db: 0
  password: ""
  max_connections: 10
  socket_timeout: 5
  socket_connect_timeout: 5
```

### 缓存配置 (cache)

```yaml
cache:
  default_ttl: 3600  # 1 hour
  max_size: 1000
  enable_compression: true
```

### 日志配置 (logging)

```yaml
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  date_format: "%Y-%m-%d %H:%M:%S"
  file_path: "logs/campusworld.log"
  max_file_size: "10MB"
  backup_count: 5
  console_output: true
  file_output: false
```

### CORS配置 (cors)

```yaml
cors:
  allowed_origins:
    - "*"
  allowed_methods:
    - "GET"
    - "POST"
    - "PUT"
    - "DELETE"
    - "PATCH"
    - "OPTIONS"
  allowed_headers:
    - "*"
  allow_credentials: true
  max_age: 86400
```

### 邮件配置 (email)

```yaml
email:
  smtp_host: "smtp.gmail.com"
  smtp_port: 587
  smtp_user: ""
  smtp_password: ""
  use_tls: true
  from_email: "noreply@campusworld.com"
  from_name: "CampusWorld"
```

### 文件存储配置 (storage)

```yaml
storage:
  type: "local"  # local, s3, azure, gcs
  local_path: "uploads/"
  max_file_size: "10MB"
  allowed_extensions:
    - "jpg"
    - "jpeg"
    - "png"
    - "gif"
    - "pdf"
    - "doc"
    - "docx"
```

### 监控配置 (monitoring)

```yaml
monitoring:
  enable_metrics: true
  metrics_port: 9090
  health_check_interval: 30
  enable_tracing: false
  tracing_host: "localhost"
  tracing_port: 6831
```

### 第三方服务配置 (external_services)

```yaml
external_services:
  payment:
    provider: "stripe"
    api_key: ""
    webhook_secret: ""
  sms:
    provider: "twilio"
    account_sid: ""
    auth_token: ""
    from_number: ""
  maps:
    provider: "google"
    api_key: ""
```

### 业务配置 (business)

```yaml
business:
  user:
    default_avatar: "default-avatar.png"
    max_login_attempts: 5
    lockout_duration: 900  # 15 minutes
  campus:
    max_members: 1000
    max_activities: 100
  world:
    max_players: 10000
    save_interval: 300  # 5 minutes
```

### 开发配置 (development)

```yaml
development:
  enable_debug_toolbar: false
  enable_profiling: false
  mock_external_services: true
  seed_data: true
```

## 🔧 环境变量覆盖

### 环境变量命名规则

环境变量使用 `CAMPUSWORLD_` 前缀，配置路径用下划线分隔：

```bash
# 数据库配置
export CAMPUSWORLD_DATABASE_HOST=production-db.example.com
export CAMPUSWORLD_DATABASE_PASSWORD=secure_password

# 安全配置
export CAMPUSWORLD_SECURITY_SECRET_KEY=your-production-secret-key

# Redis配置
export CAMPUSWORLD_REDIS_PASSWORD=redis_password
```

### 环境变量优先级

1. **环境变量** (最高优先级)
2. **环境特定配置文件** (`settings.{env}.yaml`)
3. **基础配置文件** (`settings.yaml`)
4. **默认值** (最低优先级)

## 🚀 使用方法

### 1. 在代码中使用配置

```python
from app.core.config import get_setting, get_config

# 获取单个配置值
db_host = get_setting('database.host', 'localhost')
api_prefix = get_setting('api.v1_prefix', '/api/v1')

# 获取配置管理器
config = get_config()
db_url = config.get_database_url()
redis_url = config.get_redis_url()

# 获取整个配置段
db_config = get_setting('database')
redis_config = get_setting('redis')
```

### 2. 使用Pydantic配置模型

```python
from app.core.settings import Settings, create_settings_from_config
from app.core.config_manager import get_config

# 创建配置实例
config_manager = get_config()
settings = create_settings_from_config(config_manager)

# 访问配置
app_name = settings.app.name
db_host = settings.database.host
security_config = settings.security
```

### 3. 环境变量配置

```bash
# 设置环境
export ENVIRONMENT=production

# 设置敏感配置
export CAMPUSWORLD_SECURITY_SECRET_KEY=your-production-secret
export CAMPUSWORLD_DATABASE_PASSWORD=production-db-password
export CAMPUSWORLD_REDIS_PASSWORD=production-redis-password

# 启动应用
python -m app.main
```

## 🔍 配置验证

### 1. 使用验证脚本

```bash
cd backend
python scripts/validate_config.py
```

### 2. 手动验证

```python
from app.core.config_manager import ConfigManager

# 创建配置管理器
config_manager = ConfigManager()

# 验证配置
if config_manager.validate():
    print("配置验证通过")
else:
    print("配置验证失败")

# 重新加载配置
config_manager.reload()
```

## 📝 最佳实践

### 1. 配置文件管理

- 将敏感信息（密码、密钥）放在环境变量中
- 使用有意义的默认值
- 为不同环境创建专门的配置文件
- 定期审查和更新配置

### 2. 环境分离

- 开发环境：启用调试功能，使用本地服务
- 测试环境：模拟生产环境，禁用调试功能
- 生产环境：优化性能，启用监控，禁用开发功能

### 3. 安全考虑

- 不要在配置文件中硬编码敏感信息
- 使用强密码和密钥
- 定期轮换密钥和密码
- 限制配置文件的访问权限

### 4. 性能优化

- 合理设置连接池大小
- 配置适当的缓存策略
- 优化日志级别和输出
- 监控配置对性能的影响

## 🐛 故障排除

### 1. 常见问题

**配置加载失败**
```bash
# 检查配置文件路径
ls -la backend/config/

# 检查YAML语法
python -c "import yaml; yaml.safe_load(open('backend/config/settings.yaml'))"
```

**环境变量不生效**
```bash
# 检查环境变量
env | grep CAMPUSWORLD

# 重新加载shell配置
source ~/.bashrc  # 或 ~/.zshrc
```

**配置验证失败**
```bash
# 运行验证脚本
python backend/scripts/validate_config.py

# 检查必需配置
python -c "from app.core.config_manager import ConfigManager; ConfigManager().validate()"
```

### 2. 调试技巧

```python
# 启用调试模式
import logging
logging.basicConfig(level=logging.DEBUG)

# 查看配置内容
from app.core.config_manager import get_config
config = get_config()
print(config.get_all())
```

## 📚 相关资源

- [YAML 官方文档](https://yaml.org/)
- [Pydantic 配置管理](https://pydantic-docs.helpmanual.io/usage/settings/)
- [Python 环境变量管理](https://docs.python.org/3/library/os.html#os.environ)
- [FastAPI 配置最佳实践](https://fastapi.tiangolo.com/tutorial/settings/)

---

通过使用这套配置系统，您可以灵活地管理不同环境的配置，确保应用的安全性和可维护性。
