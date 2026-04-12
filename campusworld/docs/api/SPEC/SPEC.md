# API SPEC

> **Architecture Role**: 本模块是系统的 **REST API 入口**，属于"系统适配层"的接入协议之一，为前端和外部调用者提供 GraphNode/Account/User 的 CRUD 操作接口。

## Module Overview

API 层（`backend/app/api/v1/`）提供 HTTP REST 接口，是 Agent 服务层与后端知识本体交互的主要通道。

当前端点：

| 前缀 | 端点 | 方法 | 权限 | 说明 |
|------|------|------|------|------|
| `/auth` | `/auth/register` | POST | 公开 | 注册用户，JWT 登录 |
| `/auth` | `/auth/login` | POST | 公开 | OAuth2 密码登录 |
| `/accounts` | `/accounts/` | GET | `user.manage` | 账号列表（分页/筛选） |
| `/accounts` | `/accounts/{id}` | GET | `user.view` | 账号详情 |
| `/accounts` | `/accounts/` | POST | `user.create` | 创建账号 |
| `/accounts` | `/accounts/{id}` | PUT | `user.edit` | 更新账号 |
| `/accounts` | `/accounts/{id}/status` | PATCH | `user.manage` | 锁定/暂停账号 |
| `/accounts` | `/accounts/{id}/change-password` | POST | `user.manage` | 修改密码 |
| `/accounts` | `/accounts/{id}` | DELETE | Admin | 删除（软删除）账号 |
| `/accounts` | `/accounts/types/list` | GET | 公开 | 账号类型列表 |
| `/command` | `/command/execute` 等 | POST/GET | 已认证 | 命令执行（与原子图 API 编排组合使用） |

**规划（初稿契约，实现见后续 PR）** — 本体与图谱 **原子服务**：

| 前缀 | 资源 | 方法（草案） | 建议权限 | 说明 |
|------|------|----------------|----------|------|
| `/ontology` | `/ontology/node-types` | GET/POST/PATCH/DELETE | `ontology.*` | 节点类型注册表（`NodeType`） |
| `/ontology` | `/ontology/relationship-types` | GET/POST/PATCH/DELETE | `ontology.*` | 关系类型注册表（`RelationshipType`） |
| `/graph` | `/graph/nodes` | GET/POST/PATCH/DELETE | `graph.*` | 图节点实例（`Node`） |
| `/graph` | `/graph/relationships` | GET/POST/PATCH/DELETE | `graph.*` | 语义边实例（`Relationship`） |
| `/worlds/{world_id}` | `/worlds/{world_id}/nodes` | GET/POST/PATCH/DELETE | `graph.*` | world 作用域节点操作（仅该 world 内节点） |
| `/worlds/{world_id}` | `/worlds/{world_id}/relationships` | GET/POST/PATCH/DELETE | `graph.*` | world 作用域关系操作（仅该 world 内关系） |

详见 [`features/F10_ONTOLOGY_AND_GRAPH_API.md`](features/F10_ONTOLOGY_AND_GRAPH_API.md)（OpenAPI / RFC 9457 / F01 trait 语义；含 world scope 约束与样例）。

**工具调用**：使用 curl、HTTPie、Postman/Insomnia/Bruno、OpenAPI Generator、Python httpx 等调用同一套接口的说明与示例见 F10 文档中的 [「业界工具调用样例」](features/F10_ONTOLOGY_AND_GRAPH_API.md#tooling-http-clients) 一节（含 `/openapi.json` 导入与 JWT / API Key 两种鉴权写法）。

## Core Abstractions

### Schemas

```
auth.py:
  - UserCreate { email, username, password }
  - UserLogin { email, password }
  - Token { access_token, token_type }

account.py:
  - AccountCreate { username, email, password, account_type, roles, permissions }
  - AccountUpdate { email, description, roles, permissions, is_active, is_verified, access_level }
  - AccountStatusUpdate { is_locked, lock_reason, is_suspended, suspension_reason, suspension_until }
  - PasswordChange { old_password, new_password }
  - AccountResponse { id, uuid, username, email, account_type, roles, is_active, ... }
  - AccountListResponse { total, accounts, skip, limit }
  - AccountStats { total_accounts, active_accounts, ... }
```

### 认证流程

```
注册: POST /auth/register → UserCreate → User JWT Token
登录: POST /auth/login → OAuth2PasswordRequestForm → User JWT Token
验证: Authorization: Bearer <token> → FastAPI Depends → current user
```

## User Stories

1. **用户注册登录**: 未注册用户通过邮箱和用户名注册，获得 JWT Token 后访问受保护资源
2. **账号管理**: 管理员列出/创建/更新/锁定账号，普通用户查看和修改自己的信息
3. **权限控制**: 每个端点通过 `@require_permission` / `@require_admin` 装饰器进行权限校验

## Acceptance Criteria

- [ ] `POST /auth/register` 成功返回 JWT Token，邮箱/用户名重复时返回 400
- [ ] `POST /auth/login` 使用 OAuth2PasswordRequestForm 格式，成功返回 JWT Token
- [ ] `GET /accounts/` 返回分页结果，支持 `account_type` 和 `is_active` 筛选
- [ ] `POST /accounts/` 在 GraphNode 上创建 account 类型节点
- [ ] `DELETE /accounts/{id}` 执行软删除（`is_active=False`），系统账号（admin/dev/campus）禁止删除
- [ ] 所有受保护端点未携带 Token 时返回 401
- [ ] 权限不足时返回 403

## Design Decisions

1. **为何使用 GraphNode 存储 Account**：与项目全图数据结构一致，Account 作为知识节点便于与其他实体（User/Character）建立关系
2. **为何账号 API 和用户认证 API 分开**：账号管理（GraphNode）和用户认证（User）是不同的关注点，前者偏管理，后者偏身份验证

## Open Questions

- [ ] 是否需要刷新 Token 机制？（当前只有 access_token）
- [ ] 账号类型（ACCOUNT_TYPES）是否有枚举定义需要补充？
- [ ] `/accounts/types/list` 是否需要权限控制？

## Feature Specs

- `F10` 本体与图谱原子服务 REST API（初稿）  
  [`features/F10_ONTOLOGY_AND_GRAPH_API.md`](features/F10_ONTOLOGY_AND_GRAPH_API.md)
- `F11` Graph API 数据访问策略（账号 `data_access`、能力 vs 数据范围）  
  [`features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md`](features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md)

## Dependencies

- 依赖 `backend/app/core/security.py`（JWT 加密/验证）
- 依赖 `backend/app/core/authorization.py`（权限装饰器）
- 依赖 `backend/app/models/graph.py`（Node/NodeType）
- 依赖 `backend/app/models/accounts.py`（account 工厂）