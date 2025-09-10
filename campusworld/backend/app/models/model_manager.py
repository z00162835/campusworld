"""
模型管理器

"""

from typing import Dict, Any, List, Optional, Type, Union, TYPE_CHECKING
from datetime import datetime
import json
import uuid
from abc import ABC, abstractmethod
import importlib
from contextlib import contextmanager

from .base import DefaultObject
from .graph_sync import GraphSynchronizer
from .graph import Node, Relationship, NodeType, RelationshipType

class ModelManager(ABC):
    """
    模型管理器抽象基类
    
    定义模型管理的基本接口
    """
    
    @abstractmethod
    def get_attribute(self, obj: DefaultObject, key: str, default: Any = None) -> Any:
        """获取属性"""
        pass
    
    @abstractmethod
    def set_attribute(self, obj: DefaultObject, key: str, value: Any) -> bool:
        """设置属性"""
        pass
    
    @abstractmethod
    def remove_attribute(self, obj: DefaultObject, key: str) -> bool:
        """移除属性"""
        pass
    
    @abstractmethod
    def get_all_attributes(self, obj: DefaultObject) -> Dict[str, Any]:
        """获取所有属性"""
        pass
    
    @abstractmethod
    def update_attributes(self, obj: DefaultObject, attributes: Dict[str, Any]) -> bool:
        """批量更新属性"""
        pass


class ModelManager(ModelManager):
    """
    模型管理器
    """
    
    def __init__(self, synchronizer: GraphSynchronizer = None):
        self.synchronizer = synchronizer or GraphSynchronizer()
        self.logger = self.synchronizer.logger
        
        # 类型缓存，避免重复查询数据库
        self._node_type_cache: Dict[str, NodeType] = {}
        self._relationship_type_cache: Dict[str, RelationshipType] = {}
        self._class_cache: Dict[str, Type[DefaultObject]] = {}
        
        # 初始化类型缓存
        self._load_type_caches()
    
    def _load_type_caches(self):
        """加载类型缓存"""
        try:
            # 通过GraphSynchronizer获取节点类型
            node_types = self.synchronizer.get_all_node_types()
            for node_type in node_types:
                self._node_type_cache[node_type.type_code] = node_type
            
            # 通过GraphSynchronizer获取关系类型
            rel_types = self.synchronizer.get_all_relationship_types()
            for rel_type in rel_types:
                self._relationship_type_cache[rel_type.type_code] = rel_type
 
        except Exception as e:
            self.logger.error(f"加载类型缓存失败: {e}")
    
    def _get_node_type_class(self, type_code: str) -> Optional[Type[DefaultObject]]:
        """根据类型代码获取节点类"""
        # 先查缓存
        if type_code in self._class_cache:
            return self._class_cache[type_code]
        
        try:
            # 从缓存获取节点类型
            node_type = self._node_type_cache.get(type_code)
            if not node_type:
                # 通过GraphSynchronizer获取
                node_type = self.synchronizer.get_node_type_by_code(type_code)
                if node_type:
                    self._node_type_cache[type_code] = node_type
            
            if not node_type:
                self.logger.warning(f"未找到节点类型: {type_code}")
                return None
            
            # 动态导入类
            module_path = node_type.module_path
            class_name = node_type.classname
            
            try:
                module = importlib.import_module(module_path)
                obj_class = getattr(module, class_name)
                self._class_cache[type_code] = obj_class
                return obj_class
            except (ImportError, AttributeError) as e:
                self.logger.error(f"动态导入类失败 {module_path}.{class_name}: {e}")
                return None
                
        except Exception as e:
            self.logger.error(f"获取节点类型类失败: {e}")
            return None
    
    def _get_relationship_type(self, type_code: str) -> Optional[RelationshipType]:
        """根据类型代码获取关系类型"""
        # 先查缓存
        if type_code in self._relationship_type_cache:
            return self._relationship_type_cache[type_code]
        
        try:
            # 通过GraphSynchronizer获取
            rel_type = self.synchronizer.get_relationship_type_by_code(type_code)
            if rel_type:
                self._relationship_type_cache[type_code] = rel_type
            return rel_type
                
        except Exception as e:
            self.logger.error(f"获取关系类型失败: {e}")
            return None
    
    # ==================== 基础属性管理 ====================
    
    def get_attribute(self, obj: DefaultObject, key: str, default: Any = None) -> Any:
        """获取对象属性"""
        try:
            return obj.get_node_attribute(key, default)
        except Exception as e:
            self.logger.error(f"获取属性失败: {e}")
            return default
    
    def set_attribute(self, obj: DefaultObject, key: str, value: Any) -> bool:
        """设置对象属性"""
        try:
            obj.set_node_attribute(key, value)
            return True
        except Exception as e:
            self.logger.error(f"设置属性失败: {e}")
            return False
    
    def remove_attribute(self, obj: DefaultObject, key: str) -> bool:
        """移除对象属性"""
        try:
            if key in obj.get_node_attributes():
                obj.update_timestamp()
                obj.remove_node_attribute(key)
                return True
            return False
        except Exception as e:
            self.logger.error(f"移除属性失败: {e}")
            return False
    
    def get_all_attributes(self, obj: DefaultObject) -> Dict[str, Any]:
        """获取对象所有属性"""
        try:
            return obj.get_node_attributes()
        except Exception as e:
            self.logger.error(f"获取所有属性失败: {e}")
            return {}
    
    def update_attributes(self, obj: DefaultObject, attributes: Dict[str, Any]) -> bool:
        """批量更新对象属性"""
        try:
            for key, value in attributes.items():
                obj.set_node_attribute(key, value)
            return True
        except Exception as e:
            self.logger.error(f"批量更新属性失败: {e}")
            return False
    
    # ==================== 标签管理 ====================
    
    def get_tags(self, obj: DefaultObject) -> List[str]:
        """获取对象标签"""
        try:
            return obj.get_node_tags()
        except Exception as e:
            self.logger.error(f"获取标签失败: {e}")
            return []
    
    def add_tag(self, obj: DefaultObject, tag: str) -> bool:
        """添加标签"""
        try:
            obj.add_node_tag(tag)
            return True
        except Exception as e:
            self.logger.error(f"添加标签失败: {e}")
            return False
    
    def remove_tag(self, obj: DefaultObject, tag: str) -> bool:
        """移除标签"""
        try:
            obj.remove_node_tag(tag)
            return True
        except Exception as e:
            self.logger.error(f"移除标签失败: {e}")
            return False
    
    def has_tag(self, obj: DefaultObject, tag: str) -> bool:
        """检查是否有指定标签"""
        try:
            # 修复：使用正确的方法
            return tag in obj.get_node_tags()
        except Exception as e:
            self.logger.error(f"检查标签失败: {e}")
            return False
    
    def set_tags(self, obj: DefaultObject, tags: List[str]) -> bool:
        """设置标签列表（替换现有标签）"""
        try:
            obj.set_node_tags(tags)
            return True
        except Exception as e:
            self.logger.error(f"设置标签失败: {e}")
            return False
    
    # ==================== 单个Node操作方法 ====================
    
    def create_node(self, name: str, node_type: str, attributes: Dict[str, Any] = None) -> Optional[DefaultObject]:
        """创建单个节点"""
        try:
            # 获取节点类
            node_class = self._get_node_type_class(node_type)
            if not node_class:
                self.logger.error(f"未找到节点类型对应的类: {node_type}")
                return None
            
            # 创建节点 - 修复参数名
            node = node_class(name=name, **attributes or {})
            return node
            
        except Exception as e:
            self.logger.error(f"创建节点失败: {e}")
            return None
    
    def get_node_by_uuid(self, uuid: str) -> Optional[DefaultObject]:
        """根据UUID获取节点"""
        try:
            node = self.synchronizer.get_node_by_uuid(uuid)
            if node:
                return self._node_to_object(node)
            return None
        except Exception as e:
            self.logger.error(f"根据UUID获取节点失败: {e}")
            return None
    
    def get_node_by_name(self, name: str, node_type: str = None) -> Optional[DefaultObject]:
        """根据名称获取节点 - 通过GraphSynchronizer"""
        try:
            node = self.synchronizer.get_node_by_name(name, node_type)
            if node:
                return self._node_to_object(node)
            return None
        except Exception as e:
            self.logger.error(f"根据名称获取节点失败: {e}")
            return None
    
    def update_node_attributes(self, node: DefaultObject, attributes: Dict[str, Any] = None) -> bool:
        """更新单个节点"""
        try:
            # 更新属性
            if attributes:
                self.update_attributes(node, attributes)
        
            # 更新时间戳
            node.update_timestamp()
            
            return True
            
        except Exception as e:
            self.logger.error(f"更新节点失败: {e}")
            return False
    
    def update_node_tags(self, node: DefaultObject, tags: List[str]) -> bool:
        """更新节点标签"""
        try:
            self.set_tags(node, tags)
            return True
        except Exception as e:
            self.logger.error(f"更新节点标签失败: {e}")
            return False
    
    def delete_node(self, node: DefaultObject) -> bool:
        """删除单个节点, 未实际删除, 只是标记为不活跃"""
        try:
            # 使用对象的方法，会自动同步到数据库
            node.set_node_active(False)
            return True
        except Exception as e:
            self.logger.error(f"删除节点失败: {e}")
            return False
    
    def _node_to_object(self, node: Node) -> Optional[DefaultObject]:
        """将Node转换为DefaultObject"""
        try:
            # 获取节点类
            node_class = self._get_node_type_class(node.type_code)
            if not node_class:
                self.logger.warning(f"未找到节点类型对应的类: {node.type_code}")
                return None
            
            # 创建对象 - 修复参数名
            obj = node_class(name=node.name, **node.attributes or {})
            obj._node_uuid = str(node.uuid)
            return obj
        except Exception as e:
            self.logger.error(f"转换Node到Object失败: {e}")
            return None
    
    # ==================== NodeType操作方法 - 通过GraphSynchronizer ====================
    
    def create_node_type(self, type_code: str, type_name: str, typeclass: str, 
                        classname: str, module_path: str, description: str = None,
                        schema_definition: Dict[str, Any] = None) -> Optional[NodeType]:
        """创建节点类型 - 通过GraphSynchronizer"""
        try:
            return self.synchronizer.create_node_type(
                type_code=type_code,
                type_name=type_name,
                typeclass=typeclass,
                classname=classname,
                module_path=module_path,
                description=description,
                schema_definition=schema_definition
            )
        except Exception as e:
            self.logger.error(f"创建节点类型失败: {e}")
            return None
    
    def get_node_type(self, type_code: str) -> Optional[NodeType]:
        """获取节点类型 - 通过GraphSynchronizer"""
        return self.synchronizer.get_node_type_by_code(type_code)
    
    def get_all_node_types(self) -> List[NodeType]:
        """获取所有节点类型 - 通过GraphSynchronizer"""
        return self.synchronizer.get_all_node_types()
    
    def update_node_type(self, type_code: str, **updates) -> bool:
        """更新节点类型 - 通过GraphSynchronizer"""
        try:
            return self.synchronizer.update_node_type(type_code, **updates)
        except Exception as e:
            self.logger.error(f"更新节点类型失败: {e}")
            return False
    
    def delete_node_type(self, type_code: str) -> bool:
        """删除节点类型"""
        try:
            return self.synchronizer.delete_node_type(type_code)
        except Exception as e:
            self.logger.error(f"删除节点类型失败: {e}")
            return False
    
    # ==================== 关系管理====================
    
    def create_relationship(self, source: DefaultObject, target: DefaultObject, 
                          rel_type: str, **attributes) -> Optional[Relationship]:
        """创建关系"""
        try:
            return self.synchronizer.create_relationship(source, target, rel_type, **attributes)
        except Exception as e:
            self.logger.error(f"创建关系失败: {e}")
            return None
    
    def get_relationship_by_node(self, source: DefaultObject, target: DefaultObject, rel_code: str) -> Optional[List[Relationship]]:
        """根据源节点和目标节点获取关系列表"""
        try:
            return self.synchronizer.get_relationship_by_node(source, target, rel_code)
        except Exception as e:
            self.logger.error(f"获取关系失败: {e}")
            return None
            
    def get_relationships(self, obj: DefaultObject, rel_type: str = None) -> List[Relationship]:
        """获取对象关系"""
        try:
            return self.synchronizer.get_object_relationships(obj, rel_type)
        except Exception as e:
            self.logger.error(f"获取关系失败: {e}")
            return []
    
    def update_relationship(self, rel_id: int, **attributes) -> bool:
        """更新关系"""
        try:
            return self.synchronizer.update_relationship(rel_id, **attributes)
        except Exception as e:
            self.logger.error(f"更新关系失败: {e}")
            return False
    
    def delete_relationship(self, rel_id: int) -> bool:
        """删除关系"""
        try:
            return self.synchronizer.delete_relationship(rel_id)
        except Exception as e:
            self.logger.error(f"删除关系失败: {e}")
            return False
    
    def remove_relationship(self, source: DefaultObject, target: DefaultObject, 
                          rel_type: str) -> bool:
        """移除关系"""
        try:
            return self.synchronizer.remove_relationship(source, target, rel_type)
        except Exception as e:
            self.logger.error(f"移除关系失败: {e}")
            return False
    
    # ==================== RelationshipType操作方法 ====================
    
    def create_relationship_type(self, type_code: str, type_name: str, typeclass: str,
                               description: str = None, is_directed: bool = True,
                               is_symmetric: bool = False, is_transitive: bool = False,
                               schema_definition: Dict[str, Any] = None) -> Optional[RelationshipType]:
        """创建关系类型"""
        try:
            return self.synchronizer.create_relationship_type(
                type_code=type_code,
                type_name=type_name,
                typeclass=typeclass,
                description=description,
                is_directed=is_directed,
                is_symmetric=is_symmetric,
                is_transitive=is_transitive,
                schema_definition=schema_definition
            )
        except Exception as e:
            self.logger.error(f"创建关系类型失败: {e}")
            return None
    
    def get_relationship_type(self, type_code: str) -> Optional[RelationshipType]:
        """获取关系类型"""
        return self._get_relationship_type(type_code)
    
    def get_all_relationship_types(self) -> List[RelationshipType]:
        """获取所有关系类型"""
        try:
            return self.synchronizer.get_all_relationship_types()
        except Exception as e:
            self.logger.error(f"获取所有关系类型失败: {e}")
            return []
    
    def update_relationship_type(self, type_code: str, **updates) -> bool:
        """更新关系类型"""
        try:
            return self.synchronizer.update_relationship_type(type_code, **updates)
        except Exception as e:
            self.logger.error(f"更新关系类型失败: {e}")
            return False
    
    def delete_relationship_type(self, type_code: str) -> bool:
        """删除关系类型"""
        try:
            return self.synchronizer.delete_relationship_type(type_code)
        except Exception as e:
            self.logger.error(f"删除关系类型失败: {e}")
            return False
    
    # ==================== 优化后的批量生成Node ====================
    
    def batch_create_nodes(self, node_configs: List[Dict[str, Any]]) -> List[DefaultObject]:
        """
        批量创建Node
        
        Args:
            node_configs: 节点配置列表，每个配置包含name、type和attributes
            
        Returns:
            创建成功的节点列表
        """
        created_nodes = []
        
        for config in node_configs:
            try:
                name = config.get('name')
                node_type = config.get('type')
                attributes = config.get('attributes', {})
                
                if not name:
                    self.logger.warning("节点配置缺少name字段，跳过")
                    continue
                
                if not node_type:
                    self.logger.warning("节点配置缺少type字段，跳过")
                    continue
                
                # 从NodeType表获取具体类
                node_class = self._get_node_type_class(node_type)
                if not node_class:
                    self.logger.warning(f"未找到节点类型对应的类: {node_type}")
                    continue
                
                # 创建节点
                node = node_class(name=name, config=attributes)
                created_nodes.append(node)
                
            except Exception as e:
                self.logger.error(f"创建节点失败: {e}")
                continue
        
        return created_nodes
    
    def batch_create_nodes_by_type(self, node_configs: List[Dict[str, Any]], 
                                 node_type: str) -> List[DefaultObject]:
        """
        批量创建指定类型的Node
        
        Args:
            node_configs: 节点配置列表，每个配置包含name和attributes
            node_type: 节点类型
            
        Returns:
            创建成功的节点列表
        """
        # 为每个配置添加类型信息
        typed_configs = []
        for config in node_configs:
            typed_config = config.copy()
            typed_config['type'] = node_type
            typed_configs.append(typed_config)
        
        return self.batch_create_nodes(typed_configs)
    
    # ==================== 查询和过滤 ====================
    
    def get_nodes_by_type(self, node_type: str) -> List[DefaultObject]:
        """根据类型获取节点列表"""
        try:
            nodes = self.synchronizer.get_nodes_by_type(node_type)
            objects = []
            for node in nodes:
                obj = self._node_to_object(node)
                if obj:
                    objects.append(obj)
            return objects
        except Exception as e:
            self.logger.error(f"根据类型获取节点失败: {e}")
            return []
    
    def get_active_nodes_by_type(self, node_type: str) -> List[DefaultObject]:
        """根据类型获取活跃节点列表"""
        try:
            nodes = self.synchronizer.get_active_nodes_by_type(node_type)
            objects = []
            for node in nodes:
                obj = self._node_to_object(node)
                if obj:
                    objects.append(obj)
            return objects
        except Exception as e:
            self.logger.error(f"根据类型获取活跃节点失败: {e}")
            return []
    
    def find_nodes_by_attribute(self, node_type: str, key: str, value: Any) -> List[DefaultObject]:
        """根据属性查找节点"""
        try:
            nodes = self.synchronizer.find_nodes_by_attribute(key, value, node_type)
            objects = []
            for node in nodes:
                obj = self._node_to_object(node)
                if obj:
                    objects.append(obj)
            return objects
        except Exception as e:
            self.logger.error(f"根据属性查找节点失败: {e}")
            return []
    
    def find_nodes_by_tag(self, node_type: str, tag: str) -> List[DefaultObject]:
        """根据标签查找节点"""
        try:
            nodes = self.synchronizer.find_nodes_by_tag(tag, node_type)
            objects = []
            for node in nodes:
                obj = self._node_to_object(node)
                if obj:
                    objects.append(obj)
            return objects
        except Exception as e:
            self.logger.error(f"根据标签查找节点失败: {e}")
            return []
    
    # ==================== 统计和监控 ====================
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            stats = self.synchronizer.get_sync_stats()
            stats.update({
                'node_types_count': len(self._node_type_cache),
                'relationship_types_count': len(self._relationship_type_cache),
                'generated_at': datetime.now().isoformat()
            })
            return stats
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def refresh_type_caches(self):
        """刷新类型缓存"""
        self._load_type_caches()
    
    # ==================== 批量操作 ====================
    
    def batch_validate_objects(self, objects: List[DefaultObject]) -> Dict[str, List[str]]:
        """批量验证对象"""
        results = {}
        for obj in objects:
            obj_id = obj.get_node_uuid()
            results[obj_id] = obj.validate_attributes()
        return results
    
    def batch_sync_objects(self, objects: List[DefaultObject]) -> List[DefaultObject]:
        """批量同步对象"""
        synced_objects = []
        for obj in objects:
            try:
                obj.sync_to_node()
                synced_objects.append(obj)
            except Exception as e:
                self.logger.error(f"同步对象 {obj.get_node_name()} 失败: {e}")
        return synced_objects
    
    def batch_reset_objects(self, objects: List[DefaultObject]) -> int:
        """批量重置对象"""
        success_count = 0
        for obj in objects:
            try:
                obj.reset_to_defaults()
                success_count += 1
            except Exception as e:
                self.logger.error(f"重置对象 {obj.get_node_name()} 失败: {e}")
        return success_count


# ==================== 全局模型管理器实例 ====================

# 创建全局模型管理器实例
optimized_model_manager = ModelManager()

# 便捷函数
def get_optimized_model_manager() -> ModelManager:
    """获取全局优化模型管理器实例"""
    return optimized_model_manager
    
