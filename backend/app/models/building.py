"""
建筑模型定义 - 纯图数据设计
"""
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime
from enum import Enum
from .base import DefaultObject

class BuildingType(Enum):
    """建筑类型枚举"""
    ACADEMIC = 'academic'
    ADMINISTRATIVE = 'administrative'
    RESIDENTIAL = 'residential'
    RESEARCH = 'research'
    LIBRARY = 'library'
    SPORTS = 'sports'
    DINING = 'dining'
    MEDICAL = 'medical'
    PARKING = 'parking'
    UTILITY = 'utility'
    CULTURAL = 'cultural'
    COMMERCIAL = 'commercial'
    MIXED_USE = 'mixed_use'

class BuildingStatus(Enum):
    """建筑状态枚举"""
    PLANNING = 'planning'
    DESIGN = 'design'
    CONSTRUCTION = 'construction'
    ACTIVE = 'active'
    MAINTENANCE = 'maintenance'
    RENOVATION = 'renovation'
    INACTIVE = 'inactive'
    DEMOLISHED = 'demolished'

class BuildingClass(Enum):
    """建筑等级枚举"""
    CLASS_A = 'class_a'
    CLASS_B = 'class_b'
    CLASS_C = 'class_c'
    HISTORIC = 'historic'
    LANDMARK = 'landmark'

class Building(DefaultObject):
    """
    建筑模型 - 纯图数据设计
    """

    def __init__(self, name: str, config: Dict[str, Any]=None, **kwargs):
        self._node_type = 'building'
        default_attrs = {'uns': 'RES001/BLD001', 'building_type': 'academic', 'building_status': 'active', 'building_class': 'class_b', 'building_code': 'BLD001', 'building_name': '示例教学楼', 'building_name_en': 'Example Academic Building', 'building_abbreviation': 'EAB', 'building_description': '', 'building_tagline': '', 'building_address': '深圳市龙岗区坂田街道', 'building_city': '深圳市', 'building_province': '广东省', 'building_country': '中国', 'building_postal_code': '518100', 'building_latitude': 22.586667, 'building_longitude': 114.103611, 'building_altitude': 0, 'building_dtmodels': {}, 'building_area': 5000, 'building_floor_area': 4500, 'building_land_area': 2000, 'building_height': 30, 'building_floors': 6, 'building_basement_floors': 1, 'building_capacity': 500, 'building_rooms': 0, 'building_classrooms': 0, 'building_offices': 0, 'building_labs': 0, 'building_construction_start': None, 'building_construction_end': None, 'building_occupancy_date': None, 'building_last_renovation': None, 'building_expected_lifespan': 50, 'building_manager': '', 'building_manager_phone': '', 'building_manager_email': '', 'building_owner': '', 'building_architect': '', 'building_contractor': '', 'building_dtmodels': {}, 'building_carbon_footprint': 0.0, 'building_energy_consumption': 0.0, 'building_water_consumption': 0.0, 'building_waste_generation': 0.0, 'building_floors_list': []}
        default_tags = ['building', 'academic']
        if config:
            if 'attributes' in config:
                default_attrs.update(config['attributes'])
            if 'tags' in config:
                default_tags.extend(config['tags'])
        default_attrs.update(kwargs)
        default_config = {'attributes': default_attrs, 'tags': default_tags}
        super().__init__(name=name, **default_config)

    def __repr__(self):
        building_type = self._node_attributes.get('building_type', 'academic')
        building_code = self._node_attributes.get('building_code', '')
        return f"<Building(name='{self._node_name}', type='{building_type}', code='{building_code}')>"

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
        summary = f"\n建筑信息摘要:\n  名称: {name}\n  统一命名空间标识: {uns}\n  代码: {building_code}\n  类型: {building_type}\n  状态: {building_status}\n  地址: {building_address}\n  建筑面积: {building_area} 平方米\n  楼层数: {building_floors} 层\n  容量: {building_capacity} 人\n  房间数: {self._node_attributes.get('building_rooms', 0)} 间\n        "
        return summary.strip()

    def get_detailed_info(self) -> Dict[str, Any]:
        """获取建筑详细信息"""
        return {'id': self.id, 'uuid': self._node_uuid, 'name': self._node_name, 'uns': self._node_attributes.get('uns'), 'type': self._node_attributes.get('building_type'), 'status': self._node_attributes.get('building_status'), 'class': self._node_attributes.get('building_class'), 'code': self._node_attributes.get('building_code'), 'address': self._node_attributes.get('building_address'), 'coordinates': {'latitude': self._node_attributes.get('building_latitude'), 'longitude': self._node_attributes.get('building_longitude'), 'altitude': self._node_attributes.get('building_altitude')}, 'physical_properties': {'area': self._node_attributes.get('building_area'), 'floor_area': self._node_attributes.get('building_floor_area'), 'land_area': self._node_attributes.get('building_land_area'), 'height': self._node_attributes.get('building_height'), 'floors': self._node_attributes.get('building_floors'), 'basement_floors': self._node_attributes.get('building_basement_floors')}, 'capacity': {'total_capacity': self._node_attributes.get('building_capacity'), 'rooms': self._node_attributes.get('building_rooms'), 'classrooms': self._node_attributes.get('building_classrooms'), 'offices': self._node_attributes.get('building_offices'), 'labs': self._node_attributes.get('building_labs')}, 'manager': {'name': self._node_attributes.get('building_manager'), 'phone': self._node_attributes.get('building_manager_phone'), 'email': self._node_attributes.get('building_manager_email')}, 'created_at': self._node_created_at.isoformat() if self._node_created_at else None, 'updated_at': self._node_updated_at.isoformat() if self._node_updated_at else None}

class BuildingFloor(DefaultObject):
    """
    建筑楼层模型
    
    继承自DefaultObject，提供楼层相关功能
    所有数据都存储在Node中，type为'building_floor'
    支持通过config配置生成
    """

    def __init__(self, name: str, floor_number: int, config: Dict[str, Any]=None, **kwargs):
        self._node_type = 'building_floor'
        default_attrs = {'uns': 'RES001/BLD001/FLOOR01', 'floor_number': floor_number, 'floor_name': f'第{floor_number}层', 'floor_code': 'campuscode_bldcode_floorcode', 'floor_type': 'normal', 'floor_area': 0.0, 'floor_height': 3.0, 'floor_capacity': 0, 'floor_rooms': 0, 'floor_rooms_list': [], 'floor_dtmodels': {}, 'floor_description': '', 'floor_short_description': ''}
        default_tags = ['building_floor', f'floor_{floor_number}']
        if config:
            if 'attributes' in config:
                default_attrs.update(config['attributes'])
            if 'tags' in config:
                default_tags.extend(config['tags'])
            for (key, value) in config.items():
                if key not in ['attributes', 'tags']:
                    default_attrs[key] = value
        default_attrs.update(kwargs)
        if default_attrs.get('floor_type') != 'normal':
            default_tags.append(default_attrs['floor_type'])
        default_config = {'attributes': default_attrs, 'tags': default_tags}
        super().__init__(name=name, **default_config)

    def __repr__(self):
        floor_number = self._node_attributes.get('floor_number', 0)
        return f"<BuildingFloor(name='{self._node_name}', floor={floor_number})>"

    def get_floor_info(self) -> Dict[str, Any]:
        """获取楼层信息"""
        return {'id': self.id, 'uuid': self._node_uuid, 'name': self._node_name, 'uns': self._node_attributes.get('uns'), 'floor_number': self._node_attributes.get('floor_number'), 'floor_type': self._node_attributes.get('floor_type'), 'area': self._node_attributes.get('floor_area'), 'height': self._node_attributes.get('floor_height'), 'capacity': self._node_attributes.get('floor_capacity'), 'rooms': self._node_attributes.get('floor_rooms')}
