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
        self.logger = logging.getLogger(f'game.{game.name}.commands')
        self.is_running = False
        self.command_handlers = {'look': self._cmd_look, 'move': self._cmd_move, 'take': self._cmd_take, 'drop': self._cmd_drop, 'inventory': self._cmd_inventory, 'stats': self._cmd_stats, 'help': self._cmd_help, 'go': self._cmd_move, 'l': self._cmd_look, 'i': self._cmd_inventory}

    def start(self):
        """启动命令系统"""
        self.is_running = True
        self.logger.info('CampusWorld command system started successfully')

    def stop(self):
        """停止命令系统"""
        self.is_running = False
        self.logger.info('CampusWorld command system stopped')

    def get_commands(self) -> Dict[str, Any]:
        """获取命令列表"""
        return self.command_handlers

    def get_command_help(self, command: str) -> Optional[str]:
        """获取命令帮助信息"""
        help_texts = {'look': '\nlook 命令帮助\n============\n\n用法: look [目标]\n\n描述: 查看当前位置和周围环境，或者查看特定物品\n\n示例:\n  look          - 查看当前位置\n  look books    - 查看书籍\n  look fountain - 查看喷泉\n\n', 'move': '\nmove 命令帮助\n============\n\n用法: move <目标位置>\n\n描述: 移动到指定位置\n\n可用位置:\n  campus    - 园区广场\n  library   - 图书馆\n  canteen   - 食堂\n  dormitory - 宿舍\n\n示例:\n  move library  - 移动到图书馆\n  move canteen - 移动到食堂\n\n', 'take': '\ntake 命令帮助\n============\n\n用法: take <物品名>\n\n描述: 拾取指定物品到背包\n\n示例:\n  take books - 拾取书籍\n  take food  - 拾取食物\n\n', 'drop': '\ndrop 命令帮助\n============\n\n用法: drop <物品名>\n\n描述: 从背包丢弃指定物品\n\n示例:\n  drop books - 丢弃书籍\n  drop food  - 丢弃食物\n\n', 'inventory': '\ninventory 命令帮助\n=================\n\n用法: inventory\n\n描述: 查看背包中的物品\n\n示例:\n  inventory - 显示背包内容\n\n', 'stats': '\nstats 命令帮助\n==============\n\n用法: stats\n\n描述: 查看角色状态\n\n显示信息:\n  energy   - 体力值\n  hunger   - 饥饿值\n  knowledge - 知识值\n  social   - 社交值\n\n示例:\n  stats - 显示角色状态\n\n', 'help': '\nhelp 命令帮助\n=============\n\n用法: help [命令名]\n\n描述: 显示帮助信息\n\n示例:\n  help         - 显示场景总体帮助\n  help look    - 显示look命令帮助\n  help move    - 显示move命令帮助\n\n'}
        return help_texts.get(command, f"命令 '{command}' 没有帮助信息")

    def execute_command(self, command: str, *args, **kwargs) -> str:
        """执行命令"""
        try:
            if not self.is_running:
                return '命令系统未启动'
            if command not in self.command_handlers:
                return f'未知命令: {command}'
            handler = self.command_handlers[command]
            result = handler(*args, **kwargs)
            self.logger.debug(f"command '{command}' executed successfully")
            return result
        except Exception as e:
            self.logger.error(f"Execute command '{command}' failed: {e}")
            return f'命令执行失败: {str(e)}'

    def _cmd_look(self, *args) -> str:
        """look命令 - 查看环境"""
        try:
            if not args:
                return '请指定要查看的目标'
            target = args[0].lower()
            if target in self.game.locations:
                location = self.game.locations[target]
                return f"\n{location['name']}\n{'=' * len(location['name'])}\n\n{location['description']}\n\n可用出口: {', '.join(location['exits'])}\n物品: {', '.join(location['items'])}\n"
            if target in self.game.items:
                item = self.game.items[target]
                return f"\n{item['name']}\n{'=' * len(item['name'])}\n\n{item['description']}\n类型: {item['type']}\n位置: {item['location']}\n"
            return f'找不到目标: {target}'
        except Exception as e:
            self.logger.error(f'look command execution failed: {e}')
            return f'查看失败: {str(e)}'

    def _cmd_move(self, *args) -> str:
        """move命令 - 移动位置"""
        try:
            if not args:
                return '请指定要移动到的位置'
            target_location = args[0].lower()
            if target_location not in self.game.locations:
                return f'位置不存在: {target_location}'
            return f'移动到 {target_location} 成功！\n\n{self._cmd_look(target_location)}'
        except Exception as e:
            self.logger.error(f'move command execution failed: {e}')
            return f'移动失败: {str(e)}'

    def _cmd_take(self, *args) -> str:
        """take命令 - 拾取物品"""
        try:
            if not args:
                return '请指定要拾取的物品'
            item_name = args[0].lower()
            if item_name not in self.game.items:
                return f'物品不存在: {item_name}'
            return f'拾取 {item_name} 成功！'
        except Exception as e:
            self.logger.error(f'take command execution failed: {e}')
            return f'拾取失败: {str(e)}'

    def _cmd_drop(self, *args) -> str:
        """drop命令 - 丢弃物品"""
        try:
            if not args:
                return '请指定要丢弃的物品'
            item_name = args[0].lower()
            return f'丢弃 {item_name} 成功！'
        except Exception as e:
            self.logger.error(f'drop command execution failed: {e}')
            return f'丢弃失败: {str(e)}'

    def _cmd_inventory(self, *args) -> str:
        """inventory命令 - 查看背包"""
        try:
            return '\n背包内容\n========\n\n书籍 (study_material) - 各种学科的教材和参考书\n食物 (consumable) - 食堂提供的各种美食\n\n背包已满: 2/10\n'
        except Exception as e:
            self.logger.error(f'inventory command execution failed: {e}')
            return f'查看背包失败: {str(e)}'

    def _cmd_stats(self, *args) -> str:
        """stats命令 - 查看角色状态"""
        try:
            return '\n角色状态\n========\n\n体力值: 85/100\n饥饿值: 25/100\n知识值: 45/100\n社交值: 30/100\n\n状态: 正常\n'
        except Exception as e:
            self.logger.error(f'stats command execution failed: {e}')
            return f'查看状态失败: {str(e)}'

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
            self.logger.error(f'help command execution failed: {e}')
            return f'显示帮助失败: {str(e)}'
