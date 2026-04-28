#!/usr/bin/env python3
"""
Room Connection Visualizer

可视化房间连接关系，验证物理连接的合理性
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.test_demo_building_generator import DemoBuildingGenerator
from app.core.log import get_logger, LoggerNames


class RoomConnectionVisualizer:
    """房间连接可视化器"""
    
    def __init__(self):
        self.logger = get_logger(LoggerNames.GAME)
        self.generator = DemoBuildingGenerator()
    
    def visualize_floor_layout(self, floor_num: int, room_count: int):
        """可视化楼层布局和连接"""
        print(f"\n{'='*60}")
        print(f"楼层 {floor_num} 布局可视化 ({room_count} 个房间)")
        print(f"{'='*60}")
        
        # 创建模拟房间列表
        floor_rooms = [f"{floor_num}_{i+1}" for i in range(room_count)]
        
        # 计算楼层布局
        cols = self._get_floor_cols(room_count)
        rows = (room_count + cols - 1) // cols
        
        print(f"布局: {rows}行 x {cols}列")
        print()
        
        # 创建房间网格
        room_grid = {}
        for room_id in floor_rooms:
            room_num = int(room_id.split("_")[1])
            row = (room_num - 1) // cols
            col = (room_num - 1) % cols
            room_grid[(row, col)] = room_id
        
        # 显示房间网格
        for row in range(rows):
            for col in range(cols):
                room_id = room_grid.get((row, col), "  ")
                if room_id != "  ":
                    room_num = int(room_id.split("_")[1])
                    print(f"{room_num:2d}", end=" ")
                else:
                    print("  ", end=" ")
            print()
        
        print()
        
        # 显示连接关系
        self._show_room_connections(floor_rooms, cols)
    
    def _get_floor_cols(self, room_count: int) -> int:
        """获取楼层列数"""
        if room_count <= 10:
            return 5 if room_count <= 10 else 4
        elif room_count <= 20:
            return 5
        elif room_count <= 32:
            return 6 if room_count <= 36 else 8
        else:
            return 8
    
    def _show_room_connections(self, floor_rooms: List[str], cols: int):
        """显示房间连接关系"""
        print("房间连接关系:")
        print("-" * 40)
        
        # 只显示前10个房间的连接，避免输出过长
        display_rooms = floor_rooms[:10]
        
        for room_id in display_rooms:
            room_num = int(room_id.split("_")[1])
            room_coords = self.generator._get_room_coordinates(room_num, len(floor_rooms))
            
            # 找到相邻房间
            adjacent_rooms = self.generator._find_adjacent_rooms(room_id, floor_rooms, room_coords)
            
            # 生成连接
            connections = self.generator._generate_room_connections(room_id, floor_rooms)
            
            print(f"房间 {room_num:2d} (坐标{room_coords}):")
            print(f"  相邻房间: {len(adjacent_rooms)}个 - {[int(r.split('_')[1]) for r in adjacent_rooms]}")
            print(f"  实际连接: {len(connections)}个")
            
            for direction, target_room_id in connections.items():
                target_num = int(target_room_id.split("_")[1])
                target_coords = self.generator._get_room_coordinates(target_num, len(floor_rooms))
                print(f"    {direction:8s} -> 房间{target_num:2d} (坐标{target_coords})")
            
            print()
    
    def visualize_adjacency_matrix(self, floor_num: int, room_count: int):
        """可视化相邻关系矩阵"""
        print(f"\n{'='*60}")
        print(f"楼层 {floor_num} 相邻关系矩阵")
        print(f"{'='*60}")
        
        floor_rooms = [f"{floor_num}_{i+1}" for i in range(room_count)]
        cols = self._get_floor_cols(room_count)
        
        # 创建相邻关系矩阵
        adjacency_matrix = {}
        for room_id in floor_rooms:
            room_num = int(room_id.split("_")[1])
            room_coords = self.generator._get_room_coordinates(room_num, room_count)
            adjacent_rooms = self.generator._find_adjacent_rooms(room_id, floor_rooms, room_coords)
            adjacency_matrix[room_num] = [int(r.split("_")[1]) for r in adjacent_rooms]
        
        # 显示矩阵
        print("房间编号 -> 相邻房间")
        print("-" * 30)
        for room_num in sorted(adjacency_matrix.keys()):
            adjacent_nums = sorted(adjacency_matrix[room_num])
            print(f"{room_num:2d} -> {adjacent_nums}")
    
    def analyze_connection_statistics(self, floor_num: int, room_count: int):
        """分析连接统计信息"""
        print(f"\n{'='*60}")
        print(f"楼层 {floor_num} 连接统计分析")
        print(f"{'='*60}")
        
        floor_rooms = [f"{floor_num}_{i+1}" for i in range(room_count)]
        
        total_connections = 0
        connection_counts = {}
        direction_counts = {}
        
        for room_id in floor_rooms:
            room_num = int(room_id.split("_")[1])
            room_coords = self.generator._get_room_coordinates(room_num, room_count)
            connections = self.generator._generate_room_connections(room_id, floor_rooms)
            
            connection_count = len(connections)
            total_connections += connection_count
            connection_counts[connection_count] = connection_counts.get(connection_count, 0) + 1
            
            for direction in connections.keys():
                direction_counts[direction] = direction_counts.get(direction, 0) + 1
        
        print(f"总连接数: {total_connections}")
        print(f"平均每房间连接数: {total_connections / room_count:.2f}")
        print()
        
        print("连接数分布:")
        for count, rooms in sorted(connection_counts.items()):
            print(f"  {count}个连接: {rooms}个房间")
        
        print()
        print("方向分布:")
        for direction, count in sorted(direction_counts.items()):
            print(f"  {direction:8s}: {count}次")
    
    def run_visualization(self):
        """运行完整的可视化"""
        print("房间连接可视化工具")
        print("=" * 60)
        
        # 测试不同楼层的布局
        test_floors = [
            {"floor": 1, "rooms": 10, "description": "小楼层"},
            {"floor": 2, "rooms": 20, "description": "中等楼层"},
            {"floor": 3, "rooms": 32, "description": "大楼层"},
        ]
        
        for test_case in test_floors:
            floor_num = test_case["floor"]
            room_count = test_case["rooms"]
            description = test_case["description"]
            
            print(f"\n测试 {description} (楼层{floor_num}, {room_count}个房间)")
            
            # 可视化楼层布局
            self.visualize_floor_layout(floor_num, room_count)
            
            # 显示相邻关系矩阵
            self.visualize_adjacency_matrix(floor_num, room_count)
            
            # 分析连接统计
            self.analyze_connection_statistics(floor_num, room_count)


def main():
    """主函数"""
    try:
        visualizer = RoomConnectionVisualizer()
        visualizer.run_visualization()
        
        print("\n🎉 房间连接可视化完成！")
        print("\n验证要点:")
        print("1. 所有连接都是物理相邻的房间")
        print("2. 方向计算正确")
        print("3. 连接数量合理 (1-3个)")
        print("4. 楼层布局符合实际建筑结构")
        
    except Exception as e:
        print(f"❌ 可视化失败: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
