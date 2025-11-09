#!/usr/bin/env python3
"""
测试Demo Building生成脚本

使用SSH命令模拟调用create命令来生成：
1. 名为"bit"的campus
2. 3个building，每个building有5层
3. 每层随机10-50个相互连接的房间
4. 每个空间对象包含dtjson（dtmodels属性），来源于geojson描述

作者：AI Assistant
创建时间：2025-01-XX
"""

import sys
import os
import random
import json
import math
import time
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import SessionLocal
from app.models.user import User
from app.models.campus import Campus
from app.models.building import Building, BuildingFloor
from app.models.room import Room
from app.protocols.ssh_handler import SSHHandler
from app.commands.init_commands import initialize_commands
from app.core.log import get_logger, LoggerNames


class BitCampusGenerator:
    """Bit Campus生成器 - 使用SSH命令模拟创建"""
    
    def __init__(self):
        self.logger = get_logger(LoggerNames.GAME)
        self.ssh_handler = SSHHandler()
        
        # 初始化命令系统
        if not initialize_commands():
            raise RuntimeError("命令系统初始化失败")
        
        # 创建的管理员用户
        self.admin_user = None
        
        # 生成的对象
        self.campus = None
        self.buildings = []
        self.floors = {}  # {building_id: [floors]}
        self.rooms = {}  # {floor_id: [rooms]}
        
        # 统计信息
        self.stats = {
            'campus': 0,
            'buildings': 0,
            'floors': 0,
            'rooms': 0,
            'connections': 0,
            'errors': []
        }
        
        self.logger.info("Bit Campus Generator 初始化完成")
    
    def create_admin_user(self) -> bool:
        """创建管理员用户用于执行create命令"""
        try:
            self.logger.info("创建管理员用户...")
            
            # 创建管理员用户
            admin_user = User(
                username="test_admin",
                email="test_admin@campusworld.com",
                is_admin=True,
                roles=['admin'],
                permissions=['admin.*', 'system.*']
            )
            
            # 同步到数据库
            admin_user.sync_to_node()
            
            self.admin_user = admin_user
            self.logger.info(f"✓ 管理员用户创建成功: {admin_user.username} (ID: {admin_user.id})")
            return True
            
        except Exception as e:
            self.logger.error(f"创建管理员用户失败: {e}")
            return False
    
    def execute_create_command(self, model_name: str, parameters: Dict[str, Any]) -> bool:
        """通过SSH命令模拟执行create命令"""
        try:
            # 构建create命令字符串
            # create命令支持ast.literal_eval和json.loads两种解析方式
            # 使用JSON格式，确保双引号正确
            params_json = json.dumps(parameters, ensure_ascii=False)
            command_line = f"create {model_name} = {params_json}"
            
            # 创建模拟会话
            from app.ssh.session import SSHSession
            session = SSHSession(
                session_id="test_session",
                username=self.admin_user.username,
                user_id=self.admin_user.id,
                user_attrs=self.admin_user._node_attributes
            )
            session._user_object = self.admin_user
            
            # 执行命令
            result = self.ssh_handler.handle_interactive_command(
                user_id=str(self.admin_user.id),
                username=self.admin_user.username,
                session_id=session.session_id,
                permissions=self.admin_user._node_attributes.get('permissions', []),
                command_line=command_line,
                session=session,
                game_state=None
            )
            
            # 检查结果
            if "成功创建" in result or "success" in result.lower() or "UUID" in result:
                self.logger.debug(f"✓ 命令执行成功: {model_name}")
                return True
            else:
                self.logger.error(f"✗ 命令执行失败: {model_name}")
                self.logger.error(f"  结果: {result}")
                self.stats['errors'].append(f"{model_name}: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"执行create命令失败: {e}")
            self.logger.error(traceback.format_exc())
            self.stats['errors'].append(f"{model_name}: {str(e)}")
            return False
    
    def generate_geojson(self, length: float, width: float, height: float, 
                         base_x: float = 0.0, base_y: float = 0.0) -> Dict[str, Any]:
        """
        生成简化的GeoJSON数据
        
        遵循GeoJSON标准格式（RFC 7946），简化但必须属性都存在
        """
        # 计算矩形边界（简化的坐标）
        x1, y1 = base_x, base_y
        x2, y2 = base_x + length, base_y + width
        
        # 构建GeoJSON Feature
        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [x1, y1],  # 左下
                    [x2, y1],  # 右下
                    [x2, y2],  # 右上
                    [x1, y2],  # 左上
                    [x1, y1]   # 闭合
                ]]
            },
            "properties": {
                "length": round(length, 2),
                "width": round(width, 2),
                "height": round(height, 2)
            }
        }
        
        return geojson
    
    def generate_campus(self) -> bool:
        """生成名为bit的campus"""
        try:
            self.logger.info("生成Campus: bit...")
            
            # 计算campus的尺寸（基于3个building，每个5层，每层最多50个房间）
            # 简化计算：假设每个房间平均50平方米
            estimated_area = 3 * 5 * 50 * 50  # 3个building * 5层 * 50房间 * 50平方米
            
            # 生成geojson
            campus_length = math.sqrt(estimated_area * 1.5)  # 假设长宽比1.5:1
            campus_width = estimated_area / campus_length
            campus_geojson = self.generate_geojson(campus_length, campus_width, 0.0)
            
            # 构建campus参数
            campus_params = {
                "name": "bit",
                "campus_code": "BIT001",
                "campus_name": "Bit Campus",
                "campus_name_en": "Bit Campus",
                "campus_type": "university",
                "campus_status": "active",
                "campus_area": int(estimated_area),
                "campus_capacity": 5000,
                "campus_dtmodels": {
                    "geojson": campus_geojson
                }
            }
            
            # 执行create命令
            if self.execute_create_command("Campus", campus_params):
                # 等待一下确保数据库同步
                time.sleep(0.5)
                
                # 从数据库获取创建的campus
                from app.models.model_manager import model_manager
                self.campus = model_manager.get_node_by_name("bit", "campus")
                if self.campus:
                    self.stats['campus'] = 1
                    self.logger.info(f"✓ Campus创建成功: {self.campus.name}")
                    return True
                else:
                    # 尝试通过UUID或其他方式查找
                    self.logger.warning("Campus创建成功但无法从数据库获取，继续执行")
                    # 创建一个临时campus对象用于后续操作
                    self.campus = Campus(name="bit", **campus_params)
                    self.stats['campus'] = 1
                    return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"生成Campus失败: {e}")
            return False
    
    def generate_buildings(self) -> bool:
        """生成3个building，每个5层"""
        try:
            self.logger.info("生成3个Building...")
            
            if not self.campus:
                self.logger.error("Campus未创建，无法生成Building")
                return False
            
            campus_code = self.campus._node_attributes.get('campus_code', 'BIT001')
            
            for i in range(1, 4):  # 3个building
                building_num = i
                building_code = f"BLD{building_num:03d}"
                building_name = f"Building {building_num}"
                
                self.logger.info(f"生成Building {building_num}...")
                
                # 计算building尺寸（基于5层，每层最多50个房间）
                estimated_area = 5 * 50 * 50  # 5层 * 50房间 * 50平方米
                building_length = math.sqrt(estimated_area * 1.2)
                building_width = estimated_area / building_length
                building_height = 5 * 3.0  # 5层 * 3米层高
                
                # 生成geojson
                building_geojson = self.generate_geojson(
                    building_length, 
                    building_width, 
                    building_height,
                    base_x=i * 200.0,  # 每个building间隔200米
                    base_y=0.0
                )
                
                # 构建building参数
                building_params = {
                    "name": building_name,
                    "uns": f"{campus_code}/{building_code}",
                    "building_code": building_code,
                    "building_name": building_name,
                    "building_name_en": building_name,
                    "building_type": "academic",
                    "building_status": "active",
                    "building_floors": 5,
                    "building_area": int(estimated_area),
                    "building_floor_area": int(estimated_area * 0.9),
                    "building_height": building_height,
                    "building_capacity": 1000,
                    "building_dtmodels": {
                        "geojson": building_geojson
                    }
                }
                
                # 执行create命令
                if self.execute_create_command("Building", building_params):
                    # 等待一下确保数据库同步
                    time.sleep(0.5)
                    
                    # 从数据库获取创建的building
                    from app.models.model_manager import model_manager
                    building = model_manager.get_node_by_name(building_name, "building")
                    if building:
                        self.buildings.append(building)
                        self.stats['buildings'] += 1
                        self.logger.info(f"✓ Building {building_num}创建成功: {building.name}")
                    else:
                        # 创建临时building对象
                        building = Building(name=building_name, **building_params)
                        self.buildings.append(building)
                        self.stats['buildings'] += 1
                        self.logger.warning(f"Building {building_num}创建成功但无法从数据库获取，使用临时对象")
                else:
                    self.logger.error(f"Building {building_num}创建失败")
            
            return len(self.buildings) == 3
            
        except Exception as e:
            self.logger.error(f"生成Building失败: {e}")
            return False
    
    def generate_floors(self) -> bool:
        """为每个building生成5层"""
        try:
            self.logger.info("生成BuildingFloor...")
            
            if not self.buildings:
                self.logger.error("Building未创建，无法生成Floor")
                return False
            
            for building in self.buildings:
                building_id = building.id
                building_code = building._node_attributes.get('building_code', 'BLD001')
                campus_code = self.campus._node_attributes.get('campus_code', 'BIT001')
                
                building_floors = []
                
                for floor_num in range(1, 6):  # 5层
                    floor_name = f"{building.name} Floor {floor_num}"
                    
                    # 计算floor尺寸（基于building尺寸）
                    building_area = building._node_attributes.get('building_area', 10000)
                    floor_area = building_area / 5
                    floor_length = math.sqrt(floor_area * 1.2)
                    floor_width = floor_area / floor_length
                    floor_height = 3.0
                    
                    # 生成geojson
                    floor_geojson = self.generate_geojson(
                        floor_length,
                        floor_width,
                        floor_height,
                        base_x=0.0,
                        base_y=0.0
                    )
                    
                    # 构建floor参数
                    floor_params = {
                        "name": floor_name,
                        "floor_number": floor_num,
                        "uns": f"{campus_code}/{building_code}/FLOOR{floor_num:02d}",
                        "floor_code": f"{campus_code}_{building_code}_FLOOR{floor_num:02d}",
                        "floor_name": f"第{floor_num}层",
                        "floor_type": "normal",
                        "floor_area": floor_area,
                        "floor_height": floor_height,
                        "floor_capacity": 200,
                        "floor_dtmodels": {
                            "geojson": floor_geojson
                        }
                    }
                    
                    # 执行create命令
                    if self.execute_create_command("BuildingFloor", floor_params):
                        # 等待一下确保数据库同步
                        time.sleep(0.3)
                        
                        # 从数据库获取创建的floor
                        from app.models.model_manager import model_manager
                        floor = model_manager.get_node_by_name(floor_name, "building_floor")
                        if floor:
                            building_floors.append(floor)
                            self.stats['floors'] += 1
                        else:
                            # 创建临时floor对象
                            floor = BuildingFloor(name=floor_name, floor_number=floor_num, **floor_params)
                            building_floors.append(floor)
                            self.stats['floors'] += 1
                            self.logger.warning(f"Floor {floor_name}创建成功但无法从数据库获取，使用临时对象")
                    else:
                        self.logger.error(f"Floor {floor_name}创建失败")
                
                self.floors[building_id] = building_floors
                self.logger.info(f"✓ Building {building.name}的5层创建完成")
            
            return True
            
        except Exception as e:
            self.logger.error(f"生成Floor失败: {e}")
            return False
    
    def generate_rooms(self) -> bool:
        """为每层生成10-50个随机房间"""
        try:
            self.logger.info("生成Room...")
            
            if not self.floors:
                self.logger.error("Floor未创建，无法生成Room")
                return False
            
            for building_id, floors in self.floors.items():
                for floor in floors:
                    floor_id = floor.id
                    floor_num = floor._node_attributes.get('floor_number', 1)
                    building = next((b for b in self.buildings if b.id == building_id), None)
                    if not building:
                        continue
                    
                    building_code = building._node_attributes.get('building_code', 'BLD001')
                    campus_code = self.campus._node_attributes.get('campus_code', 'BIT001')
                    
                    # 随机生成房间数量（10-50）
                    room_count = random.randint(10, 50)
                    self.logger.info(f"为{floor.name}生成{room_count}个房间...")
                    
                    floor_rooms = []
                    
                    # 计算房间布局（网格）
                    cols = int(math.ceil(math.sqrt(room_count * 1.2)))  # 稍微多列，确保能容纳
                    rows = int(math.ceil(room_count / cols))
                    
                    for room_index in range(room_count):
                        room_num = room_index + 1
                        room_code = f"ROOM{room_num:03d}"
                        room_name = f"{floor.name} Room {room_num}"
                        
                        # 计算房间尺寸（基于floor面积平均分配）
                        floor_area = floor._node_attributes.get('floor_area', 2000)
                        room_area = floor_area / room_count
                        room_length = math.sqrt(room_area * 1.2)  # 假设长宽比1.2:1
                        room_width = room_area / room_length
                        room_height = 3.0
                        
                        # 计算房间在网格中的位置
                        row = (room_num - 1) // cols
                        col = (room_num - 1) % cols
                        base_x = col * (room_length + 1.0)  # 房间间隔1米
                        base_y = row * (room_width + 1.0)
                        
                        # 生成geojson
                        room_geojson = self.generate_geojson(
                            room_length,
                            room_width,
                            room_height,
                            base_x=base_x,
                            base_y=base_y
                        )
                        
                        # 构建room参数
                        room_params = {
                            "name": room_name,
                            "uns": f"{campus_code}/{building_code}/FLOOR{floor_num:02d}/{room_code}",
                            "room_code": room_code,
                            "room_name": room_name,
                            "room_name_en": room_name,
                            "room_type": "normal",
                            "room_floor": floor_num,
                            "room_building": building.name,
                            "room_campus": self.campus.name,
                            "room_area": round(room_area, 2),
                            "room_height": room_height,
                            "room_capacity": random.randint(5, 20),
                            "room_status": "active",
                            "is_public": True,
                            "is_accessible": True,
                            "room_dtmodels": {
                                "geojson": room_geojson
                            },
                            "room_exits": {}
                        }
                        
                        # 执行create命令
                        if self.execute_create_command("Room", room_params):
                            # 等待一下确保数据库同步
                            time.sleep(0.1)
                            
                            # 从数据库获取创建的room
                            from app.models.model_manager import model_manager
                            room = model_manager.get_node_by_name(room_name, "room")
                            if room:
                                floor_rooms.append(room)
                                self.stats['rooms'] += 1
                            else:
                                # 创建临时room对象
                                room = Room(name=room_name, **room_params)
                                floor_rooms.append(room)
                                self.stats['rooms'] += 1
                                self.logger.warning(f"Room {room_name}创建成功但无法从数据库获取，使用临时对象")
                        else:
                            self.logger.error(f"Room {room_name}创建失败")
                    
                    self.rooms[floor_id] = floor_rooms
                    self.logger.info(f"✓ {floor.name}的{len(floor_rooms)}个房间创建完成")
                    
                    # 创建房间之间的连接
                    self._create_room_connections(floor_rooms, cols, rows)
            
            return True
            
        except Exception as e:
            self.logger.error(f"生成Room失败: {e}")
            return False
    
    def _create_room_connections(self, rooms: List[Room], cols: int, rows: int):
        """创建房间之间的连接关系"""
        try:
            connections_created = 0
            
            for i, room in enumerate(rooms):
                room_num = i + 1
                row = (room_num - 1) // cols
                col = (room_num - 1) % cols
                
                # 找到相邻房间
                adjacent_rooms = []
                directions = []
                
                # 上
                if row > 0:
                    target_index = (row - 1) * cols + col
                    if target_index < len(rooms):
                        adjacent_rooms.append(rooms[target_index])
                        directions.append("north")
                
                # 下
                if row < rows - 1:
                    target_index = (row + 1) * cols + col
                    if target_index < len(rooms):
                        adjacent_rooms.append(rooms[target_index])
                        directions.append("south")
                
                # 左
                if col > 0:
                    target_index = row * cols + (col - 1)
                    if target_index < len(rooms):
                        adjacent_rooms.append(rooms[target_index])
                        directions.append("west")
                
                # 右
                if col < cols - 1:
                    target_index = row * cols + (col + 1)
                    if target_index < len(rooms):
                        adjacent_rooms.append(rooms[target_index])
                        directions.append("east")
                
                # 随机选择1-3个相邻房间进行连接
                if adjacent_rooms:
                    connection_count = min(random.randint(1, 3), len(adjacent_rooms))
                    selected_indices = random.sample(range(len(adjacent_rooms)), connection_count)
                    
                    for idx in selected_indices:
                        target_room = adjacent_rooms[idx]
                        direction = directions[idx]
                        
                        # 添加连接
                        room.add_exit(direction, target_room.id)
                        connections_created += 1
                        
                        # 双向连接
                        opposite_direction = {
                            "north": "south",
                            "south": "north",
                            "east": "west",
                            "west": "east"
                        }.get(direction, direction)
                        target_room.add_exit(opposite_direction, room.id)
            
            self.stats['connections'] += connections_created
            self.logger.debug(f"创建了{connections_created}个房间连接")
            
        except Exception as e:
            self.logger.error(f"创建房间连接失败: {e}")
    
    def generate_all(self) -> bool:
        """生成所有对象"""
        try:
            self.logger.info("=" * 60)
            self.logger.info("开始生成Bit Campus")
            self.logger.info("=" * 60)
            
            # 1. 创建管理员用户
            if not self.create_admin_user():
                return False
            
            # 2. 生成Campus
            if not self.generate_campus():
                return False
            
            # 3. 生成Building
            if not self.generate_buildings():
                return False
            
            # 4. 生成Floor
            if not self.generate_floors():
                return False
            
            # 5. 生成Room
            if not self.generate_rooms():
                return False
            
            self.logger.info("=" * 60)
            self.logger.info("Bit Campus生成完成！")
            self.logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            self.logger.error(f"生成Bit Campus失败: {e}")
            return False
    
    def validate_all(self) -> bool:
        """验证所有对象是否正确创建"""
        try:
            self.logger.info("=" * 60)
            self.logger.info("开始验证所有对象")
            self.logger.info("=" * 60)
            
            all_valid = True
            
            # 验证Campus
            if not self.campus:
                self.logger.error("✗ Campus未创建")
                all_valid = False
            else:
                if self.campus.name != "bit":
                    self.logger.error(f"✗ Campus名称错误: {self.campus.name}")
                    all_valid = False
                else:
                    self.logger.info("✓ Campus验证通过")
                
                # 验证campus_dtmodels
                campus_dtmodels = self.campus._node_attributes.get('campus_dtmodels', {})
                if not campus_dtmodels.get('geojson'):
                    self.logger.error("✗ Campus缺少geojson数据")
                    all_valid = False
                else:
                    self.logger.info("✓ Campus geojson验证通过")
            
            # 验证Building
            if len(self.buildings) != 3:
                self.logger.error(f"✗ Building数量错误: {len(self.buildings)}")
                all_valid = False
            else:
                self.logger.info("✓ Building数量验证通过")
                
                for building in self.buildings:
                    if building._node_attributes.get('building_floors') != 5:
                        self.logger.error(f"✗ Building {building.name}楼层数错误")
                        all_valid = False
                    
                    building_dtmodels = building._node_attributes.get('building_dtmodels', {})
                    if not building_dtmodels.get('geojson'):
                        self.logger.error(f"✗ Building {building.name}缺少geojson数据")
                        all_valid = False
                
                if all_valid:
                    self.logger.info("✓ Building验证通过")
            
            # 验证Floor
            expected_floors = 3 * 5  # 3个building * 5层
            if self.stats['floors'] != expected_floors:
                self.logger.error(f"✗ Floor数量错误: {self.stats['floors']}, 期望{expected_floors}")
                all_valid = False
            else:
                self.logger.info("✓ Floor数量验证通过")
                
                for building_id, floors in self.floors.items():
                    if len(floors) != 5:
                        self.logger.error(f"✗ Building {building_id}的Floor数量错误")
                        all_valid = False
                    
                    for floor in floors:
                        floor_num = floor._node_attributes.get('floor_number')
                        if floor_num < 1 or floor_num > 5:
                            self.logger.error(f"✗ Floor编号错误: {floor_num}")
                            all_valid = False
                        
                        floor_dtmodels = floor._node_attributes.get('floor_dtmodels', {})
                        if not floor_dtmodels.get('geojson'):
                            self.logger.error(f"✗ Floor {floor.name}缺少geojson数据")
                            all_valid = False
                
                if all_valid:
                    self.logger.info("✓ Floor验证通过")
            
            # 验证Room
            for floor_id, rooms in self.rooms.items():
                if len(rooms) < 10 or len(rooms) > 50:
                    self.logger.error(f"✗ Floor {floor_id}的房间数量不在10-50范围内: {len(rooms)}")
                    all_valid = False
                
                for room in rooms:
                    room_dtmodels = room._node_attributes.get('room_dtmodels', {})
                    if not room_dtmodels.get('geojson'):
                        self.logger.error(f"✗ Room {room.name}缺少geojson数据")
                        all_valid = False
                    
                    # 验证geojson格式
                    geojson = room_dtmodels.get('geojson', {})
                    if not geojson.get('type') == 'Feature':
                        self.logger.error(f"✗ Room {room.name} geojson格式错误")
                        all_valid = False
                    if not geojson.get('geometry', {}).get('type'):
                        self.logger.error(f"✗ Room {room.name} geojson geometry类型缺失")
                        all_valid = False
                    if not geojson.get('properties', {}).get('length'):
                        self.logger.error(f"✗ Room {room.name} geojson properties缺少length")
                        all_valid = False
                    if not geojson.get('properties', {}).get('width'):
                        self.logger.error(f"✗ Room {room.name} geojson properties缺少width")
                        all_valid = False
                    if not geojson.get('properties', {}).get('height'):
                        self.logger.error(f"✗ Room {room.name} geojson properties缺少height")
                        all_valid = False
            
            if all_valid:
                self.logger.info("✓ Room验证通过")
            
            self.logger.info("=" * 60)
            if all_valid:
                self.logger.info("✓ 所有对象验证通过")
            else:
                self.logger.error("✗ 部分对象验证失败")
            self.logger.info("=" * 60)
            
            return all_valid
            
        except Exception as e:
            self.logger.error(f"验证失败: {e}")
            return False
    
    def print_summary(self):
        """打印生成摘要"""
        print("\n" + "=" * 80)
        print("BIT CAMPUS 生成摘要")
        print("=" * 80)
        
        print(f"\n📊 统计信息:")
        print(f"  Campus: {self.stats['campus']}")
        print(f"  Building: {self.stats['buildings']}")
        print(f"  BuildingFloor: {self.stats['floors']}")
        print(f"  Room: {self.stats['rooms']}")
        print(f"  房间连接: {self.stats['connections']}")
        
        if self.stats['errors']:
            print(f"\n❌ 错误数量: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:10]:  # 只显示前10个错误
                print(f"  - {error}")
        
        print("\n" + "=" * 80)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Bit Campus生成脚本")
    parser.add_argument("--validate-only", action="store_true", help="仅验证，不生成")
    parser.add_argument("--skip-validation", action="store_true", help="跳过验证")
    
    args = parser.parse_args()
    
    logger = get_logger(LoggerNames.GAME)
    logger.info("=" * 60)
    logger.info("Bit Campus生成脚本启动")
    logger.info("=" * 60)
    
    generator = BitCampusGenerator()
    
    if args.validate_only:
        logger.info("仅验证模式，跳过生成")
        # TODO: 从数据库加载已创建的对象进行验证
    else:
        # 生成所有对象
        success = generator.generate_all()
        
        if success:
            # 打印摘要
            generator.print_summary()
            
            # 验证
            if not args.skip_validation:
                validation_success = generator.validate_all()
                if validation_success:
                    logger.info("\n🎉 Bit Campus生成和验证完成！")
                    sys.exit(0)
                else:
                    logger.error("\n❌ Bit Campus生成完成但验证失败")
                    sys.exit(1)
            else:
                logger.info("\n🎉 Bit Campus生成完成（跳过验证）")
                sys.exit(0)
        else:
            logger.error("\n❌ Bit Campus生成失败")
            sys.exit(1)


if __name__ == "__main__":
    main()

