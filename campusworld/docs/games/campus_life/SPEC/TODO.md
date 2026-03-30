# TODO - games/campus_life 开发任务

## 空间扩展

### 高优先级

- [ ] **study_room 空间**: 图书馆内的自习室
  - 从 library 可进入
  - 包含书桌、椅子等物品

- [ ] **kitchen 空间**: 食堂后厨
  - 从 canteen 可进入
  - 包含食物制作工具

- [ ] **bathroom 空间**: 宿舍卫生间
  - 从 dormitory 可进入

- [ ] **新增物品**: 具体物品数据定义
  - 书本、桌子、椅子（library/study_room）
  - 食物、桌子（canteen/kitchen）
  - 床铺、桌子、衣柜（dormitory/bathroom）

### 中优先级

- [ ] **scripts.py 实现**: 脚本触发系统
  - 进入图书馆触发 "安静的学习环境" 提示
  - 进入食堂触发 "美食香味" 提示
  - 饥饿度 > 80 时提示 "肚子饿了"

- [ ] **stats 刷新机制**:
  - 精力随时间自然减少
  - 饱食度随时间增加
  - 触发阈值时发送提示

- [ ] **用户在线状态**
  - 在线用户数量统计
  - 用户位置广播（附近用户可见）

### 低优先级

- [ ] **园区存档**: 用户状态持久化到数据库
- [ ] **园区恢复**: 用户重新登录时恢复园区状态
- [ ] **多空间包支持**: games/campus_office/ 第二个空间包

## 命令扩展

| 命令 | 说明 | 权限 |
|------|------|------|
| `sleep` | 恢复精力到 100 | GAME |
| `eat` | 消耗食物，减少饥饿度 | GAME |
| `study` | 在 library 增加知识值 | GAME |
| `socialize` | 增加社交值 | GAME |

## 验收检查清单

- [ ] `game.py` 初始化后 locations 有 4 个预定义空间
- [ ] `add_user("user1")` 后用户在 campus 位置
- [ ] `move_user("user1", "library")` 后用户在 library
- [ ] `get_location_info("campus")` 返回完整的 location 数据
- [ ] `get_game_info()` 返回园区统计（用户数/空间数/物品数）