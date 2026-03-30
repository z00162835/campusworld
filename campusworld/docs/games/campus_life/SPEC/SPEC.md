# games/campus_life SPEC

> **Architecture Role**: 本模块是**能力服务层**的核心组成部分，通过 MUD 设计原理将世界语义具象化为可操作的园区体验。它是 CampusWorld 智慧园区的具体空间实现，与游戏引擎（game_engine/）解耦，可独立扩展。

## Module Overview

`games/campus_life/` 是园区体验内容包，以高校校园为例，实现了一个样例园区的具体空间、对象、脚本和命令。

> **注**：CampusWorld 是智慧园区 OS，不是游戏。系统借鉴 MUD 的设计原理构筑世界语义。"玩家行为"对应"用户行为"，"场景"对应"园区空间"，"玩家"对应"用户"。

## Entry Boundary (System vs World)

- `campus_life` 只定义**世界内**行为与出生点，不定义系统级登录入口。
- 系统登录入口统一为 `SingularityRoom`（由 SSH/模型层规范）。
- 用户进入 `campus_life` 世界后，默认出生点才是 `campus`。

```
game_engine/          # 引擎框架
    └── games/
        └── campus_life/   # 园区体验包
            ├── game.py        # 园区主类（locations/users/items）
            ├── commands.py    # 园区命令
            ├── game_commands.py  # 命令定义
            ├── objects.py     # 对象定义
            └── scripts.py     # 脚本定义
```

## Core Abstractions

### Game 主类

```python
class Game(BaseGame):
    name: str = "campus_life"
    version: str = "1.0.0"

    # 园区组件
    commands: CampusLifeCommands
    objects: CampusLifeObjects
    scripts: CampusLifeScripts

    # 园区状态
    users: Dict[str, UserData]          # user_id → {location, inventory, stats}
    locations: Dict[str, LocationData] # location_id → {name, exits, items}
    items: Dict[str, ItemData]         # item_id → {name, type, location}

    # 生命周期
    def initialize_game() -> bool
    def start() -> bool
    def stop() -> bool
    def get_game_info() -> Dict
```

### UserData

```python
{
    "location": "campus",      # 当前位置
    "inventory": [],           # 物品列表
    "stats": {
        "energy": 100,        # 精力
        "hunger": 0,          # 饥饿度
        "knowledge": 0,       # 知识
        "social": 0           # 社交
    }
}
```

### LocationData

```python
{
    "name": "校园广场",
    "description": "校园的中心区域，有喷泉和绿树",
    "exits": ["library", "canteen", "dormitory"],
    "items": ["fountain", "tree", "bench"]
}
```

### 预定义空间

| ID | 名称 | 描述 | 出口 |
|---|---|---|---|
| `library` | 图书馆 | 安静的学习环境，有大量的书籍和自习室 | campus, study_room |
| `campus` | 校园广场 | 校园的中心区域，有喷泉和绿树 | library, canteen, dormitory |
| `canteen` | 食堂 | 提供各种美食的食堂，是人员聚集的地方 | campus, kitchen |
| `dormitory` | 宿舍 | 人员的休息场所，有床铺和书桌 | campus, bathroom |

## User Stories

1. **进入世界后探索园区**: 用户从系统入口进入 `campus_life` 后，在 `campus` 广场开始探索并通过 `go` 命令移动到图书馆/食堂/宿舍等空间
2. **物品管理**: 用户通过 `take`/`drop` 管理物品，通过 `inventory` 查看物品列表
3. **状态变化**: 用户的 stats（精力/饱食度）随时间/行动变化，驱动行为决策

## Event Hooks

```python
user_join(user_id, user_data)        # 用户进入园区
user_leave(user_id, user_data)        # 用户离开园区
user_move(user_id, old_loc, new_loc)  # 用户移动
user_action(user_id, action, *args)   # 用户执行动作
```

## Acceptance Criteria

- [ ] 园区初始化后预定义 4 个空间（library/campus/canteen/dormitory）
- [ ] 用户进入 `campus_life` 世界时，世界内默认 spawn 到 `campus` 位置
- [ ] `go library` 成功移动到图书馆，返回新空间信息
- [ ] `go north` 当前空间无该出口时返回错误
- [ ] `add_user()` 触发 `user_join` hook
- [ ] `move_user()` 触发 `user_move` hook

## Design Decisions

1. **为何园区体验与引擎分离**: 便于扩展新的空间包（如 `games/campus_office/`），只需实现 Game 接口即可
2. **为何 location 用 Dict 而非数据库**: 开发阶段快速迭代，数据库持久化可在后续添加
3. **stats 系统**: 模拟真实园区体验，精力消耗驱动用户行为决策

## Open Questions

- [ ] stats 的刷新机制？（定时任务还是按需计算）
- [ ] 物品是否需要属性（如耐久度）？
- [ ] 脚本触发系统是否需要完整实现？
- [ ] 园区状态是否需要存档/恢复功能？