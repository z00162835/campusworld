# API 验收检查表

## 功能验收

### 认证 API

- [ ] `POST /auth/register` 成功返回 `{"access_token": "...", "token_type": "bearer"}`
- [ ] `POST /auth/register` 重复邮箱返回 400 `{"detail": "Email already registered"}`
- [ ] `POST /auth/login` 成功返回 Token
- [ ] `POST /auth/login` 错误密码返回 401 `{"detail": "Incorrect email or password"}`
- [ ] 受保护端点无 Token 返回 401

### 账号 API

- [ ] `GET /accounts/` 返回 `{ total, accounts[], skip, limit }`
- [ ] `GET /accounts/` 支持 `?account_type=admin&is_active=true` 筛选
- [ ] `GET /accounts/` 支持 `?skip=0&limit=10` 分页
- [ ] `GET /accounts/{id}` 找到返回 AccountResponse，找不到返回 404
- [ ] `POST /accounts/` 成功创建并返回 AccountResponse
- [ ] `POST /accounts/` 用户名重复返回 400
- [ ] `PUT /accounts/{id}` 成功更新并返回 AccountResponse
- [ ] `PUT /accounts/{id}` 邮箱被其他账号使用返回 400
- [ ] `PATCH /accounts/{id}/status` 锁定账号后 is_locked=true
- [ ] `PATCH /accounts/{id}/status` 解锁账号后 is_locked=false
- [ ] `POST /accounts/{id}/change-password` 旧密码正确则更新
- [ ] `POST /accounts/{id}/change-password` 旧密码错误返回 400
- [ ] `DELETE /accounts/{id}` 软删除（is_active=false）
- [ ] `DELETE /accounts/{id}` 删除 admin/dev/campus 账号返回 400
- [ ] `GET /accounts/types/list` 返回 ACCOUNT_TYPES 字典

### 权限验收

- [ ] 无 `user.manage` 权限访问 `GET /accounts/` 返回 403
- [ ] 无 `user.view` 权限访问 `GET /accounts/{id}` 返回 403
- [ ] 无 `user.create` 权限访问 `POST /accounts/` 返回 403
- [ ] 无 `user.edit` 权限访问 `PUT /accounts/{id}` 返回 403
- [ ] 非 Admin 访问 `DELETE /accounts/{id}` 返回 403

## 性能验收

- [ ] `GET /accounts/` 分页 limit=100 时响应 < 500ms
- [ ] `POST /accounts/` 响应 < 1s

## 安全验收

- [ ] 密码使用 bcrypt 加密（不可逆）
- [ ] JWT Token 包含过期时间（`exp` claim）
- [ ] 错误响应不泄露敏感信息（数据库结构等）

## F10 本体与图谱原子服务（实现后验收）

契约见 [`features/F10_ONTOLOGY_AND_GRAPH_API.md`](features/F10_ONTOLOGY_AND_GRAPH_API.md) 文末检查清单；下列为 **占位**，待路由落地后勾选。

### OpenAPI 与错误体

- [ ] 导出 `openapi.json` 含 `/ontology/*`、`/graph/*`（或实现所选路径）全部 operation 与 `operationId`
- [ ] `components.securitySchemes` 含 **`bearerAuth`** 与 **`apiKeyAuth`**（或文档约定的 `X-Api-Key` / `Authorization: ApiKey` 唯一方案）
- [ ] 4xx/5xx 支持 `application/problem+json`（RFC 9457 最小字段），或与 SPEC 过渡期映射一致

### API Key（若实现）

- [ ] 仅 HTTPS；密钥仅存哈希；创建时一次性明文展示
- [ ] `X-Api-Key` 或 `Authorization: ApiKey` 与 JWT **互斥** 策略与 400/401 行为符合 F10
- [ ] scope 与 `ontology.*` / `graph.*` 权限映射一致

### Ontology

- [ ] `GET /ontology/node-types` 分页与过滤符合 F10；无权限返回 403
- [ ] `PATCH /ontology/node-types/{type_code}` 对图种子锁定类型返回 409/403（与策略一致）
- [ ] `relationship-types` 路径行为与 node-types 对称

### Graph

- [ ] `GET /graph/nodes` 支持 `trait_class`、`required_any_mask`、`required_all_mask`；`mask=0` 不过滤
- [ ] `POST /graph/nodes` 创建后响应 201 + `Location`；持久化后 `trait_*` 与类型表一致（触发器）
- [ ] `GET /graph/relationships` 支持按 `source_id`/`target_id`/`type_code` 过滤
- [ ] `GET /worlds/{world_id}/nodes` 仅返回该 world 作用域节点（基于 `attributes.world_id` 或等价规则）
- [ ] `POST /worlds/{world_id}/nodes` 自动补齐/校验 `attributes.world_id={world_id}`，冲突时返回 409/400（与 OpenAPI 一致）
- [ ] `POST /worlds/{world_id}/relationships` 仅允许连接同一 world 内节点；跨 world 返回 404 或 409（与策略一致）
- [ ] `GET /worlds/{world_id}/relationships` 支持按 `source_id`/`target_id`/`type_code` 在 world 内过滤