# CampusWorld 配置系统迁移指南

本指南帮助您从旧的配置系统迁移到新的基于YAML的配置系统。

## 🔄 迁移概述

### 变更内容

1. **删除 LegacySettings 类**: 移除了基于Pydantic BaseSettings的旧配置类
2. **简化配置接口**: 提供更清晰的配置访问函数
3. **统一配置管理**: 所有配置都通过YAML文件和配置管理器管理

### 迁移好处

- **更清晰的配置结构**: 按领域组织的配置项
- **更好的环境分离**: 开发、测试、生产环境配置独立
- **更强的类型安全**: 基于Pydantic的配置验证
- **更灵活的配置覆盖**: 支持环境变量覆盖

## 📋 迁移步骤

### 1. 更新导入语句

#### 旧代码
```python
from app.core.config import settings

# 使用配置
app_name = settings.PROJECT_NAME
db_url = settings.DATABASE_URL
secret_key = settings.SECRET_KEY
```

#### 新代码
```python
from app.core.config import get_app_config, get_database_config, get_security_config

# 使用配置
app_config = get_app_config()
app_name = app_config['name']

db_config = get_database_config()
db_url = db_config.get('url')

security_config = get_security_config()
secret_key = security_config['secret_key']
```

### 2. 配置访问方式变更

#### 旧方式
```python
# 直接访问属性
if settings.is_development:
    print("开发环境")
    
if settings.is_production:
    print("生产环境")

# 访问配置值
api_prefix = settings.API_V1_STR
debug_mode = settings.DEBUG
```

#### 新方式
```python
# 使用环境检查函数
from app.core.config import is_development, is_production

if is_development():
    print("开发环境")
    
if is_production():
    print("生产环境")

# 使用配置函数
from app.core.config import get_api_config, get_app_config

api_config = get_api_config()
api_prefix = api_config['v1_prefix']

app_config = get_app_config()
debug_mode = app_config['debug']
```

### 3. 配置函数映射

| 旧配置属性 | 新配置函数 | 说明 |
|------------|------------|------|
| `settings.PROJECT_NAME` | `get_app_config()['name']` | 应用名称 |
| `settings.VERSION` | `get_app_config()['version']` | 应用版本 |
| `settings.DESCRIPTION` | `get_app_config()['description']` | 应用描述 |
| `settings.API_V1_STR` | `get_api_config()['v1_prefix']` | API前缀 |
| `settings.SECRET_KEY` | `get_security_config()['secret_key']` | 安全密钥 |
| `settings.DATABASE_URL` | `config_manager.get_database_url()` | 数据库URL |
| `settings.REDIS_URL` | `config_manager.get_redis_url()` | Redis URL |
| `settings.ALLOWED_HOSTS` | `get_cors_config()['allowed_origins']` | 允许的主机 |
| `settings.LOG_LEVEL` | `get_logging_config()['level']` | 日志级别 |
| `settings.ENVIRONMENT` | `get_app_config()['environment']` | 运行环境 |
| `settings.DEBUG` | `get_app_config()['debug']` | 调试模式 |

## 🔧 具体迁移示例

### 示例1: 主应用配置

#### 旧代码
```python
from app.core.config import settings

def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
    )
    return app
```

#### 新代码
```python
from app.core.config import get_app_config, get_api_config

def create_application() -> FastAPI:
    app_config = get_app_config()
    api_config = get_api_config()
    
    app = FastAPI(
        title=app_config['name'],
        version=app_config['version'],
        description=app_config['description'],
        openapi_url=f"{api_config['v1_prefix']}/openapi.json",
    )
    return app
```

### 示例2: 数据库配置

#### 旧代码
```python
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
)
```

#### 新代码
```python
from app.core.config import get_database_config, config_manager

db_config = get_database_config()
engine = create_engine(
    config_manager.get_database_url(),
    pool_pre_ping=db_config.get('pool_pre_ping', True),
    pool_recycle=db_config.get('pool_recycle', 300),
)
```

### 示例3: 安全配置

#### 旧代码
```python
from app.core.config import settings

def create_access_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(data, settings.SECRET_KEY, algorithm="HS256")
```

#### 新代码
```python
from app.core.config import get_security_config

def create_access_token(data: dict) -> str:
    security_config = get_security_config()
    expire = datetime.utcnow() + timedelta(
        minutes=security_config['access_token_expire_minutes']
    )
    return jwt.encode(
        data, 
        security_config['secret_key'], 
        algorithm=security_config['algorithm']
    )
```

### 示例4: 环境检查

#### 旧代码
```python
from app.core.config import settings

if settings.is_development:
    print("开发环境配置")
elif settings.is_production:
    print("生产环境配置")
```

#### 新代码
```python
from app.core.config import is_development, is_production

if is_development():
    print("开发环境配置")
elif is_production():
    print("生产环境配置")
```

## 🚀 批量迁移脚本

如果您需要批量更新多个文件，可以使用以下脚本：

```python
#!/usr/bin/env python3
"""
配置迁移脚本
批量更新代码中的配置访问方式
"""

import os
import re
from pathlib import Path

def update_config_imports(file_path):
    """更新配置文件中的导入语句"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 更新导入语句
    old_import = "from app.core.config import settings"
    new_import = """from app.core.config import (
    get_app_config, get_api_config, get_server_config,
    get_database_config, get_redis_config, get_security_config,
    get_cors_config, get_logging_config, is_development,
    is_production, is_testing
)"""
    
    if old_import in content:
        content = content.replace(old_import, new_import)
        print(f"更新导入语句: {file_path}")
    
    return content

def update_config_usage(content):
    """更新配置使用方式"""
    # 更新配置访问
    replacements = [
        (r'settings\.PROJECT_NAME', "get_app_config()['name']"),
        (r'settings\.VERSION', "get_app_config()['version']"),
        (r'settings\.DESCRIPTION', "get_app_config()['description']"),
        (r'settings\.API_V1_STR', "get_api_config()['v1_prefix']"),
        (r'settings\.SECRET_KEY', "get_security_config()['secret_key']"),
        (r'settings\.DATABASE_URL', "config_manager.get_database_url()"),
        (r'settings\.REDIS_URL', "config_manager.get_redis_url()"),
        (r'settings\.ALLOWED_HOSTS', "get_cors_config()['allowed_origins']"),
        (r'settings\.LOG_LEVEL', "get_logging_config()['level']"),
        (r'settings\.ENVIRONMENT', "get_app_config()['environment']"),
        (r'settings\.DEBUG', "get_app_config()['debug']"),
        (r'settings\.is_development', "is_development()"),
        (r'settings\.is_production', "is_production()"),
        (r'settings\.is_testing', "is_testing()"),
    ]
    
    for old_pattern, new_pattern in replacements:
        content = re.sub(old_pattern, new_pattern, content)
    
    return content

def migrate_file(file_path):
    """迁移单个文件"""
    try:
        content = update_config_imports(file_path)
        content = update_config_usage(content)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        print(f"成功迁移: {file_path}")
        
    except Exception as e:
        print(f"迁移失败 {file_path}: {e}")

def main():
    """主函数"""
    project_root = Path(".")
    python_files = project_root.rglob("*.py")
    
    for file_path in python_files:
        if "migrations" not in str(file_path) and "venv" not in str(file_path):
            migrate_file(file_path)

if __name__ == "__main__":
    main()
```

## ✅ 迁移检查清单

### 导入语句更新
- [ ] 更新 `from app.core.config import settings` 导入
- [ ] 添加新的配置函数导入

### 配置访问更新
- [ ] 替换 `settings.PROJECT_NAME` 为 `get_app_config()['name']`
- [ ] 替换 `settings.API_V1_STR` 为 `get_api_config()['v1_prefix']`
- [ ] 替换 `settings.SECRET_KEY` 为 `get_security_config()['secret_key']`
- [ ] 替换 `settings.DATABASE_URL` 为 `config_manager.get_database_url()`
- [ ] 替换环境检查属性为函数调用

### 配置函数使用
- [ ] 使用 `get_app_config()` 获取应用配置
- [ ] 使用 `get_api_config()` 获取API配置
- [ ] 使用 `get_server_config()` 获取服务器配置
- [ ] 使用 `get_database_config()` 获取数据库配置
- [ ] 使用 `get_security_config()` 获取安全配置
- [ ] 使用 `get_cors_config()` 获取CORS配置
- [ ] 使用 `get_logging_config()` 获取日志配置

### 环境检查更新
- [ ] 替换 `settings.is_development` 为 `is_development()`
- [ ] 替换 `settings.is_production` 为 `is_production()`
- [ ] 替换 `settings.is_testing` 为 `is_testing()`

## 🧪 测试迁移

### 1. 运行配置测试
```bash
cd backend
python -m pytest tests/test_config.py -v
```

### 2. 验证配置加载
```bash
cd backend
python scripts/validate_config.py
```

### 3. 启动应用测试
```bash
cd backend
python -m app.main
```

## 🐛 常见问题

### 1. 配置加载失败
**问题**: 应用启动时配置加载失败
**解决**: 检查YAML配置文件语法和路径

### 2. 配置值未找到
**问题**: 某些配置值返回None或默认值
**解决**: 检查配置文件中的键名和层级结构

### 3. 类型错误
**问题**: 配置值类型不匹配
**解决**: 检查YAML文件中的值类型，确保与Pydantic模型匹配

## 📚 相关资源

- [配置系统文档](./configuration.md)
- [Pydantic配置管理](https://pydantic-docs.helpmanual.io/usage/settings/)
- [YAML语法指南](https://yaml.org/spec/)

---

通过遵循本迁移指南，您可以顺利地从旧的配置系统迁移到新的基于YAML的配置系统，享受更好的配置管理和类型安全。
