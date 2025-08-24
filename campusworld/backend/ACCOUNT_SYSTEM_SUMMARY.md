# CampusWorld 账号系统完整总结

## 🎯 系统概述

CampusWorld 账号系统是一个基于 Evennia 框架设计的企业级用户权限管理系统，采用图数据库存储架构，支持多种账号类型和细粒度权限控制。

## ✨ 核心特性

### 1. 多层级权限系统
- **权限级别**: GUEST → USER → MODERATOR → DEVELOPER → ADMIN → OWNER
- **角色系统**: 支持多种角色组合，每个角色拥有特定权限集合
- **访问级别**: normal → developer → admin，支持层级权限继承

### 2. 账号类型支持
- **AdminAccount**: 系统管理员，拥有所有管理权限
- **DeveloperAccount**: 开发者账号，拥有开发和调试权限
- **UserAccount**: 普通用户账号，基本功能权限
- **CampusUserAccount**: 校园用户账号，扩展校园相关功能

### 3. 图数据库架构
- 所有对象存储在统一的 `nodes` 表中
- 通过 `type` 和 `typeclass` 区分不同对象类型
- 支持复杂的关系查询和属性管理

## 🏗️ 系统架构

### 核心模块

```
app/
├── core/
│   ├── permissions.py      # 权限管理核心
│   ├── auth.py            # 权限验证装饰器
│   ├── security.py        # 安全功能（JWT、密码哈希）
│   └── database.py        # 数据库连接管理
├── models/
│   ├── base.py            # 基础对象类
│   ├── accounts.py        # 账号类型定义
│   └── graph.py           # 图数据模型
├── api/v1/
│   └── accounts.py        # 账号管理API
└── schemas/
    └── account.py         # 数据验证模型
```

### 权限系统设计

```python
# 权限定义
class Permission(Enum):
    # 用户管理权限
    USER_CREATE = "user.create"
    USER_VIEW = "user.view"
    USER_EDIT = "user.edit"
    USER_DELETE = "user.delete"
    USER_MANAGE = "user.manage"
    
    # 系统管理权限
    SYSTEM_ADMIN = "system.admin"
    SYSTEM_DEBUG = "system.debug"
    SYSTEM_LOGS = "system.logs"
    
    # 世界管理权限
    WORLD_VIEW = "world.view"
    WORLD_EDIT = "world.edit"
    WORLD_MANAGE = "world.manage"
    
    # 校园管理权限
    CAMPUS_VIEW = "campus.view"
    CAMPUS_EDIT = "campus.edit"
    CAMPUS_MANAGE = "campus.manage"
```

### 角色权限映射

```python
# 角色权限配置
ROLE_PERMISSIONS = {
    "admin": [
        "user.*",      # 所有用户权限
        "system.*",    # 所有系统权限
        "world.*",     # 所有世界权限
        "campus.*"     # 所有校园权限
    ],
    "dev": [
        "user.view", "user.edit",
        "world.view", "world.edit",
        "system.debug", "system.logs"
    ],
    "user": [
        "user.view", "world.view", "campus.view"
    ]
}
```

## 🔐 安全特性

### 1. 密码安全
- 使用 bcrypt 进行密码哈希
- 支持密码强度验证
- 防止常见弱密码使用

### 2. JWT 令牌系统
- 访问令牌和刷新令牌分离
- 可配置的令牌过期时间
- 支持令牌验证和刷新

### 3. 账号保护
- 失败登录次数限制
- 账号锁定和暂停机制
- 活动状态监控

## 📊 数据库设计

### 核心表结构

```sql
-- 节点类型表
CREATE TABLE node_types (
    id SERIAL PRIMARY KEY,
    type_code VARCHAR(50) UNIQUE NOT NULL,
    type_name VARCHAR(100) NOT NULL,
    typeclass VARCHAR(200),
    classname VARCHAR(100),
    module_path VARCHAR(200),
    description TEXT,
    schema_definition JSONB,
    is_active BOOLEAN DEFAULT TRUE
);

-- 节点实例表
CREATE TABLE nodes (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE NOT NULL,
    type_id INTEGER REFERENCES node_types(id),
    type_code VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_public BOOLEAN DEFAULT FALSE,
    access_level VARCHAR(20) DEFAULT 'normal',
    attributes JSONB DEFAULT '{}',
    tags JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 关系类型表
CREATE TABLE relationship_types (
    id SERIAL PRIMARY KEY,
    type_code VARCHAR(50) UNIQUE NOT NULL,
    type_name VARCHAR(100) NOT NULL,
    description TEXT,
    schema_definition JSONB
);

-- 关系实例表
CREATE TABLE relationships (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE NOT NULL,
    type_id INTEGER REFERENCES relationship_types(id),
    type_code VARCHAR(50) NOT NULL,
    source_id INTEGER REFERENCES nodes(id),
    target_id INTEGER REFERENCES nodes(id),
    attributes JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 索引优化

```sql
-- 性能优化索引
CREATE INDEX idx_nodes_type_code ON nodes(type_code);
CREATE INDEX idx_nodes_name ON nodes(name);
CREATE INDEX idx_nodes_uuid ON nodes(uuid);
CREATE INDEX idx_nodes_attributes ON nodes USING GIN(attributes);
CREATE INDEX idx_nodes_tags ON nodes USING GIN(tags);
CREATE INDEX idx_nodes_access_level ON nodes(access_level);
CREATE INDEX idx_nodes_is_active ON nodes(is_active);

-- 全文搜索支持
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_nodes_name_trgm ON nodes USING GIN(name gin_trgm_ops);
```

## 🚀 API 接口

### 账号管理接口

```python
# 获取账号列表
GET /api/v1/accounts/
  - 支持分页、筛选
  - 权限要求: user.manage

# 获取账号详情
GET /api/v1/accounts/{account_id}
  - 权限要求: user.view

# 创建新账号
POST /api/v1/accounts/
  - 权限要求: user.create
  - 支持多种账号类型

# 更新账号信息
PUT /api/v1/accounts/{account_id}
  - 权限要求: user.edit

# 更新账号状态
PATCH /api/v1/accounts/{account_id}/status
  - 支持锁定、暂停等状态管理
  - 权限要求: user.manage

# 修改账号密码
POST /api/v1/accounts/{account_id}/change-password
  - 权限要求: user.manage

# 删除账号
DELETE /api/v1/accounts/{account_id}
  - 仅管理员可操作
  - 软删除机制
```

### 权限验证装饰器

```python
# 权限验证
@require_permission("user.create")
def create_user():
    pass

# 角色验证
@require_role("admin")
def admin_only():
    pass

# 访问级别验证
@require_access_level("developer")
def dev_only():
    pass

# 便捷装饰器
@require_admin
@require_developer
@require_moderator
@require_user
```

## 🧪 测试覆盖

### 测试项目

1. **安全功能测试**
   - 密码哈希和验证
   - 密码强度检测
   - JWT 令牌生成和验证

2. **权限系统测试**
   - 权限检查功能
   - 角色验证功能
   - 访问级别检查

3. **账号管理测试**
   - 账号创建和实例化
   - 状态管理功能
   - 权限和角色管理

4. **数据库集成测试**
   - 数据库连接
   - 查询功能
   - 数据完整性

5. **完整工作流程测试**
   - 端到端功能验证
   - 权限验证流程
   - 令牌管理流程

### 测试结果

```
总计测试: 5
通过测试: 5
失败测试: 0
通过率: 100.0%
```

## 📋 默认账号

系统预置了三个默认账号用于开发和测试：

| 账号 | 用户名 | 密码 | 角色 | 权限级别 |
|------|--------|------|------|----------|
| 管理员 | admin | admin123 | admin | admin |
| 开发者 | dev | dev123 | dev | developer |
| 校园用户 | campus | campus123 | user, campus_user | normal |

## 🔧 配置说明

### 环境变量

```bash
# 数据库配置
DATABASE_URL=postgresql://user:password@localhost/campusworld
REDIS_URL=redis://localhost:6379

# 安全配置
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=11520
REFRESH_TOKEN_EXPIRE_DAYS=30

# 应用配置
ENVIRONMENT=development
DEBUG=true
```

### YAML 配置文件

```yaml
app:
  name: CampusWorld
  version: 0.1.0
  environment: development
  debug: true

security:
  secret_key: your-secret-key-here
  algorithm: HS256
  access_token_expire_minutes: 11520
  refresh_token_expire_days: 30
  password_min_length: 8
  bcrypt_rounds: 12

database:
  host: localhost
  port: 5432
  name: campusworld
  user: postgres
  password: password
```

## 🚀 部署说明

### 1. 环境准备

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 启动 PostgreSQL
docker-compose up -d postgres

# 启动 Redis
docker-compose up -d redis
```

### 2. 数据库初始化

```bash
# 创建数据库 schema
python db/schemas/run_schema_direct.py

# 创建账号类型
python scripts/create_account_type.py

# 创建默认账号
python scripts/create_default_accounts.py
```

### 3. 启动应用

```bash
# 开发模式
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## 🔮 后续优化建议

### 短期目标
- **动态命令类加载**: 实现从数据库动态创建命令类实例
- **配置热更新**: 支持运行时配置修改和实时生效
- **权限管理**: 基于数据库的命令权限配置

### 中期目标
- **配置版本管理**: 支持配置的版本控制和回滚
- **配置模板**: 提供常用配置的模板和快速应用
- **性能监控**: 添加配置加载的性能指标和告警

### 长期目标
- **配置管理界面**: Web界面进行配置管理
- **配置同步**: 支持多环境配置同步
- **配置分析**: 基于AI的配置优化建议

## 📚 技术栈

- **后端框架**: FastAPI + Python 3.13
- **数据库**: PostgreSQL + SQLAlchemy 2.0
- **缓存**: Redis
- **认证**: JWT + bcrypt
- **配置管理**: YAML + Pydantic
- **测试**: pytest + 自定义测试框架
- **部署**: Docker + Docker Compose

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

**CampusWorld 账号系统** - 企业级权限管理解决方案 🚀
