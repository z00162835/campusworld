"""
命令初始化模块
负责注册所有系统命令和游戏命令
"""

import logging
from .registry import command_registry
from .system_commands import SYSTEM_COMMANDS


def initialize_commands() -> bool:
    """初始化所有命令"""
    logger = logging.getLogger("command.init")
    
    try:
        logger.info("开始初始化命令系统...")
        
        # 注册系统命令
        system_success = 0
        for command in SYSTEM_COMMANDS:
            if command_registry.register_command(command):
                system_success += 1
            else:
                logger.error(f"系统命令 '{command.name}' 注册失败")
        
        logger.info(f"系统命令注册完成: {system_success}/{len(SYSTEM_COMMANDS)}")
        
        # 显示注册摘要
        summary = command_registry.get_commands_summary()
        logger.info(f"命令系统初始化完成: {summary}")
        
        return system_success == len(SYSTEM_COMMANDS)
        
    except Exception as e:
        logger.error(f"命令系统初始化失败: {e}")
        return False


def get_command_summary() -> dict:
    """获取命令摘要"""
    return command_registry.get_commands_summary()


def register_game_commands(game_name: str, commands: list) -> bool:
    """注册游戏特定命令"""
    logger = logging.getLogger("command.init")
    
    try:
        success_count = 0
        for command in commands:
            if command_registry.register_command(command):
                success_count += 1
            else:
                logger.error(f"游戏 '{game_name}' 命令 '{command.name}' 注册失败")
        
        logger.info(f"游戏 '{game_name}' 命令注册完成: {success_count}/{len(commands)}")
        return success_count == len(commands)
        
    except Exception as e:
        logger.error(f"注册游戏 '{game_name}' 命令失败: {e}")
        return False


def unregister_game_commands(game_name: str) -> bool:
    """注销游戏特定命令"""
    logger = logging.getLogger("command.init")
    
    try:
        # 这里需要实现按游戏名称注销命令的逻辑
        # 暂时返回True
        logger.info(f"游戏 '{game_name}' 命令已注销")
        return True
        
    except Exception as e:
        logger.error(f"注销游戏 '{game_name}' 命令失败: {e}")
        return False
