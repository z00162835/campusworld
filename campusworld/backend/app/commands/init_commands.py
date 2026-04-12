"""
命令初始化模块
负责注册所有系统命令和场景命令
"""

from .registry import command_registry
from .system_commands import SYSTEM_COMMANDS
from .agent_commands import AGENT_COMMANDS
from .game import GAME_COMMANDS
from .builder import build_cmdset
import threading
from app.core.log import get_logger, LoggerNames
logger = get_logger(LoggerNames.COMMAND)

_commands_initialized = False
_init_lock = threading.Lock()


def initialize_commands(force_reinit: bool = False) -> bool:
    """初始化命令系统 - 单例模式"""
    global _commands_initialized
    
    if _commands_initialized and not force_reinit:
        return True
    
    with _init_lock:
        if _commands_initialized and not force_reinit:
            return True
        
        try:
            
            # 注册系统命令
            system_success = 0
            for command in SYSTEM_COMMANDS:
                if command_registry.register_command(command):
                    system_success += 1
                else:
                    logger.error(f"系统命令 '{command.name}' 注册失败")
            for command in AGENT_COMMANDS:
                if command_registry.register_command(command):
                    system_success += 1
                else:
                    logger.error(f"系统命令 '{command.name}' 注册失败")
            
            # 注册场景命令
            game_success = 0
            for command in GAME_COMMANDS:
                if command_registry.register_command(command):
                    game_success += 1
                else:
                    logger.error(f"场景命令 '{command.name}' 注册失败")
            
            if build_cmdset:
                build_success = 0
                for command in build_cmdset.get_commands().values():
                    if command_registry.register_command(command):
                        build_success += 1
                    else:
                        logger.error(f"建造命令 '{command.name}' 注册失败")

            try:
                from app.core.database import db_session_context
                from app.commands.policy_store import ensure_default_command_policies

                with db_session_context() as session:
                    ensure_default_command_policies(session)
                    try:
                        from app.commands.ability_sync import ensure_command_ability_nodes

                        ensure_command_ability_nodes(session)
                    except Exception as e:
                        logger.error("command ability sync failed: %s", e)
                        return False
            except Exception as e:
                logger.error("command policy bootstrap failed: %s", e)
                return False

            # 显示注册摘要
            summary = command_registry.get_commands_summary()
            
            _commands_initialized = True
            expected_sys = len(SYSTEM_COMMANDS) + len(AGENT_COMMANDS)
            return system_success == expected_sys and game_success == len(GAME_COMMANDS)
            
        except Exception as e:
            logger.error(f"命令系统初始化失败: {e}")
            return False


def ensure_commands_initialized() -> None:
    """
    若注册表仍为空则执行初始化。
    历史上 initialize_commands 仅在 SSH 控制台首次连接时调用，纯 HTTP/WebSocket/CLI 会拿到空 registry。
    """
    if command_registry.commands:
        return
    initialize_commands()


def get_command_summary() -> dict:
    """获取命令摘要"""
    return command_registry.get_commands_summary()


def register_game_commands(game_name: str, commands: list) -> bool:
    """注册场景特定命令"""
    try:
        success_count = 0
        for command in commands:
            if command_registry.register_command(command):
                success_count += 1
            else:
                logger.error(f"场景 '{game_name}' 命令 '{command.name}' 注册失败")
        
        logger.info(f"场景 '{game_name}' 命令注册完成: {success_count}/{len(commands)}")
        return success_count == len(commands)
        
    except Exception as e:
        logger.error(f"注册场景 '{game_name}' 命令失败: {e}")
        return False


def unregister_game_commands(game_name: str) -> bool:
    """注销场景特定命令"""
    try:
        # 这里需要实现按场景名称注销命令的逻辑
        # 暂时返回True
        logger.info(f"场景 '{game_name}' 命令已注销")
        return True
        
    except Exception as e:
        logger.error(f"注销场景 '{game_name}' 命令失败: {e}")
        return False
