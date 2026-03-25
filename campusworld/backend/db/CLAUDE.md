# Database Module - 数据库模块

PostgreSQL 数据库管理和初始化。

## 模块结构

```
db/
├── init_database.py          # 数据库初始化脚本
├── schemas/
│   ├── database_schema.sql  # 完整数据库schema
│   ├── verify_schema.py    # Schema验证脚本
│   └── run_schema_direct.py # 直接运行schema脚本
└── schemas/README.md        # Schema文档
```

## 核心概念

### 数据模型 (backend/app/models/)

| 模型 | 描述 |
|------|------|
| User | 用户账户 |
| Character | 游戏角色 |
| Room | 房间/位置 |
| World | 游戏世界 |
| Building | 建筑 |
| Exit | 出口/通道 |
| GraphNode | 图节点 |
| GraphEdge | 图边 |

### 关系

```
World (1) ──────< Room (N)
     │
     └─< Character (N)
     │
     └─< Building (N)

Room (1) ──────< Exit (N)
     │
     └─< Building (N)

Room ───< GraphNode ───< GraphEdge
```

## 数据库操作

### 使用 SessionLocal

```python
from app.core.database import SessionLocal, get_db

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 在FastAPI依赖中
@app.get("/users")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return users
```

### CRUD 操作

```python
from app.models.user import User
from app.core.database import SessionLocal

db = SessionLocal()

# 创建
user = User(username="test", email="test@example.com")
db.add(user)
db.commit()

# 读取
user = db.query(User).filter(User.username == "test").first()

# 更新
user.email = "new@example.com"
db.commit()

# 删除
db.delete(user)
db.commit()

db.close()
```

## 初始化数据库

```bash
# 方式1: 使用初始化脚本
cd backend
python -m db.init_database

# 方式2: 直接运行SQL
psql -U postgres -d campusworld -f db/schemas/database_schema.sql

# 方式3: Docker环境
docker compose -f docker-compose.dev.yml up -d db-init
```

## 配置

```yaml
database:
  engine: postgresql
  host: localhost
  port: 5432
  name: campusworld
  user: postgres
  password: ${DB_PASSWORD}
  pool_size: 20
  max_overflow: 30
  echo: false  # 是否显示SQL语句
```

## 开发提示

- 生产环境设置 `echo: false`
- 使用迁移工具 (Alembic) 管理 schema 变更
- 大批量操作使用 `bulk_insert_mappings`
- 事务中注意异常回滚
