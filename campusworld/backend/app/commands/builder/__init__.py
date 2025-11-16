"""
建造命令模块初始化
"""
from app.commands.cmdset import CmdSet
from app.commands.builder.model_discovery import model_discoverer
from app.commands.builder.create_command import CreateCommand, CreateInfoCommand
from app.core.log import get_logger, LoggerNames

logger = get_logger(LoggerNames.COMMAND)

class BuildCmdSet(CmdSet):
    """建造命令集合"""
    def __init__(self):
        super().__init__()
        self.add_command(CreateCommand())
        self.add_command(CreateInfoCommand())
        self.priority = 100


def initialize_build_commands():
    """初始化建造命令系统"""
    try:
        logger.info("初始化建造命令系统...")

        model_discoverer.discover_models()

        build_cmdset = BuildCmdSet()

        logger.info("建造命令系统初始化完成")
        return build_cmdset
    except Exception as e:
        logger.error(f"建造命令系统初始化失败: {e}")
        return None


# 自动初始化
build_cmdset = initialize_build_commands()