# Game Engine SPEC

> **Architecture Role**: 引擎是**能力服务层**的核心，管理园区空间状态和业务能力。它将**世界语义**（Room/Character/Building 等图节点）封装为可操作的内容包，驱动园区的运行逻辑。与命令系统（commands/）和图数据模型（models/）紧密协作。

## Module Overview

引擎（`backend/app/game_engine/`）参考 Evennia 框架设计，提供场景与引擎解耦的基础设施。

> **注**：CampusWorld 是智慧园区 OS，"引擎"是驱动园区空间运行的核心服务，"内容包"是具体的园区体验实现（如 campus_life）。

```
game_engine/
├── base.py      # 引擎基类 (GameEngine/BaseGame)
├── manager.py   # 引擎管理器 (GameEngineManager)
├── loader.py    # 内容加载器 (GameLoader)
└── interface.py # 园区接口 (GameInterface)
```

## Core Abstractions

### 核心类

| 类 | 文件 | 说明 |
|---|---|---|
| `GameEngine` | base.py | 引擎基类：start/stop/reload/get_info |
| `BaseGame` | base.py | 内容包基类：name/version/description |
| `CampusWorldGameEngine` | base.py | 园区世界引擎实现 |
| `GameEngineManager` | manager.py | 全局引擎管理器单例 |
| `GameLoader` | loader.py | 内容加载器：auto_load_games/reload_game |
| `GameInterface` | interface.py | 园区接口：用户状态/空间状态/事件 |

### 引擎生命周期

```
初始化 → 启动（加载内容包）→ 运行（处理命令）→ 停止
```

```python
class GameEngine:
    name: str
    version: str
    started: bool

    def start() -> bool       # 启动引擎，加载内容包
    def stop() -> bool       # 停止引擎，保存状态
    def reload() -> bool     # 热重载内容包
    def get_info() -> dict   # 获取引擎信息

class GameEngineManager:
    def start_engine() -> bool
    def stop_engine() -> bool
    def get_engine() -> GameEngine
    def reload() -> bool
```

### 内容包结构

每个内容包（如 `games/campus_life/`）实现 `BaseGame` 接口：

```python
class BaseGame:
    name: str
    version: str
    description: str

    def initialize_game() -> bool
    def start() -> bool
    def stop() -> bool
    def get_game_info() -> Dict

    def get_commands() -> Dict      # 可用命令
    def get_objects() -> Dict        # 空间/物品对象
    def get_hooks() -> Dict          # 事件钩子
```

## User Stories

1. **启动园区**: `game_engine_manager.start_engine()` 启动引擎，自动加载所有内容包
2. **空间管理**: 引擎管理园区空间状态，用户 move 时引擎更新位置
3. **事件触发**: 用户动作触发事件钩子（如进入空间触发脚本）

## Acceptance Criteria

- [ ] `CampusWorldGameEngine().start()` 成功加载 campus_life 内容包
- [ ] `game_engine_manager.start_engine()` 后引擎处于 running 状态
- [ ] `game_engine_manager.get_engine().get_info()` 返回引擎信息
- [ ] 引擎停止后所有内容包正确清理

## Design Decisions

1. **为何引擎与内容分离**: 便于扩展新的园区体验（games/campus_office/），只需实现 BaseGame 接口
2. **为何用 Manager 单例**: 全局唯一引擎实例，统一生命周期管理
3. **为何用 Hook 系统**: 解耦事件处理，脚本系统可挂载到钩子上

## Dependencies

- 依赖 `backend/app/games/`（内容包）
- 依赖 `backend/app/commands/`（命令系统）
- 依赖 `backend/app/models/`（图数据模型）