"""
Demo Building Generator 测试

测试建筑生成器的配置和逻辑
"""

import math
from pathlib import Path

import pytest

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(project_root))


def calculate_grid_columns(room_count: int) -> int:
    """计算网格列数"""
    return math.ceil(math.sqrt(room_count))


def get_room_coordinates(room_num: int, room_count: int) -> tuple:
    """计算房间坐标"""
    cols = calculate_grid_columns(room_count)
    row = (room_num - 1) // cols
    col = (room_num - 1) % cols
    return (row, col)


class TestRoomCoordinateCalculation:
    """房间坐标计算测试"""

    def test_10_rooms(self):
        """10个房间的坐标计算"""
        # 10 rooms -> 4 columns (sqrt(10) = 3.16, ceil = 4)
        cols = calculate_grid_columns(10)
        assert cols == 4

        # 验证坐标
        result = get_room_coordinates(1, 10)
        assert result == (0, 0)
        result = get_room_coordinates(4, 10)
        assert result == (0, 3)
        result = get_room_coordinates(5, 10)
        assert result == (1, 0)
        result = get_room_coordinates(10, 10)
        assert result == (2, 1)

    def test_20_rooms(self):
        """20个房间的坐标计算"""
        # 20 rooms -> 5 columns
        cols = calculate_grid_columns(20)
        assert cols == 5

        result = get_room_coordinates(1, 20)
        assert result == (0, 0)
        result = get_room_coordinates(5, 20)
        assert result == (0, 4)
        result = get_room_coordinates(6, 20)
        assert result == (1, 0)

    def test_32_rooms(self):
        """32个房间的坐标计算"""
        # 32 rooms -> 6 columns
        cols = calculate_grid_columns(32)
        assert cols == 6

        result = get_room_coordinates(1, 32)
        assert result == (0, 0)
        result = get_room_coordinates(6, 32)
        assert result == (0, 5)
        result = get_room_coordinates(7, 32)
        assert result == (1, 0)

    def test_50_rooms(self):
        """50个房间的坐标计算"""
        # 50 rooms -> 8 columns
        cols = calculate_grid_columns(50)
        assert cols == 8

        result = get_room_coordinates(1, 50)
        assert result == (0, 0)
        result = get_room_coordinates(8, 50)
        assert result == (0, 7)
        result = get_room_coordinates(9, 50)
        assert result == (1, 0)


class TestFloorConfiguration:
    """楼层配置测试"""

    def test_floor_config(self):
        """验证楼层配置"""
        floor_config = {
            -2: {"room_count": 30, "room_type": "parking", "floor_type": "basement"},
            -1: {"room_count": 30, "room_type": "mixed", "floor_type": "basement"},
            1: {"room_count": 10, "room_type": "normal", "floor_type": "normal"},
            2: {"room_count": 20, "room_type": "normal", "floor_type": "normal"},
            3: {"room_count": 50, "room_type": "normal", "floor_type": "normal"},
            4: {"room_count": 32, "room_type": "normal", "floor_type": "normal"},
            5: {"room_count": 32, "room_type": "normal", "floor_type": "normal"},
            6: {"room_count": 32, "room_type": "normal", "floor_type": "normal"},
            7: {"room_count": 16, "room_type": "normal", "floor_type": "normal"},
            8: {"room_count": 36, "room_type": "normal", "floor_type": "normal"},
        }

        # 验证楼层数量
        assert len(floor_config) == 10

        # 验证总房间数
        total_rooms = sum(config["room_count"] for config in floor_config.values())
        assert total_rooms == 288

        # 验证地下楼层类型
        assert floor_config[-2]["room_type"] == "parking"
        assert floor_config[-1]["room_type"] == "mixed"

    def test_floor_room_counts(self):
        """验证各楼层房间数量"""
        floor_config = {
            -2: {"room_count": 30},
            -1: {"room_count": 30},
            1: {"room_count": 10},
            2: {"room_count": 20},
            3: {"room_count": 50},
            4: {"room_count": 32},
            5: {"room_count": 32},
            6: {"room_count": 32},
            7: {"room_count": 16},
            8: {"room_count": 36},
        }

        expected = [30, 30, 10, 20, 50, 32, 32, 32, 16, 36]
        actual = [config["room_count"] for config in floor_config.values()]

        assert actual == expected


class TestFurnitureTemplates:
    """家具模板测试"""

    def test_furniture_categories(self):
        """验证家具分类"""
        furniture_templates = {
            "office": ["办公桌", "办公椅", "文件柜", "书架", "打印机", "电脑", "电话", "白板"],
            "classroom": ["讲台", "黑板", "课桌椅", "投影仪", "音响设备", "储物柜"],
            "meeting": ["会议桌", "会议椅", "投影屏幕", "音响系统", "咖啡机"],
            "lab": ["实验台", "实验椅", "实验设备", "安全柜", "通风设备", "显微镜"],
            "common": ["沙发", "茶几", "电视", "空调", "饮水机", "垃圾桶", "植物"],
            "parking": ["停车位", "充电桩", "监控设备", "消防设备", "通风系统"],
            "cold_room": ["冷机设备", "温度控制器", "监控系统", "报警系统", "维护工具"]
        }

        # 验证分类数量
        assert len(furniture_templates) == 7

        # 验证每个分类都有物品
        for category, items in furniture_templates.items():
            assert len(items) > 0, f"{category} 分类为空"

    def test_wifi_ap_config(self):
        """验证 WiFi AP 配置"""
        wifi_ap_config = {
            "name": "WiFi AP",
            "object_type": "equipment",
            "category": "network",
            "description": "无线网络接入点",
            "is_interactive": True,
            "is_movable": False,
            "functions": ["wifi_access", "network_monitoring"],
            "value": 500,
            "weight": 2.0
        }

        # 验证必要字段
        assert wifi_ap_config["name"] == "WiFi AP"
        assert wifi_ap_config["category"] == "network"
        assert wifi_ap_config["is_interactive"] is True
        assert wifi_ap_config["is_movable"] is False
