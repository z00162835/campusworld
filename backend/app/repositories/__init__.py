"""
Repository层 - 数据访问抽象

使用统一的Session管理，封装ORM方法，提供简洁的数据访问接口。

设计原则:
1. 使用 db_session_context() 统一管理Session生命周期
2. 内部调用 graph.py 中已定义的ORM类方法
3. 返回业务友好的数据结构
"""

from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Union
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.database import db_session_context
from app.models.graph import Node, Relationship, NodeType, RelationshipType


class NodeRepository:
    """
    图节点数据访问仓库

    封装Node模型的常用查询和操作，使用统一的Session管理。

    用法:
        repo = NodeRepository()
        node = repo.get_by_uuid("...")
        nodes = repo.get_by_type("user")
    """

    def __init__(self, session: Optional[Session] = None):
        """
        初始化仓库

        Args:
            session: 可选的 Session。传入时各方法使用该会话（写路径仅 ``flush``，由调用方 ``commit``）；
                未传入时各方法内部使用 ``db_session_context()`` 并在写路径上 ``commit``。
        """
        self._session = session

    @contextmanager
    def _session_scope(self):
        """Use injected Session when provided; otherwise a short ``db_session_context`` (commit/close owned by context)."""
        if self._session is not None:
            yield self._session
        else:
            with db_session_context() as session:
                yield session

    def _owns_session(self) -> bool:
        return self._session is None

    def get_by_id(self, node_id: int) -> Optional[Node]:
        """根据ID获取节点"""
        with self._session_scope() as session:
            return session.query(Node).filter(Node.id == node_id).first()

    def get_by_uuid(self, uid: Union[str, UUID]) -> Optional[Node]:
        """根据UUID获取节点"""
        with self._session_scope() as session:
            return Node.get_by_uuid(session, uid)

    def get_by_name(self, name: str) -> Optional[Node]:
        """根据名称获取节点"""
        with self._session_scope() as session:
            return Node.get_by_name(session, name)

    def get_by_type(self, type_code: str) -> List[Node]:
        """根据类型获取节点列表"""
        with self._session_scope() as session:
            return Node.get_by_type(session, type_code)

    def get_active_nodes(
        self,
        type_code: str = None,
        trait_class: str = None,
        required_any_mask: int = 0,
        required_all_mask: int = 0,
    ) -> List[Node]:
        """获取活跃节点；trait 过滤语义与 ``Node.get_active_nodes`` 一致（mask=0 不过滤）。"""
        with self._session_scope() as session:
            return Node.get_active_nodes(
                session,
                type_code,
                trait_class=trait_class,
                required_any_mask=required_any_mask,
                required_all_mask=required_all_mask,
            )

    def search_by_attribute(self, key: str, value: Any, type_code: str = None) -> List[Node]:
        """根据属性搜索节点"""
        with self._session_scope() as session:
            return Node.search_by_attribute(session, key, value, type_code)

    def search_by_tag(self, tag: str, type_code: str = None) -> List[Node]:
        """根据标签搜索节点"""
        with self._session_scope() as session:
            return Node.search_by_tag(session, tag, type_code)

    def get_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        type_code: str = None,
        is_active: bool = True,
        **filters
    ) -> Dict[str, Any]:
        """分页获取节点"""
        with self._session_scope() as session:
            return Node.get_paginated(session, page, page_size, type_code, is_active, **filters)

    def get_related_nodes(self, node_id: int, relationship_type: str = None) -> List[Node]:
        """获取相关节点"""
        with self._session_scope() as session:
            return Node.get_related_nodes(session, node_id, relationship_type)

    def create(self, type_code: str, name: str, **kwargs) -> Node:
        """
        创建新节点

        Args:
            type_code: 节点类型代码
            name: 节点名称
            **kwargs: 其他属性 (description, attributes, tags, etc.)

        Returns:
            创建的节点对象
        """
        with self._session_scope() as session:
            # 获取类型ID
            node_type = session.query(NodeType).filter(NodeType.type_code == type_code).first()
            if not node_type:
                raise ValueError(f"未找到节点类型: {type_code}")

            node = Node(
                type_id=node_type.id,
                type_code=type_code,
                name=name,
                description=kwargs.get('description'),
                is_active=kwargs.get('is_active', True),
                is_public=kwargs.get('is_public', True),
                access_level=kwargs.get('access_level', 'normal'),
                attributes=kwargs.get('attributes', {}),
                tags=kwargs.get('tags', []),
                location_id=kwargs.get('location_id'),
                home_id=kwargs.get('home_id'),
            )
            session.add(node)
            if self._owns_session():
                session.commit()
            else:
                session.flush()
            session.refresh(node)
            return node

    def update(self, node_id: int, **kwargs) -> Optional[Node]:
        """更新节点"""
        with self._session_scope() as session:
            node = session.query(Node).filter(Node.id == node_id).first()
            if not node:
                return None

            for key, value in kwargs.items():
                if hasattr(node, key):
                    setattr(node, key, value)

            if self._owns_session():
                session.commit()
            else:
                session.flush()
            session.refresh(node)
            return node

    def delete(self, node_id: int) -> bool:
        """删除节点（软删除）"""
        with self._session_scope() as session:
            node = session.query(Node).filter(Node.id == node_id).first()
            if not node:
                return False
            node.is_active = False
            if self._owns_session():
                session.commit()
            else:
                session.flush()
            return True

    def hard_delete(self, node_id: int) -> bool:
        """硬删除节点"""
        with self._session_scope() as session:
            node = session.query(Node).filter(Node.id == node_id).first()
            if not node:
                return False
            session.delete(node)
            if self._owns_session():
                session.commit()
            else:
                session.flush()
            return True


class RelationshipRepository:
    """
    图关系数据访问仓库

    封装Relationship模型的常用查询和操作。
    """

    def get_by_id(self, rel_id: int) -> Optional[Relationship]:
        """根据ID获取关系"""
        with db_session_context() as session:
            return session.query(Relationship).filter(Relationship.id == rel_id).first()

    def get_by_uuid(self, uid: Union[str, UUID]) -> Optional[Relationship]:
        """根据UUID获取关系"""
        with db_session_context() as session:
            return Relationship.get_by_uuid(session, uid)

    def get_by_type(self, type_code: str) -> List[Relationship]:
        """根据类型获取关系列表"""
        with db_session_context() as session:
            return Relationship.get_by_type(session, type_code)

    def get_by_source(self, source_id: int, type_code: str = None) -> List[Relationship]:
        """获取源节点的所有关系"""
        with db_session_context() as session:
            return Relationship.get_by_source(session, source_id, type_code)

    def get_by_target(self, target_id: int, type_code: str = None) -> List[Relationship]:
        """获取目标节点的所有关系"""
        with db_session_context() as session:
            return Relationship.get_by_target(session, target_id, type_code)

    def create(
        self,
        type_code: str,
        source_id: int,
        target_id: int,
        **kwargs
    ) -> Relationship:
        """
        创建新关系

        Args:
            type_code: 关系类型代码
            source_id: 源节点ID
            target_id: 目标节点ID
            **kwargs: 其他属性

        Returns:
            创建的关系对象
        """
        with db_session_context() as session:
            rel_type = session.query(RelationshipType).filter(
                RelationshipType.type_code == type_code
            ).first()
            if not rel_type:
                raise ValueError(f"未找到关系类型: {type_code}")

            rel = Relationship(
                type_id=rel_type.id,
                type_code=type_code,
                source_id=source_id,
                target_id=target_id,
                source_role=kwargs.get('source_role'),
                target_role=kwargs.get('target_role'),
                weight=kwargs.get('weight', 1),
                attributes=kwargs.get('attributes', {}),
                tags=kwargs.get('tags', []),
                is_active=kwargs.get('is_active', True),
            )
            session.add(rel)
            session.commit()
            session.refresh(rel)
            return rel

    def delete(self, rel_id: int) -> bool:
        """删除关系（软删除）"""
        with db_session_context() as session:
            rel = session.query(Relationship).filter(Relationship.id == rel_id).first()
            if not rel:
                return False
            rel.is_active = False
            session.commit()
            return True


class NodeTypeRepository:
    """节点类型数据访问仓库"""

    def get_by_code(self, type_code: str) -> Optional[NodeType]:
        """根据类型代码获取节点类型"""
        with db_session_context() as session:
            return NodeType.get_by_type_code(session, type_code)

    def get_all(self) -> List[NodeType]:
        """获取所有节点类型"""
        with db_session_context() as session:
            return session.query(NodeType).all()

    def get_active(self) -> List[NodeType]:
        """获取所有活跃的节点类型"""
        with db_session_context() as session:
            return session.query(NodeType).filter(NodeType.status == 0).all()


class RelationshipTypeRepository:
    """关系类型数据访问仓库"""

    def get_by_code(self, type_code: str) -> Optional[RelationshipType]:
        """根据类型代码获取关系类型"""
        with db_session_context() as session:
            return RelationshipType.get_by_type_code(session, type_code)

    def get_all(self) -> List[RelationshipType]:
        """获取所有关系类型"""
        with db_session_context() as session:
            return session.query(RelationshipType).all()

    def get_active(self) -> List[RelationshipType]:
        """获取所有活跃的关系类型"""
        with db_session_context() as session:
            return session.query(RelationshipType).filter(RelationshipType.status == 0).all()


# Repository工厂函数
def get_node_repository() -> NodeRepository:
    """获取NodeRepository实例"""
    return NodeRepository()


def get_relationship_repository() -> RelationshipRepository:
    """获取RelationshipRepository实例"""
    return RelationshipRepository()


def get_node_type_repository() -> NodeTypeRepository:
    """获取NodeTypeRepository实例"""
    return NodeTypeRepository()


def get_relationship_type_repository() -> RelationshipTypeRepository:
    """获取RelationshipTypeRepository实例"""
    return RelationshipTypeRepository()