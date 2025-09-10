"""
图同步器 - 纯图数据设计

实现DefaultObject与图节点系统的自动同步
所有对象都存储在Node中，通过type和typeclass区分
"""

from typing import Dict, Any, List, Optional, Type, Union, TYPE_CHECKING
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, Text
import time
import uuid
from app.core.log import get_logger, LoggerNames
from .graph import (
    Node, NodeType, Relationship, RelationshipType
)
from app.core.database import SessionLocal

if TYPE_CHECKING:
    from .base import DefaultObject

class GraphSynchronizer:
    """
    图同步器
    
    负责DefaultObject与图节点系统的自动同步
    """
    
    def __init__(self, db_session: Session = None):
        self.db_session = db_session
        self.logger = get_logger(LoggerNames.DATABASE)
    
    def _get_db_session(self) -> Session:
        """获取数据库会话"""
        if not self.db_session:
            self.db_session = SessionLocal()
        return self.db_session
    
    # ==================== 对象到图节点同步 ====================
    
    def sync_object_to_node(self, obj: 'DefaultObject') -> Optional[Node]:
        """将DefaultObject同步到图节点"""
        try:
            session = self._get_db_session()
            
            # 检查是否已存在对应的图节点
            existing_node = session.query(Node).filter(
                Node.uuid == obj.get_node_uuid()
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
            self.logger.error(f"同步对象到图节点失败: {e}")
            return None
    
    def _create_graph_node_from_object(self, obj: 'DefaultObject') -> Node:
        """从DefaultObject创建图节点"""
        # 获取对象属性（不包含name）
        attributes = obj.get_node_attributes()
        type_id = self._get_type_id(obj.get_node_type())

        # 创建图节点，name从对象的独立字段获取
        node = Node(
            uuid=obj.get_node_uuid(),
            type_id=type_id,
            type_code=obj.get_node_type(),
            name=obj.get_node_name(),
            description=obj.get_node_description(),
            attributes=attributes,  # 只包含动态属性
            tags=obj.get_node_tags(),
            is_active=obj.is_node_active(),
            is_public=obj.is_node_public(),
            access_level=obj.get_node_access_level(),
            location_id=obj.get_node_location_id(),
            home_id=obj.get_node_home_id()
        )
        
        return node
    
    def _update_graph_node_from_object(self, node: Node, obj: 'DefaultObject') -> None:
        """从DefaultObject更新图节点"""
        attributes = obj.get_node_attributes()
        
        # 更新节点固定字段
        node.name = obj.get_node_name()
        node.description = obj.get_node_description()
        node.attributes = attributes
        node.tags = obj.get_node_tags()
        node.is_active = obj.is_node_active()
        node.is_public = obj.is_node_public()
        node.access_level = obj.get_node_access_level()
        node.location_id = obj.get_node_location_id()
        node.home_id = obj.get_node_home_id()
        node.updated_at = func.now()
        
        self.db_session.commit()
    
    def _get_type_id(self, type_code: str) -> int:
        """获取节点类型ID"""
        session = self._get_db_session()
    
        node_type = session.query(NodeType).filter(
            NodeType.type_code == type_code
        ).first()
    
        if not node_type:
            raise ValueError(f"节点类型不存在: {type_code}")
    
        if not node_type.is_active:
            raise ValueError(f"节点类型已禁用: {type_code}")
    
        return node_type.id

    def _get_relationship_type_id(self, type_code: str) -> int:
        """获取关系类型ID"""
        session = self._get_db_session()
        from .graph import RelationshipType
    
        rel_type = session.query(RelationshipType).filter(
            RelationshipType.type_code == type_code
        ).first()
    
        if not rel_type:
            raise ValueError(f"关系类型不存在: {type_code}")
    
        if not rel_type.is_active:
            raise ValueError(f"关系类型已禁用: {type_code}")
    
        return rel_type.id
    # ==================== 图节点到对象同步 ====================
    
    def sync_node_to_object(self, node: Node, obj_class: Type['DefaultObject']) -> Optional['DefaultObject']:
        """将图节点同步到DefaultObject"""
        try:
            # 从节点属性创建对象（不包含name）
            attributes = node.attributes or {}
            
            # 从节点的独立name字段获取名称
            name = node.name
            
            # 创建对象实例
            obj = obj_class(name=name, **attributes)
            
            # 设置节点UUID
            obj._node_uuid = node.uuid
            
            return obj
            
        except Exception as e:
            self.logger.error(f"同步图节点到对象失败: {e}")
            return None
    
    # ==================== 关系管理 ====================
    
    def create_relationship(self, source: 'DefaultObject', target: 'DefaultObject', 
                          rel_type: str, **attributes) -> Optional[Relationship]:
        """创建关系"""
        try:
            session = self._get_db_session()
            
            # 验证关系类型存在
            rel_type_id = self._get_relationship_type_id(rel_type)
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
                type_id=rel_type_id,
                type_code=rel_type,
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
            self.logger.error(f"创建关系失败: {e}")
            return None
    
    def _get_relationship(self, source_node: Node, target_node: Node, 
                         rel_type: str) -> Optional[Relationship]:
        """获取关系"""
        session = self._get_db_session()
        return session.query(Relationship).filter(
            and_(
                Relationship.source_id == source_node.id,
                Relationship.target_id == target_node.id,
                Relationship.type_code == rel_type,
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
    
    def get_object_relationships(self, obj: 'DefaultObject', rel_type: str = None) -> List[Relationship]:
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
                query = query.filter(Relationship.type_code == rel_type)
            
            return query.all()
            
        except Exception as e:
            self.logger.error(f"获取对象关系失败: {e}")
            return []
    
    def remove_relationship(self, source: 'DefaultObject', target: 'DefaultObject', 
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
            self.logger.error(f"移除关系失败: {e}")
            return False
    
    # ==================== 批量同步 ====================
    
    def sync_objects_batch(self, objects: List['DefaultObject']) -> List[Node]:
        """批量同步对象到图节点"""
        synced_nodes = []
        
        for obj in objects:
            try:
                node = self.sync_object_to_node(obj)
                if node:
                    synced_nodes.append(node)
            except Exception as e:
                self.logger.error(f"批量同步对象 {obj.name} 失败: {e}")
        
        return synced_nodes
    
    def sync_graph_nodes_batch(self, nodes: List[Node], 
                              obj_class: Type['DefaultObject']) -> List['DefaultObject']:
        """批量同步图节点到对象"""
        synced_objects = []
        
        for node in nodes:
            try:
                obj = self.sync_node_to_object(node, obj_class)
                if obj:
                    synced_objects.append(obj)
            except Exception as e:
                self.logger.error(f"批量同步图节点 {node.name} 失败: {e}")
        
        return synced_objects
    
    def get_node_by_uuid(self, node_uuid: str) -> Optional[Node]:
        """根据UUID获取图节点"""
        try:
            session = self._get_db_session()
            return session.query(Node).filter(Node.uuid == node_uuid).first()
        except Exception as e:
            self.logger.error(f"根据UUID获取节点失败: {e}")
            return None
    
    # ==================== 查询和搜索 ====================
    
    def find_objects_by_attribute(self, attribute_key: str, attribute_value: Any, 
                                 obj_class: Type['DefaultObject'] = None) -> List['DefaultObject']:
        """通过属性查找对象"""
        try:
            session = self._get_db_session()
            
            # 在图节点中查找
            query = session.query(Node).filter(
                Node.attributes[attribute_key].astext == str(attribute_value)
            )
            
            if obj_class:
                query = query.filter(Node.type_code == obj_class.get_node_type())
            
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
                        self.logger.error(f"动态导入类 {node.typeclass} 失败: {e}")
                
                return objects
                
        except Exception as e:
            self.logger.error(f"通过属性查找对象失败: {e}")
            return []
    
    def find_objects_by_tag(self, tag: str, obj_class: Type['DefaultObject'] = None) -> List['DefaultObject']:
        """通过标签查找对象"""
        try:
            session = self._get_db_session()
            
            # 在图节点中查找
            query = session.query(Node).filter(
                Node.tags.contains([tag])
            )
            
            if obj_class:
                query = query.filter(Node.type_code == obj_class.get_node_type())
            
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
                        self.logger.error(f"动态导入类 {node.typeclass} 失败: {e}")
                
                return objects
                
        except Exception as e:
            self.logger.error(f"通过标签查找对象失败: {e}")
            return []
    
    def search_objects(self, query: str, obj_class: Type['DefaultObject'] = None) -> List['DefaultObject']:
        """搜索对象"""
        try:
            session = self._get_db_session()
            
            # 在图节点中搜索
            search_query = session.query(Node).filter(
                or_(
                    Node.name.ilike(f"%{query}%"),
                    Node.description.ilike(f"%{query}%"),
                    Node.attributes.cast(Text).ilike(f"%{query}%")
                )
            )
            
            if obj_class:
                search_query = search_query.filter(
                    Node.type_code == obj_class.get_node_type()
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
                        self.logger.error(f"动态导入类 {node.typeclass} 失败: {e}")
                
                return objects
                
        except Exception as e:
            self.logger.error(f"搜索对象失败: {e}")
            return []
    
    # ==================== 统计和监控 ====================
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """获取同步统计信息"""
        try:
            session = self._get_db_session()
            
            total_nodes = session.query(func.count(Node.id)).scalar()
            total_relationships = session.query(func.count(Relationship.id)).scalar()
            active_nodes = session.query(func.count(Node.id)).filter(
                Node.is_active == True
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
            self.logger.error(f"获取同步统计失败: {e}")
            return {}
    
    def cleanup_orphaned_nodes(self) -> int:
        """清理孤立的图节点"""
        try:
            session = self._get_db_session()
            
            # 查找没有关系的孤立节点
            orphaned_nodes = session.query(Node).outerjoin(
                Relationship, 
                or_(
                    Node.id == Relationship.source_id,
                    Node.id == Relationship.target_id
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
    
    def get_relationship_by_node(self, source: 'DefaultObject', target: 'DefaultObject', rel_code: str) -> Optional[List[Relationship]]:
        """根据源节点和目标节点获取关系列表"""
        try:
            session = self._get_db_session()
            return session.query(Relationship).filter(
                and_(
                    Relationship.source_id == source.id, 
                    Relationship.target_id == target.id, 
                    Relationship.type_code == rel_code,
                    Relationship.is_active == True
                )
            ).all()
        except Exception as e:
            self.logger.error(f"获取关系失败: {e}")
            return None

    # ==================== 新增查询方法 ====================
    
    def get_node_by_name(self, name: str, node_type: str = None) -> Optional[Node]:
        """根据名称获取节点"""
        try:
            session = self._get_db_session()
            query = session.query(Node).filter(Node.name == name)
            if node_type:
                query = query.filter(Node.type_code == node_type)
            return query.first()
        except Exception as e:
            self.logger.error(f"根据名称获取节点失败: {e}")
            return None
    
    def get_node_by_code(self, type_code: str) -> Optional[Node]:
        """根据类型代码获取节点"""
        try:
            session = self._get_db_session()
            return session.query(Node).filter(Node.type_code == type_code).first()
        except Exception as e:
            self.logger.error(f"根据类型代码获取节点失败: {e}")
            return None
    
    def get_nodes_by_type(self, node_type: str) -> List[Node]:
        """根据类型获取节点列表"""
        try:
            session = self._get_db_session()
            return session.query(Node).filter(Node.type_code == node_type).all()
        except Exception as e:
            self.logger.error(f"根据类型获取节点失败: {e}")
            return []
    
    def get_active_nodes_by_type(self, node_type: str) -> List[Node]:
        """根据类型获取活跃节点列表"""
        try:
            session = self._get_db_session()
            return session.query(Node).filter(
                Node.type_code == node_type,
                Node.is_active == True
            ).all()
        except Exception as e:
            self.logger.error(f"根据类型获取活跃节点失败: {e}")
            return []
    
    def find_nodes_by_attribute(self, key: str, value: Any, node_type: str = None) -> List[Node]:
        """根据属性查找节点"""
        try:
            session = self._get_db_session()
            query = session.query(Node).filter(Node.attributes.contains({key: value}))
            if node_type:
                query = query.filter(Node.type_code == node_type)
            return query.all()
        except Exception as e:
            self.logger.error(f"根据属性查找节点失败: {e}")
            return []
    
    def find_nodes_by_tag(self, tag: str, node_type: str = None) -> List[Node]:
        """根据标签查找节点"""
        try:
            session = self._get_db_session()
            query = session.query(Node).filter(Node.tags.contains([tag]))
            if node_type:
                query = query.filter(Node.type_code == node_type)
            return query.all()
        except Exception as e:
            self.logger.error(f"根据标签查找节点失败: {e}")
            return []
    
    def get_node_type_by_code(self, type_code: str) -> Optional[NodeType]:
        """根据类型代码获取节点类型"""
        try:
            session = self._get_db_session()
            return NodeType.get_by_type_code(session, type_code)
        except Exception as e:
            self.logger.error(f"根据类型代码获取节点类型失败: {e}")
            return None
    
    def get_node_type_by_name(self, type_name: str) -> Optional[NodeType]:
        """根据类型名称获取节点类型"""
        try:
            session = self._get_db_session()
            return session.query(NodeType).filter(NodeType.type_name == type_name).first()
        except Exception as e:
            self.logger.error(f"根据类型名称获取节点类型失败: {e}")
            return None
    
    def get_all_node_types(self) -> List[NodeType]:
        """获取所有节点类型"""
        try:
            session = self._get_db_session()
            return NodeType.get_active_types(session)
        except Exception as e:
            self.logger.error(f"获取所有节点类型失败: {e}")
            return []
    
    def create_node_type(self, type_code: str, type_name: str, typeclass: str, 
                        classname: str, module_path: str, description: str = None,
                        schema_definition: Dict[str, Any] = None) -> Optional[NodeType]:
        """创建节点类型"""
        try:
            session = self._get_db_session()
            
            # 检查是否已存在
            existing = NodeType.get_by_type_code(session, type_code)
            if existing:
                self.logger.warning(f"节点类型已存在: {type_code}")
                return existing
            
            # 创建新节点类型
            node_type = NodeType(
                type_code=type_code,
                type_name=type_name,
                typeclass=typeclass,
                classname=classname,
                module_path=module_path,
                description=description,
                schema_definition=schema_definition or {}
            )
            
            session.add(node_type)
            session.commit()
            return node_type
            
        except Exception as e:
            self.logger.error(f"创建节点类型失败: {e}")
            return None
    
    def update_node_type(self, type_code: str, **updates) -> bool:
        """更新节点类型"""
        try:
            session = self._get_db_session()
            node_type = NodeType.get_by_type_code(session, type_code)
            if not node_type:
                self.logger.warning(f"节点类型不存在: {type_code}")
                return False
            
            # 更新字段
            for key, value in updates.items():
                if hasattr(node_type, key):
                    setattr(node_type, key, value)
            
            session.commit()
            return True
        except Exception as e:
            self.logger.error(f"更新节点类型失败: {e}")
            return False
    
    def delete_node_type(self, type_code: str) -> bool:
        """删除节点类型"""
        try:
            session = self._get_db_session()
            node_type = NodeType.get_by_type_code(session, type_code)
            if not node_type:
                self.logger.warning(f"节点类型不存在: {type_code}")
                return False
            
            # 标记为不活跃
            node_type.is_active = False
            session.commit()
            return True
        except Exception as e:
            self.logger.error(f"删除节点类型失败: {e}")
            return False
    
    def get_relationship_type_by_code(self, type_code: str) -> Optional[RelationshipType]:
        """根据类型代码获取关系类型"""
        try:
            session = self._get_db_session()
            return RelationshipType.get_by_type_code(session, type_code)
        except Exception as e:
            self.logger.error(f"根据类型代码获取关系类型失败: {e}")
            return None
    
    def get_relationship_type_by_name(self, type_name: str) -> Optional[RelationshipType]:
        """根据类型名称获取关系类型"""
        try:
            session = self._get_db_session()
            return session.query(RelationshipType).filter(RelationshipType.type_name == type_name).first()
        except Exception as e:
            self.logger.error(f"根据类型名称获取关系类型失败: {e}")
            return None
    
    def get_all_relationship_types(self) -> List[RelationshipType]:
        """获取所有关系类型"""
        try:
            session = self._get_db_session()
            return RelationshipType.get_active_types(session)
        except Exception as e:
            self.logger.error(f"获取所有关系类型失败: {e}")
            return []
    
    def create_relationship_type(self, type_code: str, type_name: str, typeclass: str,
                               description: str = None, is_directed: bool = True,
                               is_symmetric: bool = False, is_transitive: bool = False,
                               schema_definition: Dict[str, Any] = None) -> Optional[RelationshipType]:
        """创建关系类型"""
        try:
            session = self._get_db_session()
            
            # 检查是否已存在
            existing = RelationshipType.get_by_type_code(session, type_code)
            if existing:
                self.logger.warning(f"关系类型已存在: {type_code}")
                return existing
            
            # 创建新关系类型
            rel_type = RelationshipType(
                type_code=type_code,
                type_name=type_name,
                typeclass=typeclass,
                description=description,
                is_directed=is_directed,
                is_symmetric=is_symmetric,
                is_transitive=is_transitive,
                schema_definition=schema_definition or {}
            )
            
            session.add(rel_type)
            session.commit()
            return rel_type
            
        except Exception as e:
            self.logger.error(f"创建关系类型失败: {e}")
            return None
    
    def update_relationship_type(self, type_code: str, **updates) -> bool:
        """更新关系类型"""
        try:
            session = self._get_db_session()
            rel_type = RelationshipType.get_by_type_code(session, type_code)
            if not rel_type:
                self.logger.warning(f"关系类型不存在: {type_code}")
                return False
            
            # 更新字段
            for key, value in updates.items():
                if hasattr(rel_type, key):
                    setattr(rel_type, key, value)
            
            session.commit()
            return True
        except Exception as e:
            self.logger.error(f"更新关系类型失败: {e}")
            return False
    
    def delete_relationship_type(self, type_code: str) -> bool:
        """删除关系类型"""
        try:
            session = self._get_db_session()
            rel_type = RelationshipType.get_by_type_code(session, type_code)
            if not rel_type:
                self.logger.warning(f"关系类型不存在: {type_code}")
                return False
            
            # 标记为不活跃
            rel_type.is_active = False
            session.commit()
            return True
        except Exception as e:
            self.logger.error(f"删除关系类型失败: {e}")
            return False
    
    def update_relationship(self, rel_id: int, **attributes) -> bool:
        """更新关系"""
        try:
            session = self._get_db_session()
            relationship = session.query(Relationship).filter(Relationship.id == rel_id).first()
            if not relationship:
                self.logger.warning(f"关系不存在: {rel_id}")
                return False
            
            # 更新属性
            for key, value in attributes.items():
                relationship.set_attribute(key, value)
            
            session.commit()
            return True
        except Exception as e:
            self.logger.error(f"更新关系失败: {e}")
            return False
    
    def delete_relationship(self, rel_id: int) -> bool:
        """删除关系"""
        try:
            session = self._get_db_session()
            relationship = session.query(Relationship).filter(Relationship.id == rel_id).first()
            if not relationship:
                self.logger.warning(f"关系不存在: {rel_id}")
                return False
            
            # 标记为不活跃
            relationship.is_active = False
            session.commit()
            return True
        except Exception as e:
            self.logger.error(f"删除关系失败: {e}")
            return False