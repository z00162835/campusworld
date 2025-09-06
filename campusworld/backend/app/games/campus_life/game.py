"""
校园生活游戏主类

继承自BaseGame，实现校园生活游戏的核心逻辑。
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from app.game_engine.base import BaseGame
from .commands import CampusLifeCommands
from .objects import CampusLifeObjects
from .scripts import CampusLifeScripts
from app.core.log import (
    get_logger, 
    LoggerNames,
)

class Game(BaseGame):
    """校园生活游戏主类 - 兼容接口"""
    
    def __init__(self):
        super().__init__(
            name="campus_life",
            version="1.0.0"
        )
        
        self.description = "一个基于文本的校园生活模拟游戏"
        self.author = "CampusWorld Team"
        
        # 游戏组件
        self.commands = CampusLifeCommands(self)
        self.objects = CampusLifeObjects(self)
        self.scripts = CampusLifeScripts(self)
        
        # 游戏状态
        self.players: Dict[str, Any] = {}
        self.locations: Dict[str, Any] = {}
        self.items: Dict[str, Any] = {}
        
        # 兼容性属性
        self.game_name = self.name
        self.game_version = self.version
        self.game_description = self.description
        self.game_author = self.author
        self.is_initialized = False
        
        # 初始化游戏世界
        self._init_game_world()
        
        self.logger.info("校园生活游戏初始化完成")
    
    def initialize_game(self) -> bool:
        """初始化游戏 - 兼容接口"""
        try:
            if self.is_initialized:
                self.logger.warning("游戏已初始化")
                return True
            
            self.is_initialized = True
            self.logger.info("校园生活游戏初始化成功")
            return True
            
        except Exception as e:
            self.logger.error(f"校园生活游戏初始化失败: {e}")
            return False
    
    def get_game_info(self) -> Dict[str, Any]:
        """获取游戏信息 - 兼容接口"""
        return {
            "name": self.game_name,
            "version": self.game_version,
            "description": self.game_description,
            "author": self.game_author,
            "is_initialized": self.is_initialized,
            "is_running": self.is_running,
            "start_time": self.start_time,
            "rooms_count": len(self.locations),
            "items_count": len(self.items),
            "characters_count": len(self.players)
        }
    
    def _init_game_world(self):
        """初始化游戏世界"""
        try:
            # 初始化位置
            self.locations = {
                "library": {
                    "name": "图书馆",
                    "description": "安静的学习环境，有大量的书籍和自习室",
                    "exits": ["campus", "study_room"],
                    "items": ["books", "desk", "chair"]
                },
                "campus": {
                    "name": "校园广场",
                    "description": "校园的中心区域，有喷泉和绿树",
                    "exits": ["library", "canteen", "dormitory"],
                    "items": ["fountain", "tree", "bench"]
                },
                "canteen": {
                    "name": "食堂",
                    "description": "提供各种美食的食堂，是学生聚集的地方",
                    "exits": ["campus", "kitchen"],
                    "items": ["food", "table", "chair"]
                },
                "dormitory": {
                    "name": "宿舍",
                    "description": "学生的休息场所，有床铺和书桌",
                    "exits": ["campus", "bathroom"],
                    "items": ["bed", "desk", "closet"]
                }
            }
            
            # 初始化物品
            self.items = {
                "books": {
                    "name": "书籍",
                    "description": "各种学科的教材和参考书",
                    "type": "study_material",
                    "location": "library"
                },
                "food": {
                    "name": "食物",
                    "description": "食堂提供的各种美食",
                    "type": "consumable",
                    "location": "canteen"
                },
                "bed": {
                    "name": "床铺",
                    "description": "舒适的床铺，用于休息",
                    "type": "furniture",
                    "location": "dormitory"
                }
            }
            
            self.logger.info("游戏世界初始化完成")
            
        except Exception as e:
            self.logger.error(f"游戏世界初始化失败: {e}")
    
    def start(self) -> bool:
        """启动游戏"""
        try:
            if self.is_running:
                self.logger.warning("游戏已在运行中")
                return True
            
            self.start_time = datetime.now()
            self.is_running = True
            
            # 启动游戏组件
            self.commands.start()
            self.objects.start()
            self.scripts.start()
            
            self.logger.info(f"校园生活游戏启动成功，启动时间: {self.start_time}")
            return True
            
        except Exception as e:
            self.logger.error(f"校园生活游戏启动失败: {e}")
            return False
    
    def stop(self) -> bool:
        """停止游戏"""
        try:
            if not self.is_running:
                self.logger.warning("游戏未在运行")
                return True
            
            # 停止游戏组件
            self.commands.stop()
            self.objects.stop()
            self.scripts.stop()
            
            self.is_running = False
            runtime = datetime.now() - self.start_time if self.start_time else None
            
            self.logger.info(f"校园生活游戏已停止，运行时间: {runtime}")
            return True
            
        except Exception as e:
            self.logger.error(f"校园生活游戏停止失败: {e}")
            return False
    
    def get_commands(self) -> Dict[str, Any]:
        """获取游戏命令列表"""
        return self.commands.get_commands()
    
    def get_objects(self) -> Dict[str, Any]:
        """获取游戏对象列表"""
        return self.objects.get_objects()
    
    def get_hooks(self) -> Dict[str, Any]:
        """获取游戏事件钩子"""
        return {
            "player_join": self._on_player_join,
            "player_leave": self._on_player_leave,
            "player_move": self._on_player_move,
            "player_action": self._on_player_action
        }
    
    def get_player_count(self) -> int:
        """获取玩家数量"""
        return len(self.players)
    
    def add_player(self, player_id: str, player_data: Dict[str, Any]) -> bool:
        """添加玩家"""
        try:
            if player_id in self.players:
                self.logger.warning(f"玩家 '{player_id}' 已存在")
                return False
            
            # 设置玩家初始位置
            player_data["location"] = "campus"
            player_data["inventory"] = []
            player_data["stats"] = {
                "energy": 100,
                "hunger": 0,
                "knowledge": 0,
                "social": 0
            }
            
            self.players[player_id] = player_data
            
            # 触发玩家加入事件
            self.engine.hook_manager.trigger_hook("player_join", player_id, player_data)
            
            self.logger.info(f"玩家 '{player_id}' 加入游戏成功")
            return True
            
        except Exception as e:
            self.logger.error(f"添加玩家 '{player_id}' 失败: {e}")
            return False
    
    def remove_player(self, player_id: str) -> bool:
        """移除玩家"""
        try:
            if player_id not in self.players:
                self.logger.warning(f"玩家 '{player_id}' 不存在")
                return False
            
            player_data = self.players.pop(player_id)
            
            # 触发玩家离开事件
            self.engine.hook_manager.trigger_hook("player_leave", player_id, player_data)
            
            self.logger.info(f"玩家 '{player_id}' 离开游戏成功")
            return True
            
        except Exception as e:
            self.logger.error(f"移除玩家 '{player_id}' 失败: {e}")
            return False
    
    def get_player(self, player_id: str) -> Optional[Dict[str, Any]]:
        """获取玩家信息"""
        return self.players.get(player_id)
    
    def move_player(self, player_id: str, new_location: str) -> bool:
        """移动玩家到新位置"""
        try:
            if player_id not in self.players:
                self.logger.error(f"玩家 '{player_id}' 不存在")
                return False
            
            if new_location not in self.locations:
                self.logger.error(f"位置 '{new_location}' 不存在")
                return False
            
            old_location = self.players[player_id]["location"]
            self.players[player_id]["location"] = new_location
            
            # 触发玩家移动事件
            self.engine.hook_manager.trigger_hook(
                "player_move", player_id, old_location, new_location
            )
            
            self.logger.info(f"玩家 '{player_id}' 从 '{old_location}' 移动到 '{new_location}'")
            return True
            
        except Exception as e:
            self.logger.error(f"移动玩家 '{player_id}' 失败: {e}")
            return False
    
    def get_location_info(self, location_name: str) -> Optional[Dict[str, Any]]:
        """获取位置信息"""
        return self.locations.get(location_name)
    
    def get_item_info(self, item_name: str) -> Optional[Dict[str, Any]]:
        """获取物品信息"""
        return self.items.get(item_name)
    
    def _on_player_join(self, player_id: str, player_data: Dict[str, Any]):
        """玩家加入事件处理"""
        self.logger.info(f"玩家 '{player_id}' 加入游戏")
    
    def _on_player_leave(self, player_id: str, player_data: Dict[str, Any]):
        """玩家离开事件处理"""
        self.logger.info(f"玩家 '{player_id}' 离开游戏")
    
    def _on_player_move(self, player_id: str, old_location: str, new_location: str):
        """玩家移动事件处理"""
        self.logger.info(f"玩家 '{player_id}' 从 '{old_location}' 移动到 '{new_location}'")
    
    def _on_player_action(self, player_id: str, action: str, *args, **kwargs):
        """玩家行动事件处理"""
        self.logger.info(f"玩家 '{player_id}' 执行行动: {action}")
    
    def get_help(self, command: str = None) -> Optional[str]:
        """获取游戏帮助信息"""
        if command:
            return self.commands.get_command_help(command)
        
        help_text = f"""
校园生活游戏帮助
================

游戏简介: {self.description}
版本: {self.version}
作者: {self.author}

可用命令:
  look     - 查看当前位置和周围环境
  move     - 移动到其他位置
  take     - 拾取物品
  drop     - 丢弃物品
  inventory - 查看背包
  stats    - 查看角色状态
  help     - 显示帮助信息

当前位置: 校园广场
可用出口: 图书馆、食堂、宿舍

输入 'help <命令名>' 获取具体命令的帮助信息。
"""
        return help_text
