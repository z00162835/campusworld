# 验收检查表

## 生命周期验收

- [ ] `CampusWorldGameEngine()` 实例化后 `started = False`
- [ ] `start()` 后 `started = True`，加载所有内容包
- [ ] `stop()` 后 `started = False`，清理所有内容包
- [ ] `reload()` 热重载成功，状态保持

## 内容包验收

- [ ] `loader.auto_load_games()` 加载 campus_life 内容包
- [ ] `loader.get_game("campus_life")` 返回 Game 实例
- [ ] 不存在的包返回 None

## 引擎管理验收

- [ ] `game_engine_manager` 是单例
- [ ] `start_engine()` 成功启动
- [ ] `stop_engine()` 成功停止
- [ ] `get_engine()` 返回当前引擎实例

## 接口验收

- [ ] `GameInterface.get_player_state()` 返回用户状态
- [ ] `GameInterface.get_world_state()` 返回园区状态
- [ ] `GameInterface.trigger_event()` 触发事件钩子