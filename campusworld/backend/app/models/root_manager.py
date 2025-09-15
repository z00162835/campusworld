"""
根节点管理器 - 纯图数据设计

负责管理系统的根节点（Singularity Room）
参考Evennia的DefaultHome管理机制
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from .graph import Node, NodeType
from .room import SingularityRoom
from app.core.database import SessionLocal
from app.core.log import get_logger, LoggerNames


class RootNodeManager:
    """
    根节点管理器
    
    负责创建、管理和维护系统的根节点
    确保Singularity Room作为所有用户的默认home存在
    """
    
    def __init__(self):
        self.logger = get_logger(LoggerNames.GAME)
        self._root_node_id: Optional[int] = None
        self._root_node_uuid: Optional[str] = None
    
    @property
    def root_node_id(self) -> Optional[int]:
        """获取根节点ID"""
        return self._root_node_id
    
    @property
    def root_node_uuid(self) -> Optional[str]:
        """获取根节点UUID"""
        return self._root_node_uuid
    
    def initialize_root_node(self, force_recreate: bool = False) -> bool:
        """
        初始化根节点
        
        Args:
            force_recreate: 是否强制重新创建根节点
            
        Returns:
            bool: 初始化是否成功
        """
        try:
            session = SessionLocal()
            try:
                # 检查是否已存在根节点
                existing_root = self._get_existing_root_node(session)
                
                if existing_root and not force_recreate:
                    self._root_node_id = existing_root.id
                    self._root_node_uuid = str(existing_root.uuid)
                    self.logger.info(f"根节点已存在: {existing_root.name} (ID: {existing_root.id})")
                    return True
                
                # 如果存在旧根节点且需要重新创建，先删除
                if existing_root and force_recreate:
                    self.logger.info(f"删除现有根节点: {existing_root.name}")
                    self._delete_root_node(session, existing_root.id)
                
                # 创建新的根节点
                root_room = self._create_singularity_room(session)
                if root_room:
                    self._root_node_id = root_room.id
                    self._root_node_uuid = str(root_room.uuid)
                    self.logger.info(f"根节点创建成功: {root_room.name} (ID: {root_room.id})")
                    return True
                else:
                    self.logger.error("根节点创建失败")
                    return False
                    
            finally:
                session.close()
                
        except Exception as e:
            self.logger.error(f"初始化根节点失败: {e}")
            return False
    
    def _get_existing_root_node(self, session: Session) -> Optional[Node]:
        """获取现有的根节点"""
        try:
            # 查找标记为根节点的房间
            root_node = session.query(Node).filter(
                and_(
                    Node.type_code == 'room',
                    Node.attributes['is_root'].astext == 'true'
                )
            ).first()
            
            return root_node
        except Exception as e:
            self.logger.error(f"查找现有根节点失败: {e}")
            return None
    
    def _create_singularity_room(self, session: Session) -> Optional[Node]:
        """创建奇点房间"""
        try:
            # 创建SingularityRoom实例
            singularity_room = SingularityRoom()
            
            # 获取或创建room类型
            room_type_id = self._get_or_create_room_type(session)
            if not room_type_id:
                self.logger.error("无法获取room类型ID")
                return None
            
            # 创建Node记录
            node = Node(
                uuid=singularity_room._node_uuid,
                type_id=room_type_id,
                type_code='room',
                name=singularity_room._node_name,
                description=singularity_room.room_description,
                is_active=True,
                is_public=True,
                access_level='normal',
                attributes=singularity_room._node_attributes,
                tags=singularity_room._node_attributes.get('tags', [])
            )
            
            session.add(node)
            session.commit()
            session.refresh(node)
            
            self.logger.info(f"奇点房间创建成功: {node.name} (UUID: {node.uuid})")
            return node
            
        except Exception as e:
            self.logger.error(f"创建奇点房间失败: {e}")
            session.rollback()
            return None
    
    def _get_or_create_room_type(self, session: Session) -> Optional[int]:
        """获取或创建room类型"""
        try:
            
            # 查找现有的room类型
            room_type = session.query(NodeType).filter(
                NodeType.type_code == 'room'
            ).first()
            
            if room_type:
                return room_type.id
            
            # 创建新的room类型
            room_type = NodeType(
                type_code='room',
                type_name='Room',
                typeclass='app.models.room.Room',
                classname='Room',
                module_path='app.models.room',
                description='场景世界中的房间/地点',
                schema_definition={
                    'room_type': 'string',
                    'room_description': 'text',
                    'is_root': 'boolean',
                    'is_home': 'boolean',
                    'room_capacity': 'integer'
                },
                is_active=True
            )
            
            session.add(room_type)
            session.commit()
            session.refresh(room_type)
            
            return room_type.id
            
        except Exception as e:
            self.logger.error(f"获取或创建room类型失败: {e}")
            return None
    
    def _delete_root_node(self, session: Session, node_id: int) -> bool:
        """删除根节点"""
        try:
            # 查找节点
            node = session.query(Node).filter(Node.id == node_id).first()
            if not node:
                return True  # 节点不存在，认为删除成功
            
            # 检查是否有其他节点依赖此节点
            dependent_nodes = session.query(Node).filter(
                Node.location_id == node_id
            ).count()
            
            if dependent_nodes > 0:
                self.logger.warning(f"根节点有{dependent_nodes}个依赖节点，无法删除")
                return False
            
            # 删除节点
            session.delete(node)
            session.commit()
            
            self.logger.info(f"根节点删除成功: {node.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"删除根节点失败: {e}")
            session.rollback()
            return False
    
    def get_root_node(self, session: Session = None) -> Optional[Node]:
        """获取根节点"""
        try:
            if session is None:
                session = SessionLocal()
                should_close = True
            else:
                should_close = False
            
            try:
                if self._root_node_id:
                    # 使用缓存的ID查找
                    root_node = session.query(Node).filter(
                        Node.id == self._root_node_id
                    ).first()
                else:
                    # 重新查找根节点
                    root_node = self._get_existing_root_node(session)
                    if root_node:
                        self._root_node_id = root_node.id
                        self._root_node_uuid = str(root_node.uuid)
                
                return root_node
                
            finally:
                if should_close:
                    session.close()
                    
        except Exception as e:
            self.logger.error(f"获取根节点失败: {e}")
            return None
    
    def is_root_node(self, node_id: int) -> bool:
        """检查指定节点是否为根节点"""
        try:
            session = SessionLocal()
            try:
                node = session.query(Node).filter(Node.id == node_id).first()
                if not node:
                    return False
                
                return node.attributes.get('is_root', False) if node.attributes else False
                
            finally:
                session.close()
                
        except Exception as e:
            self.logger.error(f"检查根节点失败: {e}")
            return False
    
    def get_root_node_info(self) -> Optional[Dict[str, Any]]:
        """获取根节点信息"""
        try:
            session = SessionLocal()
            try:
                root_node = self.get_root_node(session)
                if not root_node:
                    return None
                
                return {
                    'id': root_node.id,
                    'uuid': str(root_node.uuid),
                    'name': root_node.name,
                    'type': root_node.type_code,
                    'description': root_node.description,
                    'is_active': root_node.is_active,
                    'is_public': root_node.is_public,
                    'access_level': root_node.access_level,
                    'is_root': root_node.attributes.get('is_root', False) if root_node.attributes else False,
                    'is_home': root_node.attributes.get('is_home', False) if root_node.attributes else False,
                    'room_capacity': root_node.attributes.get('room_capacity', 0) if root_node.attributes else 0,
                    'created_at': root_node.created_at.isoformat() if root_node.created_at else None,
                    'updated_at': root_node.updated_at.isoformat() if root_node.updated_at else None
                }
                
            finally:
                session.close()
                
        except Exception as e:
            self.logger.error(f"获取根节点信息失败: {e}")
            return None
    
    def ensure_root_node_exists(self) -> bool:
        """确保根节点存在，如果不存在则创建"""
        try:
            session = SessionLocal()
            try:
                root_node = self.get_root_node(session)
                if root_node:
                    return True
                
                # 根节点不存在，创建它
                self.logger.info("根节点不存在，开始创建...")
                return self.initialize_root_node(force_recreate=False)
                
            finally:
                session.close()
                
        except Exception as e:
            self.logger.error(f"确保根节点存在失败: {e}")
            return False
    
    def get_users_in_root(self) -> List[Dict[str, Any]]:
        """获取在根节点的用户列表"""
        try:
            session = SessionLocal()
            try:
                root_node = self.get_root_node(session)
                if not root_node:
                    return []
                
                # 查找位置在根节点的用户
                users_in_root = session.query(Node).filter(
                    and_(
                        Node.type_code == 'user',
                        Node.location_id == root_node.id,
                        Node.is_active == True
                    )
                ).all()
                
                user_list = []
                for user_node in users_in_root:
                    user_info = {
                        'id': user_node.id,
                        'uuid': str(user_node.uuid),
                        'username': user_node.attributes.get('username', 'Unknown') if user_node.attributes else 'Unknown',
                        'email': user_node.attributes.get('email', '') if user_node.attributes else '',
                        'last_activity': user_node.attributes.get('last_activity') if user_node.attributes else None,
                        'created_at': user_node.created_at.isoformat() if user_node.created_at else None
                    }
                    user_list.append(user_info)
                
                return user_list
                
            finally:
                session.close()
                
        except Exception as e:
            self.logger.error(f"获取根节点用户列表失败: {e}")
            return []
    
    def get_root_node_statistics(self) -> Dict[str, Any]:
        """获取根节点统计信息"""
        try:
            session = SessionLocal()
            try:
                root_node = self.get_root_node(session)
                if not root_node:
                    return {}
                
                # 统计在根节点的用户数量
                user_count = session.query(Node).filter(
                    and_(
                        Node.type_code == 'user',
                        Node.location_id == root_node.id,
                        Node.is_active == True
                    )
                ).count()
                
                # 统计在根节点的对象数量
                object_count = session.query(Node).filter(
                    and_(
                        Node.location_id == root_node.id,
                        Node.is_active == True
                    )
                ).count()
                
                return {
                    'root_node_id': root_node.id,
                    'root_node_name': root_node.name,
                    'users_in_root': user_count,
                    'objects_in_root': object_count,
                    'is_active': root_node.is_active,
                    'is_public': root_node.is_public,
                    'room_capacity': root_node.attributes.get('room_capacity', 0) if root_node.attributes else 0,
                    'is_full': object_count >= (root_node.attributes.get('room_capacity', 0) if root_node.attributes else 0),
                    'timestamp': datetime.now().isoformat()
                }
                
            finally:
                session.close()
                
        except Exception as e:
            self.logger.error(f"获取根节点统计信息失败: {e}")
            return {}


# 全局根节点管理器实例
root_manager = RootNodeManager()
