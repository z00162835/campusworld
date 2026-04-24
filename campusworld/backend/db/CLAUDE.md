# Database Module - 数据库模块

> **Architecture Role**: 本模块是**知识本体**的持久化层。PostgreSQL 通过 GraphNode/GraphEdge 表支撑 CampusWorld 的**全图数据结构**，所有实体和语义关系都持久化于此。属于"系统适配层"的数据接入能力，为上层的知识服务层提供可靠的数据存储。

PostgreSQL 数据库管理和初始化。

## 模块结构

```
db/
├── init_database.py          # CLI：migrate（默认）/ reset（PostgreSQL 危险重建）
├── migrate_report.py         # ensure_* 顺序执行、报表、reset 门闸
├── schema_migrations.py      # 轻量增量迁移（非 Alembic）
├── schemas/
│   ├── database_schema.sql   # 完整/片段 SQL 真源（补丁从片段抽取）
│   ├── verify_schema.py      # Schema 验证脚本
│   └── run_schema_direct.py  # 直接运行 SQL 文件
└── schemas/README.md         # Schema 文档
```

## 核心概念

### 数据模型 (backend/app/models/)

| 模型 | 描述 |
|------|------|
| User | 用户账户 |
| Character | 角色 |
| Room | 房间/位置 |
| World | 世界 |
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

## 初始化与迁移

**默认（migrate，与无参等价）**：PostgreSQL 上先 **`schema_migrations.ensure_required_extensions`**（postgis / vector 等，否则 `geometry` / `vector` 类型在 `create_all` 时不存在）→ `create_all` → 其余 `ensure_*`（含 `ensure_graph_seed_ontology`）+ 可选种子数据。

```bash
cd backend
python -m db.init_database
# 或显式
python -m db.init_database migrate
# JSON 报表
python -m db.init_database migrate --json-report
```

**危险重建（reset，仅 PostgreSQL）**：删除 `public` schema 内全部对象后，再执行与 migrate 相同后续步骤。

- 必须：`--i-understand`
- 门闸：`CAMPUSWORLD_ALLOW_DB_RESET=true` **或** 配置 `development.allow_db_reset: true`（各环境 YAML 中默认为 `false`）

```bash
CAMPUSWORLD_ALLOW_DB_RESET=true python -m db.init_database reset --i-understand

`scripts/setup.sh` 在设置 `RESET_DB=1` 时会导出 `CAMPUSWORLD_ALLOW_DB_RESET=true` 并执行上述 reset 命令（仅本地自动化场景）。
```

**其他方式**：

```bash
# 直接跑 SQL（高级）
psql -U postgres -d campusworld -f db/schemas/database_schema.sql

# Docker（若 compose 中定义了 db-init 服务）
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
- **现状**：增量结构变更优先写在 `schema_migrations.py`（`ensure_*`），并在 `migrate_report.run_schema_migrations` 中登记顺序；**未接入 Alembic**。
- **可选后续**：对需版本链或数据迁移的变更引入 Alembic，与现有 `ensure_*` 并存并逐步收敛。
- 大批量操作使用 `bulk_insert_mappings`
- 事务中注意异常回滚
