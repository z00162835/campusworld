"""
命令配置动态加载器

提供从数据库动态加载命令和命令集合配置的功能
支持配置的热更新和缓存机制

作者：AI Assistant
创建时间：2025-08-24
"""

import json
import logging
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime, timedelta
from functools import lru_cache

try:
    from app.core.database import SessionLocal
    from sqlalchemy import text
    from .base.command import Command
    from .base.cmdset import CmdSet
except ImportError as e:
    logging.warning(f"导入依赖失败: {e}")
    SessionLocal = None
    text = None
    Command = None
    CmdSet = None


class CommandLoader:
    """
    命令配置动态加载器
    
    负责从数据库加载命令配置，支持缓存和热更新
    """
    
    def __init__(self, cache_ttl: int = 300):
        """
        初始化命令加载器
        
        Args:
            cache_ttl: 缓存生存时间（秒），默认5分钟
        """
        self.cache_ttl = cache_ttl
        self._command_cache = {}
        self._cmdset_cache = {}
        self._last_cache_update = {}
        self.logger = logging.getLogger(__name__)
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self._last_cache_update:
            return False
        
        last_update = self._last_cache_update[cache_key]
        return datetime.now() - last_update < timedelta(seconds=self.cache_ttl)
    
    def _update_cache_timestamp(self, cache_key: str):
        """更新缓存时间戳"""
        self._last_cache_update[cache_key] = datetime.now()
    
    def load_command_config(self, command_key: str, force_reload: bool = False) -> Optional[Dict[str, Any]]:
        """
        加载命令配置
        
        Args:
            command_key: 命令关键字
            force_reload: 是否强制重新加载
            
        Returns:
            命令配置字典或None
        """
        cache_key = f"command_{command_key}"
        
        # 检查缓存
        if not force_reload and self._is_cache_valid(cache_key):
            if cache_key in self._command_cache:
                self.logger.debug(f"从缓存加载命令配置: {command_key}")
                return self._command_cache[cache_key]
        
        try:
            if not SessionLocal:
                self.logger.error("数据库会话不可用")
                return None
            
            session = SessionLocal()
            
            # 使用ORM查询替代原始SQL
            from app.models.graph import Node, NodeType
            
            # 查询命令节点
            command_node = session.query(Node).join(
                NodeType, Node.type_id == NodeType.id
            ).filter(
                NodeType.type_code == 'command',
                Node.name == command_key
            ).first()
            
            session.close()
            
            if not command_node:
                self.logger.warning(f"命令配置未找到: {command_key}")
                return None
            
            # 构建配置字典
            config = {
                'key': command_node.name,
                'description': command_node.description,
                'attributes': command_node.attributes or {},
                'tags': command_node.tags or [],
                'loaded_at': datetime.now().isoformat()
            }
            
            # 更新缓存
            self._command_cache[cache_key] = config
            self._update_cache_timestamp(cache_key)
            
            self.logger.info(f"成功加载命令配置: {command_key}")
            return config
            
        except Exception as e:
            self.logger.error(f"加载命令配置失败 {command_key}: {e}")
            return False
    
    def load_all_command_configs(self, force_reload: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        加载所有命令配置
        
        Args:
            force_reload: 是否强制重新加载
            
        Returns:
            所有命令配置的字典
        """
        cache_key = "all_commands"
        
        # 检查缓存
        if not force_reload and self._is_cache_valid(cache_key):
            if cache_key in self._command_cache:
                self.logger.debug("从缓存加载所有命令配置")
                return self._command_cache[cache_key]
        
        try:
            if not SessionLocal:
                self.logger.error("数据库会话不可用")
                return {}
            
            session = SessionLocal()
            
            # 使用ORM查询替代原始SQL
            from app.models.graph import Node, NodeType
            
            # 查询所有命令节点
            command_nodes = session.query(Node).join(
                NodeType, Node.type_id == NodeType.id
            ).filter(
                NodeType.type_code == 'command'
            ).order_by(Node.name).all()
            
            session.close()
            
            all_configs = {}
            
            for command_node in command_nodes:
                # 构建配置字典
                config = {
                    'key': command_node.name,
                    'description': command_node.description,
                    'attributes': command_node.attributes or {},
                    'tags': command_node.tags or [],
                    'loaded_at': datetime.now().isoformat()
                }
                
                all_configs[command_node.name] = config
            
            # 更新缓存
            self._command_cache[cache_key] = all_configs
            self._update_cache_timestamp(cache_key)
            
            self.logger.info(f"成功加载 {len(all_configs)} 个命令配置")
            return all_configs
            
        except Exception as e:
            self.logger.error(f"加载所有命令配置失败: {e}")
            return {}
    
    def load_commands_by_category(self, category: str, force_reload: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        按分类加载命令配置
        
        Args:
            category: 命令分类
            force_reload: 是否强制重新加载
            
        Returns:
            指定分类的命令配置字典
        """
        cache_key = f"category_{category}"
        
        # 检查缓存
        if not force_reload and self._is_cache_valid(cache_key):
            if cache_key in self._command_cache:
                self.logger.debug(f"从缓存加载分类命令配置: {category}")
                return self._command_cache[cache_key]
        
        try:
            if not SessionLocal:
                self.logger.error("数据库会话不可用")
                return {}
            
            session = SessionLocal()
            
            # 使用ORM查询替代原始SQL
            from app.models.graph import Node, NodeType
            
            # 查询指定分类的命令节点
            command_nodes = session.query(Node).join(
                NodeType, Node.type_id == NodeType.id
            ).filter(
                NodeType.type_code == 'command',
                Node.attributes.contains({'help_category': category})
            ).order_by(Node.name).all()
            
            session.close()
            
            category_configs = {}
            
            for command_node in command_nodes:
                # 构建配置字典
                config = {
                    'key': command_node.name,
                    'description': command_node.description,
                    'attributes': command_node.attributes or {},
                    'tags': command_node.tags or [],
                    'loaded_at': datetime.now().isoformat()
                }
                
                category_configs[command_node.name] = config
            
            # 更新缓存
            self._command_cache[cache_key] = category_configs
            self._update_cache_timestamp(cache_key)
            
            self.logger.info(f"成功加载分类 {category} 的 {len(category_configs)} 个命令配置")
            return category_configs
            
        except Exception as e:
            self.logger.error(f"加载分类命令配置失败 {category}: {e}")
            return {}
    
    def clear_cache(self, cache_key: str = None):
        """
        清除缓存
        
        Args:
            cache_key: 指定缓存键，None表示清除所有缓存
        """
        if cache_key:
            if cache_key in self._command_cache:
                del self._command_cache[cache_key]
            if cache_key in self._last_cache_update:
                del self._last_cache_update[cache_key]
            self.logger.info(f"清除缓存: {cache_key}")
        else:
            self._command_cache.clear()
            self._last_cache_update.clear()
            self.logger.info("清除所有缓存")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        return {
            'command_cache_size': len(self._command_cache),
            'last_update': self._last_cache_update,
            'cache_ttl': self.cache_ttl
        }


class CmdSetLoader:
    """
    命令集合配置动态加载器
    
    负责从数据库加载命令集合配置，支持缓存和热更新
    """
    
    def __init__(self, cache_ttl: int = 300):
        """
        初始化命令集合加载器
        
        Args:
            cache_ttl: 缓存生存时间（秒），默认5分钟
        """
        self.cache_ttl = cache_ttl
        self._cmdset_cache = {}
        self._last_cache_update = {}
        self.logger = logging.getLogger(__name__)
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self._last_cache_update:
            return False
        
        last_update = self._last_cache_update[cache_key]
        return datetime.now() - last_update < timedelta(seconds=self.cache_ttl)
    
    def _update_cache_timestamp(self, cache_key: str):
        """更新缓存时间戳"""
        self._last_cache_update[cache_key] = datetime.now()
    
    def load_cmdset_config(self, cmdset_key: str, force_reload: bool = False) -> Optional[Dict[str, Any]]:
        """
        加载命令集合配置
        
        Args:
            cmdset_key: 命令集合关键字
            force_reload: 是否强制重新加载
            
        Returns:
            命令集合配置字典或None
        """
        cache_key = f"cmdset_{cmdset_key}"
        
        # 检查缓存
        if not force_reload and self._is_cache_valid(cache_key):
            if cache_key in self._cmdset_cache:
                self.logger.debug(f"从缓存加载命令集合配置: {cmdset_key}")
                return self._cmdset_cache[cache_key]
        
        try:
            if not SessionLocal:
                self.logger.error("数据库会话不可用")
                return None
            
            session = SessionLocal()
            
            # 使用ORM查询替代原始SQL
            from app.models.graph import Node, NodeType
            
            # 查询命令集合节点
            cmdset_node = session.query(Node).join(
                NodeType, Node.type_id == NodeType.id
            ).filter(
                NodeType.type_code.in_(['cmdset', 'system_cmdset']),
                Node.name == cmdset_key
            ).first()
            
            session.close()
            
            if not cmdset_node:
                self.logger.warning(f"命令集合配置未找到: {cmdset_key}")
                return None
            
            # 构建配置字典
            config = {
                'key': cmdset_node.name,
                'description': cmdset_node.description,
                'attributes': cmdset_node.attributes or {},
                'tags': cmdset_node.tags or [],
                'loaded_at': datetime.now().isoformat()
            }
            
            # 更新缓存
            self._cmdset_cache[cache_key] = config
            self._update_cache_timestamp(cache_key)
            
            self.logger.info(f"成功加载命令集合配置: {cmdset_key}")
            return config
            
        except Exception as e:
            self.logger.error(f"加载命令集合配置失败 {cmdset_key}: {e}")
            return None
    
    def load_cmdset_commands(self, cmdset_key: str, force_reload: bool = False) -> List[Dict[str, Any]]:
        """
        加载命令集合包含的命令
        
        Args:
            cmdset_key: 命令集合关键字
            force_reload: 是否强制重新加载
            
        Returns:
            命令列表
        """
        cache_key = f"cmdset_commands_{cmdset_key}"
        
        # 检查缓存
        if not force_reload and self._is_cache_valid(cache_key):
            if cache_key in self._cmdset_cache:
                self.logger.debug(f"从缓存加载命令集合命令: {cmdset_key}")
                return self._cmdset_cache[cache_key]
        
        try:
            if not SessionLocal:
                self.logger.error("数据库会话不可用")
                return []
            
            session = SessionLocal()
            
            # 使用ORM查询替代原始SQL
            from app.models.graph import Node, Relationship, NodeType
            
            # 首先获取命令集合节点
            cmdset_node = session.query(Node).join(
                NodeType, Node.type_id == NodeType.id
            ).filter(
                NodeType.type_code.in_(['cmdset', 'system_cmdset']),
                Node.name == cmdset_key
            ).first()
            
            if not cmdset_node:
                session.close()
                return []
            
            # 然后查询该命令集合包含的命令
            # 使用子查询避免JOIN冲突
            command_relationships = session.query(Relationship).filter(
                Relationship.source_id == cmdset_node.id,
                Relationship.type_code == 'contains'
            ).all()
            
            commands = []
            
            for rel in command_relationships:
                # 获取目标命令节点
                command_node = session.query(Node).join(
                    NodeType, Node.type_id == NodeType.id
                ).filter(
                    NodeType.type_code == 'command',
                    Node.id == rel.target_id
                ).first()
                
                if command_node:
                    # 构建命令信息
                    command_info = {
                        'key': command_node.name,
                        'description': command_node.description,
                        'attributes': command_node.attributes or {},
                        'tags': command_node.tags or [],
                        'relationship': rel.attributes or {},
                        'loaded_at': datetime.now().isoformat()
                    }
                    
                    commands.append(command_info)
            
            session.close()
            
            # 更新缓存
            self._cmdset_cache[cache_key] = commands
            self._update_cache_timestamp(cache_key)
            
            self.logger.info(f"成功加载命令集合 {cmdset_key} 的 {len(commands)} 个命令")
            return commands
            
        except Exception as e:
            self.logger.error(f"加载命令集合命令失败 {cmdset_key}: {e}")
            return []
    
    def load_all_cmdset_configs(self, force_reload: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        加载所有命令集合配置
        
        Args:
            force_reload: 是否强制重新加载
            
        Returns:
            所有命令集合配置的字典
        """
        cache_key = "all_cmdsets"
        
        # 检查缓存
        if not force_reload and self._is_cache_valid(cache_key):
            if cache_key in self._cmdset_cache:
                self.logger.debug("从缓存加载所有命令集合配置")
                return self._cmdset_cache[cache_key]
        
        try:
            if not SessionLocal:
                self.logger.error("数据库会话不可用")
                return {}
            
            session = SessionLocal()
            
            # 使用ORM查询替代原始SQL
            from app.models.graph import Node, NodeType
            
            # 查询所有命令集合节点
            cmdset_nodes = session.query(Node).join(
                NodeType, Node.type_id == NodeType.id
            ).filter(
                NodeType.type_code.in_(['cmdset', 'system_cmdset'])
            ).order_by(Node.name).all()
            
            session.close()
            
            all_configs = {}
            
            for cmdset_node in cmdset_nodes:
                # 构建配置字典
                config = {
                    'key': cmdset_node.name,
                    'description': cmdset_node.description,
                    'attributes': cmdset_node.attributes or {},
                    'tags': cmdset_node.tags or [],
                    'loaded_at': datetime.now().isoformat()
                }
                
                all_configs[cmdset_node.name] = config
            
            # 更新缓存
            self._cmdset_cache[cache_key] = all_configs
            self._update_cache_timestamp(cache_key)
            
            self.logger.info(f"成功加载 {len(all_configs)} 个命令集合配置")
            return all_configs
            
        except Exception as e:
            self.logger.error(f"加载所有命令集合配置失败: {e}")
            return {}
    
    def clear_cache(self, cache_key: str = None):
        """
        清除缓存
        
        Args:
            cache_key: 指定缓存键，None表示清除所有缓存
        """
        if cache_key:
            if cache_key in self._cmdset_cache:
                del self._cmdset_cache[cache_key]
            if cache_key in self._last_cache_update:
                del self._last_cache_update[cache_key]
            self.logger.info(f"清除缓存: {cache_key}")
        else:
            self._cmdset_cache.clear()
            self._last_cache_update.clear()
            self.logger.info("清除所有缓存")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        return {
            'cmdset_cache_size': len(self._cmdset_cache),
            'last_update': self._last_cache_update,
            'cache_ttl': self.cache_ttl
        }


# 创建全局加载器实例
command_loader = CommandLoader()
cmdset_loader = CmdSetLoader()
