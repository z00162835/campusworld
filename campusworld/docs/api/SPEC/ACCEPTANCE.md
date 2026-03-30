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