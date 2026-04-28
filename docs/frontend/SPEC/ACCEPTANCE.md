# 验收检查表

## 页面验收

- [ ] `/auth/login` 登录表单正常提交
- [ ] `/auth/register` 注册表单正常提交
- [ ] `/spaces` 显示空间列表
- [ ] `/works` 显示工作台
- [ ] `/agents` 显示 Agent 列表

## 路由验收

- [ ] 未登录用户访问 `/spaces` 跳转登录页
- [ ] 已登录用户访问 `/auth/login` 跳转首页
- [ ] `/` 显示首页

## API 集成验收

- [ ] Axios 正确配置 baseURL
- [ ] JWT Token 正确添加到请求头
- [ ] 401 响应正确处理（跳转登录页）
- [ ] 403 响应正确处理（显示权限不足）

## 组件验收

- [ ] NavBar 正确显示
- [ ] Sidebar 正确显示
- [ ] Dashboard 正确显示用户状态