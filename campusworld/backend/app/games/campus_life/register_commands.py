"""
园区世界命令注册
将场景命令注册到全局命令系统
"""

import logging
from app.commands.registry import command_registry
from .game_commands import CAMPUS_LIFE_GAME_COMMANDS


def register_campus_life_commands() -> bool:
    """注册园区世界命令"""
    logger = logging.getLogger("game.campus_life.commands")
    
    try:
        logger.info("开始注册园区世界命令...")
        
        success_count = 0
        for command in CAMPUS_LIFE_GAME_COMMANDS:
            if command_registry.register_command(command):
                success_count += 1
                logger.debug(f"场景命令 '{command.name}' 注册成功")
            else:
                logger.error(f"场景命令 '{command.name}' 注册失败")
        
        logger.info(f"园区世界命令注册完成: {success_count}/{len(CAMPUS_LIFE_GAME_COMMANDS)}")
        return success_count == len(CAMPUS_LIFE_GAME_COMMANDS)
        
    except Exception as e:
        logger.error(f"注册园区世界命令失败: {e}")
        return False


def unregister_campus_life_commands() -> bool:
    """注销园区世界命令"""
    logger = logging.getLogger("game.campus_life.commands")
    
    try:
        logger.info("开始注销园区世界命令...")
        
        success_count = 0
        for command in CAMPUS_LIFE_GAME_COMMANDS:
            if command_registry.unregister_command(command.name):
                success_count += 1
                logger.debug(f"场景命令 '{command.name}' 注销成功")
            else:
                logger.warning(f"场景命令 '{command.name}' 注销失败")
        
        logger.info(f"园区世界命令注销完成: {success_count}/{len(CAMPUS_LIFE_GAME_COMMANDS)}")
        return success_count == len(CAMPUS_LIFE_GAME_COMMANDS)
        
    except Exception as e:
        logger.error(f"注销园区世界命令失败: {e}")
        return False

