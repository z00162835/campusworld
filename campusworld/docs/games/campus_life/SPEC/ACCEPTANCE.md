# 验收检查表

## 初始化验收

- [ ] `Game()` 实例化后 `is_initialized = False`
- [ ] `initialize_game()` 执行后 `is_initialized = True`
- [ ] 初始化后 `locations` 包含 4 个预定义空间
- [ ] 初始化后 `items` 包含预定义物品
- [ ] 初始化后 `users = {}`

## 生命周期验收

- [ ] `start()` 执行后 `is_running = True`，触发组件 start
- [ ] `stop()` 执行后 `is_running = False`，触发组件 stop
- [ ] `get_game_info()` 返回 name/version/user_count

## 用户管理验收

- [ ] `add_user("user1", {})` 成功添加
- [ ] 新用户默认位置为 `campus`
- [ ] 新用户默认 stats 为 `{energy:100, hunger:0, knowledge:0, social:0}`
- [ ] `get_user("user1")` 返回用户数据
- [ ] `remove_user("user1")` 成功移除
- [ ] 对不存在的用户调用 `move_user` 返回 False

## 空间移动验收

- [ ] `move_user("user1", "library")` 成功移动
- [ ] 移动触发 `user_move` hook
- [ ] `move_user("user1", "nonexistent")` 返回 False（空间不存在）
- [ ] `get_location_info("campus")` 返回名称/描述/出口/物品

## 组件验收

- [ ] `get_commands()` 返回园区命令列表
- [ ] `get_objects()` 返回园区对象列表
- [ ] `get_hooks()` 返回 4 个 hook 函数