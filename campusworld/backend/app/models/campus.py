"""
校园模型 - 纯图数据设计（优化版）

基于JSON配置的灵活属性定义
移除硬编码属性，通过工具类进行统一管理
优化时间处理，移除类型检查方法
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import DefaultObject


class Campus(DefaultObject):
    """
    校园模型 - 纯图数据设计（优化版）
    
    继承自DefaultObject，提供校园相关功能
    所有数据都存储在Node中，type为'campus'
    属性基于传入的JSON配置进行定义，不进行硬编码
    """
    
    def __init__(self, name: str, config: Dict[str, Any] = None, **kwargs):
        # 设置校园特定的节点类型
        self._node_type = 'campus'
        
        # 合并配置和kwargs
        merged_config = {}
        if config:
            merged_config.update(config)
        merged_config.update(kwargs)
        
        # 设置默认属性（仅包含必要的系统属性）
        # 时间字段使用系统生成的时间，不使用输入的时间
        current_time = datetime.now().isoformat()
        default_attrs = {
            'campus_type': merged_config.get('campus_type', 'university'),
            'campus_status': 'active',
            'campus_level': 'university',
            'created_at': current_time,  # 使用系统时间
            'updated_at': current_time,  # 使用系统时间
        }
        
        # 将配置中的所有属性添加到节点属性中
        # 但排除时间相关字段，使用系统生成的时间
        campus_attrs = {**default_attrs}
        for key, value in merged_config.items():
            if key not in ['created_at', 'updated_at']:  # 排除时间字段
                campus_attrs[key] = value
        
        super().__init__(name=name, **campus_attrs)
    
    def _init_default_cmdset(self):
        """初始化校园默认命令集合"""
        try:
            from app.commands.base import CmdSet
            from app.commands.system.cmdset import SystemCmdSet
            
            # 校园默认包含系统命令
            self._cmdset = SystemCmdSet()
            
        except ImportError:
            # 如果命令系统不可用，创建空的命令集合
            self._cmdset = None
    
    def __repr__(self):
        return f"<Campus(name='{self._node_name}', type='{self._node_type}')>"
    
    # ==================== 校园业务方法 ====================
    
    def get_campus_summary(self) -> str:
        """获取校园摘要信息"""
        name = self._node_name
        campus_type = self._node_attributes.get('campus_type', 'university')
        campus_code = self._node_attributes.get('campus_code', '')
        campus_address = self._node_attributes.get('campus_address', '')
        campus_area = self._node_attributes.get('campus_area', 0)
        campus_capacity = self._node_attributes.get('campus_capacity', 0)
        campus_president = self._node_attributes.get('campus_president', '')
        
        summary = f"""
校园信息摘要:
  名称: {name}
  类型: {campus_type}
  代码: {campus_code}
  地址: {campus_address}
  面积: {campus_area} 平方米
  容量: {campus_capacity} 人
  校长: {campus_president}
        """
        
        return summary.strip()
    
    def update_timestamp(self):
        """更新对象时间戳"""
        current_time = datetime.now().isoformat()
        self.set_node_attribute('updated_at', current_time)