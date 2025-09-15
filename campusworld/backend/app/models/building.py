"""
建筑模型定义 - 纯图数据设计
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime
from enum import Enum

from .base import DefaultObject

class BuildingType(Enum):
    """建筑类型枚举"""
    ACADEMIC = "academic"  # 学术建筑
    ADMINISTRATIVE = "administrative"  # 行政建筑
    RESIDENTIAL = "residential"  # 居住建筑
    RESEARCH = "research"  # 研究建筑
    LIBRARY = "library"  # 图书馆
    SPORTS = "sports"  # 体育建筑
    DINING = "dining"  # 餐饮建筑
    MEDICAL = "medical"  # 医疗建筑
    PARKING = "parking"  # 停车建筑
    UTILITY = "utility"  # 公用设施
    CULTURAL = "cultural"  # 文化建筑
    COMMERCIAL = "commercial"  # 商业建筑
    MIXED_USE = "mixed_use"  # 混合用途


class BuildingStatus(Enum):
    """建筑状态枚举"""
    PLANNING = "planning"  # 规划中
    DESIGN = "design"  # 设计中
    CONSTRUCTION = "construction"  # 建设中
    ACTIVE = "active"  # 使用中
    MAINTENANCE = "maintenance"  # 维护中
    RENOVATION = "renovation"  # 翻新中
    INACTIVE = "inactive"  # 停用
    DEMOLISHED = "demolished"  # 已拆除


class BuildingClass(Enum):
    """建筑等级枚举"""
    CLASS_A = "class_a"  # A级建筑
    CLASS_B = "class_b"  # B级建筑
    CLASS_C = "class_c"  # C级建筑
    HISTORIC = "historic"  # 历史建筑
    LANDMARK = "landmark"  # 地标建筑


class Building(DefaultObject):
    """
    建筑模型 - 纯图数据设计
    """
    
    def __init__(self, name: str, config: Dict[str, Any] = None, **kwargs):
        # 设置建筑特定的节点类型
        self._node_type = 'building'
        
        # 设置建筑默认属性
        default_attrs = {
            # ==================== 基础信息 ====================
            "uns": "RES001/BLD001", # 统一命名空间标识, 格式是：园区代码/建筑代码, 如：RES001/BLD001, 作为统一命名空间标识
            "building_type": "academic",
            "building_status": "active",
            "building_class": "class_b",
            "building_code": "BLD001", # 建筑代码, 如：BLD001
            "building_name": "示例教学楼",
            "building_name_en": "Example Academic Building",
            "building_abbreviation": "EAB",
            
            # ==================== 位置信息 ====================
            "building_address": "深圳市龙岗区坂田街道",
            "building_city": "深圳市",
            "building_province": "广东省",
            "building_country": "中国",
            "building_postal_code": "518100",
            
            # ==================== 地理坐标 ====================
            "building_latitude": 22.586667,
            "building_longitude": 114.103611,
            "building_altitude": 0,
            "building_geojson": {},
            
            # ==================== 物理属性 ====================
            "building_area": 5000,  # 建筑面积(平方米)
            "building_floor_area": 4500,  # 使用面积(平方米)
            "building_land_area": 2000,  # 占地面积(平方米)
            "building_height": 30,  # 建筑高度(米)
            "building_floors": 6,  # 楼层数
            "building_basement_floors": 1,  # 地下层数
            
            # ==================== 容量信息 ====================
            "building_capacity": 500,  # 建筑容量(人)
            "building_rooms": 0,  # 房间数量
            "building_classrooms": 0,  # 教室数量
            "building_offices": 0,  # 办公室数量
            "building_labs": 0,  # 实验室数量
            
            # ==================== 时间信息 ====================
            "building_construction_start": None,
            "building_construction_end": None,
            "building_occupancy_date": None,
            "building_last_renovation": None,
            "building_expected_lifespan": 50,  # 预期寿命(年)
            
            # ==================== 管理信息 ====================
            "building_manager": "",
            "building_manager_phone": "",
            "building_manager_email": "",
            "building_owner": "",
            "building_architect": "",
            "building_contractor": "",
            
            # ==================== 数字孪生 ====================
            "building_dtmodels": {},  # 数字孪生模型信息
            
            # ==================== 环境信息 ====================
            "building_carbon_footprint": 0.0,
            "building_energy_consumption": 0.0,
            "building_water_consumption": 0.0,
            "building_waste_generation": 0.0,
            
            # ==================== 关联信息 ====================
            "building_floors_list": [],  # 楼层ID列表
        }
        
        # 设置默认标签
        default_tags = ['building', 'academic']
        
        # 合并配置
        if config:
            # 合并attributes
            if 'attributes' in config:
                default_attrs.update(config['attributes'])
            # 合并tags
            if 'tags' in config:
                default_tags.extend(config['tags'])

        # 合并kwargs
        default_attrs.update(kwargs)
        
        default_config = {
            'attributes': default_attrs,
            'tags': default_tags,
        }
        
        super().__init__(name=name, **default_config)
    
    def __repr__(self):
        building_type = self._node_attributes.get('building_type', 'academic')
        building_code = self._node_attributes.get('building_code', '')
        return f"<Building(name='{self._node_name}', type='{building_type}', code='{building_code}')>"
    
    # ==================== 建筑属性访问器 ====================

    
    # ==================== 建筑管理方法 ====================
    

    
    # ==================== 建筑信息方法 ====================
    
    def get_building_summary(self) -> str:
        """获取建筑摘要信息"""
        name = self._node_name
        uns = self._node_attributes.get('uns', '')
        building_type = self._node_attributes.get('building_type', '')
        building_code = self._node_attributes.get('building_code', '')
        building_status = self._node_attributes.get('building_status', '')
        building_area = self._node_attributes.get('building_area', 0)
        building_floors = self._node_attributes.get('building_floors', 0)
        building_capacity = self._node_attributes.get('building_capacity', 0)
        building_address = self._node_attributes.get('building_address', '')
        
        summary = f"""
建筑信息摘要:
  名称: {name}
  统一命名空间标识: {uns}
  代码: {building_code}
  类型: {building_type}
  状态: {building_status}
  地址: {building_address}
  建筑面积: {building_area} 平方米
  楼层数: {building_floors} 层
  容量: {building_capacity} 人
  房间数: {self._node_attributes.get('building_rooms', 0)} 间
        """
        
        return summary.strip()
    
    def get_detailed_info(self) -> Dict[str, Any]:
        """获取建筑详细信息"""
        return {
            'id': self.id,
            'uuid': self._node_uuid,
            'name': self._node_name,
            'uns': self._node_attributes.get('uns'),
            'type': self._node_attributes.get('building_type'),
            'status': self._node_attributes.get('building_status'),
            'class': self._node_attributes.get('building_class'),
            'code': self._node_attributes.get('building_code'),
            'address': self._node_attributes.get('building_address'),
            'coordinates': {
                'latitude': self._node_attributes.get('building_latitude'),
                'longitude': self._node_attributes.get('building_longitude'),
                'altitude': self._node_attributes.get('building_altitude')
            },
            'physical_properties': {
                'area': self._node_attributes.get('building_area'),
                'floor_area': self._node_attributes.get('building_floor_area'),
                'land_area': self._node_attributes.get('building_land_area'),
                'height': self._node_attributes.get('building_height'),
                'floors': self._node_attributes.get('building_floors'),
                'basement_floors': self._node_attributes.get('building_basement_floors')
            },
            'capacity': {
                'total_capacity': self._node_attributes.get('building_capacity'),
                'rooms': self._node_attributes.get('building_rooms'),
                'classrooms': self._node_attributes.get('building_classrooms'),
                'offices': self._node_attributes.get('building_offices'),
                'labs': self._node_attributes.get('building_labs')
            },
            'manager': {
                'name': self._node_attributes.get('building_manager'),
                'phone': self._node_attributes.get('building_manager_phone'),
                'email': self._node_attributes.get('building_manager_email')
            },
            'created_at': self._node_created_at.isoformat() if self._node_created_at else None,
            'updated_at': self._node_updated_at.isoformat() if self._node_updated_at else None
        }

class BuildingFloor(DefaultObject):
    """
    建筑楼层模型
    
    继承自DefaultObject，提供楼层相关功能
    所有数据都存储在Node中，type为'building_floor'
    支持通过config配置生成
    """
    
    def __init__(self, name: str, floor_number: int, config: Dict[str, Any] = None, **kwargs):
        # 设置楼层特定的节点类型
        self._node_type = 'building_floor'
        
        # 设置楼层默认属性
        default_attrs = {
            'uns': 'RES001/BLD001/FLOOR01', # 统一命名空间标识, 格式是：园区代码/建筑代码/楼层代码, 如：RES001/BLD001/FLOOR01, 作为统一命名空间标识
            'floor_number': floor_number,
            'floor_name': f'第{floor_number}层',
            'floor_code': 'campuscode_bldcode_floorcode', # 园区代码_建筑代码_楼层代码, 如：RES001_BLD001_FLOOR01, 作为索引标识
            'floor_type': 'normal',  # normal, basement, mezzanine, roof
            'floor_area': 0.0,
            'floor_height': 3.0,
            'floor_capacity': 0,
            'floor_rooms': 0,
            'floor_rooms_list': [],
            'floor_dtmodels': {}, # 数字孪生模型信息
        }
        
        # 设置默认标签
        default_tags = ['building_floor', f'floor_{floor_number}']
        
        # 合并配置
        if config:
            if 'attributes' in config:
                default_attrs.update(config['attributes'])
            if 'tags' in config:
                default_tags.extend(config['tags'])
            for key, value in config.items():
                if key not in ['attributes', 'tags']:
                    default_attrs[key] = value
        
        # 合并kwargs
        default_attrs.update(kwargs)
        
        # 根据配置更新标签
        if default_attrs.get('floor_type') != 'normal':
            default_tags.append(default_attrs['floor_type'])
        
        default_config = {
            'attributes': default_attrs,
            'tags': default_tags,
        }
        
        super().__init__(name=name, **default_config)
    
    def __repr__(self):
        floor_number = self._node_attributes.get('floor_number', 0)
        return f"<BuildingFloor(name='{self._node_name}', floor={floor_number})>"
    
    def get_floor_info(self) -> Dict[str, Any]:
        """获取楼层信息"""
        return {
            'id': self.id,
            'uuid': self._node_uuid,
            'name': self._node_name,
            'uns': self._node_attributes.get('uns'),
            'floor_number': self._node_attributes.get('floor_number'),
            'floor_type': self._node_attributes.get('floor_type'),
            'area': self._node_attributes.get('floor_area'),
            'height': self._node_attributes.get('floor_height'),
            'capacity': self._node_attributes.get('floor_capacity'),
            'rooms': self._node_attributes.get('floor_rooms'),
        }
