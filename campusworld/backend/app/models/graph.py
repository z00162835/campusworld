"""
基于PostgreSQL图数据结构的持久化系统 - 纯图数据设计

参考Evennia存储设计，实现：
- Node作为图节点的基础类型，存储所有对象
- Relationship作为节点间关系的基础类型
- 使用JSONB字段存储属性和元数据
- 通过type和typeclass区分不同的对象类型
"""

import uuid as uuidlib
from typing import Dict, Any, List, Optional, Type, Union, TYPE_CHECKING
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Index, UniqueConstraint, or_, and_, SmallInteger
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, declarative_base, Session
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
import json
import inspect
from abc import ABC, abstractmethod

from geoalchemy2 import Geometry
from pgvector.sqlalchemy import Vector

from app.core.database import Base

# ==================== 基础类型定义 ====================

class BaseNode:
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


class BaseRelationship:
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

class Node(Base, BaseNode):
    """
    图节点基础类型 - 纯图数据设计
    
    所有持久化对象都存储在此表中，通过type和typeclass区分
    """
    
    __tablename__ = "nodes"
    
    # 基础标识 - 修复类型匹配
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True, default=uuidlib.uuid4)
    
    # 类型元数据
    type_id = Column(Integer, ForeignKey("node_types.id"), nullable=False)
    type_code = Column(String(128), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # 节点状态
    is_active = Column(Boolean, default=True, index=True)
    is_public = Column(Boolean, default=True)
    access_level = Column(String(50), default="normal")
    
    # 位置信息（图内引用 + PostGIS + GeoJSON 互换）
    location_id = Column(Integer, ForeignKey("nodes.id"), nullable=True)
    home_id = Column(Integer, ForeignKey("nodes.id"), nullable=True)
    location_geom = Column(Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True)
    home_geom = Column(Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True)
    geom_geojson = Column(JSONB, nullable=True)

    # 向量与时序引用（可选）
    semantic_embedding = Column(Vector(1536), nullable=True)
    structure_embedding = Column(Vector(256), nullable=True)
    ts_data_ref_id = Column(UUID(as_uuid=True), nullable=True, unique=True, index=True)

    # 节点属性
    attributes = Column(JSONB, default=dict)
    tags = Column(JSONB, default=list)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系映射
    location = relationship(
        "Node",
        foreign_keys=[location_id],
        remote_side=[id],
        backref="located_objects",
        overlaps="contents"
    )
    
    home = relationship(
        "Node",
        foreign_keys=[home_id],
        remote_side=[id],
        backref="home_objects"
    )
    
    # 添加contents关系作为location的反向关系
    @property
    def contents(self):
        """获取当前位置的内容"""
        return self.located_objects
    
    # 图关系映射
    source_relationships = relationship(
        "Relationship",
        foreign_keys="Relationship.source_id",
        back_populates="source_node",
        lazy="dynamic"
    )
    
    target_relationships = relationship(
        "Relationship",
        foreign_keys="Relationship.target_id", 
        back_populates="target_node",
        lazy="dynamic"
    )
    
    # 图结构方法
    def get_related_nodes(self, relationship_type: str = None):
        """获取相关节点"""
        if relationship_type:
            return [rel.target_node for rel in self.source_relationships 
                   if rel.type_code == relationship_type and rel.is_active]
        return [rel.target_node for rel in self.source_relationships if rel.is_active]
    
    # 实现BaseNode接口
    def get_uuid(self) -> str:
        return str(self.uuid) if self.uuid is not None else ""

    def get_name(self) -> str:
        return self.name
    
    def get_type(self) -> str:
        return self.type_code
    
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
    
    def get_tag(self, tag: str) -> bool:
        """检查是否包含指定标签"""
        if not self.tags:
            return False
        return tag in self.tags
    
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
    
    # ORM查询方法
    @classmethod
    def get_by_uuid(cls, session: Session, uid: Union[str, uuidlib.UUID]) -> Optional["Node"]:
        """根据UUID获取节点"""
        try:
            u = uuidlib.UUID(str(uid)) if uid is not None else None
        except (ValueError, TypeError):
            return None
        if u is None:
            return None
        return session.query(cls).filter(cls.uuid == u).first()
    
    @classmethod
    def get_by_name(cls, session: Session, name: str) -> Optional['Node']:
        """根据名称获取节点"""
        return session.query(cls).filter(cls.name == name).first()
    
    @classmethod
    def get_by_type(cls, session: Session, type_code: str) -> List['Node']:
        """根据类型获取节点列表"""
        return session.query(cls).filter(cls.type_code == type_code).all()
    
    @classmethod
    def get_active_nodes(cls, session: Session, type_code: str = None) -> List['Node']:
        """获取活跃节点"""
        query = session.query(cls).filter(cls.is_active == True)
        if type_code:
            query = query.filter(cls.type_code == type_code)
        return query.all()
    
    @classmethod
    def search_by_attribute(cls, session: Session, key: str, value: Any, type_code: str = None) -> List['Node']:
        """根据属性搜索节点"""
        query = session.query(cls).filter(cls.attributes.contains({key: value}))
        if type_code:
            query = query.filter(cls.type_code == type_code)
        return query.all()
    
    @classmethod
    def search_by_tag(cls, session: Session, tag: str, type_code: str = None) -> List['Node']:
        """根据标签搜索节点"""
        query = session.query(cls).filter(cls.tags.contains([tag]))
        if type_code:
            query = query.filter(cls.type_code == type_code)
        return query.all()

    @classmethod
    def get_paginated(
        cls,
        session: Session,
        page: int = 1,
        page_size: int = 20,
        type_code: str = None,
        is_active: bool = True,
        **filters
    ) -> Dict[str, Any]:
        """
        分页获取节点

        Args:
            session: 数据库会话
            page: 页码（从1开始）
            page_size: 每页数量
            type_code: 节点类型过滤
            is_active: 是否只获取活跃节点
            **filters: 其他过滤条件

        Returns:
            包含items、total、page、page_size、total_pages的字典
        """
        query = session.query(cls)

        # 应用过滤条件
        if is_active is not None:
            query = query.filter(cls.is_active == is_active)

        if type_code:
            query = query.filter(cls.type_code == type_code)

        for key, value in filters.items():
            if hasattr(cls, key):
                query = query.filter(getattr(cls, key) == value)

        # 获取总数
        total = query.count()

        # 计算分页
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        offset = (page - 1) * page_size

        # 获取分页数据
        items = query.order_by(cls.created_at.desc()).offset(offset).limit(page_size).all()

        return {
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages
        }

    @classmethod
    def get_related_nodes(cls, session: Session, node_id: int, relationship_type: str = None) -> List['Node']:
        """
        获取相关节点 - 使用UNION优化索引利用率

        将双向查询拆分为两个独立查询，利用索引避免OR条件导致的索引失效
        """
        # 查询作为source的相关节点
        source_query = session.query(cls).join(
            Relationship,
            and_(
                Relationship.source_id == node_id,
                Relationship.target_id == cls.id
            )
        )

        # 查询作为target的相关节点
        target_query = session.query(cls).join(
            Relationship,
            and_(
                Relationship.target_id == node_id,
                Relationship.source_id == cls.id
            )
        )

        # 应用关系类型过滤
        if relationship_type:
            source_query = source_query.filter(Relationship.type_code == relationship_type)
            target_query = target_query.filter(Relationship.type_code == relationship_type)

        # 使用UNION合并结果
        return source_query.union(target_query).all()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'uuid': str(self.uuid) if self.uuid is not None else None,
            'type_code': self.type_code,
            'name': self.name,
            'description': self.description,
            'is_active': self.is_active,
            'is_public': self.is_public,
            'access_level': self.access_level,
            'location_id': self.location_id,
            'home_id': self.home_id,
            'geom_geojson': self.geom_geojson,
            'ts_data_ref_id': str(self.ts_data_ref_id) if self.ts_data_ref_id is not None else None,
            'attributes': self.attributes,
            'tags': self.tags,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Relationship(Base, BaseRelationship):
    """
    图关系基础类型
    
    表示节点间的关系，支持属性存储
    """
    
    __tablename__ = "relationships"
    
    # 基础标识
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True, default=uuidlib.uuid4)

    # 关系类型
    type_id = Column(Integer, ForeignKey("relationship_types.id"), nullable=False)
    type_code = Column(String(128), nullable=False, index=True)

    # 节点引用（内部整数 id，与图遍历一致）
    source_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True)

    # 关系属性与本体角色
    source_role = Column(String(128), nullable=True)
    target_role = Column(String(128), nullable=True)
    attributes = Column(JSONB, default=dict)
    tags = Column(JSONB, default=list)

    # 关系状态
    is_active = Column(Boolean, default=True, index=True)
    weight = Column(Integer, default=1)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系定义 - 确保back_populates正确
    source_node = relationship(
        "Node", 
        foreign_keys=[source_id], 
        back_populates="source_relationships"
    )
    target_node = relationship(
        "Node", 
        foreign_keys=[target_id], 
        back_populates="target_relationships"
    )
    
    # 部分唯一索引 (is_active) 在数据库侧定义；此处仅声明查询索引
    __table_args__ = (
        Index('idx_relationship_type', 'type_code'),
        Index('idx_relationship_source', 'source_id'),
        Index('idx_relationship_target', 'target_id'),
        Index('idx_relationship_attributes', 'attributes', postgresql_using='gin'),
        Index('idx_relationship_tags', 'tags', postgresql_using='gin'),
    )
    
    def __repr__(self):
        return f"<Relationship(id={self.id}, type='{self.type_code}', source={self.source_id}->{self.target_id})>"
    
    # 实现BaseRelationship接口
    def get_uuid(self) -> str:
        return str(self.uuid) if self.uuid is not None else ""

    def get_type(self) -> str:
        return self.type_code
    
    def get_source_id(self) -> int:
        return self.source_id
    
    def get_target_id(self) -> int:
        return self.target_id
    
    def get_weight(self) -> int:
        return self.weight
    
    def get_attributes(self) -> Dict[str, Any]:
        return self.attributes or {}
    
    def set_attribute(self, key: str, value: Any) -> None:
        """设置关系属性"""
        if not self.attributes:
            self.attributes = {}
        self.attributes[key] = value
    
    def get_attribute(self, key: str, default: Any = None) -> Any:
        """获取关系属性"""
        if not self.attributes:
            return default
        return self.attributes.get(key, default)
    
    def is_relationship_active(self) -> bool:
        """检查关系是否活跃"""
        return self.is_active
    
    # ORM查询方法
    @classmethod
    def get_by_uuid(cls, session: Session, uid: Union[str, uuidlib.UUID]) -> Optional["Relationship"]:
        """根据UUID获取关系"""
        try:
            u = uuidlib.UUID(str(uid)) if uid is not None else None
        except (ValueError, TypeError):
            return None
        if u is None:
            return None
        return session.query(cls).filter(cls.uuid == u).first()
    
    @classmethod
    def get_by_type(cls, session: Session, type_code: str) -> List['Relationship']:
        """根据类型获取关系列表"""
        return session.query(cls).filter(cls.type_code == type_code).all()
    
    @classmethod
    def get_by_source(cls, session: Session, source_id: int, type_code: str = None) -> List['Relationship']:
        """根据源节点获取关系"""
        query = session.query(cls).filter(cls.source_id == source_id)
        if type_code:
            query = query.filter(cls.type_code == type_code)
        return query.all()
    
    @classmethod
    def get_by_target(cls, session: Session, target_id: int, type_code: str = None) -> List['Relationship']:
        """根据目标节点获取关系"""
        query = session.query(cls).filter(cls.target_id == target_id)
        if type_code:
            query = query.filter(cls.type_code == type_code)
        return query.all()
    
    @classmethod
    def get_between_nodes(cls, session: Session, source_id: int, target_id: int, type_code: str = None) -> List['Relationship']:
        """获取两个节点之间的关系"""
        query = session.query(cls).filter(
            or_(
                and_(cls.source_id == source_id, cls.target_id == target_id),
                and_(cls.source_id == target_id, cls.target_id == source_id)
            )
        )
        if type_code:
            query = query.filter(cls.type_code == type_code)
        return query.all()
    
    @classmethod
    def get_active_relationships(cls, session: Session, type_code: str = None) -> List['Relationship']:
        """获取活跃关系"""
        query = session.query(cls).filter(cls.is_active == True)
        if type_code:
            query = query.filter(cls.type_code == type_code)
        return query.all()
    
    @classmethod
    def search_by_attribute(cls, session: Session, key: str, value: Any, type_code: str = None) -> List['Relationship']:
        """根据属性搜索关系"""
        query = session.query(cls).filter(cls.attributes.contains({key: value}))
        if type_code:
            query = query.filter(cls.type_code == type_code)
        return query.all()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'uuid': str(self.uuid) if self.uuid is not None else None,
            'type_code': self.type_code,
            'source_id': self.source_id,
            'target_id': self.target_id,
            'source_role': self.source_role,
            'target_role': self.target_role,
            'is_active': self.is_active,
            'weight': self.weight,
            'attributes': self.attributes,
            'tags': self.tags,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


# ==================== 节点类型和关系类型模型 ====================

class NodeType(Base):
    """节点类型定义表（层级 + 本体默认 + 推理约束 + 配置 UI）"""

    __tablename__ = "node_types"

    id = Column(Integer, primary_key=True)
    type_code = Column(String(128), unique=True, nullable=False)
    parent_type_code = Column(String(128), ForeignKey("node_types.type_code", ondelete="RESTRICT"), nullable=True)
    type_name = Column(String(255), nullable=False)
    typeclass = Column(String(500), nullable=False)
    status = Column(SmallInteger, nullable=False, default=0)
    classname = Column(String(100), nullable=False)
    module_path = Column(String(300), nullable=False)
    description = Column(Text)
    schema_definition = Column(JSONB, nullable=False, default=dict)
    schema_default = Column(JSONB, nullable=False, default=dict)
    inferred_rules = Column(JSONB, nullable=False, default=dict)
    tags = Column(JSONB, nullable=False, default=list)
    ui_config = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    nodes = relationship("Node", backref="node_type_info")

    __table_args__ = (
        Index("idx_node_type_code", "type_code"),
        Index("idx_node_type_parent", "parent_type_code"),
        Index("idx_node_type_status", "status"),
        Index("idx_node_type_schema", "schema_definition", postgresql_using="gin"),
        Index("idx_node_type_schema_default", "schema_default", postgresql_using="gin"),
        Index("idx_node_type_inferred", "inferred_rules", postgresql_using="gin"),
        Index("idx_node_type_ui", "ui_config", postgresql_using="gin"),
    )

    @hybrid_property
    def is_active(self) -> bool:
        return self.status == 0

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.status = 0 if value else 1

    @is_active.expression
    def is_active(cls):
        return cls.status == 0

    def __repr__(self):
        return f"<NodeType(id={self.id}, type_code='{self.type_code}', type_name='{self.type_name}')>"

    @classmethod
    def get_by_type_code(cls, session: Session, type_code: str) -> Optional["NodeType"]:
        return session.query(cls).filter(cls.type_code == type_code).first()

    @classmethod
    def get_active_types(cls, session: Session) -> List["NodeType"]:
        return session.query(cls).filter(cls.status == 0).all()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type_code": self.type_code,
            "parent_type_code": self.parent_type_code,
            "type_name": self.type_name,
            "typeclass": self.typeclass,
            "status": self.status,
            "classname": self.classname,
            "module_path": self.module_path,
            "description": self.description,
            "schema_definition": self.schema_definition,
            "schema_default": self.schema_default,
            "inferred_rules": self.inferred_rules,
            "tags": self.tags,
            "ui_config": self.ui_config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class RelationshipType(Base):
    """关系类型定义表"""

    __tablename__ = "relationship_types"

    id = Column(Integer, primary_key=True, index=True)
    type_code = Column(String(128), unique=True, nullable=False, index=True)
    type_name = Column(String(255), nullable=False)
    typeclass = Column(String(500), nullable=False)
    status = Column(SmallInteger, nullable=False, default=0)
    constraints = Column(JSONB, nullable=False, default=dict)
    description = Column(Text, nullable=True)
    schema_definition = Column(JSONB, nullable=False, default=dict)
    inferred_rules = Column(JSONB, nullable=False, default=dict)
    tags = Column(JSONB, nullable=False, default=list)
    ui_config = Column(JSONB, nullable=False, default=dict)
    is_directed = Column(Boolean, nullable=False, default=True)
    is_symmetric = Column(Boolean, nullable=False, default=False)
    is_transitive = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    relationships = relationship("Relationship", backref="relationship_type_info")

    __table_args__ = (
        Index("idx_relationship_type_code", "type_code"),
        Index("idx_relationship_type_status", "status"),
        Index("idx_relationship_type_schema", "schema_definition", postgresql_using="gin"),
        Index("idx_relationship_type_constraints", "constraints", postgresql_using="gin"),
        Index("idx_relationship_type_ui", "ui_config", postgresql_using="gin"),
    )

    @hybrid_property
    def is_active(self) -> bool:
        return self.status == 0

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.status = 0 if value else 1

    @is_active.expression
    def is_active(cls):
        return cls.status == 0

    def __repr__(self):
        return f"<RelationshipType(id={self.id}, type_code='{self.type_code}', type_name='{self.type_name}')>"

    @classmethod
    def get_by_type_code(cls, session: Session, type_code: str) -> Optional["RelationshipType"]:
        return session.query(cls).filter(cls.type_code == type_code).first()

    @classmethod
    def get_active_types(cls, session: Session) -> List["RelationshipType"]:
        return session.query(cls).filter(cls.status == 0).all()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type_code": self.type_code,
            "type_name": self.type_name,
            "typeclass": self.typeclass,
            "status": self.status,
            "constraints": self.constraints,
            "description": self.description,
            "schema_definition": self.schema_definition,
            "inferred_rules": self.inferred_rules,
            "tags": self.tags,
            "ui_config": self.ui_config,
            "is_directed": self.is_directed,
            "is_symmetric": self.is_symmetric,
            "is_transitive": self.is_transitive,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class NodeAttributeIndex(Base):
    """节点属性索引表"""
    __tablename__ = "node_attribute_indexes"
    
    id = Column(Integer, primary_key=True)
    node_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)
    attribute_key = Column(String(255), nullable=False)
    attribute_value = Column(Text)
    attribute_type = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class NodeTagIndex(Base):
    """节点标签索引表"""
    __tablename__ = "node_tag_indexes"
    
    id = Column(Integer, primary_key=True)
    node_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)
    tag = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint('node_id', 'tag', name='idx_node_tag_indexes_unique'),
    )