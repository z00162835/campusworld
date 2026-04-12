# TODO - API 开发任务清单

## 待实现功能

### 高优先级

- [ ] **账户统计端点** `GET /accounts/stats`
  - 返回 `AccountStats`（total/active/suspended/locked by type/role/access_level）
  - 权限：`user.manage`

- [ ] **账户搜索端点** `POST /accounts/search`
  - 支持全文搜索 username/email
  - 支持多条件筛选（account_type/role/access_level/is_active）
  - 分页返回
  - 权限：`user.manage`

- [ ] **批量更新端点** `PATCH /accounts/bulk`
  - 接收 `AccountBulkUpdateRequest`
  - 批量更新 is_active/roles/permissions
  - 返回成功/失败统计
  - 权限：`user.manage`

### 中优先级

- [ ] **Token 服务端黑名单 / 全量撤销增强**（可选）
  - 当前：`POST /auth/logout`、`POST /auth/logout-all` 已存在，刷新令牌按服务端存储撤销（见实现）
  - 增强：Redis 等集中式黑名单、审计与多实例一致撤销（若需要）

- [ ] **密码重置请求端点** `POST /auth/password-reset-request`
  - 发送邮件/生成 Token
  - 权限：公开

- [ ] **密码重置确认端点** `POST /auth/password-reset-confirm`
  - 用 Token 设置新密码
  - 权限：公开

### 低优先级

- [ ] **OAuth2 第三方登录**
  - 支持 Google/GitHub OAuth2
  - 权限：公开

- [ ] **API 版本控制**
  - 实现 `/api/v2/` 版本
  - v1 兼容策略

## 已实现（近期交付，契约见 F10/F11 与 OpenAPI）

- [x] **刷新 Token**：`POST /auth/refresh`（见 `auth` 端点）
- [x] **当前用户**：`GET /accounts/me`（需已认证）
- [x] **F10 本体与图谱原子服务**：`ontology/*`、`graph/*`、`worlds/{world_id}/*`（见 [`features/F10_ONTOLOGY_AND_GRAPH_API.md`](features/F10_ONTOLOGY_AND_GRAPH_API.md)）
- [x] **F11 数据访问策略**：账号 `attributes.data_access` 与图/本体查询过滤（见 [`features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md`](features/F11_DATA_ACCESS_POLICY_FOR_GRAPH_API.md)）

## 已实现端点检查清单

确保以下端点测试通过：

- [ ] `POST /auth/register` — 注册并返回 Token
- [ ] `POST /auth/login` — OAuth2 登录并返回 Token
- [ ] `POST /auth/refresh` — 刷新 access_token
- [ ] `GET /accounts/me` — 当前登录账号信息
- [ ] `GET /accounts/` — 列表（分页 + 筛选）
- [ ] `GET /accounts/{id}` — 详情
- [ ] `POST /accounts/` — 创建
- [ ] `PUT /accounts/{id}` — 更新
- [ ] `PATCH /accounts/{id}/status` — 状态更新
- [ ] `POST /accounts/{id}/change-password` — 改密
- [ ] `DELETE /accounts/{id}` — 软删除
- [ ] `GET /accounts/types/list` — 类型列表

## 错误码规范

| HTTP 状态码 | 使用场景 |
|-------------|----------|
| 400 | 参数验证失败、用户名/邮箱已存在 |
| 401 | Token 缺失或无效 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 409 | 资源冲突 |
| 422 | Pydantic 验证错误 |
| 500 | 服务器内部错误 |
