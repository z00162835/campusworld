"""
系统命令集合

管理所有系统命令，包括查看、统计、帮助、版本、时间等
参考Evennia框架的CmdSet设计

作者：AI Assistant
创建时间：2025-08-24
"""

from ..base import CmdSet
from . import CmdLook, CmdStats, CmdHelp, CmdVersion, CmdTime


class SystemCmdSet(CmdSet):
    """
    系统命令集合
    
    包含所有系统级命令，这些命令对所有用户都可用
    """
    
    key = "system_cmdset"
    mergetype = "Union"  # 与其他命令集合合并
    priority = 0          # 基础优先级
    
    def at_cmdset_creation(self):
        """创建命令集合时调用"""
        # 添加所有系统命令
        self.add(CmdLook)
        self.add(CmdStats)
        self.add(CmdHelp)
        self.add(CmdVersion)
        self.add(CmdTime)
        
        # 设置命令集合描述
        self.description = "系统命令集合 - 提供基础系统功能"
        self.category = "system"
    
    def get_help(self, category: str = None) -> str:
        """
        获取帮助信息
        
        Args:
            category: 指定分类，None表示所有分类
            
        Returns:
            帮助信息字符串
        """
        if category and category.lower() != 'system':
            return ""
        
        help_text = """
系统命令集合 - 提供基础系统功能

可用命令:
  look (l, examine, exa)     - 查看对象、房间、方向等
  stats (stat, system, sys)  - 显示系统统计信息
  help (h, ?, man)           - 显示命令帮助信息
  version (ver, v, about)    - 显示系统版本信息
  time (t, clock, date)      - 显示时间和日期信息

使用 help <命令名> 获取特定命令的详细帮助
        """
        
        return help_text.strip()
    
    def get_command_info(self) -> dict:
        """
        获取命令集合信息
        
        Returns:
            命令集合信息字典
        """
        return {
            'key': self.key,
            'mergetype': self.mergetype,
            'priority': self.priority,
            'description': self.description,
            'category': self.category,
            'command_count': len(self.commands),
            'commands': list(self.commands.keys())
        }
