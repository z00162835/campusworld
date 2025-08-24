"""
校园模型 - 纯图数据设计

校园对象，继承自DefaultObject
所有数据都存储在Node中，type为'campus'
集成命令系统，支持校园特定命令
"""

from typing import Dict, Any, List, Optional
from .base import DefaultObject


class Campus(DefaultObject):
    """
    校园模型 - 纯图数据设计
    
    继承自DefaultObject，提供校园相关功能
    所有数据都存储在Node中，type为'campus'
    集成命令系统，支持校园管理命令
    """
    
    def __init__(self, name: str, campus_type: str = 'university', **kwargs):
        # 设置校园特定的节点类型
        self._node_type = 'campus'
        
        # 设置校园默认属性
        campus_attrs = {
            'campus_type': campus_type,
            'campus_code': kwargs.get('campus_code', ''),
            'campus_address': kwargs.get('campus_address', ''),
            'campus_area': kwargs.get('campus_area', 0.0),
            'campus_capacity': kwargs.get('campus_capacity', 0),
            'campus_founded': kwargs.get('campus_founded', None),
            'campus_president': kwargs.get('campus_president', ''),
            'campus_website': kwargs.get('campus_website', ''),
            'campus_phone': kwargs.get('campus_phone', ''),
            'campus_email': kwargs.get('campus_email', ''),
            'campus_status': 'active',
            'campus_level': 'university',
            'campus_ranking': kwargs.get('campus_ranking', 0),
            'campus_features': kwargs.get('campus_features', []),
            'campus_departments': kwargs.get('campus_departments', []),
            'campus_facilities': kwargs.get('campus_facilities', []),
            'campus_services': kwargs.get('campus_services', []),
            **kwargs
        }
        
        super().__init__(name=name, **campus_attrs)
    
    def _init_default_cmdset(self):
        """初始化校园默认命令集合"""
        try:
            from app.commands.base import CmdSet
            from app.commands.system.cmdset import SystemCmdSet
            
            # 校园默认包含系统命令
            self._cmdset = SystemCmdSet()
            
            # 这里可以添加校园特定的命令
            # 例如：校园管理、部门管理、设施管理等
            
        except ImportError:
            # 如果命令系统不可用，创建空的命令集合
            self._cmdset = None
    
    # ==================== 校园属性访问器 ====================
    
    @property
    def campus_type(self) -> str:
        """获取校园类型"""
        return self._node_attributes.get('campus_type', 'university')
    
    @campus_type.setter
    def campus_type(self, value: str):
        """设置校园类型"""
        self.set_node_attribute('campus_type', value)
    
    @property
    def campus_code(self) -> str:
        """获取校园代码"""
        return self._node_attributes.get('campus_code', '')
    
    @campus_code.setter
    def campus_code(self, value: str):
        """设置校园代码"""
        self.set_node_attribute('campus_code', value)
    
    @property
    def campus_address(self) -> str:
        """获取校园地址"""
        return self._node_attributes.get('campus_address', '')
    
    @campus_address.setter
    def campus_address(self, value: str):
        """设置校园地址"""
        self.set_node_attribute('campus_address', value)
    
    @property
    def campus_area(self) -> float:
        """获取校园面积"""
        return self._node_attributes.get('campus_area', 0.0)
    
    @campus_area.setter
    def campus_area(self, value: float):
        """设置校园面积"""
        self.set_node_attribute('campus_area', value)
    
    @property
    def campus_capacity(self) -> int:
        """获取校园容量"""
        return self._node_attributes.get('campus_capacity', 0)
    
    @campus_capacity.setter
    def campus_capacity(self, value: int):
        """设置校园容量"""
        self.set_node_attribute('campus_capacity', value)
    
    @property
    def campus_founded(self):
        """获取建校时间"""
        return self._node_attributes.get('campus_founded')
    
    @campus_founded.setter
    def campus_founded(self, value):
        """设置建校时间"""
        self.set_node_attribute('campus_founded', value)
    
    @property
    def campus_president(self) -> str:
        """获取校长"""
        return self._node_attributes.get('campus_president', '')
    
    @campus_president.setter
    def campus_president(self, value: str):
        """设置校长"""
        self.set_node_attribute('campus_president', value)
    
    @property
    def campus_website(self) -> str:
        """获取校园网站"""
        return self._node_attributes.get('campus_website', '')
    
    @campus_website.setter
    def campus_website(self, value: str):
        """设置校园网站"""
        self.set_node_attribute('campus_website', value)
    
    @property
    def campus_phone(self) -> str:
        """获取校园电话"""
        return self._node_attributes.get('campus_phone', '')
    
    @campus_phone.setter
    def campus_phone(self, value: str):
        """设置校园电话"""
        self.set_node_attribute('campus_phone', value)
    
    @property
    def campus_email(self) -> str:
        """获取校园邮箱"""
        return self._node_attributes.get('campus_email', '')
    
    @campus_email.setter
    def campus_email(self, value: str):
        """设置校园邮箱"""
        self.set_node_attribute('campus_email', value)
    
    @property
    def campus_status(self) -> str:
        """获取校园状态"""
        return self._node_attributes.get('campus_status', 'active')
    
    @campus_status.setter
    def campus_status(self, value: str):
        """设置校园状态"""
        self.set_node_attribute('campus_status', value)
    
    @property
    def campus_level(self) -> str:
        """获取校园级别"""
        return self._node_attributes.get('campus_level', 'university')
    
    @campus_level.setter
    def campus_level(self, value: str):
        """设置校园级别"""
        self.set_node_attribute('campus_level', value)
    
    @property
    def campus_ranking(self) -> int:
        """获取校园排名"""
        return self._node_attributes.get('campus_ranking', 0)
    
    @campus_ranking.setter
    def campus_ranking(self, value: int):
        """设置校园排名"""
        self.set_node_attribute('campus_ranking', value)
    
    # ==================== 校园类型检查属性 ====================
    
    @property
    def is_university(self) -> bool:
        """是否为大学"""
        return self.campus_type in ['university', 'college']
    
    @property
    def is_college(self) -> bool:
        """是否为学院"""
        return self.campus_type == 'college'
    
    @property
    def is_school(self) -> bool:
        """是否为学校"""
        return self.campus_type == 'school'
    
    @property
    def is_institute(self) -> bool:
        """是否为研究所"""
        return self.campus_type == 'institute'
    
    @property
    def is_academy(self) -> bool:
        """是否为学院"""
        return self.campus_type == 'academy'
    
    # ==================== 校园管理方法 ====================
    
    def add_department(self, department_name: str, department_type: str = 'academic') -> bool:
        """添加部门"""
        departments = self._node_attributes.get('campus_departments', [])
        
        # 检查部门是否已存在
        for dept in departments:
            if dept.get('name') == department_name:
                return False
        
        # 添加新部门
        new_department = {
            'name': department_name,
            'type': department_type,
            'created_at': self._node_attributes.get('created_at'),
            'status': 'active'
        }
        
        departments.append(new_department)
        self._node_attributes['campus_departments'] = departments
        self._schedule_node_sync()
        
        return True
    
    def remove_department(self, department_name: str) -> bool:
        """移除部门"""
        departments = self._node_attributes.get('campus_departments', [])
        
        for i, dept in enumerate(departments):
            if dept.get('name') == department_name:
                departments.pop(i)
                self._node_attributes['campus_departments'] = departments
                self._schedule_node_sync()
                return True
        
        return False
    
    def get_departments(self, department_type: str = None) -> List[Dict[str, Any]]:
        """获取部门列表"""
        departments = self._node_attributes.get('campus_departments', [])
        
        if department_type:
            return [dept for dept in departments if dept.get('type') == department_type]
        
        return departments
    
    def add_facility(self, facility_name: str, facility_type: str = 'general') -> bool:
        """添加设施"""
        facilities = self._node_attributes.get('campus_facilities', [])
        
        # 检查设施是否已存在
        for facility in facilities:
            if facility.get('name') == facility_name:
                return False
        
        # 添加新设施
        new_facility = {
            'name': facility_name,
            'type': facility_type,
            'created_at': self._node_attributes.get('created_at'),
            'status': 'active'
        }
        
        facilities.append(new_facility)
        self._node_attributes['campus_facilities'] = facilities
        self._schedule_node_sync()
        
        return True
    
    def remove_facility(self, facility_name: str) -> bool:
        """移除设施"""
        facilities = self._node_attributes.get('campus_facilities', [])
        
        for i, facility in enumerate(facilities):
            if facility.get('name') == facility_name:
                facilities.pop(i)
                self._node_attributes['campus_facilities'] = facilities
                self._schedule_node_sync()
                return True
        
        return False
    
    def get_facilities(self, facility_type: str = None) -> List[Dict[str, Any]]:
        """获取设施列表"""
        facilities = self._node_attributes.get('campus_facilities', [])
        
        if facility_type:
            return [facility for facility in facilities if facility.get('type') == facility_type]
        
        return facilities
    
    def add_service(self, service_name: str, service_type: str = 'general') -> bool:
        """添加服务"""
        services = self._node_attributes.get('campus_services', [])
        
        # 检查服务是否已存在
        for service in services:
            if service.get('name') == service_name:
                return False
        
        # 添加新服务
        new_service = {
            'name': service_name,
            'type': service_type,
            'created_at': self._node_attributes.get('created_at'),
            'status': 'active'
        }
        
        services.append(new_service)
        self._node_attributes['campus_services'] = services
        self._schedule_node_sync()
        
        return True
    
    def remove_service(self, service_name: str) -> bool:
        """移除服务"""
        services = self._node_attributes.get('campus_services', [])
        
        for i, service in enumerate(services):
            if service.get('name') == service_name:
                services.pop(i)
                self._node_attributes['campus_services'] = services
                self._schedule_node_sync()
                return True
        
        return False
    
    def get_services(self, service_type: str = None) -> List[Dict[str, Any]]:
        """获取服务列表"""
        services = self._node_attributes.get('campus_services', [])
        
        if service_type:
            return [service for service in services if service.get('type') == service_type]
        
        return services
    
    # ==================== 校园统计方法 ====================
    
    def get_campus_statistics(self) -> Dict[str, Any]:
        """获取校园统计信息"""
        return {
            'name': self.name,
            'type': self.campus_type,
            'code': self.campus_code,
            'address': self.campus_address,
            'area': self.campus_area,
            'capacity': self.campus_capacity,
            'founded': self.campus_founded,
            'president': self.campus_president,
            'website': self.campus_website,
            'phone': self.campus_phone,
            'email': self.campus_email,
            'status': self.campus_status,
            'level': self.campus_level,
            'ranking': self.campus_ranking,
            'department_count': len(self.get_departments()),
            'facility_count': len(self.get_facilities()),
            'service_count': len(self.get_services()),
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def get_campus_summary(self) -> str:
        """获取校园摘要信息"""
        stats = self.get_campus_statistics()
        
        summary = f"""
校园信息摘要:
  名称: {stats['name']}
  类型: {stats['type']}
  代码: {stats['code']}
  地址: {stats['address']}
  面积: {stats['area']} 平方米
  容量: {stats['capacity']} 人
  建校时间: {stats['founded']}
  校长: {stats['president']}
  部门数量: {stats['department_count']}
  设施数量: {stats['facility_count']}
  服务数量: {stats['service_count']}
        """
        
        return summary.strip()
    
    # ==================== 类型信息获取方法 ====================
    
    def get_campus_type_info(self) -> Dict[str, Any]:
        """获取校园类型信息 - 从nodetypes获取"""
        # 使用基类的类型信息获取方法
        type_info = self.get_complete_type_info()
        
        # 添加类型检查结果
        type_info.update({
            'is_university': self.is_university,
            'is_college': self.is_college,
            'is_school': self.is_school,
            'is_institute': self.is_institute,
            'is_academy': self.is_academy,
        })
        
        return type_info