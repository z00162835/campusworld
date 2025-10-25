"""
建造命令模块初始化
"""

from app.commands.builder.model_discovery import ModelDiscoverer
from app.commands.builder.create_command import CreateCommand, CreateInfoCommand
from app.core.log import get_logger, LoggerNames

logger = get_logger(LoggerNames.COMMAND)

def initialize_build_commands():
    """初始化建造命令系统"""
    try:
        logger.info("初始化建造命令系统...")
        
        # 发现模型类
        ModelDiscoverer.discover_models()
        
        # 创建建造命令集合
        build_cmdset = CreateCommand()
        build_cmdset.add_command(CreateInfoCommand())
        
        logger.info("建造命令系统初始化完成")
        return build_cmdset
        
    except Exception as e:
        logger.error(f"建造命令系统初始化失败: {e}")
        return None

# 自动初始化
build_cmdset = initialize_build_commands()