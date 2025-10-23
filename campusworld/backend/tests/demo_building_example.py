#!/usr/bin/env python3
"""
Demo Building Generator Usage Example

演示如何使用Demo Building Generator创建和测试demo building
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.test_demo_building_generator import DemoBuildingGenerator
from app.core.log import get_logger, LoggerNames


def main():
    """主函数 - 演示Demo Building Generator的使用"""
    logger = get_logger(LoggerNames.GAME)
    
    print("=" * 80)
    print("Demo Building Generator 使用示例")
    print("=" * 80)
    
    try:
        # 创建生成器实例
        print("1. 创建Demo Building Generator...")
        generator = DemoBuildingGenerator()
        
        # 生成demo building
        print("2. 生成Demo Building...")
        success = generator.generate_building()
        
        if success:
            print("✓ Demo Building生成成功！")
            
            # 显示生成摘要
            print("\n3. 生成摘要:")
            generator.print_building_summary()
            
            # 显示详细信息
            print("\n4. 详细信息:")
            _show_detailed_info(generator)
            
            print("\n🎉 Demo Building Generator使用示例完成！")
            
        else:
            print("❌ Demo Building生成失败！")
            return False
            
    except Exception as e:
        logger.error(f"使用示例执行失败: {e}")
        print(f"❌ 错误: {e}")
        return False
    
    return True


def _show_detailed_info(generator: DemoBuildingGenerator):
    """显示详细信息"""
    print("\n楼层详情:")
    
    for floor_num in sorted(generator.floors.keys()):
        floor = generator.floors[floor_num]
        floor_rooms = [room_id for room_id in generator.rooms.keys() if room_id.startswith(f"{floor_num}_")]
        
        print(f"\n第{floor_num}层 ({floor.name}):")
        print(f"  房间数量: {len(floor_rooms)}")
        print(f"  楼层面积: {floor.get_node_attribute('floor_area', 0):.1f}㎡")
        print(f"  楼层高度: {floor.get_node_attribute('floor_height', 0)}m")
        
        # 显示前几个房间的详细信息
        sample_rooms = floor_rooms[:3]  # 只显示前3个房间
        for room_id in sample_rooms:
            room = generator.rooms[room_id]
            room_type = room.get_node_attribute("room_type")
            room_area = room.get_node_attribute("room_area", 0)
            room_capacity = room.get_node_attribute("room_capacity", 0)
            room_objects = room.get_node_attribute("room_objects", [])
            
            print(f"    {room.name}:")
            print(f"      类型: {room_type}")
            print(f"      面积: {room_area}㎡")
            print(f"      容量: {room_capacity}人")
            print(f"      对象数: {len(room_objects)}个")
        
        if len(floor_rooms) > 3:
            print(f"    ... 还有{len(floor_rooms) - 3}个房间")


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
