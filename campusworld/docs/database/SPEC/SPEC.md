# Database SPEC

> **Architecture Role**: 本模块是**知识本体**的持久化层。PostgreSQL 通过 **`nodes`** / **`relationships`** 等表支撑 CampusWorld 的**全图数据结构**，所有实体和语义关系都持久化于此。属于"系统适配层"的数据接入能力。

## Module Overview

数据库模块（`backend/db/`）管理 PostgreSQL schema 和初始化。

```
db/
├── init_database.py      # 数据库初始化脚本
├── seed_data.py         # 种子数据
└── schemas/
    ├── database_schema.sql   # 完整 schema
    ├── verify_schema.py     # Schema 验证
    └── run_schema_direct.py # 直接运行脚本
```

## Core Abstractions

### 表结构

| 表 | 说明 |
|---|---|
| `nodes` | 知识节点：id/uuid/type_id/type_code/name/description/**attributes**(JSONB)/is_active… |
| `relationships` | 语义边：source_id/target_id/rel_type_code/attributes… |
| `node_types` | 节点类型注册：`type_code`、`schema_definition`（属性 JSON Schema + 同级元数据）、`schema_default`、`inferred_rules`、`typeclass` 等 |
| `users` | 用户账户：id/email/username/hashed_password... |

**`schema_definition` 与实例 `attributes` 的约定**见 [`backend/db/schemas/README.md`](../../../backend/db/schemas/README.md)。

### 关系

```
nodes (1) ───< relationships (N) >─── (N) nodes
     │
     └───< node_types (1)
```

## User Stories

1. **初始化**: 运行 `init_database.py` 创建所有表
2. **种子数据**: 运行 `seed_data.py` 填充初始数据（预定义空间、默认角色）
3. **Schema 验证**: 运行 `verify_schema.py` 检查数据库结构

## Acceptance Criteria

- [ ] `init_database.py` 创建所有表
- [ ] `seed_data.py` 填充预定义空间数据
- [ ] `nodes` / `relationships` 表正确存储实体和关系

## Design Decisions

1. **为何用 PostgreSQL**: 支持 JSONB 属性（Node.attributes），支持复杂查询，支持向量扩展
2. **为何分离 schema 和数据**: schema 定义与种子数据分离，便于版本管理和部署

## Dependencies

- 依赖 `backend/app/models/`（ORM 模型）
- 依赖 `backend/app/core/database.py`（连接管理）