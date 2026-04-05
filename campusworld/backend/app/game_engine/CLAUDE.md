# Game Engine - 游戏引擎

> **Architecture Role**: 游戏引擎是**能力服务层**的核心，管理世界状态和业务能力。它将**世界语义**（Room/Character/Building 等图节点）封装为可操作的游戏内容包（games/campus_life），驱动世界的运行逻辑。与 commands/（命令系统）和 models/（全图数据模型）紧密协作：命令系统触发引擎操作，引擎操作修改图数据模型中的实体。

CampusWorld 内容引擎，参考 Evennia 框架设计，提供场景与引擎解耦的基础设施。

## 模块结构

```
game_engine/
├── base.py           # 引擎基类
├── manager.py        # 引擎管理器
├── loader.py         # 内容加载器
├── interface.py      # 游戏接口定义
└── __init__.py
```

## 核心组件

### GameEngine / BaseGame (基类)

```python
class GameEngine:
    """引擎基类"""
    name: str
    version: str
    started: bool

    def start(self) -> bool
    def stop(self) -> bool
    def reload(self) -> bool
    def get_info(self) -> dict

class BaseGame:
    """游戏基类"""
    name: str
    description: str
```

### GameEngineManager

引擎管理器:

```python
class GameEngineManager:
    """游戏引擎管理器"""

    def start_engine(self) -> bool
    def stop_engine(self) -> bool
    def get_engine(self) -> GameEngine
    def reload(self) -> bool
```

### CampusWorldGameEngine

继承自 GameEngine:

```python
class CampusWorldGameEngine(GameEngine):
    def __init__(self):
        self.loader = GameLoader(self)
        self.interface = GameInterface(self)

    def start(self) -> bool:
        # 默认 game_engine.load_installed_worlds_on_start=true：从 DB 已 install 的世界 load_game；见 settings.yaml
        ...
```

### GameLoader

内容加载器:

```python
class GameLoader:
    def load_game(self, game_name: str) -> bool
    def load_installed_worlds_at_start(self) -> List[str]
    def auto_load_games(self, only_world_ids: Optional[List[str]] = None) -> List[str]
    def reload_game(self, game_name: str) -> bool
```

可安装世界包（如 `games/hicampus`）在 **`manifest.yaml`** 中设置 `graph_seed: true` 时，`load_game` / `reload_game` 会把包快照经 **`graph_seed/pipeline.run_graph_seed`** 写入 PostgreSQL（需已执行 **`ensure_graph_seed_ontology`** 相关迁移）。无 PG 的环境应关闭 `graph_seed`，否则安装会失败。运维入口与奇点屋路径见仓库根 **`CLAUDE.md`**「安装 HiCampus 世界」。

### GameInterface

游戏接口，提供:

- 玩家状态管理
- 世界状态查询
- 命令执行
- 事件触发

## 使用方式

```python
from app.game_engine import game_engine_manager, GameEngineManager

# 方式1: 使用全局管理器
game_engine_manager.start_engine()
info = game_engine_manager.get_engine().get_info()
game_engine_manager.stop_engine()

# 方式2: 直接使用
from app.game_engine import CampusWorldGameEngine
engine = CampusWorldGameEngine()
engine.start()
```

## 游戏内容

游戏内容定义在 `backend/app/games/`:

```
games/
├── campus_life/      # 校园生活游戏
│   ├── game.py      # 游戏定义
│   ├── commands.py  # 游戏命令
│   ├── objects.py   # 游戏对象
│   └── scripts.py   # 脚本
└── __init__.py
```

## 导出接口

```python
from app.game_engine import (
    GameEngine,
    BaseGame,
    GameLoader,
    GameInterface,
    GameEngineManager,
    CampusWorldGameEngine,
    game_engine_manager
)
```

## 生命周期

1. **初始化**: 创建引擎实例
2. **启动**: 加载游戏内容
3. **运行**: 处理命令和事件
4. **停止**: 保存状态，清理资源

## 配置

```yaml
game_engine:
  load_installed_worlds_on_start: true
  auto_load_discovered_on_start: false
  auto_load_worlds: null
```
