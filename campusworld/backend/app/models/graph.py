"""
基于PostgreSQL图数据结构的持久化系统 - 纯图数据设计

参考Evennia存储设计，实现：
- Node作为图节点的基础类型，存储所有对象
- Relationship作为节点间关系的基础类型
- 使用JSONB字段存储属性和元数据
- 通过type和typeclass区分不同的对象类型
"""

from typing import Dict, Any, List, Optional, Type, Union, TYPE_CHECKING
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declared_attr
import json
import inspect
from abc import ABC, abstractmethod

from app.core.database import Base

if TYPE_CHECKING:
    from .graph_manager import GraphManager


# ==================== 基础类型定义 ====================

class BaseNode(ABC):
    """
    节点基础抽象类
    
    定义所有节点的基本接口和行为
    """
    
    @abstractmethod
    def get_uuid(self) -> str:
        """获取节点UUID"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """获取节点名称"""
        pass
    
    @abstractmethod
    def get_type(self) -> str:
        """获取节点类型"""
        pass
    
    @abstractmethod
    def get_typeclass(self) -> str:
        """获取节点类型类"""
        pass
    
    @abstractmethod
    def is_node_active(self) -> bool:
        """检查节点是否活跃"""
        pass


class BaseRelationship(ABC):
    """
    关系基础抽象类
    
    定义所有关系的基本接口和行为
    """
    
    @abstractmethod
    def get_uuid(self) -> str:
        """获取关系UUID"""
        pass
    
    @abstractmethod
    def get_type(self) -> str:
        """获取关系类型"""
        pass
    
    @abstractmethod
    def get_source_id(self) -> int:
        """获取源节点ID"""
        pass
    
    @abstractmethod
    def get_target_id(self) -> int:
        """获取目标节点ID"""
        pass
    
    @abstractmethod
    def is_relationship_active(self) -> bool:
        """检查关系是否活跃"""
        pass


# ==================== 数据库模型定义 ====================

class Node(Base):
    """
    图节点基础类型 - 纯图数据设计
    
    所有持久化对象都存储在此表中，通过type和typeclass区分
    """
    
    __abstract__ = True
    
    # 基础标识
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True)  # 全局唯一标识
    
    # 类型元数据 - 用于区分不同的对象类型
    type = Column(String(100), nullable=False, index=True)  # 对象类型: 'campus', 'user', 'world'
    typeclass = Column(String(500), nullable=False, index=True)  # 完整类路径: 'app.models.campus.Campus'
    classname = Column(String(100), nullable=False, index=True)  # 类名
    module_path = Column(String(300), nullable=False, index=True)  # 模块路径
    
    # 节点属性
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    attributes = Column(JSONB, default=dict)  # 动态属性，使用JSONB提高性能
    
    # 节点状态
    is_active = Column(Boolean, default=True, index=True)
    is_public = Column(Boolean, default=True)
    access_level = Column(String(50), default="normal")
    
    # 位置信息
    location_id = Column(Integer, ForeignKey("nodes.id"), nullable=True)
    home_id = Column(Integer, ForeignKey("nodes.id"), nullable=True)
    
    # 标签系统
    tags = Column(JSONB, default=list)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 图结构索引
    __table_args__ = (
        Index('idx_node_type', 'type'),
        Index('idx_node_typeclass', 'typeclass'),
        Index('idx_node_attributes', 'attributes', postgresql_using='gin'),
        Index('idx_node_tags', 'tags', postgresql_using='gin'),
        Index('idx_node_uuid', 'uuid'),
    )
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id}, uuid='{self.uuid}', name='{self.name}', type='{self.type}')>"
    
    # 实现BaseNode接口
    def get_uuid(self) -> str:
        return self.uuid
    
    def get_name(self) -> str:
        return self.name
    
    def get_type(self) -> str:
        return self.type
    
    def get_typeclass(self) -> str:
        return self.typeclass
    
    def is_node_active(self) -> bool:
        return self.is_active
    
    @classmethod
    def get_type(cls) -> str:
        """获取类的节点类型"""
        return cls.__name__.lower()
    
    @classmethod
    def get_typeclass(cls) -> str:
        """获取类的完整路径"""
        return f"{cls.__module__}.{cls.__name__}"
    
    @classmethod
    def get_module_path(cls) -> str:
        """获取模块路径"""
        return cls.__module__
    
    def get_attribute(self, key: str, default: Any = None) -> Any:
        """获取动态属性"""
        if not self.attributes:
            return default
        return self.attributes.get(key, default)
    
    def set_attribute(self, key: str, value: Any) -> None:
        """设置动态属性"""
        if not self.attributes:
            self.attributes = {}
        self.attributes[key] = value
    
    def has_attribute(self, key: str) -> bool:
        """检查是否有指定属性"""
        return self.attributes and key in self.attributes
    
    def remove_attribute(self, key: str) -> bool:
        """移除属性"""
        if self.attributes and key in self.attributes:
            del self.attributes[key]
            return True
        return False
    
    def get_all_attributes(self) -> Dict[str, Any]:
        """获取所有属性"""
        return self.attributes or {}
    
    def update_attributes(self, attributes: Dict[str, Any]) -> None:
        """批量更新属性"""
        if not self.attributes:
            self.attributes = {}
        self.attributes.update(attributes)
    
    def add_tag(self, tag: str) -> None:
        """添加标签"""
        if not self.tags:
            self.tags = []
        if tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag: str) -> None:
        """移除标签"""
        if self.tags and tag in self.tags:
            self.tags.remove(tag)
    
    def has_tag(self, tag: str) -> bool:
        """检查是否有指定标签"""
        return self.tags and tag in self.tags


class Relationship(Base):
    """
    图关系基础类型
    
    表示节点间的关系，支持属性存储
    """
    
    __tablename__ = "relationships"
    
    # 基础标识
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True)
    
    # 关系类型
    type = Column(String(100), nullable=False, index=True)  # 关系类型
    typeclass = Column(String(500), nullable=False, index=True)  # 关系类的完整路径
    
    # 节点引用
    source_id = Column(Integer, ForeignKey("nodes.id"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("nodes.id"), nullable=False, index=True)
    
    # 关系属性
    attributes = Column(JSONB, default=dict)  # 关系属性
    
    # 关系状态
    is_active = Column(Boolean, default=True, index=True)
    weight = Column(Integer, default=1)  # 关系权重
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 约束和索引
    __table_args__ = (
        UniqueConstraint('source_id', 'target_id', 'type', name='uq_relationship_unique'),
        Index('idx_relationship_type', 'type'),
        Index('idx_relationship_source', 'source_id'),
        Index('idx_relationship_target', 'target_id'),
        Index('idx_relationship_attributes', 'attributes', postgresql_using='gin'),
    )
    
    # 关系定义
    source = relationship("GraphNode", foreign_keys=[source_id], backref="outgoing_relationships")
    target = relationship("GraphNode", foreign_keys=[target_id], backref="incoming_relationships")
    
    def __repr__(self):
        return f"<Relationship(id={self.id}, type='{self.type}', source={self.source_id}->{self.target_id})>"
    
    # 实现BaseRelationship接口
    def get_uuid(self) -> str:
        return self.uuid
    
    def get_type(self) -> str:
        return self.type
    
    def get_source_id(self) -> int:
        return self.source_id
    
    def get_target_id(self) -> int:
        return self.target_id
    
    def is_relationship_active(self) -> bool:
        return self.is_active
    
    def get_attribute(self, key: str, default: Any = None) -> Any:
        """获取关系属性"""
        if not self.attributes:
            return default
        return self.attributes.get(key, default)
    
    def set_attribute(self, key: str, value: Any) -> None:
        """设置关系属性"""
        if not self.attributes:
            self.attributes = {}
        self.attributes[key] = value


# ==================== 具体节点类型 ====================

class GraphNode(Node):
    """
    图节点实现 - 纯图数据设计
    
    继承自Node，提供图结构功能
    所有对象都存储在此表中，通过type和typeclass区分
    """
    
    __tablename__ = "nodes"
    
    # 确保继承Base - 移除有问题的__table_args__继承
    
    # 关系定义
    @declared_attr
    def location(cls):
        """当前位置"""
        return relationship(
            "GraphNode",
            foreign_keys=[cls.location_id],
            remote_side=[cls.id],
            backref="contents"
        )
    
    @declared_attr
    def home(cls):
        """默认位置"""
        return relationship(
            "GraphNode",
            foreign_keys=[cls.home_id],
            remote_side=[cls.id]
        )
    
    def get_related_nodes(self, relationship_type: str = None) -> List['GraphNode']:
        """获取相关节点"""
        if relationship_type:
            return [rel.target for rel in self.outgoing_relationships 
                   if rel.type == relationship_type and rel.is_active]
        return [rel.target for rel in self.outgoing_relationships if rel.is_active]
    
    def create_relationship(self, target: 'GraphNode', rel_type: str, **attributes) -> 'Relationship':
        """创建关系"""
        try:
            from .graph_manager import get_graph_manager
            graph_manager = get_graph_manager()
            return graph_manager.create_relationship(self, target, rel_type, **attributes)
        except Exception as e:
            print(f"创建关系失败: {e}")
            return None


# ==================== 具体关系类型 ====================

# 移除具体关系类型，使用统一的Relationship类
# 关系类型通过type字段和attributes中的特定属性来区分


# 移除具体关系类型，使用统一的Relationship类
# 关系类型通过type字段和attributes中的特定属性来区分


# 移除装饰器，使用GraphSynchronizer进行同步