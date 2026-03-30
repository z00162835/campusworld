# 验收检查表

## 配置验收

- [ ] `get_config()` 返回全局配置实例
- [ ] `get_setting("app.name")` 返回应用名称
- [ ] 多环境配置（dev/prod）正确切换
- [ ] 配置热重载生效

## 安全验收

- [ ] `create_access_token()` 生成 JWT
- [ ] Token 包含过期时间
- [ ] `verify_password()` 验证正确
- [ ] `@require_permission()` 正确拦截无权限请求

## 日志验收

- [ ] `get_logger(LoggerNames.API)` 返回正确的日志器
- [ ] 日志格式为 JSON
- [ ] 上下文信息正确传播

## 数据库验收

- [ ] `SessionLocal` 正确创建数据库连接
- [ ] 连接池正常工作
- [ ] 数据库错误正确处理