"""
校园生活游戏命令注册
将游戏命令注册到全局命令系统
"""

import logging
from app.commands.registry import command_registry
from .game_commands import CAMPUS_LIFE_GAME_COMMANDS


def register_campus_life_commands() -> bool:
    """注册校园生活游戏命令"""
    logger = logging.getLogger("game.campus_life.commands")
    
    try:
        logger.info("开始注册校园生活游戏命令...")
        
        success_count = 0
        for command in CAMPUS_LIFE_GAME_COMMANDS:
            if command_registry.register_command(command):
                success_count += 1
                logger.debug(f"游戏命令 '{command.name}' 注册成功")
            else:
                logger.error(f"游戏命令 '{command.name}' 注册失败")
        
        logger.info(f"校园生活游戏命令注册完成: {success_count}/{len(CAMPUS_LIFE_GAME_COMMANDS)}")
        return success_count == len(CAMPUS_LIFE_GAME_COMMANDS)
        
    except Exception as e:
        logger.error(f"注册校园生活游戏命令失败: {e}")
        return False


def unregister_campus_life_commands() -> bool:
    """注销校园生活游戏命令"""
    logger = logging.getLogger("game.campus_life.commands")
    
    try:
        logger.info("开始注销校园生活游戏命令...")
        
        success_count = 0
        for command in CAMPUS_LIFE_GAME_COMMANDS:
            if command_registry.unregister_command(command.name):
                success_count += 1
                logger.debug(f"游戏命令 '{command.name}' 注销成功")
            else:
                logger.warning(f"游戏命令 '{command.name}' 注销失败")
        
        logger.info(f"校园生活游戏命令注销完成: {success_count}/{len(CAMPUS_LIFE_GAME_COMMANDS)}")
        return success_count == len(CAMPUS_LIFE_GAME_COMMANDS)
        
    except Exception as e:
        logger.error(f"注销校园生活游戏命令失败: {e}")
        return False

