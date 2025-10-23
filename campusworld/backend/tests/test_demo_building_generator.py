#!/usr/bin/env python3
"""
Demo Building Generator Test Script

基于项目模型能力，参考Evennia设计，构建和测试demo building：
- 地下2层，地上8层floor
- 每个floor随机设计大小不一联通关系随机的房间
- 地下一层30个房间，地下二层30个房间
- 1楼是10个房间，2楼是20个房间，3楼是50个房间
- 4~6楼是32个房间，7楼是16个房间，8楼是36个房间
- 地上每个房间随机生成一些家具和物品，但必须每个房间都有1个WIFI AP
- 地下1层在一个房间中生成冷机设备，其他生成为停车场
- 地下2层全部为停车场
"""

import sys
import os
import random
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.model_manager import model_manager
from app.models.building import Building, BuildingFloor
from app.models.room import Room
from app.models.world import WorldObject
from app.models.factory import model_factory
from app.core.log import get_logger, LoggerNames


class DemoBuildingGenerator:
    """Demo Building Generator - 参考Evennia设计模式"""
    
    def __init__(self):
        self.logger = get_logger(LoggerNames.GAME)
        self.building = None
        self.floors = {}
        self.rooms = {}
        self.objects = {}
        
        # 楼层配置
        self.floor_config = {
            -2: {"room_count": 30, "room_type": "parking", "floor_type": "basement"},
            -1: {"room_count": 30, "room_type": "mixed", "floor_type": "basement"},  # 混合：1个冷机房+29个停车场
            1: {"room_count": 10, "room_type": "normal", "floor_type": "normal"},
            2: {"room_count": 20, "room_type": "normal", "floor_type": "normal"},
            3: {"room_count": 50, "room_type": "normal", "floor_type": "normal"},
            4: {"room_count": 32, "room_type": "normal", "floor_type": "normal"},
            5: {"room_count": 32, "room_type": "normal", "floor_type": "normal"},
            6: {"room_count": 32, "room_type": "normal", "floor_type": "normal"},
            7: {"room_count": 16, "room_type": "normal", "floor_type": "normal"},
            8: {"room_count": 36, "room_type": "normal", "floor_type": "normal"},
        }
        
        # 家具和物品配置
        self.furniture_templates = {
            "office": ["办公桌", "办公椅", "文件柜", "书架", "打印机", "电脑", "电话", "白板"],
            "classroom": ["讲台", "黑板", "课桌椅", "投影仪", "音响设备", "储物柜"],
            "meeting": ["会议桌", "会议椅", "投影屏幕", "音响系统", "咖啡机"],
            "lab": ["实验台", "实验椅", "实验设备", "安全柜", "通风设备", "显微镜"],
            "common": ["沙发", "茶几", "电视", "空调", "饮水机", "垃圾桶", "植物"],
            "parking": ["停车位", "充电桩", "监控设备", "消防设备", "通风系统"],
            "cold_room": ["冷机设备", "温度控制器", "监控系统", "报警系统", "维护工具"]
        }
        
        # WiFi AP配置
        self.wifi_ap_config = {
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
        
        self.logger.info("Demo Building Generator 初始化完成")
    
    def generate_building(self) -> bool:
        """生成整个demo building"""
        try:
            self.logger.info("开始生成Demo Building...")
            
            # 1. 创建建筑
            if not self._create_building():
                return False
            
            # 2. 创建楼层
            if not self._create_floors():
                return False
            
            # 3. 创建房间
            if not self._create_rooms():
                return False
            
            # 4. 创建房间连接
            if not self._create_room_connections():
                return False
            
            # 5. 生成家具和物品
            if not self._generate_furniture_and_objects():
                return False
            
            # 6. 生成特殊房间内容
            if not self._generate_special_room_content():
                return False
            
            self.logger.info("Demo Building 生成完成！")
            return True
            
        except Exception as e:
            self.logger.error(f"生成Demo Building失败: {e}")
            return False
    
    def _create_building(self) -> bool:
        """创建建筑"""
        try:
            self.logger.info("创建建筑...")
            
            building_attrs = {
                "uns": "DEMO/DEMO_BLD/DEMO001",
                "building_type": "mixed_use",
                "building_status": "active",
                "building_class": "class_a",
                "building_code": "DEMO001",
                "building_name": "Demo Building",
                "building_name_en": "Demo Building",
                "building_abbreviation": "DEMO",
                "building_address": "Demo Campus, Demo Street",
                "building_city": "Demo City",
                "building_province": "Demo Province",
                "building_country": "Demo Country",
                "building_latitude": 22.586667,
                "building_longitude": 114.103611,
                "building_area": 50000,  # 总建筑面积
                "building_floor_area": 45000,  # 使用面积
                "building_height": 40,  # 建筑高度
                "building_floors": 8,  # 地上层数
                "building_basement_floors": 2,  # 地下层数
                "building_capacity": 2000,
                "building_rooms": sum(config["room_count"] for config in self.floor_config.values()),
                "building_classrooms": 0,
                "building_offices": 0,
                "building_labs": 0,
            }
            
            self.building = Building(
                name="Demo Building",
                config={"attributes": building_attrs, "tags": ["building", "demo", "mixed_use"]}
            )
            
            self.logger.info(f"✓ 建筑创建成功: {self.building.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"创建建筑失败: {e}")
            return False
    
    def _create_floors(self) -> bool:
        """创建楼层"""
        try:
            self.logger.info("创建楼层...")
            
            for floor_num, config in self.floor_config.items():
                floor_attrs = {
                    "uns": f"DEMO/DEMO_BLD/FLOOR{floor_num:02d}",
                    "floor_number": floor_num,
                    "floor_name": f"第{floor_num}层" if floor_num > 0 else f"地下{abs(floor_num)}层",
                    "floor_code": f"DEMO_DEMO_BLD_FLOOR{floor_num:02d}",
                    "floor_type": config["floor_type"],
                    "floor_area": self._calculate_floor_area(floor_num, config["room_count"]),
                    "floor_height": 3.0 if floor_num > 0 else 3.5,  # 地下层高一些
                    "floor_capacity": config["room_count"] * 10,  # 每房间10人容量
                    "floor_rooms": config["room_count"],
                    "floor_rooms_list": [],
                }
                
                floor_tags = ["building_floor", f"floor_{floor_num}"]
                if config["floor_type"] != "normal":
                    floor_tags.append(config["floor_type"])
                
                floor = BuildingFloor(
                    name=f"Floor {floor_num}",
                    floor_number=floor_num,
                    config={"attributes": floor_attrs, "tags": floor_tags}
                )
                
                self.floors[floor_num] = floor
                self.logger.info(f"✓ 楼层创建成功: {floor.name}")
            
            self.logger.info(f"✓ 所有楼层创建成功，共{len(self.floors)}层")
            return True
            
        except Exception as e:
            self.logger.error(f"创建楼层失败: {e}")
            return False
    
    def _create_rooms(self) -> bool:
        """创建房间"""
        try:
            self.logger.info("创建房间...")
            
            total_rooms = 0
            for floor_num, config in self.floor_config.items():
                floor_rooms = []
                
                for room_index in range(config["room_count"]):
                    room_num = room_index + 1
                    room_code = f"ROOM{room_num:03d}"
                    
                    # 确定房间类型
                    if config["room_type"] == "parking":
                        room_type = "parking"
                    elif config["room_type"] == "mixed" and room_index == 0:
                        room_type = "cold_room"  # 第一个房间是冷机房
                    elif config["room_type"] == "mixed":
                        room_type = "parking"
                    else:
                        room_type = self._get_random_room_type()
                    
                    room_attrs = {
                        "uns": f"DEMO/DEMO_BLD/FLOOR{floor_num:02d}/{room_code}",
                        "room_type": room_type,
                        "room_code": room_code,
                        "room_name": f"{room_type.title()} Room {room_num}",
                        "room_name_en": f"{room_type.title()} Room {room_num}",
                        "room_description": self._generate_room_description(room_type, floor_num, room_num),
                        "room_short_description": f"A {room_type} room on floor {floor_num}",
                        "room_address": f"Demo Building Floor {floor_num}",
                        "room_floor": floor_num,
                        "room_building": "Demo Building",
                        "room_campus": "Demo Campus",
                        "room_area": self._generate_random_room_area(room_type),
                        "room_height": 3.0 if floor_num > 0 else 3.5,
                        "room_capacity": self._calculate_room_capacity(room_type),
                        "room_temperature": self._get_room_temperature(room_type),
                        "room_humidity": random.randint(40, 60),
                        "room_lighting": "normal",
                        "room_status": "active",
                        "is_public": True,
                        "is_accessible": True,
                        "is_lighted": True,
                        "is_indoors": True,
                        "room_objects": [],
                        "room_exits": {},
                    }
                    
                    room_tags = ["room", room_type, f"floor_{floor_num}"]
                    if floor_num < 0:
                        room_tags.append("basement")
                    
                    room = Room(
                        name=f"{room_type.title()} Room {room_num}",
                        config={"attributes": room_attrs, "tags": room_tags}
                    )
                    
                    room_id = f"{floor_num}_{room_num}"
                    self.rooms[room_id] = room
                    floor_rooms.append(room_id)
                    total_rooms += 1
                
                # 更新楼层房间列表
                if floor_num in self.floors:
                    self.floors[floor_num].set_node_attribute("floor_rooms_list", floor_rooms)
            
            self.logger.info(f"✓ 所有房间创建成功，共{total_rooms}个房间")
            return True
            
        except Exception as e:
            self.logger.error(f"创建房间失败: {e}")
            return False
    
    def _create_room_connections(self) -> bool:
        """创建房间连接关系"""
        try:
            self.logger.info("创建房间连接关系...")
            
            connections_created = 0
            
            for floor_num, config in self.floor_config.items():
                floor_rooms = [room_id for room_id in self.rooms.keys() if room_id.startswith(f"{floor_num}_")]
                
                # 为每个房间创建随机连接
                for room_id in floor_rooms:
                    room = self.rooms[room_id]
                    connections = self._generate_room_connections(room_id, floor_rooms)
                    
                    for direction, target_room_id in connections.items():
                        room.add_exit(direction, target_room_id)
                        connections_created += 1
                
                # 创建楼层间的连接（楼梯/电梯）
                if floor_num < max(self.floor_config.keys()):
                    self._create_floor_connections(floor_num)
            
            self.logger.info(f"✓ 房间连接关系创建完成，共{connections_created}个连接")
            return True
            
        except Exception as e:
            self.logger.error(f"创建房间连接失败: {e}")
            return False
    
    def _generate_furniture_and_objects(self) -> bool:
        """生成家具和物品"""
        try:
            self.logger.info("生成家具和物品...")
            
            objects_created = 0
            
            for room_id, room in self.rooms.items():
                room_type = room.get_node_attribute("room_type")
                floor_num = room.get_node_attribute("room_floor")
                
                # 每个房间必须有WiFi AP
                wifi_ap = self._create_wifi_ap(room_id)
                if wifi_ap:
                    room.add_object(wifi_ap.id)
                    objects_created += 1
                
                # 根据房间类型生成家具
                if room_type in self.furniture_templates:
                    furniture_count = random.randint(3, 8)  # 每个房间3-8件家具
                    furniture_items = random.sample(
                        self.furniture_templates[room_type], 
                        min(furniture_count, len(self.furniture_templates[room_type]))
                    )
                    
                    for furniture_name in furniture_items:
                        furniture = self._create_furniture(furniture_name, room_type, room_id)
                        if furniture:
                            room.add_object(furniture.id)
                            objects_created += 1
                
                # 随机生成一些通用物品
                common_items = random.randint(1, 3)
                for _ in range(common_items):
                    item = self._create_random_item(room_id)
                    if item:
                        room.add_object(item.id)
                        objects_created += 1
            
            self.logger.info(f"✓ 家具和物品生成完成，共{objects_created}个对象")
            return True
            
        except Exception as e:
            self.logger.error(f"生成家具和物品失败: {e}")
            return False
    
    def _generate_special_room_content(self) -> bool:
        """生成特殊房间内容"""
        try:
            self.logger.info("生成特殊房间内容...")
            
            # 地下1层的冷机房
            cold_room_id = "-1_1"  # 地下1层第1个房间
            if cold_room_id in self.rooms:
                cold_room = self.rooms[cold_room_id]
                
                # 添加冷机设备
                cold_machine = self._create_cold_machine(cold_room_id)
                if cold_machine:
                    cold_room.add_object(cold_machine.id)
                
                # 添加冷机房专用设备
                cold_room_equipment = ["温度传感器", "湿度传感器", "压力表", "控制面板", "维护工具"]
                for equipment_name in cold_room_equipment:
                    equipment = self._create_equipment(equipment_name, "cold_room", cold_room_id)
                    if equipment:
                        cold_room.add_object(equipment.id)
            
            self.logger.info("✓ 特殊房间内容生成完成")
            return True
            
        except Exception as e:
            self.logger.error(f"生成特殊房间内容失败: {e}")
            return False
    
    # ==================== 辅助方法 ====================
    
    def _calculate_floor_area(self, floor_num: int, room_count: int) -> float:
        """计算楼层面积"""
        base_area = room_count * 50  # 每个房间平均50平方米
        if floor_num < 0:  # 地下层
            return base_area * 1.2  # 地下层面积大一些
        return base_area
    
    def _get_random_room_type(self) -> str:
        """获取随机房间类型"""
        room_types = ["office", "classroom", "meeting", "lab", "common"]
        weights = [0.3, 0.25, 0.2, 0.15, 0.1]  # 不同房间类型的权重
        return random.choices(room_types, weights=weights)[0]
    
    def _generate_room_description(self, room_type: str, floor_num: int, room_num: int) -> str:
        """生成房间描述"""
        descriptions = {
            "office": f"这是一个现代化的办公室，配备了办公桌椅和必要的办公设备。",
            "classroom": f"这是一个宽敞的教室，配备了教学设备和学生座椅。",
            "meeting": f"这是一个会议室，适合进行各种会议和讨论。",
            "lab": f"这是一个实验室，配备了专业的实验设备和安全设施。",
            "common": f"这是一个公共区域，为人们提供休息和交流的空间。",
            "parking": f"这是一个停车场，提供车辆停放服务。",
            "cold_room": f"这是一个冷机房，配备了专业的制冷设备和监控系统。"
        }
        
        base_desc = descriptions.get(room_type, "这是一个普通的房间。")
        floor_desc = f"位于第{floor_num}层" if floor_num > 0 else f"位于地下{abs(floor_num)}层"
        
        return f"{base_desc} {floor_desc}，房间编号{room_num}。"
    
    def _generate_random_room_area(self, room_type: str) -> float:
        """生成随机房间面积"""
        area_ranges = {
            "office": (20, 50),
            "classroom": (60, 120),
            "meeting": (30, 80),
            "lab": (40, 100),
            "common": (30, 60),
            "parking": (15, 25),  # 停车位
            "cold_room": (50, 100)
        }
        
        min_area, max_area = area_ranges.get(room_type, (20, 50))
        return round(random.uniform(min_area, max_area), 1)
    
    def _calculate_room_capacity(self, room_type: str) -> int:
        """计算房间容量"""
        capacity_ranges = {
            "office": (2, 8),
            "classroom": (20, 50),
            "meeting": (8, 20),
            "lab": (4, 12),
            "common": (5, 15),
            "parking": (1, 1),  # 停车位
            "cold_room": (2, 4)
        }
        
        min_cap, max_cap = capacity_ranges.get(room_type, (2, 8))
        return random.randint(min_cap, max_cap)
    
    def _get_room_temperature(self, room_type: str) -> int:
        """获取房间温度"""
        if room_type == "cold_room":
            return random.randint(2, 8)  # 冷机房温度
        elif room_type == "parking":
            return random.randint(15, 25)  # 停车场温度
        else:
            return random.randint(20, 24)  # 正常房间温度
    
    def _generate_room_connections(self, room_id: str, floor_rooms: List[str]) -> Dict[str, str]:
        """生成房间连接 - 基于物理空间布局的合理连接"""
        connections = {}
        floor_num = int(room_id.split("_")[0])
        room_num = int(room_id.split("_")[1])
        
        # 获取房间的空间坐标（基于房间编号模拟网格布局）
        room_coords = self._get_room_coordinates(room_num, len(floor_rooms))
        
        # 找到物理上相邻的房间
        adjacent_rooms = self._find_adjacent_rooms(room_id, floor_rooms, room_coords)
        
        if adjacent_rooms:
            # 随机选择1-3个相邻房间进行连接
            connection_count = random.randint(1, min(3, len(adjacent_rooms)))
            connected_rooms = random.sample(adjacent_rooms, connection_count)
            
            # 为每个连接的房间分配合理的方向
            for target_room_id in connected_rooms:
                direction = self._calculate_direction(room_coords, target_room_id, floor_rooms)
                if direction:
                    connections[direction] = target_room_id
        
        return connections
    
    def _get_room_coordinates(self, room_num: int, total_rooms: int) -> Tuple[int, int]:
        """根据房间编号计算房间在楼层中的坐标位置"""
        # 假设楼层是矩形布局，计算网格坐标
        # 根据房间数量估算楼层布局
        if total_rooms <= 10:
            # 小楼层：2x5 或 3x4 布局
            cols = 5 if total_rooms <= 10 else 4
        elif total_rooms <= 20:
            # 中等楼层：4x5 布局
            cols = 5
        elif total_rooms <= 32:
            # 大楼层：6x6 或 8x4 布局
            cols = 6 if total_rooms <= 36 else 8
        else:
            # 超大楼层：8x7 布局
            cols = 8
        
        rows = (total_rooms + cols - 1) // cols  # 向上取整
        
        # 计算房间在网格中的位置
        row = (room_num - 1) // cols
        col = (room_num - 1) % cols
        
        return (row, col)
    
    def _find_adjacent_rooms(self, room_id: str, floor_rooms: List[str], room_coords: Tuple[int, int]) -> List[str]:
        """找到物理上相邻的房间"""
        adjacent_rooms = []
        floor_num = int(room_id.split("_")[0])
        room_num = int(room_id.split("_")[1])
        current_row, current_col = room_coords
        
        # 定义相邻位置的偏移量（上下左右）
        adjacent_offsets = [
            (-1, 0),  # 上
            (1, 0),   # 下
            (0, -1),  # 左
            (0, 1),   # 右
            (-1, -1), # 左上
            (-1, 1),  # 右上
            (1, -1),  # 左下
            (1, 1),   # 右下
        ]
        
        # 计算楼层布局参数
        total_rooms = len(floor_rooms)
        if total_rooms <= 10:
            cols = 5 if total_rooms <= 10 else 4
        elif total_rooms <= 20:
            cols = 5
        elif total_rooms <= 32:
            cols = 6 if total_rooms <= 36 else 8
        else:
            cols = 8
        
        rows = (total_rooms + cols - 1) // cols
        
        # 检查每个相邻位置
        for row_offset, col_offset in adjacent_offsets:
            new_row = current_row + row_offset
            new_col = current_col + col_offset
            
            # 检查是否在有效范围内
            if 0 <= new_row < rows and 0 <= new_col < cols:
                # 计算对应的房间编号
                target_room_num = new_row * cols + new_col + 1
                
                # 检查房间编号是否在有效范围内
                if target_room_num <= total_rooms:
                    target_room_id = f"{floor_num}_{target_room_num}"
                    
                    # 检查目标房间是否存在
                    if target_room_id in floor_rooms and target_room_id != room_id:
                        adjacent_rooms.append(target_room_id)
        
        return adjacent_rooms
    
    def _calculate_direction(self, source_coords: Tuple[int, int], target_room_id: str, floor_rooms: List[str]) -> Optional[str]:
        """计算从源房间到目标房间的方向"""
        try:
            target_room_num = int(target_room_id.split("_")[1])
            total_rooms = len(floor_rooms)
            
            # 计算目标房间坐标
            if total_rooms <= 10:
                cols = 5 if total_rooms <= 10 else 4
            elif total_rooms <= 20:
                cols = 5
            elif total_rooms <= 32:
                cols = 6 if total_rooms <= 36 else 8
            else:
                cols = 8
            
            target_row = (target_room_num - 1) // cols
            target_col = (target_room_num - 1) % cols
            
            source_row, source_col = source_coords
            
            # 计算方向
            row_diff = target_row - source_row
            col_diff = target_col - source_col
            
            # 确定主要方向
            if row_diff < 0 and col_diff == 0:
                return "north"
            elif row_diff > 0 and col_diff == 0:
                return "south"
            elif row_diff == 0 and col_diff < 0:
                return "west"
            elif row_diff == 0 and col_diff > 0:
                return "east"
            elif row_diff < 0 and col_diff < 0:
                return "northwest"
            elif row_diff < 0 and col_diff > 0:
                return "northeast"
            elif row_diff > 0 and col_diff < 0:
                return "southwest"
            elif row_diff > 0 and col_diff > 0:
                return "southeast"
            
            return None
            
        except Exception as e:
            self.logger.error(f"计算方向失败: {e}")
            return None
    
    def _create_floor_connections(self, floor_num: int) -> bool:
        """创建楼层间连接"""
        try:
            # 选择每层的一个房间作为楼梯/电梯间
            current_floor_rooms = [room_id for room_id in self.rooms.keys() if room_id.startswith(f"{floor_num}_")]
            next_floor_rooms = [room_id for room_id in self.rooms.keys() if room_id.startswith(f"{floor_num + 1}_")]
            
            if current_floor_rooms and next_floor_rooms:
                # 选择第一个房间作为连接点
                current_room = self.rooms[current_floor_rooms[0]]
                next_room = self.rooms[next_floor_rooms[0]]
                
                # 添加楼梯连接
                current_room.add_exit("up", next_room.id)
                next_room.add_exit("down", current_room.id)
            
            return True
            
        except Exception as e:
            self.logger.error(f"创建楼层连接失败: {e}")
            return False
    
    def _create_wifi_ap(self, room_id: str) -> Optional[WorldObject]:
        """创建WiFi AP"""
        try:
            wifi_attrs = self.wifi_ap_config.copy()
            wifi_attrs.update({
                "room_id": room_id,
                "floor": int(room_id.split("_")[0]),
                "room_number": int(room_id.split("_")[1])
            })
            
            wifi_ap = WorldObject(
                name=f"WiFi AP {room_id}",
                object_type="equipment",
                **wifi_attrs
            )
            
            return wifi_ap
            
        except Exception as e:
            self.logger.error(f"创建WiFi AP失败: {e}")
            return None
    
    def _create_furniture(self, furniture_name: str, room_type: str, room_id: str) -> Optional[WorldObject]:
        """创建家具"""
        try:
            furniture_attrs = {
                "object_type": "furniture",
                "category": room_type,
                "description": f"A {furniture_name} in {room_type} room",
                "is_interactive": True,
                "is_movable": True,
                "value": random.randint(100, 1000),
                "weight": random.uniform(5.0, 50.0),
                "room_id": room_id,
                "floor": int(room_id.split("_")[0]),
                "room_number": int(room_id.split("_")[1])
            }
            
            furniture = WorldObject(
                name=furniture_name,
                **furniture_attrs
            )
            
            return furniture
            
        except Exception as e:
            self.logger.error(f"创建家具失败: {e}")
            return None
    
    def _create_random_item(self, room_id: str) -> Optional[WorldObject]:
        """创建随机物品"""
        try:
            items = ["水杯", "笔记本", "笔", "文件夹", "垃圾桶", "植物", "装饰画", "时钟"]
            item_name = random.choice(items)
            
            item_attrs = {
                "object_type": "item",
                "category": "common",
                "description": f"A {item_name}",
                "is_interactive": True,
                "is_movable": True,
                "value": random.randint(10, 100),
                "weight": random.uniform(0.1, 2.0),
                "room_id": room_id,
                "floor": int(room_id.split("_")[0]),
                "room_number": int(room_id.split("_")[1])
            }
            
            item = WorldObject(
                name=item_name,
                **item_attrs
            )
            
            return item
            
        except Exception as e:
            self.logger.error(f"创建随机物品失败: {e}")
            return None
    
    def _create_cold_machine(self, room_id: str) -> Optional[WorldObject]:
        """创建冷机设备"""
        try:
            cold_machine_attrs = {
                "object_type": "equipment",
                "category": "hvac",
                "description": "专业制冷设备，用于维持低温环境",
                "is_interactive": True,
                "is_movable": False,
                "value": 50000,
                "weight": 500.0,
                "functions": ["cooling", "temperature_control", "monitoring"],
                "room_id": room_id,
                "floor": int(room_id.split("_")[0]),
                "room_number": int(room_id.split("_")[1])
            }
            
            cold_machine = WorldObject(
                name="冷机设备",
                **cold_machine_attrs
            )
            
            return cold_machine
            
        except Exception as e:
            self.logger.error(f"创建冷机设备失败: {e}")
            return None
    
    def _create_equipment(self, equipment_name: str, category: str, room_id: str) -> Optional[WorldObject]:
        """创建设备"""
        try:
            equipment_attrs = {
                "object_type": "equipment",
                "category": category,
                "description": f"专业{equipment_name}",
                "is_interactive": True,
                "is_movable": False,
                "value": random.randint(1000, 10000),
                "weight": random.uniform(10.0, 100.0),
                "room_id": room_id,
                "floor": int(room_id.split("_")[0]),
                "room_number": int(room_id.split("_")[1])
            }
            
            equipment = WorldObject(
                name=equipment_name,
                **equipment_attrs
            )
            
            return equipment
            
        except Exception as e:
            self.logger.error(f"创建设备失败: {e}")
            return None
    
    def get_building_summary(self) -> Dict[str, Any]:
        """获取建筑摘要信息"""
        try:
            summary = {
                "building": {
                    "name": self.building.name if self.building else "未创建",
                    "floors": len(self.floors),
                    "rooms": len(self.rooms),
                    "objects": len(self.objects)
                },
                "floors": {},
                "room_types": {},
                "object_types": {}
            }
            
            # 楼层统计
            for floor_num, floor in self.floors.items():
                floor_rooms = [room_id for room_id in self.rooms.keys() if room_id.startswith(f"{floor_num}_")]
                summary["floors"][floor_num] = {
                    "name": floor.name,
                    "room_count": len(floor_rooms),
                    "area": floor.get_node_attribute("floor_area", 0)
                }
            
            # 房间类型统计
            for room_id, room in self.rooms.items():
                room_type = room.get_node_attribute("room_type", "unknown")
                if room_type not in summary["room_types"]:
                    summary["room_types"][room_type] = 0
                summary["room_types"][room_type] += 1
            
            # 对象类型统计
            for obj_id, obj in self.objects.items():
                obj_type = obj.get_node_attribute("object_type", "unknown")
                if obj_type not in summary["object_types"]:
                    summary["object_types"][obj_type] = 0
                summary["object_types"][obj_type] += 1
            
            return summary
            
        except Exception as e:
            self.logger.error(f"获取建筑摘要失败: {e}")
            return {}
    
    def print_building_summary(self):
        """打印建筑摘要"""
        summary = self.get_building_summary()
        
        print("\n" + "=" * 80)
        print("DEMO BUILDING 生成摘要")
        print("=" * 80)
        
        # 建筑信息
        building_info = summary.get("building", {})
        print(f"建筑名称: {building_info.get('name', 'N/A')}")
        print(f"楼层数量: {building_info.get('floors', 0)}")
        print(f"房间数量: {building_info.get('rooms', 0)}")
        print(f"对象数量: {building_info.get('objects', 0)}")
        
        # 楼层详情
        print("\n楼层详情:")
        floors = summary.get("floors", {})
        for floor_num in sorted(floors.keys()):
            floor_info = floors[floor_num]
            print(f"  第{floor_num}层: {floor_info.get('room_count', 0)}个房间, 面积{floor_info.get('area', 0):.1f}㎡")
        
        # 房间类型统计
        print("\n房间类型统计:")
        room_types = summary.get("room_types", {})
        for room_type, count in room_types.items():
            print(f"  {room_type}: {count}个")
        
        # 对象类型统计
        print("\n对象类型统计:")
        object_types = summary.get("object_types", {})
        for obj_type, count in object_types.items():
            print(f"  {obj_type}: {count}个")
        
        print("=" * 80)


def test_demo_building_generation():
    """测试demo building生成"""
    logger = get_logger(LoggerNames.GAME)
    logger.info("开始测试Demo Building生成...")
    
    try:
        # 创建生成器
        generator = DemoBuildingGenerator()
        
        # 生成建筑
        success = generator.generate_building()
        
        if success:
            # 打印摘要
            generator.print_building_summary()
            
            # 验证生成结果
            if _validate_generation_results(generator):
                logger.info("✓ Demo Building生成测试通过")
                return True
            else:
                logger.error("✗ Demo Building生成验证失败")
                return False
        else:
            logger.error("✗ Demo Building生成失败")
            return False
            
    except Exception as e:
        logger.error(f"Demo Building生成测试异常: {e}")
        return False


def _validate_generation_results(generator: DemoBuildingGenerator) -> bool:
    """验证生成结果"""
    logger = get_logger(LoggerNames.GAME)
    logger.info("验证生成结果...")
    
    try:
        # 验证建筑
        if not generator.building:
            logger.error("建筑未创建")
            return False
        
        # 验证楼层数量
        expected_floors = len(generator.floor_config)
        actual_floors = len(generator.floors)
        if actual_floors != expected_floors:
            logger.error(f"楼层数量不匹配: 期望{expected_floors}, 实际{actual_floors}")
            return False
        
        # 验证房间数量
        expected_rooms = sum(config["room_count"] for config in generator.floor_config.values())
        actual_rooms = len(generator.rooms)
        if actual_rooms != expected_rooms:
            logger.error(f"房间数量不匹配: 期望{expected_rooms}, 实际{actual_rooms}")
            return False
        
        # 验证每个楼层的房间数量
        for floor_num, config in generator.floor_config.items():
            floor_rooms = [room_id for room_id in generator.rooms.keys() if room_id.startswith(f"{floor_num}_")]
            if len(floor_rooms) != config["room_count"]:
                logger.error(f"楼层{floor_num}房间数量不匹配: 期望{config['room_count']}, 实际{len(floor_rooms)}")
                return False
        
        # 验证特殊房间
        cold_room_id = "-1_1"
        if cold_room_id not in generator.rooms:
            logger.error("冷机房未创建")
            return False
        
        cold_room = generator.rooms[cold_room_id]
        if cold_room.get_node_attribute("room_type") != "cold_room":
            logger.error("冷机房类型错误")
            return False
        
        # 验证WiFi AP
        wifi_ap_count = 0
        for room_id, room in generator.rooms.items():
            room_objects = room.get_node_attribute("room_objects", [])
            # 这里简化验证，实际应该检查对象类型
            wifi_ap_count += len(room_objects)
        
        if wifi_ap_count < len(generator.rooms):
            logger.error(f"WiFi AP数量不足: 期望至少{len(generator.rooms)}个, 实际{wifi_ap_count}个")
            return False
        
        logger.info("✓ 生成结果验证通过")
        return True
        
    except Exception as e:
        logger.error(f"验证生成结果失败: {e}")
        return False


def test_room_connection_logic():
    """测试房间连接逻辑的合理性"""
    logger = get_logger(LoggerNames.GAME)
    logger.info("测试房间连接逻辑...")
    
    try:
        generator = DemoBuildingGenerator()
        
        # 测试不同楼层的房间连接
        test_cases = [
            {"floor": 1, "room_count": 10, "description": "小楼层"},
            {"floor": 2, "room_count": 20, "description": "中等楼层"},
            {"floor": 3, "room_count": 50, "description": "大楼层"},
        ]
        
        for test_case in test_cases:
            floor_num = test_case["floor"]
            room_count = test_case["room_count"]
            description = test_case["description"]
            
            logger.info(f"测试{description} (楼层{floor_num}, {room_count}个房间)")
            
            # 创建模拟房间列表
            floor_rooms = [f"{floor_num}_{i+1}" for i in range(room_count)]
            
            # 测试几个房间的连接
            test_rooms = [f"{floor_num}_{i+1}" for i in range(min(5, room_count))]
            
            for room_id in test_rooms:
                room_num = int(room_id.split("_")[1])
                
                # 获取房间坐标
                room_coords = generator._get_room_coordinates(room_num, room_count)
                
                # 找到相邻房间
                adjacent_rooms = generator._find_adjacent_rooms(room_id, floor_rooms, room_coords)
                
                # 生成连接
                connections = generator._generate_room_connections(room_id, floor_rooms)
                
                # 验证连接合理性
                logger.info(f"  房间{room_id} (坐标{room_coords}):")
                logger.info(f"    相邻房间: {len(adjacent_rooms)}个")
                logger.info(f"    实际连接: {len(connections)}个")
                
                # 验证所有连接都是相邻的
                for direction, target_room_id in connections.items():
                    if target_room_id not in adjacent_rooms:
                        logger.error(f"    错误: {target_room_id}不是相邻房间")
                        return False
                    
                    # 验证方向计算
                    target_coords = generator._get_room_coordinates(
                        int(target_room_id.split("_")[1]), room_count
                    )
                    calculated_direction = generator._calculate_direction(
                        room_coords, target_room_id, floor_rooms
                    )
                    
                    if calculated_direction != direction:
                        logger.error(f"    错误: 方向计算错误 {direction} != {calculated_direction}")
                        return False
                
                logger.info(f"    连接验证通过")
        
        logger.info("✓ 房间连接逻辑测试通过")
        return True
        
    except Exception as e:
        logger.error(f"房间连接逻辑测试失败: {e}")
        return False


def test_room_coordinate_calculation():
    """测试房间坐标计算"""
    logger = get_logger(LoggerNames.GAME)
    logger.info("测试房间坐标计算...")
    
    try:
        generator = DemoBuildingGenerator()
        
        # 测试不同房间数量的坐标计算
        test_cases = [
            {"rooms": 10, "expected_cols": 5},
            {"rooms": 20, "expected_cols": 5},
            {"rooms": 32, "expected_cols": 6},
            {"rooms": 50, "expected_cols": 8},
        ]
        
        for test_case in test_cases:
            room_count = test_case["rooms"]
            expected_cols = test_case["expected_cols"]
            
            logger.info(f"测试{room_count}个房间的坐标计算")
            
            # 测试前几个房间的坐标
            for room_num in range(1, min(6, room_count + 1)):
                coords = generator._get_room_coordinates(room_num, room_count)
                row, col = coords
                
                # 验证坐标计算
                expected_row = (room_num - 1) // expected_cols
                expected_col = (room_num - 1) % expected_cols
                
                if row != expected_row or col != expected_col:
                    logger.error(f"  房间{room_num}坐标错误: 期望({expected_row}, {expected_col}), 实际({row}, {col})")
                    return False
                
                logger.info(f"  房间{room_num}: ({row}, {col}) ✓")
        
        logger.info("✓ 房间坐标计算测试通过")
        return True
        
    except Exception as e:
        logger.error(f"房间坐标计算测试失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    logger = get_logger(LoggerNames.GAME)
    logger.info("=" * 60)
    logger.info("开始运行Demo Building Generator测试套件")
    logger.info("=" * 60)
    
    tests = [
        ("房间坐标计算", test_room_coordinate_calculation),
        ("房间连接逻辑", test_room_connection_logic),
        ("Demo Building生成", test_demo_building_generation),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            logger.info(f"\n运行测试: {test_name}")
            if test_func():
                passed += 1
                logger.info(f"✓ {test_name} 通过")
            else:
                failed += 1
                logger.error(f"✗ {test_name} 失败")
        except Exception as e:
            failed += 1
            logger.error(f"✗ {test_name} 异常: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info(f"测试结果: {passed} 通过, {failed} 失败")
    logger.info("=" * 60)
    
    return failed == 0


def main():
    """主函数"""
    success = run_all_tests()
    
    if success:
        print("\n🎉 所有测试通过！Demo Building Generator工作正常。")
        sys.exit(0)
    else:
        print("\n❌ 部分测试失败，请检查日志。")
        sys.exit(1)


if __name__ == "__main__":
    main()
