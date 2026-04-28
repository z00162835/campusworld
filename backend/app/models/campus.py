"""
园区模型
基于JSON配置的灵活属性定义
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import DefaultObject


class Campus(DefaultObject):
    """
    园区模型
    """

    def __init__(self, name: str, config: Dict[str, Any] = None, **kwargs):
        # 设置节点类型
        self._node_type = 'campus'

        default_attrs = {
            "uns": "RES001", # 统一命名空间标识, 格式是：园区代码, 如：RES001, 作为统一命名空间标识
            "campus_type": "research_institute",
            "campus_status": "active",
            "campus_level": "research",
            "campus_code": "RES001",
            "campus_name": "示例研究院园区",
            "campus_name_en": "Example Research Institute Campus",
            "campus_address": "深圳市龙岗区坂田街道",
            "campus_city": "深圳市",
            "campus_province": "广东省",
            "campus_country": "中国",
            "campus_postal_code": "518100",
            "campus_area": 100000,
            "campus_capacity": 1000,
            "campus_president": "Prof. He",
            "campus_established_year": 2019,
            "campus_website": "https://www.campusworld.com",
            "campus_phone": "0755-86791234",
            "campus_email": "info@campusworld.com",
            "campus_description": "专注于前沿科技研究的独立研究院园区",
            "campus_motto": "构建万物互联的智能世界",
            "campus_buildings": [],
            "campus_dtmodels": {}, # 数字孪生模型对象，包括：GIS模型，BIM模型等
            "campus_latitude": 22.586667,
            "campus_longitude": 114.103611,
            "campus_altitude": 0
        }
        default_tags = ['research', 'institute']
        
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
        return f"<Campus(name='{self._node_name}', type='{self._node_type}')>"

    # ==================== 方法 ====================

    def get_campus_summary(self) -> str:
        """获取摘要信息"""
        name = self._node_name
        campus_type = self._node_attributes.get('campus_type', 'university')
        campus_code = self._node_attributes.get('campus_code', '')
        campus_address = self._node_attributes.get('campus_address', '')
        campus_area = self._node_attributes.get('campus_area', 0)
        campus_capacity = self._node_attributes.get('campus_capacity', 0)
        campus_president = self._node_attributes.get('campus_president', '')

        summary = f"""
信息摘要:
  名称: {name}
  类型: {campus_type}
  代码: {campus_code}
  地址: {campus_address}
  面积: {campus_area} 平方米
  容量: {campus_capacity} 人
  负责人: {campus_president}
        """

        return summary.strip()
