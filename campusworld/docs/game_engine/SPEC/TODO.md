# TODO - 游戏引擎开发任务

## 引擎扩展

### 高优先级

- [ ] **引擎热重载**
  - 修改内容包后无需重启引擎
  - `reload_game("campus_life")` 重新加载指定内容包
  - 保留用户状态

- [ ] **引擎健康检查**
  - `health_check()` 返回引擎状态
  - 检查所有内容包是否正常
  - 检查数据库连接

- [ ] **引擎事件系统**
  - 全局事件总线
  - 内容包间事件通信
  - 事件优先级

### 中优先级

- [ ] **多内容包管理**
  - 同时运行多个内容包
  - 内容包间切换
  - 内容包依赖管理

- [ ] **引擎配置**
  - 保存间隔（auto_save_interval）
  - 最大用户数（max_players）
  - 内容包加载策略

- [ ] **Hook Manager**
  - 钩子注册/注销
  - 钩子优先级
  - 钩子异常处理

### 低优先级

- [ ] **引擎集群**: 多引擎实例负载均衡
- [ ] **引擎监控**: Prometheus 指标暴露
- [ ] **引擎迁移**: 内容包版本迁移工具

## 验收检查清单

- [ ] `start_engine()` 后 `is_running = True`
- [ ] `stop_engine()` 后 `is_running = False`
- [ ] `reload()` 重新加载所有内容包
- [ ] `get_engine().get_info()` 返回 name/version/description