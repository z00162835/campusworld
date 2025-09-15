"""
园区世界管理命令
基于重构后的命令系统，实现场景管理功能
"""

from typing import List
from app.commands.base import GameCommand, CommandContext, CommandResult, CommandType


class CampusLifeGameListCommand(GameCommand):
    """园区世界列表命令"""
    
    def __init__(self):
        super().__init__("game_list", "列出所有可用场景", ["games", "list_games"], "campus_life")
        self.group = "game"
        self.required_permission = "game.list"
    
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        """执行场景列表命令"""
        # 这里应该从场景管理器获取真实数据
        games = [
            {
                "name": "campus_life",
                "description": "校园生活模拟场景",
                "version": "1.0.0",
                "status": "available",
                "author": "CampusWorld Team"
            }
        ]
        
        message = "可用场景:\n"
        message += "=" * 50 + "\n"
        
        for game in games:
            message += f"名称: {game['name']}\n"
            message += f"描述: {game['description']}\n"
            message += f"版本: {game['version']}\n"
            message += f"状态: {game['status']}\n"
            message += f"作者: {game['author']}\n"
            message += "-" * 30 + "\n"
        
        return CommandResult.success_result(message, {"games": games}, CommandType.GAME)
    
    def _get_specific_help(self) -> str:
        return """
园区世界列表命令:
  game_list  - 列出所有可用场景
  games      - 列出所有可用场景（别名）

显示信息:
  - 场景名称和描述
  - 场景版本
  - 场景状态
  - 场景作者
"""


class CampusLifeGameLoadCommand(GameCommand):
    """园区世界加载命令"""
    
    def __init__(self):
        super().__init__("game_load", "加载指定场景", ["load_game"], "campus_life")
        self.group = "game"
        self.required_permission = "game.load"
    
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        """执行场景加载命令"""
        if not args:
            return CommandResult.error_result("用法: game_load <场景名>")
        
        game_name = args[0]
        
        # 这里应该调用场景管理器加载场景
        if game_name == "campus_life":
            # 模拟场景加载
            game_info = {
                "name": game_name,
                "status": "loaded",
                "load_time": "2024-01-01 12:00:00"
            }
            
            # 更新场景状态
            if not context.game_state:
                context.game_state = {}
            context.game_state.update({
                "current_game": game_name,
                "is_running": True,
                "game_info": game_info
            })
            
            message = f"场景 '{game_name}' 加载成功"
            return CommandResult.success_result(message, game_info, CommandType.GAME)
        else:
            return CommandResult.error_result(f"场景 '{game_name}' 不存在或无法加载")
    
    def _get_specific_help(self) -> str:
        return """
园区世界加载命令:
  game_load <场景名>  - 加载指定场景

示例:
  game_load campus_life  - 加载园区世界

注意: 加载场景需要相应权限
"""


class CampusLifeGameUnloadCommand(GameCommand):
    """园区世界卸载命令"""
    
    def __init__(self):
        super().__init__("game_unload", "卸载指定场景", ["unload_game"], "campus_life")
        self.group = "game"
        self.required_permission = "game.unload"
    
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        """执行场景卸载命令"""
        if not args:
            return CommandResult.error_result("用法: game_unload <场景名>")
        
        game_name = args[0]
        
        # 检查场景是否正在运行
        if not self.is_game_running(context):
            return CommandResult.error_result("没有场景正在运行")
        
        current_game = context.get_game_state('current_game')
        if current_game != game_name:
            return CommandResult.error_result(f"当前场景是 '{current_game}'，不是 '{game_name}'")
        
        # 这里应该调用场景管理器卸载场景
        # 模拟场景卸载
        if context.game_state:
            context.game_state.update({
                "current_game": None,
                "is_running": False,
                "game_info": {}
            })
        
        message = f"场景 '{game_name}' 卸载成功"
        return CommandResult.success_result(message, command_type=CommandType.GAME)
    
    def _get_specific_help(self) -> str:
        return """
园区世界卸载命令:
  game_unload <场景名>  - 卸载指定场景

示例:
  game_unload campus_life  - 卸载园区世界

注意: 卸载场景会停止当前场景进程
"""


class CampusLifeGameSwitchCommand(GameCommand):
    """园区世界切换命令"""
    
    def __init__(self):
        super().__init__("game_switch", "切换到指定场景", ["switch_game"], "campus_life")
        self.group = "game"
        self.required_permission = "game.switch"
    
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        """执行场景切换命令"""
        if not args:
            return CommandResult.error_result("用法: game_switch <场景名>")
        
        game_name = args[0]
        
        # 如果当前有场景运行，先停止
        if self.is_game_running(context):
            current_game = context.get_game_state('current_game')
            if current_game:
                # 这里应该停止当前场景
                pass
        
        # 加载新场景
        if game_name == "campus_life":
            game_info = {
                "name": game_name,
                "status": "running",
                "switch_time": "2024-01-01 12:00:00"
            }
            
            # 更新场景状态
            if not context.game_state:
                context.game_state = {}
            context.game_state.update({
                "current_game": game_name,
                "is_running": True,
                "game_info": game_info
            })
            
            message = f"成功切换到场景 '{game_name}'"
            return CommandResult.success_result(message, game_info, CommandType.GAME)
        else:
            return CommandResult.error_result(f"场景 '{game_name}' 不存在或无法切换")
    
    def _get_specific_help(self) -> str:
        return """
园区世界切换命令:
  game_switch <场景名>  - 切换到指定场景

示例:
  game_switch campus_life  - 切换到园区世界

注意: 切换场景会停止当前场景并启动新场景
"""


class CampusLifeGameStatusCommand(GameCommand):
    """园区世界状态命令"""
    
    def __init__(self):
        super().__init__("game_status", "显示场景状态", ["game_stat"], "campus_life")
        self.group = "game"
        self.required_permission = "game.status"
    
    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        """执行场景状态命令"""
        if not self.is_game_running(context):
            message = "当前没有场景运行"
            return CommandResult.success_result(message, command_type=CommandType.GAME)
        
        current_game = context.get_game_state('current_game')
        game_info = context.get_game_state('game_info', {})
        
        message = f"场景状态:\n"
        message += "=" * 30 + "\n"
        message += f"当前场景: {current_game}\n"
        message += f"场景状态: {'运行中' if self.is_game_running(context) else '已停止'}\n"
        
        if game_info:
            for key, value in game_info.items():
                message += f"{key}: {value}\n"
        
        return CommandResult.success_result(message, {
            "current_game": current_game,
            "is_running": self.is_game_running(context),
            "game_info": game_info
        }, CommandType.GAME)
    
    def _get_specific_help(self) -> str:
        return """
园区世界状态命令:
  game_status  - 显示当前场景状态

显示信息:
  - 当前运行的场景
  - 场景运行状态
  - 场景详细信息
"""


# 园区世界管理命令列表
CAMPUS_LIFE_GAME_COMMANDS = [
    CampusLifeGameListCommand(),
    CampusLifeGameLoadCommand(),
    CampusLifeGameUnloadCommand(),
    CampusLifeGameSwitchCommand(),
    CampusLifeGameStatusCommand()
]

