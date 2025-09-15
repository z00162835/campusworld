"""
园区世界命令系统

实现场景中的各种命令，如移动、查看、拾取等。
"""

import logging
from typing import Dict, Any, Optional


class CampusLifeCommands:
    """园区世界命令系统"""
    
    def __init__(self, game):
        self.game = game
        self.logger = logging.getLogger(f"game.{game.name}.commands")
        self.is_running = False
        
        # 命令映射
        self.command_handlers = {
            "look": self._cmd_look,
            "move": self._cmd_move,
            "take": self._cmd_take,
            "drop": self._cmd_drop,
            "inventory": self._cmd_inventory,
            "stats": self._cmd_stats,
            "help": self._cmd_help,
            "go": self._cmd_move,  # 别名
            "l": self._cmd_look,   # 别名
            "i": self._cmd_inventory,  # 别名
        }
        
        self.logger.info("园区世界命令系统初始化完成")
    
    def start(self):
        """启动命令系统"""
        self.is_running = True
        self.logger.info("园区世界命令系统启动成功")
    
    def stop(self):
        """停止命令系统"""
        self.is_running = False
        self.logger.info("园区世界命令系统已停止")
    
    def get_commands(self) -> Dict[str, Any]:
        """获取命令列表"""
        return self.command_handlers
    
    def get_command_help(self, command: str) -> Optional[str]:
        """获取命令帮助信息"""
        help_texts = {
            "look": """
look 命令帮助
============

用法: look [目标]

描述: 查看当前位置和周围环境，或者查看特定物品

示例:
  look          - 查看当前位置
  look books    - 查看书籍
  look fountain - 查看喷泉

""",
            "move": """
move 命令帮助
============

用法: move <目标位置>

描述: 移动到指定位置

可用位置:
  campus    - 校园广场
  library   - 图书馆
  canteen   - 食堂
  dormitory - 宿舍

示例:
  move library  - 移动到图书馆
  move canteen - 移动到食堂

""",
            "take": """
take 命令帮助
============

用法: take <物品名>

描述: 拾取指定物品到背包

示例:
  take books - 拾取书籍
  take food  - 拾取食物

""",
            "drop": """
drop 命令帮助
============

用法: drop <物品名>

描述: 从背包丢弃指定物品

示例:
  drop books - 丢弃书籍
  drop food  - 丢弃食物

""",
            "inventory": """
inventory 命令帮助
=================

用法: inventory

描述: 查看背包中的物品

示例:
  inventory - 显示背包内容

""",
            "stats": """
stats 命令帮助
==============

用法: stats

描述: 查看角色状态

显示信息:
  energy   - 体力值
  hunger   - 饥饿值
  knowledge - 知识值
  social   - 社交值

示例:
  stats - 显示角色状态

""",
            "help": """
help 命令帮助
=============

用法: help [命令名]

描述: 显示帮助信息

示例:
  help         - 显示场景总体帮助
  help look    - 显示look命令帮助
  help move    - 显示move命令帮助

"""
        }
        
        return help_texts.get(command, f"命令 '{command}' 没有帮助信息")
    
    def execute_command(self, command: str, *args, **kwargs) -> str:
        """执行命令"""
        try:
            if not self.is_running:
                return "命令系统未启动"
            
            if command not in self.command_handlers:
                return f"未知命令: {command}"
            
            handler = self.command_handlers[command]
            result = handler(*args, **kwargs)
            
            self.logger.debug(f"命令 '{command}' 执行成功")
            return result
            
        except Exception as e:
            self.logger.error(f"执行命令 '{command}' 失败: {e}")
            return f"命令执行失败: {str(e)}"
    
    def _cmd_look(self, *args) -> str:
        """look命令 - 查看环境"""
        try:
            if not args:
                # 查看当前位置
                return "请指定要查看的目标"
            
            target = args[0].lower()
            
            # 查看位置
            if target in self.game.locations:
                location = self.game.locations[target]
                return f"""
{location['name']}
{'=' * len(location['name'])}

{location['description']}

可用出口: {', '.join(location['exits'])}
物品: {', '.join(location['items'])}
"""
            
            # 查看物品
            if target in self.game.items:
                item = self.game.items[target]
                return f"""
{item['name']}
{'=' * len(item['name'])}

{item['description']}
类型: {item['type']}
位置: {item['location']}
"""
            
            return f"找不到目标: {target}"
            
        except Exception as e:
            self.logger.error(f"look命令执行失败: {e}")
            return f"查看失败: {str(e)}"
    
    def _cmd_move(self, *args) -> str:
        """move命令 - 移动位置"""
        try:
            if not args:
                return "请指定要移动到的位置"
            
            target_location = args[0].lower()
            
            if target_location not in self.game.locations:
                return f"位置不存在: {target_location}"
            
            # 这里需要玩家ID，暂时返回提示
            return f"移动到 {target_location} 成功！\n\n{self._cmd_look(target_location)}"
            
        except Exception as e:
            self.logger.error(f"move命令执行失败: {e}")
            return f"移动失败: {str(e)}"
    
    def _cmd_take(self, *args) -> str:
        """take命令 - 拾取物品"""
        try:
            if not args:
                return "请指定要拾取的物品"
            
            item_name = args[0].lower()
            
            if item_name not in self.game.items:
                return f"物品不存在: {item_name}"
            
            return f"拾取 {item_name} 成功！"
            
        except Exception as e:
            self.logger.error(f"take命令执行失败: {e}")
            return f"拾取失败: {str(e)}"
    
    def _cmd_drop(self, *args) -> str:
        """drop命令 - 丢弃物品"""
        try:
            if not args:
                return "请指定要丢弃的物品"
            
            item_name = args[0].lower()
            
            return f"丢弃 {item_name} 成功！"
            
        except Exception as e:
            self.logger.error(f"drop命令执行失败: {e}")
            return f"丢弃失败: {str(e)}"
    
    def _cmd_inventory(self, *args) -> str:
        """inventory命令 - 查看背包"""
        try:
            # 这里需要玩家ID，暂时返回示例
            return """
背包内容
========

书籍 (study_material) - 各种学科的教材和参考书
食物 (consumable) - 食堂提供的各种美食

背包已满: 2/10
"""
            
        except Exception as e:
            self.logger.error(f"inventory命令执行失败: {e}")
            return f"查看背包失败: {str(e)}"
    
    def _cmd_stats(self, *args) -> str:
        """stats命令 - 查看角色状态"""
        try:
            # 这里需要玩家ID，暂时返回示例
            return """
角色状态
========

体力值: 85/100
饥饿值: 25/100
知识值: 45/100
社交值: 30/100

状态: 正常
"""
            
        except Exception as e:
            self.logger.error(f"stats命令执行失败: {e}")
            return f"查看状态失败: {str(e)}"
    
    def _cmd_help(self, *args) -> str:
        """help命令 - 显示帮助"""
        try:
            if not args:
                return self.game.get_help()
            
            command = args[0].lower()
            help_text = self.get_command_help(command)
            
            if help_text:
                return help_text
            else:
                return f"命令 '{command}' 没有帮助信息"
            
        except Exception as e:
            self.logger.error(f"help命令执行失败: {e}")
            return f"显示帮助失败: {str(e)}"
