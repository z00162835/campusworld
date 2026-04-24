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

        game_logger = logging.getLogger('game.campus_life')
        original_level = game_logger.level
        game_logger.setLevel(logging.INFO)
        game_logger.addHandler(handler)

        try:
            import app.games.campus_life as cl
            instance = cl.get_game_instance()
            assert instance is not None

            log_output = log_capture.getvalue()
            assert "初始化完成" not in log_output, \
                f"Unexpected '初始化完成' log during import: {log_output}"
        finally:
            game_logger.removeHandler(handler)
            game_logger.setLevel(original_level)

    def test_factory_returns_new_instances(self):
        """验证工厂函数返回新实例"""
        import app.games.campus_life as cl

        instance1 = cl.get_game_instance()
        instance2 = cl.get_game_instance()

        assert instance1 is not instance2, "Factory should return new instances"
        assert instance1.is_initialized is False
        assert instance2.is_initialized is False

    def test_initialize_game_calls_correct_method(self):
        """验证 initialize_game() 调用的是 initialize_game() 而非 start()"""
        import app.games.campus_life as cl

        instance = cl.get_game_instance()

        with patch.object(instance, 'start') as mock_start, \
             patch.object(instance, 'initialize_game', wraps=instance.initialize_game) as mock_init:

            instance.initialize_game()

            mock_init.assert_called_once()
            mock_start.assert_not_called()

    def test_full_lifecycle_sequence(self):
        """验证完整生命周期: 创建 → 初始化 → 启动"""
        import app.games.campus_life as cl

        instance = cl.get_game_instance()

        assert instance.is_initialized is False
        assert instance.is_running is False

        init_result = instance.initialize_game()
        assert init_result is True
        assert instance.is_initialized is True

        start_result = instance.start()
        assert start_result is True
        assert instance.is_running is True

    def test_start_idempotent(self):
        """验证 start() 是幂等的"""
        import app.games.campus_life as cl

        instance = cl.get_game_instance()
        instance.initialize_game()

        result1 = instance.start()
        assert result1 is True

        # Start again - should be idempotent
        result2 = instance.start()
        assert result2 is True  # Returns True but doesn't restart