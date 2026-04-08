# API SPEC

> **Architecture Role**: 本模块是系统的 **REST API 入口**，属于"系统适配层"的接入协议之一，为前端和外部调用者提供 GraphNode/Account/User 的 CRUD 操作接口。

## Module Overview

API 层（`backend/app/api/v1/`）提供 HTTP REST 接口，是 Agent 服务层与后端知识本体交互的主要通道。

当前端点：

| 前缀 | 端点 | 方法 | 权限 | 说明 |
|------|------|------|------|------|
| `/auth` | `/auth/register` | POST | 公开 | 注册用户，返回 access_token + refresh_token |
| `/auth` | `/auth/login` | POST | 公开 | OAuth2 密码登录，返回 access_token + refresh_token |
| `/auth` | `/auth/refresh` | POST | 公开 | 用 refresh_token 换取新的 access_token + refresh_token（轮换） |
| `/auth` | `/auth/logout` | POST | 公开 | 撤销指定的 refresh_token |
| `/auth` | `/auth/logout-all` | POST | JWT | 撤销当前用户所有 refresh_tokens（所有设备） |
| `/accounts` | `/accounts/` | GET | `user.manage` | 账号列表（分页/筛选） |
| `/accounts` | `/accounts/{id}` | GET | `user.view` | 账号详情 |
| `/accounts` | `/accounts/` | POST | `user.create` | 创建账号 |
| `/accounts` | `/accounts/{id}` | PUT | `user.edit` | 更新账号 |
| `/accounts` | `/accounts/{id}/status` | PATCH | `user.manage` | 锁定/暂停账号 |
| `/accounts` | `/accounts/{id}/change-password` | POST | `user.manage` | 修改密码 |
| `/accounts` | `/accounts/{id}` | DELETE | Admin | 删除（软删除）账号 |
| `/accounts` | `/accounts/types/list` | GET | 公开 | 账号类型列表 |

## Core Abstractions

### Schemas

```
auth.py:
  - UserCreate { email, username, password }
  - UserLogin { email, password }
  - Token { access_token, refresh_token, token_type, expires_in }

account.py:
  - AccountCreate { username, email, password, account_type, roles, permissions }
  - AccountUpdate { email, description, roles, permissions, is_active, is_verified, access_level }
  - AccountStatusUpdate { is_locked, lock_reason, is_suspended, suspension_reason, suspension_until }
  - PasswordChange { old_password, new_password }
  - AccountResponse { id, uuid, username, email, account_type, roles, is_active, ... }
  - AccountListResponse { total, accounts, skip, limit }
  - AccountStats { total_accounts, active_accounts, ... }
  - RefreshTokenRequest { refresh_token }
  - RefreshTokenInfo { jti, family_id, device, issued_at, expires_at, revoked, replaced_by }
  - RefreshTokenResponse { access_token, refresh_token, token_type, expires_in }
```

### 认证流程

```
注册: POST /auth/register → UserCreate → { access_token, refresh_token, token_type, expires_in }
登录: POST /auth/login → OAuth2PasswordRequestForm → { access_token, refresh_token, token_type, expires_in }
刷新: POST /auth/refresh → { refresh_token } → { access_token, refresh_token, token_type, expires_in }（带轮换）
登出: POST /auth/logout → { refresh_token } → 撤销当前 refresh_token
全设备登出: POST /auth/logout-all → 撤销所有 refresh_tokens
验证: Authorization: Bearer <token> → FastAPI Depends → current user
```

### Refresh Token 轮换机制

- Refresh Token 存储在 Account Node 的 `attributes.refresh_tokens` 字典中，Key 为 JTI
- `RefreshTokenInfo`: `{ jti, family_id, device, issued_at, expires_at, revoked, replaced_by }`
- **Token Family**：同一登录会话的所有 refresh token 共享 `family_id`，便于追踪和管理
- 每次 `/auth/refresh` 调用时：颁发新 token，**同 family 的所有旧 token 全部被标记为 `revoked=True` + `replaced_by=<new_jti>`**
- **Token Family 语义**：同一 family 的多个 token 不能同时使用；一个设备刷新会导致同 family 的其他设备 token 失效（被迫登出）
- Token 链检测：若 token 的 `replaced_by` 非空，说明已被使用过，视为 token 被盗用（replay attack）
- `/auth/logout` 撤销单个 refresh_token；`/auth/logout-all` 撤销用户所有 refresh_tokens（带 JWT 认证）
- 用户登录时自动清理所有已过期的 token（`expires_at < now`，无论 revoked 状态）

### WebSocket Refresh Token

- 消息格式: `{"type": "refresh", "access_token": "<token>", "refresh_token": "<token>"}`
- 响应格式: `{"type": "refreshed", "access_token": "...", "refresh_token": "...", "expires_in": 11520}`
- **安全要求**：连接必须已认证 + `access_token` 与 `refresh_token` 必须属于同一用户（Token 绑定验证）
- `expected_access_token` 参数用于验证两者一致性

## User Stories

1. **用户注册登录**: 未注册用户通过邮箱和用户名注册，获得 JWT Token 后访问受保护资源
2. **账号管理**: 管理员列出/创建/更新/锁定账号，普通用户查看和修改自己的信息
3. **权限控制**: 每个端点通过 `@require_permission` / `@require_admin` 装饰器进行权限校验

## Acceptance Criteria

- [ ] `POST /auth/register` 成功返回 JWT Token，邮箱/用户名重复时返回 400
- [ ] `POST /auth/login` 使用 OAuth2PasswordRequestForm 格式，成功返回 JWT Token
- [ ] `POST /auth/refresh` 用 refresh_token 换取新 token，旧 token 被标记为 revoked + replaced_by
- [ ] `POST /auth/refresh` 检测 token 链复用（replaced_by 非空时拒绝）
- [ ] `POST /auth/logout` 撤销指定的 refresh_token
- [ ] `POST /auth/logout-all` 撤销当前用户所有 refresh_tokens（需 JWT 认证）
- [ ] `GET /accounts/` 返回分页结果，支持 `account_type` 和 `is_active` 筛选
- [ ] `POST /accounts/` 在 GraphNode 上创建 account 类型节点
- [ ] `DELETE /accounts/{id}` 执行软删除（`is_active=False`），系统账号（admin/dev/campus）禁止删除
- [ ] 所有受保护端点未携带 Token 时返回 401
- [ ] 权限不足时返回 403

## Design Decisions

1. **为何使用 GraphNode 存储 Account**：与项目全图数据结构一致，Account 作为知识节点便于与其他实体（User/Character）建立关系
2. **为何账号 API 和用户认证 API 分开**：账号管理（GraphNode）和用户认证（User）是不同的关注点，前者偏管理，后者偏身份验证

## Open Questions

- [x] ~~是否需要刷新 Token 机制？（当前只有 access_token）~~ — 已实现（2026-04-08）
- [ ] 账号类型（ACCOUNT_TYPES）是否有枚举定义需要补充？
- [ ] `/accounts/types/list` 是否需要权限控制？

## Dependencies

- 依赖 `backend/app/core/security.py`（JWT 加密/验证）
- 依赖 `backend/app/core/auth_service.py`（AuthService 认证服务，Refresh Token 核心逻辑）
- 依赖 `backend/app/core/authorization.py`（权限装饰器）
- 依赖 `backend/app/models/graph.py`（Node/NodeType）
- 依赖 `backend/app/models/accounts.py`（account 工厂）