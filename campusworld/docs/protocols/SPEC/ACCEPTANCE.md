# 验收检查表

## HTTP 协议验收

- [ ] `HTTPHandler.handle()` 处理 FastAPI Request
- [ ] 返回标准 JSON 响应
- [ ] 认证失败返回 401

## SSH 协议验收

- [ ] `SSHHandler.handle()` 处理 SSH 会话命令
- [ ] 返回文本输出
- [ ] 协议层与命令系统正确对接

## 协议抽象验收

- [ ] `ProtocolHandler` 是抽象基类，不可实例化
- [ ] 所有协议继承 `ProtocolHandler`
- [ ] 新协议通过继承添加