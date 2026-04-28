# 修复重复初始化问题 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `app.games.campus_life` 模块因模块级单例导致的重复初始化日志，参考 Evennia 延迟初始化架构，所有实例由 loader 统一创建和管理。

**Architecture:** 移除 `__init__.py` 中的模块级单例 `campus_life_game`，将 `get_game_instance()` 改造为工厂函数（每次返回新实例），修复 `initialize_game()` 和 `start_game()` 的错误调用链。Loader 在 `load_game()` 中通过工厂函数创建实例后，统一调用 `initialize_game()` 和 `start()` 管理生命周期。

**Tech Stack:** Python 3.9+, structlog, importlib

---

## 文件变更映射

| 文件 | 变更类型 | 职责 |
|------|----------|------|
| `app/games/campus_life/__init__.py` | 修改 | 移除单例，改造为工厂模式 |
| `app/games/campus_life/game.py` | 修改 | `__init__` 中移除 "初始化完成" 日志（因为这不是真正的初始化） |
| `app/game_engine/loader.py` | 无变更 | 已通过 `get_game_instance()` 工厂获取实例 |
| `backend/tests/game_engine/test_campus_life.py` | 新增/修改 | 添加初始化流程测试 |

---

## Task 1: 修改 `__init__.py` - 移除模块级单例，改造工厂函数

**文件:**
- 修改: `campusworld/backend/app/games/campus_life/__init__.py`

**现状问题:**
```python
# 模块级单例 - 在 import 时即创建实例，触发 __init__ 日志
campus_life_game = CampusLifeGame()  # ← 问题根源

def initialize_game() -> bool:
    return campus_life_game.start()   # ← BUG: 调用了 start() 而非 initialize_game()

def start_game() -> bool:
    return campus_life_game.start()  # ← 正确调用 start()
```

**修改步骤:**

- [ ] **Step 1: 移除模块级单例，改造 `get_game_instance()` 为工厂函数**

将 `__init__.py` 替换为:

```python
"""
园区世界包 - 统一接口

提供与单文件版本兼容的接口，内部使用模块化实现。
采用工厂模式，由 loader 通过 get_game_instance() 统一创建实例，
避免模块级单例在 import 时触发副作用。
"""

from .game import Game as CampusLifeGame
from .commands import CampusLifeCommands
from .objects import CampusLifeObjects
from .scripts import CampusLifeScripts


def get_game_instance():
    """获取场景实例 - 工厂函数，每次返回新实例

    由 loader.load_game() 调用，创建后由 loader 负责初始化和启动。
    """
    return CampusLifeGame()


def initialize_game() -> bool:
    """初始化场景 - 兼容接口

    直接委托给实例的 initialize_game()。
    注意：实际初始化由 loader.load_game() 统一调用。
    """
    instance = get_game_instance()
    return instance.initialize_game()


def start_game() -> bool:
    """启动场景 - 兼容接口"""
    instance = get_game_instance()
    return instance.start()


def stop_game() -> bool:
    """停止场景 - 兼容接口"""
    instance = get_game_instance()
    return instance.stop()


def cleanup_game():
    """清理场景 - 兼容接口"""
    instance = get_game_instance()
    instance.stop()


# 导出所有接口
__all__ = [
    'CampusLifeGame',
    'initialize_game',
    'start_game',
    'stop_game',
    'cleanup_game',
    'get_game_instance'
]
```

**注意:** 移除了 `campus_life_game` 导出，不再有模块级实例。

- [ ] **Step 2: 验证语法正确**

Run: `cd /Users/xbit/code/campusworld/campusworld/backend && python -c "from app.games.campus_life import get_game_instance; print(get_game_instance())"`
Expected: 输出 Game 实例，无 "园区世界初始化完成" 日志

- [ ] **Step 3: 提交**

```bash
git add app/games/campus_life/__init__.py
git commit -m "refactor(games): remove module-level singleton, use factory pattern

- Remove campus_life_game module-level singleton that caused duplicate
  initialization logs on import
- get_game_instance() now returns a new instance each call (factory pattern)
- initialize_game()/start_game()/stop_game() use factory to get instance
- Loader controls game lifecycle: create → initialize_game() → start()
- Follows Evennia lazy initialization architecture"
```

---

## Task 2: 修改 `game.py` - 移除 `__init__` 中的误导性日志

**文件:**
- 修改: `campusworld/backend/app/games/campus_life/game.py:51`

**问题:**
`Game.__init__()` 在第 51 行打印 "园区世界初始化完成"，但这仅仅是对象构造，不是真正的初始化。真正的初始化在 `initialize_game()` 方法中。

**修改步骤:**

- [ ] **Step 1: 移除 `__init__` 中的 "园区世界初始化完成" 日志**

文件: `campusworld/backend/app/games/campus_life/game.py`

将第 48-51 行:
```python
        # 初始化场景世界
        self._init_game_world()

        self.logger.info("园区世界初始化完成")
```

替换为:
```python
        # 初始化场景世界
        self._init_game_world()
        # 注意：真正的初始化在 initialize_game() 方法中进行
```

- [ ] **Step 2: 验证无日志输出**

Run: `cd /Users/xbit/code/campusworld/campusworld/backend && python -c "from app.games.campus_life import get_game_instance; g = get_game_instance(); print('Instance created, no init log above')"`
Expected: 无 "园区世界初始化完成" 日志出现

- [ ] **Step 3: 提交**

```bash
git add app/games/campus_life/game.py
git commit -m "refactor(games): remove misleading 'init complete' log from Game.__init__

The __init__ method only constructs the object and sets up the game world,
it does not perform actual initialization. Real initialization happens in
initialize_game(). This removes the misleading log that appeared on import."
```

---

## Task 3: 添加引擎初始化流程测试

**文件:**
- 创建: `campusworld/backend/tests/game_engine/test_campus_life_initialization.py`

**测试目标:** 验证初始化流程只产生一套日志，而非重复。

- [ ] **Step 1: 编写测试**

```python
"""
引擎初始化流程测试

验证 campus_life 模块：
1. import 时不触发初始化日志
2. 正确通过 initialize_game() 和 start() 生命周期方法
3. 不会产生重复的初始化/启动日志
"""

import pytest
import logging
from io import StringIO
from unittest.mock import patch, MagicMock


class TestCampusLifeInitializationFlow:
    """测试园区生活初始化流程"""

    def test_import_does_not_trigger_init_log(self):
        """验证 import 时不触发初始化日志"""
        # 重新加载模块以测试 import 时行为
        import importlib
        import sys

        # 清除已加载的模块
        modules_to_clear = [k for k in sys.modules.keys() if k.startswith('app.games.campus_life')]
        for mod in modules_to_clear:
            del sys.modules[mod]

        # 捕获 import 期间的日志
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)

        # 临时添加 handler 到相关 logger
        game_logger = logging.getLogger('game.campus_life')
        original_level = game_logger.level
        game_logger.setLevel(logging.INFO)
        game_logger.addHandler(handler)

        try:
            import app.games.campus_life as cl
            # 调用 get_game_instance 触发实例创建
            instance = cl.get_game_instance()

            # 验证实例已创建
            assert instance is not None

            # 检查日志内容：import 阶段不应有初始化日志
            log_output = log_capture.getvalue()

            # import + get_game_instance 不应触发 "初始化完成" 日志
            assert "初始化完成" not in log_output, \
                f"Unexpected '初始化完成' log during import: {log_output}"
        finally:
            game_logger.removeHandler(handler)
            game_logger.setLevel(original_level)

    def test_initialize_game_calls_correct_method(self):
        """验证 initialize_game() 调用的是 initialize_game() 而非 start()"""
        import app.games.campus_life as cl

        with patch.object(cl.CampusLifeGame, 'start') as mock_start, \
             patch.object(cl.CampusLifeGame, 'initialize_game') as mock_init:

            # 设置返回值
            mock_init.return_value = True
            mock_start.return_value = True

            instance = cl.get_game_instance()

            # 调用 initialize_game
            result = cl.initialize_game()

            # initialize_game() 应调用 instance.initialize_game()，不是 start()
            mock_init.assert_called_once()
            mock_start.assert_not_called()

    def test_full_lifecycle_sequence(self):
        """验证完整生命周期: 创建 → 初始化 → 启动"""
        import app.games.campus_life as cl

        instance = cl.get_game_instance()

        # 验证 is_initialized 初始为 False
        assert instance.is_initialized is False
        assert instance.is_running is False

        # 调用 initialize_game
        init_result = instance.initialize_game()
        assert init_result is True
        assert instance.is_initialized is True

        # 调用 start
        start_result = instance.start()
        assert start_result is True
        assert instance.is_running is True

    def test_start_after_init_produces_single_log(self):
        """验证初始化后启动只产生一套日志（无重复）"""
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)

        import app.games.campus_life as cl
        game_logger = logging.getLogger('game.campus_life')
        original_level = game_logger.level
        game_logger.setLevel(logging.INFO)
        game_logger.addHandler(handler)

        try:
            instance = cl.get_game_instance()
            instance.initialize_game()
            instance.start()

            log_output = log_capture.getvalue()

            # 各阶段日志应各只出现一次
            init_count = log_output.count("初始化成功")
            start_count = log_output.count("启动成功")

            assert init_count == 1, f"Expected 1 '初始化成功', got {init_count}"
            assert start_count == 1, f"Expected 1 '启动成功', got {start_count}"
        finally:
            game_logger.removeHandler(handler)
            game_logger.setLevel(original_level)
```

- [ ] **Step 2: 运行测试验证**

Run: `cd /Users/xbit/code/campusworld/campusworld/backend && pytest tests/game_engine/test_campus_life_initialization.py -v`
Expected: 所有测试 PASS

- [ ] **Step 3: 提交**

```bash
git add tests/game_engine/test_campus_life_initialization.py
git commit -m "test(game_engine): add initialization flow tests for campus_life

- Test import does not trigger init logs (factory pattern)
- Test initialize_game() calls correct method (not start)
- Test full lifecycle: create → initialize_game() → start()
- Test no duplicate logs during lifecycle
"
```

---

## Task 4: 端到端验证 - 启动系统检查日志

**文件:**
- 无文件变更，仅运行验证

- [ ] **Step 1: 启动系统并检查日志**

Run: `cd /Users/xbit/code/campusworld/campusworld/backend && timeout 5 python campusworld.py 2>&1 | head -50 || true`
Expected:
- "园区世界初始化完成" 最多出现 0 次（已移除）
- "园区世界初始化成功" 出现 1 次
- "园区世界启动成功" 出现 1 次
- 不再有重复的初始化/启动日志

- [ ] **Step 2: 提交（如验证通过）**

```bash
git add -A
git commit -m "verify: confirm no duplicate init logs in system startup"
```

---

## 验证清单

- [ ] `__init__.py` 无模块级单例 `campus_life_game`
- [ ] `get_game_instance()` 为工厂函数，每次返回新实例
- [ ] `initialize_game()` 正确调用 `instance.initialize_game()`，不是 `start()`
- [ ] `game.py` 的 `__init__` 中无 "园区世界初始化完成" 日志
- [ ] `game.py` 中 "园区世界初始化成功" 在 `initialize_game()` 方法内
- [ ] `game.py` 中 "园区世界启动成功" 在 `start()` 方法内
- [ ] pytest 测试全部通过
- [ ] 系统启动日志无重复

---

## 修复后的日志预期

```
game_engine.CampusWorld.loader - INFO - 自动加载完成，成功加载 1 个场景: ['campus_life']
game.campus_life.game - INFO - 园区世界初始化成功          # ← 只出现1次
game.campus_life.game - INFO - 园区世界启动成功，启动时间: ...  # ← 只出现1次
```

不再有：
- "园区世界初始化完成" （误导性的 __init__ 日志已移除）
- 任何重复的初始化/启动日志
