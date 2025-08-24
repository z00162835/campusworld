"""
图同步器 - 纯图数据设计

实现DefaultObject与图节点系统的自动同步
所有对象都存储在Node中，通过type和typeclass区分
"""

from typing import Dict, Any, List, Optional, Type, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, Text
import time
import uuid

from .base import DefaultObject, GraphNodeInterface
from .graph import (
    GraphNode, Relationship
)


class GraphSynchronizer:
    """
    图同步器
    
    负责DefaultObject与图节点系统的自动同步
    """
    
    def __init__(self, db_session: Session = None):
        self.db_session = db_session
    
    def _get_db_session(self) -> Session:
        """获取数据库会话"""
        if not self.db_session:
            from app.core.database import SessionLocal
            self.db_session = SessionLocal()
        return self.db_session
    
    # ==================== 对象到图节点同步 ====================
    
    def sync_object_to_node(self, obj: DefaultObject) -> Optional[GraphNode]:
        """将DefaultObject同步到图节点"""
        try:
            session = self._get_db_session()
            
            # 检查是否已存在对应的图节点
            existing_node = session.query(GraphNode).filter(
                GraphNode.uuid == obj.get_node_uuid()
            ).first()
            
            if existing_node:
                # 更新现有图节点
                self._update_graph_node_from_object(existing_node, obj)
                return existing_node
            else:
                # 创建新图节点
                new_node = self._create_graph_node_from_object(obj)
                session.add(new_node)
                session.commit()
                return new_node
                
        except Exception as e:
            print(f"同步对象到图节点失败: {e}")
            return None
    
    def _create_graph_node_from_object(self, obj: DefaultObject) -> GraphNode:
        """从DefaultObject创建图节点"""
        # 获取对象属性
        attributes = obj.get_node_attributes()
        
        # 创建图节点
        node = GraphNode(
            uuid=obj.get_node_uuid(),
            type=obj.get_node_type(),
            typeclass=obj.get_node_typeclass(),
            classname=obj.__class__.__name__,
            module_path=obj.__class__.__module__,
            name=attributes.get('name', ''),
            description=attributes.get('description', ''),
            attributes=attributes,
            tags=attributes.get('tags', []),
            is_active=attributes.get('is_active', True),
            is_public=attributes.get('is_public', True),
            access_level=attributes.get('access_level', 'normal'),
            location_id=attributes.get('location_id'),
            home_id=attributes.get('home_id')
        )
        
        return node
    
    def _update_graph_node_from_object(self, node: GraphNode, obj: DefaultObject) -> None:
        """从DefaultObject更新图节点"""
        # 获取对象属性
        attributes = obj.get_node_attributes()
        
        # 更新节点属性
        node.name = attributes.get('name', '')
        node.description = attributes.get('description', '')
        node.attributes = attributes
        node.tags = attributes.get('tags', [])
        node.is_active = attributes.get('is_active', True)
        node.is_public = attributes.get('is_public', True)
        node.access_level = attributes.get('access_level', 'normal')
        node.location_id = attributes.get('location_id')
        node.home_id = attributes.get('home_id')
        node.updated_at = func.now()
        
        self.db_session.commit()
    
    # ==================== 图节点到对象同步 ====================
    
    def sync_node_to_object(self, node: GraphNode, obj_class: Type[DefaultObject]) -> Optional[DefaultObject]:
        """将图节点同步到DefaultObject"""
        try:
            # 从节点属性创建对象
            attributes = node.attributes or {}
            name = attributes.get('name', node.name)
            
            # 创建对象实例
            obj = obj_class(name=name, **attributes)
            
            # 设置节点UUID
            obj._node_uuid = node.uuid
            
            return obj
            
        except Exception as e:
            print(f"同步图节点到对象失败: {e}")
            return None
    
    # ==================== 关系管理 ====================
    
    def create_relationship(self, source: DefaultObject, target: DefaultObject, 
                          rel_type: str, **attributes) -> Optional[Relationship]:
        """创建关系"""
        try:
            session = self._get_db_session()
            
            # 确保源和目标对象都已同步到图节点
            source_node = self.sync_object_to_node(source)
            target_node = self.sync_object_to_node(target)
            
            if not source_node or not target_node:
                return None
            
            # 检查是否已存在关系
            existing_rel = self._get_relationship(source_node, target_node, rel_type)
            if existing_rel:
                # 更新现有关系
                self._update_relationship_attributes(existing_rel, attributes)
                return existing_rel
            
            # 根据关系类型选择合适的关系类
            relationship_class = self._get_relationship_class_by_type(rel_type)
            
            # 创建新关系
            relationship = relationship_class(
                uuid=str(uuid.uuid4()),
                type=rel_type,
                typeclass=f"app.models.relationships.{rel_type.capitalize()}Relationship",
                source_id=source_node.id,
                target_id=target_node.id,
                attributes=attributes,
                is_active=True
            )
            
            session.add(relationship)
            session.commit()
            
            return relationship
            
        except Exception as e:
            print(f"创建关系失败: {e}")
            return None
    
    def _get_relationship(self, source_node: GraphNode, target_node: GraphNode, 
                         rel_type: str) -> Optional[Relationship]:
        """获取关系"""
        session = self._get_db_session()
        return session.query(Relationship).filter(
            and_(
                Relationship.source_id == source_node.id,
                Relationship.target_id == target_node.id,
                Relationship.type == rel_type,
                Relationship.is_active == True
            )
        ).first()
    
    def _update_relationship_attributes(self, relationship: Relationship, 
                                      attributes: Dict[str, Any]) -> None:
        """更新关系属性"""
        for key, value in attributes.items():
            relationship.set_attribute(key, value)
        relationship.updated_at = func.now()
        self.db_session.commit()
    
    def _get_relationship_class_by_type(self, rel_type: str) -> Type[Relationship]:
        """根据关系类型获取合适的关系类"""
        # 使用统一的Relationship类，关系类型通过type字段和attributes区分
        return Relationship
    
    def get_object_relationships(self, obj: DefaultObject, rel_type: str = None) -> List[Relationship]:
        """获取对象的关系"""
        try:
            session = self._get_db_session()
            
            # 确保对象已同步到图节点
            obj_node = self.sync_object_to_node(obj)
            if not obj_node:
                return []
            
            # 查询关系
            query = session.query(Relationship).filter(
                and_(
                    or_(
                        Relationship.source_id == obj_node.id,
                        Relationship.target_id == obj_node.id
                    ),
                    Relationship.is_active == True
                )
            )
            
            if rel_type:
                query = query.filter(Relationship.type == rel_type)
            
            return query.all()
            
        except Exception as e:
            print(f"获取对象关系失败: {e}")
            return []
    
    def remove_relationship(self, source: DefaultObject, target: DefaultObject, 
                          rel_type: str) -> bool:
        """移除关系"""
        try:
            session = self._get_db_session()
            
            # 确保对象已同步到图节点
            source_node = self.sync_object_to_node(source)
            target_node = self.sync_object_to_node(target)
            
            if not source_node or not target_node:
                return False
            
            # 查找并移除关系
            relationship = self._get_relationship(source_node, target_node, rel_type)
            if relationship:
                relationship.is_active = False
                session.commit()
                return True
            
            return False
            
        except Exception as e:
            print(f"移除关系失败: {e}")
            return False
    
    # ==================== 批量同步 ====================
    
    def sync_objects_batch(self, objects: List[DefaultObject]) -> List[GraphNode]:
        """批量同步对象到图节点"""
        synced_nodes = []
        
        for obj in objects:
            try:
                node = self.sync_object_to_node(obj)
                if node:
                    synced_nodes.append(node)
            except Exception as e:
                print(f"批量同步对象 {obj.name} 失败: {e}")
        
        return synced_nodes
    
    def sync_graph_nodes_batch(self, nodes: List[GraphNode], 
                              obj_class: Type[DefaultObject]) -> List[DefaultObject]:
        """批量同步图节点到对象"""
        synced_objects = []
        
        for node in nodes:
            try:
                obj = self.sync_node_to_object(node, obj_class)
                if obj:
                    synced_objects.append(obj)
            except Exception as e:
                print(f"批量同步图节点 {node.name} 失败: {e}")
        
        return synced_objects
    
    def get_node_by_uuid(self, node_uuid: str) -> Optional[GraphNode]:
        """根据UUID获取图节点"""
        try:
            session = self._get_db_session()
            return session.query(GraphNode).filter(GraphNode.uuid == node_uuid).first()
        except Exception as e:
            print(f"根据UUID获取节点失败: {e}")
            return None
    
    # ==================== 查询和搜索 ====================
    
    def find_objects_by_attribute(self, attribute_key: str, attribute_value: Any, 
                                 obj_class: Type[DefaultObject] = None) -> List[DefaultObject]:
        """通过属性查找对象"""
        try:
            session = self._get_db_session()
            
            # 在图节点中查找
            query = session.query(GraphNode).filter(
                GraphNode.attributes[attribute_key].astext == str(attribute_value)
            )
            
            if obj_class:
                query = query.filter(GraphNode.type == obj_class.get_node_type())
            
            nodes = query.all()
            
            # 同步到对象
            if obj_class:
                return self.sync_graph_nodes_batch(nodes, obj_class)
            else:
                # 尝试根据typeclass推断对象类
                objects = []
                for node in nodes:
                    try:
                        # 动态导入类
                        module_path, class_name = node.typeclass.rsplit('.', 1)
                        module = __import__(module_path, fromlist=[class_name])
                        obj_class = getattr(module, class_name)
                        obj = self.sync_node_to_object(node, obj_class)
                        if obj:
                            objects.append(obj)
                    except Exception as e:
                        print(f"动态导入类 {node.typeclass} 失败: {e}")
                
                return objects
                
        except Exception as e:
            print(f"通过属性查找对象失败: {e}")
            return []
    
    def find_objects_by_tag(self, tag: str, obj_class: Type[DefaultObject] = None) -> List[DefaultObject]:
        """通过标签查找对象"""
        try:
            session = self._get_db_session()
            
            # 在图节点中查找
            query = session.query(GraphNode).filter(
                GraphNode.tags.contains([tag])
            )
            
            if obj_class:
                query = query.filter(GraphNode.type == obj_class.get_node_type())
            
            nodes = query.all()
            
            # 同步到对象
            if obj_class:
                return self.sync_graph_nodes_batch(nodes, obj_class)
            else:
                # 尝试根据typeclass推断对象类
                objects = []
                for node in nodes:
                    try:
                        module_path, class_name = node.typeclass.rsplit('.', 1)
                        module = __import__(module_path, fromlist=[class_name])
                        obj_class = getattr(module, class_name)
                        obj = self.sync_node_to_object(node, obj_class)
                        if obj:
                            objects.append(obj)
                    except Exception as e:
                        print(f"动态导入类 {node.typeclass} 失败: {e}")
                
                return objects
                
        except Exception as e:
            print(f"通过标签查找对象失败: {e}")
            return []
    
    def search_objects(self, query: str, obj_class: Type[DefaultObject] = None) -> List[DefaultObject]:
        """搜索对象"""
        try:
            session = self._get_db_session()
            
            # 在图节点中搜索
            search_query = session.query(GraphNode).filter(
                or_(
                    GraphNode.name.ilike(f"%{query}%"),
                    GraphNode.description.ilike(f"%{query}%"),
                    GraphNode.attributes.cast(Text).ilike(f"%{query}%")
                )
            )
            
            if obj_class:
                search_query = search_query.filter(
                    GraphNode.type == obj_class.get_node_type()
                )
            
            nodes = search_query.limit(100).all()
            
            # 同步到对象
            if obj_class:
                return self.sync_graph_nodes_batch(nodes, obj_class)
            else:
                # 尝试根据typeclass推断对象类
                objects = []
                for node in nodes:
                    try:
                        module_path, class_name = node.typeclass.rsplit('.', 1)
                        module = __import__(module_path, fromlist=[class_name])
                        obj_class = getattr(module, class_name)
                        obj = self.sync_node_to_object(node, obj_class)
                        if obj:
                            objects.append(obj)
                    except Exception as e:
                        print(f"动态导入类 {node.typeclass} 失败: {e}")
                
                return objects
                
        except Exception as e:
            print(f"搜索对象失败: {e}")
            return []
    
    # ==================== 统计和监控 ====================
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """获取同步统计信息"""
        try:
            session = self._get_db_session()
            
            total_nodes = session.query(func.count(GraphNode.id)).scalar()
            total_relationships = session.query(func.count(Relationship.id)).scalar()
            active_nodes = session.query(func.count(GraphNode.id)).filter(
                GraphNode.is_active == True
            ).scalar()
            active_relationships = session.query(func.count(Relationship.id)).filter(
                Relationship.is_active == True
            ).scalar()
            
            return {
                "total_nodes": total_nodes,
                "total_relationships": total_relationships,
                "active_nodes": active_nodes,
                "active_relationships": active_relationships,
                "sync_timestamp": time.time()
            }
            
        except Exception as e:
            print(f"获取同步统计失败: {e}")
            return {}
    
    def cleanup_orphaned_nodes(self) -> int:
        """清理孤立的图节点"""
        try:
            session = self._get_db_session()
            
            # 查找没有关系的孤立节点
            orphaned_nodes = session.query(GraphNode).outerjoin(
                Relationship, 
                or_(
                    GraphNode.id == Relationship.source_id,
                    GraphNode.id == Relationship.target_id
                )
            ).filter(Relationship.id.is_(None)).all()
            
            # 标记为不活跃
            for node in orphaned_nodes:
                node.is_active = False
            
            session.commit()
            return len(orphaned_nodes)
            
        except Exception as e:
            print(f"清理孤立节点失败: {e}")
            return 0
