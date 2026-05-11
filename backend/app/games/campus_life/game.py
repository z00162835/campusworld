"""
园区世界主类

继承自BaseGame，实现园区世界的核心逻辑。
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from app.game_engine.base import BaseGame
from .commands import CampusLifeCommands
from .objects import CampusLifeObjects
from .scripts import CampusLifeScripts
from app.core.log import get_logger, LoggerNames

class Game(BaseGame):
    """园区世界主类 - 兼容接口"""

    def __init__(self):
        super().__init__(name='campus_life', version='1.0.0')
        self.description = '一个基于文本的园区生活模拟场景'
        self.author = 'CampusWorld OS Team'
        self.commands = CampusLifeCommands(self)
        self.objects = CampusLifeObjects(self)
        self.scripts = CampusLifeScripts(self)
        self.players: Dict[str, Any] = {}
        self.locations: Dict[str, Any] = {}
        self.items: Dict[str, Any] = {}
        self.game_name = self.name
        self.game_version = self.version
        self.game_description = self.description
        self.game_author = self.author
        self.is_initialized = False
        self._init_game_world()

    def initialize_game(self) -> bool:
        """初始化场景 - 兼容接口"""
        try:
            if self.is_initialized:
                self.logger.warning('World initialized')
                return True
            self.is_initialized = True
            self.logger.info('CampusWorld initialized successfully')
            return True
        except Exception as e:
            self.logger.error(f'Failed to initialize CampusWorld: {e}')
            return False

    def get_game_info(self) -> Dict[str, Any]:
        """获取场景信息 - 兼容接口"""
        return {'name': self.game_name, 'version': self.game_version, 'description': self.game_description, 'author': self.game_author, 'is_initialized': self.is_initialized, 'is_running': self.is_running, 'start_time': self.start_time, 'rooms_count': len(self.locations), 'items_count': len(self.items), 'characters_count': len(self.players)}

    def _init_game_world(self):
        """初始化场景世界"""
        try:
            self.locations = {'library': {'name': '图书馆', 'description': '安静的学习环境，有大量的书籍和自习室', 'exits': ['campus', 'study_room'], 'items': ['books', 'desk', 'chair']}, 'campus': {'name': '园区广场', 'description': '园区的中心区域，有喷泉和绿树', 'exits': ['library', 'canteen', 'dormitory'], 'items': ['fountain', 'tree', 'bench']}, 'canteen': {'name': '食堂', 'description': '提供各种美食的食堂，是学生聚集的地方', 'exits': ['campus', 'kitchen'], 'items': ['food', 'table', 'chair']}, 'dormitory': {'name': '宿舍', 'description': '学生的休息场所，有床铺和书桌', 'exits': ['campus', 'bathroom'], 'items': ['bed', 'desk', 'closet']}}
            self.items = {'books': {'name': '书籍', 'description': '各种学科的教材和参考书', 'type': 'study_material', 'location': 'library'}, 'food': {'name': '食物', 'description': '食堂提供的各种美食', 'type': 'consumable', 'location': 'canteen'}, 'bed': {'name': '床铺', 'description': '舒适的床铺，用于休息', 'type': 'furniture', 'location': 'dormitory'}}
        except Exception as e:
            self.logger.error(f'Failed to initialize worlds: {e}')

    def start(self) -> bool:
        """启动场景"""
        try:
            if self.is_running:
                self.logger.warning('World already running')
                return True
            self.start_time = datetime.now()
            self.is_running = True
            self.commands.start()
            self.objects.start()
            self.scripts.start()
            self.logger.info(f'CampusWorld started successfully, startup time: {self.start_time}')
            return True
        except Exception as e:
            self.logger.error(f'Failed to start CampusWorld: {e}')
            return False

    def stop(self) -> bool:
        """停止场景"""
        try:
            if not self.is_running:
                self.logger.warning('World not running')
                return True
            self.commands.stop()
            self.objects.stop()
            self.scripts.stop()
            self.is_running = False
            runtime = datetime.now() - self.start_time if self.start_time else None
            self.logger.info(f'CampusWorld stopped, uptime: {runtime}')
            return True
        except Exception as e:
            self.logger.error(f'Failed to stop CampusWorld: {e}')
            return False

    def get_commands(self) -> Dict[str, Any]:
        """获取场景命令列表"""
        return self.commands.get_commands()

    def get_objects(self) -> Dict[str, Any]:
        """获取场景对象列表"""
        return self.objects.get_objects()

    def get_hooks(self) -> Dict[str, Any]:
        """获取场景事件钩子"""
        return {'player_join': self._on_player_join, 'player_leave': self._on_player_leave, 'player_move': self._on_player_move, 'player_action': self._on_player_action}

    def get_player_count(self) -> int:
        """获取玩家数量"""
        return len(self.players)

    def add_player(self, player_id: str, player_data: Dict[str, Any], initial_location: str='campus') -> bool:
        """添加玩家"""
        try:
            if player_id in self.players:
                self.logger.warning(f"user '{player_id}' already exists")
                return False
            spawn_location = initial_location if initial_location in self.locations else 'campus'
            player_data['location'] = spawn_location
            player_data['inventory'] = []
            player_data['stats'] = {'energy': 100, 'hunger': 0, 'knowledge': 0, 'social': 0}
            self.players[player_id] = player_data
            self._sync_player_world_location(player_id, spawn_location)
            if self.engine and getattr(self.engine, 'hook_manager', None):
                self.engine.hook_manager.trigger_hook('player_join', player_id, player_data)
            self.logger.info(f"user '{player_id}' joined world successfully")
            return True
        except Exception as e:
            self.logger.error(f"Add user '{player_id}' failed: {e}")
            return False

    def remove_player(self, player_id: str) -> bool:
        """移除玩家"""
        try:
            if player_id not in self.players:
                self.logger.warning(f"user '{player_id}' does not exist")
                return False
            player_data = self.players.pop(player_id)
            if self.engine and getattr(self.engine, 'hook_manager', None):
                self.engine.hook_manager.trigger_hook('player_leave', player_id, player_data)
            self.logger.info(f"user '{player_id}' left world successfully")
            return True
        except Exception as e:
            self.logger.error(f"Remove user '{player_id}' failed: {e}")
            return False

    def get_player(self, player_id: str) -> Optional[Dict[str, Any]]:
        """获取玩家信息"""
        return self.players.get(player_id)

    def move_player(self, player_id: str, new_location: str) -> bool:
        """移动玩家到新位置"""
        try:
            if player_id not in self.players:
                self.logger.error(f"user '{player_id}' does not exist")
                return False
            if new_location not in self.locations:
                self.logger.error(f"Location '{new_location}' does not exist")
                return False
            old_location = self.players[player_id]['location']
            self.players[player_id]['location'] = new_location
            self._sync_player_world_location(player_id, new_location)
            if self.engine and getattr(self.engine, 'hook_manager', None):
                self.engine.hook_manager.trigger_hook('player_move', player_id, old_location, new_location)
            self.logger.info(f"user '{player_id}' from '{old_location}' moved to '{new_location}'")
            return True
        except Exception as e:
            self.logger.error(f"Move user '{player_id}' failed: {e}")
            return False

    def _sync_player_world_location(self, player_id: str, world_location: str):
        """将世界内位置同步回图节点属性，避免内存/DB漂移。"""
        try:
            from app.core.database import db_session_context
            from app.models.graph import Node
            with db_session_context() as session:
                user_node = session.query(Node).filter(Node.id == int(player_id)).first()
                if not user_node:
                    return
                attrs = user_node.attributes or {}
                attrs['active_world'] = self.name
                attrs['world_location'] = world_location
                attrs['last_world_location'] = world_location
                user_node.attributes = attrs
                session.commit()
        except Exception as e:
            self.logger.warning(f'Failed to sync user world position: {e}')

    def get_location_info(self, location_name: str) -> Optional[Dict[str, Any]]:
        """获取位置信息"""
        return self.locations.get(location_name)

    def get_item_info(self, item_name: str) -> Optional[Dict[str, Any]]:
        """获取物品信息"""
        return self.items.get(item_name)

    def _on_player_join(self, player_id: str, player_data: Dict[str, Any]):
        """玩家加入事件处理"""
        self.logger.info(f"user '{player_id}' join world")

    def _on_player_leave(self, player_id: str, player_data: Dict[str, Any]):
        """玩家离开事件处理"""
        self.logger.info(f"user '{player_id}' leave world")

    def _on_player_move(self, player_id: str, old_location: str, new_location: str):
        """玩家移动事件处理"""
        self.logger.info(f"user '{player_id}' from '{old_location}' moved to '{new_location}'")

    def _on_player_action(self, player_id: str, action: str, *args, **kwargs):
        """玩家行动事件处理"""
        self.logger.info(f"user '{player_id}' action: {action}")

    def get_help(self, command: str=None) -> Optional[str]:
        """获取场景帮助信息"""
        if command:
            return self.commands.get_command_help(command)
        help_text = f"\n园区世界帮助\n================\n\n场景简介: {self.description}\n版本: {self.version}\n作者: {self.author}\n\n可用命令:\n  look     - 查看当前位置和周围环境\n  move     - 移动到其他位置\n  take     - 拾取物品\n  drop     - 丢弃物品\n  inventory - 查看背包\n  stats    - 查看角色状态\n  help     - 显示帮助信息\n\n当前位置: 园区广场\n可用出口: 图书馆、食堂、宿舍\n\n输入 'help <命令名>' 获取具体命令的帮助信息。\n"
        return help_text
