"""
图管理器模块

提供图数据结构的操作接口，包括：
- 节点查询和管理
- 关系操作
- 图遍历算法
- 性能优化
"""

from typing import Dict, Any, List, Optional, Type, Union, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, Text
from sqlalchemy.dialects.postgresql import JSONB
import json
from uuid import uuid4

from .graph import (
    GraphNode, 
    Relationship, 
    Node
)
from .base import DefaultObject, DefaultAccount


class GraphManager:
    """
    图管理器
    
    负责图节点的创建、查询和管理
    """
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
    
    # ==================== 节点管理 ====================
    
    def create_node(self, node_class: Type[Node], **attributes) -> GraphNode:
        """创建新节点"""
        node = node_class(**attributes)
        self.db_session.add(node)
        self.db_session.commit()
        return node
    
    def get_node_by_id(self, node_id: int) -> Optional[GraphNode]:
        """通过ID获取节点"""
        return self.db_session.query(GraphNode).filter(
            GraphNode.id == node_id
        ).first()
    
    def get_node_by_uuid(self, uuid: str) -> Optional[GraphNode]:
        """通过UUID获取节点"""
        return self.db_session.query(GraphNode).filter(
            GraphNode.uuid == uuid
        ).first()
    
    def get_nodes_by_classpath(self, classpath: str) -> List[GraphNode]:
        """通过类路径获取节点"""
        return self.db_session.query(GraphNode).filter(
            GraphNode.classpath == classpath
        ).all()
    
    def get_nodes_by_type(self, node_type: str) -> List[GraphNode]:
        """通过类型获取节点"""
        return self.get_nodes_by_classpath(f"app.models.{node_type}")
    
    def get_nodes_by_attribute(self, key: str, value: Any) -> List[GraphNode]:
        """通过属性值获取节点"""
        return self.db_session.query(GraphNode).filter(
            GraphNode.attributes[key].astext == str(value)
        ).all()
    
    def get_nodes_by_tag(self, tag: str) -> List[GraphNode]:
        """通过标签获取节点"""
        return self.db_session.query(GraphNode).filter(
            GraphNode.tags.contains([tag])
        ).all()
    
    def search_nodes(self, query: str, limit: int = 100) -> List[GraphNode]:
        """搜索节点（名称、描述、属性）"""
        return self.db_session.query(GraphNode).filter(
            or_(
                GraphNode.name.ilike(f"%{query}%"),
                GraphNode.description.ilike(f"%{query}%"),
                GraphNode.attributes.cast(Text).ilike(f"%{query}%")
            )
        ).limit(limit).all()
    
    def update_node(self, node: GraphNode, **attributes) -> GraphNode:
        """更新节点"""
        for key, value in attributes.items():
            if hasattr(node, key):
                setattr(node, key, value)
        
        node.updated_at = func.now()
        self.db_session.commit()
        return node
    
    def delete_node(self, node: GraphNode) -> bool:
        """删除节点（软删除）"""
        node.is_active = False
        self.db_session.commit()
        return True
    
    # ==================== 关系管理 ====================
    
    def create_relationship(self, source: GraphNode, target: GraphNode, 
                          rel_type: str, relationship_class: Type[Relationship] = None, 
                          **attributes) -> Relationship:
        """创建关系"""
        # 检查是否已存在
        existing_rel = self.get_relationship(source, target, rel_type)
        if existing_rel:
            # 更新现有关系
            for key, value in attributes.items():
                existing_rel.set_attribute(key, value)
            existing_rel.updated_at = func.now()
            self.db_session.commit()
            return existing_rel
        
        # 根据关系类型选择合适的关系类
        if relationship_class is None:
            relationship_class = self._get_relationship_class_by_type(rel_type)
        
        # 创建新关系
        relationship = relationship_class(
            uuid=str(uuid4()),
            type=rel_type,
            classpath=relationship_class.get_classpath(),
            source_id=source.id,
            target_id=target.id,
            attributes=attributes
        )
        
        self.db_session.add(relationship)
        self.db_session.commit()
        return relationship
    
    def _get_relationship_class_by_type(self, rel_type: str) -> Type[Relationship]:
        """根据关系类型获取合适的关系类"""
        # 使用统一的Relationship类，关系类型通过type字段和attributes区分
        return Relationship
    
    def create_friendship(self, source: GraphNode, target: GraphNode, 
                         friendship_level: str = "acquaintance", **attributes) -> Relationship:
        """创建友谊关系"""
        attributes['friendship_level'] = friendship_level
        return self.create_relationship(
            source, target, "friendship", 
            **attributes
        )
    
    def create_location_relationship(self, source: GraphNode, target: GraphNode, 
                                   location_type: str = "current", **attributes) -> Relationship:
        """创建位置关系"""
        attributes['location_type'] = location_type
        return self.create_relationship(
            source, target, "location", 
            **attributes
        )
    
    def create_ownership_relationship(self, source: GraphNode, target: GraphNode, 
                                    ownership_type: str = "owner", **attributes) -> Relationship:
        """创建所有权关系"""
        attributes['ownership_type'] = ownership_type
        return self.create_relationship(
            source, target, "owns", 
            **attributes
        )
    
    def get_relationship(self, source: GraphNode, target: GraphNode, 
                        rel_type: str) -> Optional[Relationship]:
        """获取关系"""
        return self.db_session.query(Relationship).filter(
            and_(
                Relationship.source_id == source.id,
                Relationship.target_id == target.id,
                Relationship.type == rel_type,
                Relationship.is_active == True
            )
        ).first()
    
    def get_relationships_by_type(self, rel_type: str) -> List[Relationship]:
        """通过类型获取关系"""
        return self.db_session.query(Relationship).filter(
            and_(
                Relationship.type == rel_type,
                Relationship.is_active == True
            )
        ).all()
    
    def get_relationships_by_class(self, relationship_class: Type[Relationship]) -> List[Relationship]:
        """通过关系类获取关系"""
        return self.db_session.query(relationship_class).filter(
            relationship_class.is_active == True
        ).all()
    
    def get_friendship_relationships(self) -> List[Relationship]:
        """获取所有友谊关系"""
        return self.get_relationships_by_type("friendship")
    
    def get_location_relationships(self) -> List[Relationship]:
        """获取所有位置关系"""
        return self.get_relationships_by_type("location")
    
    def get_ownership_relationships(self) -> List[Relationship]:
        """获取所有所有权关系"""
        return self.get_relationships_by_type("owns")
    
    def get_relationships_by_node(self, node: GraphNode, direction: str = "both") -> List[Relationship]:
        """获取节点的关系"""
        if direction == "outgoing":
            return self.db_session.query(Relationship).filter(
                and_(
                    Relationship.source_id == node.id,
                    Relationship.is_active == True
                )
            ).all()
        elif direction == "incoming":
            return self.db_session.query(Relationship).filter(
                and_(
                    Relationship.target_id == node.id,
                    Relationship.is_active == True
                )
            ).all()
        else:  # both
            return self.db_session.query(Relationship).filter(
                and_(
                    or_(
                        Relationship.source_id == node.id,
                        Relationship.target_id == node.id
                    ),
                    Relationship.is_active == True
                )
            ).all()
    
    def remove_relationship(self, source: GraphNode, target: GraphNode, 
                          rel_type: str) -> bool:
        """移除关系（软删除）"""
        relationship = self.get_relationship(source, target, rel_type)
        if relationship:
            relationship.is_active = False
            self.db_session.commit()
            return True
        return False
    
    def update_relationship(self, relationship: Relationship, **attributes) -> Relationship:
        """更新关系"""
        for key, value in attributes.items():
            relationship.set_attribute(key, value)
        
        relationship.updated_at = func.now()
        self.db_session.commit()
        return relationship
    
    # ==================== 图遍历 ====================
    
    def get_neighbors(self, node: GraphNode, rel_type: str = None, 
                     direction: str = "both") -> List[GraphNode]:
        """获取邻居节点"""
        relationships = self.get_relationships_by_node(node, direction)
        
        neighbors = []
        for rel in relationships:
            if rel_type and rel.type != rel_type:
                continue
            
            if rel.source_id == node.id:
                neighbors.append(rel.target)
            else:
                neighbors.append(rel.source)
        
        return neighbors
    
    def get_path(self, source: GraphNode, target: GraphNode, 
                 max_depth: int = 5) -> Optional[List[GraphNode]]:
        """获取两点间的最短路径"""
        if source.id == target.id:
            return [source]
        
        # 使用BFS查找最短路径
        visited = set()
        queue = [(source, [source])]
        
        while queue and len(queue[0][1]) <= max_depth:
            current, path = queue.pop(0)
            
            if current.id in visited:
                continue
            
            visited.add(current.id)
            
            # 获取邻居
            neighbors = self.get_neighbors(current)
            for neighbor in neighbors:
                if neighbor.id == target.id:
                    return path + [neighbor]
                
                if neighbor.id not in visited:
                    queue.append((neighbor, path + [neighbor]))
        
        return None
    
    def get_subgraph(self, center_node: GraphNode, depth: int = 2) -> Dict[str, Any]:
        """获取子图"""
        subgraph = {
            "nodes": [],
            "relationships": [],
            "center": center_node
        }
        
        visited_nodes = set()
        visited_rels = set()
        
        def explore(node: GraphNode, current_depth: int):
            if current_depth > depth or node.id in visited_nodes:
                return
            
            visited_nodes.add(node.id)
            subgraph["nodes"].append(node)
            
            if current_depth < depth:
                relationships = self.get_relationships_by_node(node)
                for rel in relationships:
                    if rel.id not in visited_rels:
                        visited_rels.add(rel.id)
                        subgraph["relationships"].append(rel)
                        
                        # 探索目标节点
                        if rel.target_id == node.id:
                            target_node = self.get_node_by_id(rel.source_id)
                        else:
                            target_node = self.get_node_by_id(rel.target_id)
                        
                        if target_node:
                            explore(target_node, current_depth + 1)
        
        explore(center_node, 0)
        return subgraph
    
    # ==================== 性能优化 ====================
    
    def bulk_create_nodes(self, nodes: List[Dict[str, Any]]) -> List[GraphNode]:
        """批量创建节点"""
        created_nodes = []
        for node_data in nodes:
            node = GraphNode(**node_data)
            created_nodes.append(node)
            self.db_session.add(node)
        
        self.db_session.commit()
        return created_nodes
    
    def bulk_create_relationships(self, relationships: List[Dict[str, Any]]) -> List[Relationship]:
        """批量创建关系"""
        created_rels = []
        for rel_data in relationships:
            rel = Relationship(**rel_data)
            created_rels.append(rel)
            self.db_session.add(rel)
        
        self.db_session.commit()
        return created_rels
    
    def get_nodes_with_relationships(self, node_ids: List[int]) -> List[GraphNode]:
        """预加载关系的节点查询"""
        return self.db_session.query(GraphNode).filter(
            GraphNode.id.in_(node_ids)
        ).options(
            joinedload(GraphNode.outgoing_relationships),
            joinedload(GraphNode.incoming_relationships)
        ).all()
    
    # ==================== 统计和监控 ====================
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """获取图统计信息"""
        total_nodes = self.db_session.query(func.count(GraphNode.id)).scalar()
        total_relationships = self.db_session.query(func.count(Relationship.id)).scalar()
        active_nodes = self.db_session.query(func.count(GraphNode.id)).filter(
            GraphNode.is_active == True
        ).scalar()
        active_relationships = self.db_session.query(func.count(Relationship.id)).filter(
            Relationship.is_active == True
        ).scalar()
        
        return {
            "total_nodes": total_nodes,
            "total_relationships": total_relationships,
            "active_nodes": active_nodes,
            "active_relationships": active_relationships,
            "density": total_relationships / (total_nodes * (total_nodes - 1)) if total_nodes > 1 else 0
        }
    
    def get_node_type_distribution(self) -> Dict[str, int]:
        """获取节点类型分布"""
        result = self.db_session.query(
            GraphNode.classpath,
            func.count(GraphNode.id)
        ).group_by(GraphNode.classpath).all()
        
        return dict(result)
    
    def get_relationship_type_distribution(self) -> Dict[str, int]:
        """获取关系类型分布"""
        result = self.db_session.query(
            Relationship.type,
            func.count(Relationship.id)
        ).group_by(Relationship.type).all()
        
        return dict(result)
    
    def get_relationship_class_distribution(self) -> Dict[str, int]:
        """获取关系类分布"""
        result = self.db_session.query(
            Relationship.classpath,
            func.count(Relationship.id)
        ).group_by(Relationship.classpath).all()
        
        return dict(result)


# 全局图管理器实例
_graph_manager_instance = None

def get_graph_manager() -> GraphManager:
    """获取全局图管理器实例"""
    global _graph_manager_instance
    if _graph_manager_instance is None:
        from app.core.database import SessionLocal
        session = SessionLocal()
        _graph_manager_instance = GraphManager(session)
    return _graph_manager_instance


def get_db_session():
    """获取数据库会话（用于图管理器）"""
    from app.core.database import SessionLocal
    return SessionLocal()
