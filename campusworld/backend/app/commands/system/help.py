"""
Help命令 - 帮助命令

用于显示命令帮助信息，包括命令用法、参数说明、示例等
参考Evennia框架的help命令设计

作者：AI Assistant
创建时间：2025-08-24
"""

from typing import Optional, List, Dict, Any
from ..base import Command


class CmdHelp(Command):
    """
    Help命令 - 帮助命令
    
    用法:
        help                    - 显示帮助概览
        help <命令>            - 显示指定命令的帮助
        help <分类>            - 显示指定分类的命令
        help -a                - 显示所有命令
        help -c <分类>         - 显示指定分类的命令
        help -s <搜索词>       - 搜索命令
    """
    
    key = "help"
    aliases = ["h", "?", "man"]
    locks = ""
    help_category = "system"
    help_entry = """
帮助命令用于显示命令帮助信息，包括命令用法、参数说明、示例等。

用法:
  help                    - 显示帮助概览
  help <命令>            - 显示指定命令的帮助
  help <分类>            - 显示指定分类的命令
  help -a                - 显示所有命令
  help -c <分类>         - 显示指定分类的命令
  help -s <搜索词>       - 搜索命令

示例:
  help                   - 显示帮助概览
  help look              - 显示look命令帮助
  help system            - 显示系统命令
  help -a                - 显示所有命令
  help -c admin          - 显示管理命令
  help -s "查看"         - 搜索包含"查看"的命令

开关参数:
  -a, --all              - 显示所有命令
  -c, --category <分类>  - 显示指定分类的命令
  -s, --search <搜索词>  - 搜索命令
  -v, --verbose          - 详细模式
  -f, --format <格式>    - 指定输出格式 (text, json, csv)
    """
    
    def func(self) -> None:
        """执行help命令"""
        args = self.parsed_args
        
        # 检查开关参数
        show_all = '-a' in args.get('switches', []) or '--all' in args.get('switches', [])
        verbose = '-v' in args.get('switches', []) or '--verbose' in args.get('switches', [])
        format_output = '-f' in args.get('switches', []) or '--format' in args.get('switches', [])
        
        # 获取分类参数
        category = self._get_category_arg(args)
        
        # 获取搜索参数
        search_term = self._get_search_arg(args)
        
        # 获取输出格式
        output_format = self._get_output_format(args)
        
        # 如果没有参数，显示帮助概览
        if not args.get('args') and not show_all and not category and not search_term:
            self.show_help_overview()
            return
        
        # 如果指定了搜索词
        if search_term:
            self.search_commands(search_term, verbose, output_format)
            return
        
        # 如果指定了分类
        if category:
            self.show_commands_by_category(category, verbose, output_format)
            return
        
        # 如果显示所有命令
        if show_all:
            self.show_all_commands(verbose, output_format)
            return
        
        # 如果指定了命令名
        command_name = args.get('args', '').strip()
        if command_name:
            self.show_command_help(command_name, verbose, output_format)
            return
    
    def _get_category_arg(self, args: Dict[str, Any]) -> Optional[str]:
        """获取分类参数"""
        # 检查 -c 开关
        for i, switch in enumerate(args.get('switches', [])):
            if switch in ['-c', '--category']:
                if i + 1 < len(args.get('switches', [])):
                    return args['switches'][i + 1]
                break
        
        # 检查参数中是否包含分类信息
        if args.get('args'):
            # 这里可以解析参数中的分类信息
            pass
        
        return None
    
    def _get_search_arg(self, args: Dict[str, Any]) -> Optional[str]:
        """获取搜索参数"""
        # 检查 -s 开关
        for i, switch in enumerate(args.get('switches', [])):
            if switch in ['-s', '--search']:
                if i + 1 < len(args.get('switches', [])):
                    return args['switches'][i + 1]
                break
        
        return None
    
    def _get_output_format(self, args: Dict[str, Any]) -> str:
        """获取输出格式"""
        format_arg = args.get('lhs') or args.get('args', '')
        
        if 'json' in format_arg.lower():
            return 'json'
        elif 'csv' in format_arg.lower():
            return 'csv'
        else:
            return 'text'
    
    def show_help_overview(self) -> None:
        """显示帮助概览"""
        self.msg("=" * 60)
        self.msg("📚 CampusWorld 命令帮助系统")
        self.msg("=" * 60)
        self.msg("")
        self.msg("🎯 快速开始:")
        self.msg("  help <命令名>     - 查看特定命令的帮助")
        self.msg("  help <分类>       - 查看分类下的所有命令")
        self.msg("  help -a           - 查看所有可用命令")
        self.msg("  help -s <关键词>  - 搜索相关命令")
        self.msg("")
        self.msg("📂 主要分类:")
        
        # 获取可用分类
        categories = self.get_available_categories()
        for category in categories:
            category_name = category.get('name', 'Unknown')
            command_count = category.get('count', 0)
            description = category.get('description', '')
            self.msg(f"  {category_name:<15} - {description} ({command_count}个命令)")
        
        self.msg("")
        self.msg("💡 提示:")
        self.msg("  • 使用 help -v 获取详细帮助信息")
        self.msg("  • 使用 help -f json 获取JSON格式输出")
        self.msg("  • 命令可以组合使用，如: help -c system -v")
        self.msg("")
        self.msg("🔍 常用命令:")
        self.msg("  look              - 查看周围环境")
        self.msg("  stats             - 查看系统统计")
        self.msg("  help              - 显示此帮助信息")
        self.msg("  version           - 显示系统版本")
        self.msg("")
        self.msg("=" * 60)
    
    def show_command_help(self, command_name: str, verbose: bool = False, 
                         output_format: str = 'text') -> None:
        """
        显示指定命令的帮助
        
        Args:
            command_name: 命令名称
            verbose: 是否详细模式
            output_format: 输出格式
        """
        # 查找命令
        command_class = self.find_command(command_name)
        
        if not command_class:
            self.msg(f"❌ 找不到命令: {command_name}")
            self.msg("💡 使用 'help -a' 查看所有可用命令")
            return
        
        # 创建命令实例获取帮助信息
        command = command_class(cmdstring=command_name, args="")
        
        if output_format == 'json':
            self._display_command_help_json(command, verbose)
        elif output_format == 'csv':
            self._display_command_help_csv(command, verbose)
        else:
            self._display_command_help_text(command, verbose)
    
    def show_commands_by_category(self, category: str, verbose: bool = False, 
                                output_format: str = 'text') -> None:
        """
        显示指定分类的命令
        
        Args:
            category: 分类名称
            verbose: 是否详细模式
            output_format: 输出格式
        """
        # 获取分类下的命令
        commands = self.get_commands_by_category(category)
        
        if not commands:
            self.msg(f"❌ 找不到分类: {category}")
            self.msg("💡 使用 'help' 查看所有可用分类")
            return
        
        if output_format == 'json':
            self._display_category_commands_json(category, commands, verbose)
        elif output_format == 'csv':
            self._display_category_commands_csv(category, commands, verbose)
        else:
            self._display_category_commands_text(category, commands, verbose)
    
    def show_all_commands(self, verbose: bool = False, output_format: str = 'text') -> None:
        """
        显示所有命令
        
        Args:
            verbose: 是否详细模式
            output_format: 输出格式
        """
        # 获取所有命令
        all_commands = self.get_all_commands()
        
        if output_format == 'json':
            self._display_all_commands_json(all_commands, verbose)
        elif output_format == 'csv':
            self._display_all_commands_csv(all_commands, verbose)
        else:
            self._display_all_commands_text(all_commands, verbose)
    
    def search_commands(self, search_term: str, verbose: bool = False, 
                       output_format: str = 'text') -> None:
        """
        搜索命令
        
        Args:
            search_term: 搜索词
            verbose: 是否详细模式
            output_format: 输出格式
        """
        # 搜索命令
        search_results = self.search_commands_by_term(search_term)
        
        if not search_results:
            self.msg(f"🔍 搜索 '{search_term}' 没有找到结果")
            self.msg("💡 尝试使用其他关键词或使用 'help -a' 查看所有命令")
            return
        
        if output_format == 'json':
            self._display_search_results_json(search_term, search_results, verbose)
        elif output_format == 'csv':
            self._display_search_results_csv(search_term, search_results, verbose)
        else:
            self._display_search_results_text(search_term, search_results, verbose)
    
    def find_command(self, command_name: str):
        """查找命令类"""
        if not self.cmdset:
            return None
        
        return self.cmdset.get(command_name)
    
    def get_available_categories(self) -> List[Dict[str, Any]]:
        """获取可用分类"""
        if not self.cmdset:
            return []
        
        categories = []
        for category in self.cmdset.get_categories():
            commands = self.cmdset.get_commands_by_category(category)
            categories.append({
                'name': category,
                'count': len(commands),
                'description': self._get_category_description(category)
            })
        
        return categories
    
    def get_commands_by_category(self, category: str) -> List[Any]:
        """获取分类下的命令"""
        if not self.cmdset:
            return []
        
        return self.cmdset.get_commands_by_category(category)
    
    def get_all_commands(self) -> List[Any]:
        """获取所有命令"""
        if not self.cmdset:
            return []
        
        return self.cmdset.get_commands()
    
    def search_commands_by_term(self, search_term: str) -> List[Any]:
        """根据搜索词搜索命令"""
        if not self.cmdset:
            return []
        
        search_results = []
        all_commands = self.cmdset.get_commands()
        
        for command_class in all_commands:
            # 搜索命令名
            if search_term.lower() in command_class.key.lower():
                search_results.append(command_class)
                continue
            
            # 搜索别名
            for alias in command_class.aliases:
                if search_term.lower() in alias.lower():
                    search_results.append(command_class)
                    break
            
            # 搜索描述
            if command_class.help_entry and search_term.lower() in command_class.help_entry.lower():
                search_results.append(command_class)
                continue
        
        return search_results
    
    def _get_category_description(self, category: str) -> str:
        """获取分类描述"""
        descriptions = {
            'system': '系统基础命令',
            'admin': '管理员命令',
            'user': '用户命令',
            'general': '通用命令'
        }
        return descriptions.get(category, '其他命令')
    
    def _display_command_help_text(self, command: Any, verbose: bool) -> None:
        """文本格式显示命令帮助"""
        self.msg("=" * 60)
        self.msg(f"📖 命令帮助: {command.key}")
        self.msg("=" * 60)
        
        # 基本信息
        self.msg(f"命令: {command.key}")
        if command.aliases:
            self.msg(f"别名: {', '.join(command.aliases)}")
        self.msg(f"分类: {command.help_category}")
        self.msg(f"描述: {command.description}")
        
        # 详细帮助
        if command.help_entry:
            self.msg("")
            self.msg("详细帮助:")
            self.msg(command.help_entry)
        
        # 用法
        self.msg("")
        self.msg("用法:")
        self.msg(command.usage())
        
        # 权限信息
        if command.locks:
            self.msg("")
            self.msg(f"权限要求: {command.locks}")
        
        # 元数据
        if verbose:
            self.msg("")
            self.msg("元数据:")
            self.msg(f"  创建时间: {command.get_created_at()}")
            self.msg(f"  更新时间: {command.get_updated_at()}")
            self.msg(f"  是否为出口命令: {command.is_exit_command()}")
            self.msg(f"  是否为频道命令: {command.is_channel_command()}")
        
        self.msg("=" * 60)
    
    def _display_command_help_json(self, command: Any, verbose: bool) -> None:
        """JSON格式显示命令帮助"""
        import json
        
        help_data = command.to_dict()
        if verbose:
            help_data.update({
                'created_at': command.get_created_at().isoformat() if command.get_created_at() else None,
                'updated_at': command.get_updated_at().isoformat() if command.get_updated_at() else None,
                'is_exit': command.is_exit_command(),
                'is_channel': command.is_channel_command()
            })
        
        json_str = json.dumps(help_data, indent=2, ensure_ascii=False)
        self.msg(json_str)
    
    def _display_command_help_csv(self, command: Any, verbose: bool) -> None:
        """CSV格式显示命令帮助"""
        # 暂时使用文本格式
        self._display_command_help_text(command, verbose)
    
    def _display_category_commands_text(self, category: str, commands: List[Any], verbose: bool) -> None:
        """文本格式显示分类命令"""
        self.msg("=" * 60)
        self.msg(f"📂 分类: {category}")
        self.msg(f"命令数量: {len(commands)}")
        self.msg("=" * 60)
        
        for i, command_class in enumerate(commands, 1):
            self.msg(f"{i:2d}. {command_class.key:<15} - {command_class.help_entry or command_class.description}")
            
            if verbose and command_class.aliases:
                self.msg(f"    别名: {', '.join(command_class.aliases)}")
        
        self.msg("")
        self.msg(f"💡 使用 'help <命令名>' 查看特定命令的详细帮助")
        self.msg("=" * 60)
    
    def _display_category_commands_json(self, category: str, commands: List[Any], verbose: bool) -> None:
        """JSON格式显示分类命令"""
        import json
        
        commands_data = []
        for command_class in commands:
            cmd_data = {
                'key': command_class.key,
                'description': command_class.help_entry or command_class.description,
                'category': command_class.help_category
            }
            if verbose:
                cmd_data.update({
                    'aliases': command_class.aliases,
                    'locks': command_class.locks
                })
            commands_data.append(cmd_data)
        
        category_data = {
            'category': category,
            'command_count': len(commands),
            'commands': commands_data
        }
        
        json_str = json.dumps(category_data, indent=2, ensure_ascii=False)
        self.msg(json_str)
    
    def _display_category_commands_csv(self, category: str, commands: List[Any], verbose: bool) -> None:
        """CSV格式显示分类命令"""
        # 暂时使用文本格式
        self._display_category_commands_text(category, commands, verbose)
    
    def _display_all_commands_text(self, commands: List[Any], verbose: bool) -> None:
        """文本格式显示所有命令"""
        self.msg("=" * 60)
        self.msg(f"📚 所有命令 ({len(commands)}个)")
        self.msg("=" * 60)
        
        # 按分类组织
        categories = {}
        for command_class in commands:
            category = command_class.help_category
            if category not in categories:
                categories[category] = []
            categories[category].append(command_class)
        
        for category in sorted(categories.keys()):
            self.msg(f"\n【{category}】")
            category_commands = categories[category]
            for i, command_class in enumerate(category_commands, 1):
                self.msg(f"  {i:2d}. {command_class.key:<15} - {command_class.help_entry or command_class.description}")
                
                if verbose and command_class.aliases:
                    self.msg(f"      别名: {', '.join(command_class.aliases)}")
        
        self.msg("")
        self.msg("💡 使用 'help <命令名>' 查看特定命令的详细帮助")
        self.msg("💡 使用 'help <分类>' 查看分类下的命令")
        self.msg("=" * 60)
    
    def _display_all_commands_json(self, commands: List[Any], verbose: bool) -> None:
        """JSON格式显示所有命令"""
        import json
        
        # 按分类组织
        categories = {}
        for command_class in commands:
            category = command_class.help_category
            if category not in categories:
                categories[category] = []
            
            cmd_data = {
                'key': command_class.key,
                'description': command_class.help_entry or command_class.description
            }
            if verbose:
                cmd_data.update({
                    'aliases': command_class.aliases,
                    'locks': command_class.locks
                })
            categories[category].append(cmd_data)
        
        all_commands_data = {
            'total_commands': len(commands),
            'categories': categories
        }
        
        json_str = json.dumps(all_commands_data, indent=2, ensure_ascii=False)
        self.msg(json_str)
    
    def _display_all_commands_csv(self, commands: List[Any], verbose: bool) -> None:
        """CSV格式显示所有命令"""
        # 暂时使用文本格式
        self._display_all_commands_text(commands, verbose)
    
    def _display_search_results_text(self, search_term: str, results: List[Any], verbose: bool) -> None:
        """文本格式显示搜索结果"""
        self.msg("=" * 60)
        self.msg(f"🔍 搜索 '{search_term}' 的结果 ({len(results)}个)")
        self.msg("=" * 60)
        
        for i, command_class in enumerate(results, 1):
            self.msg(f"{i:2d}. {command_class.key:<15} - {command_class.help_entry or command_class.description}")
            self.msg(f"    分类: {command_class.help_category}")
            
            if verbose and command_class.aliases:
                self.msg(f"    别名: {', '.join(command_class.aliases)}")
            
            self.msg("")
        
        self.msg("💡 使用 'help <命令名>' 查看特定命令的详细帮助")
        self.msg("=" * 60)
    
    def _display_search_results_json(self, search_term: str, results: List[Any], verbose: bool) -> None:
        """JSON格式显示搜索结果"""
        import json
        
        results_data = []
        for command_class in results:
            cmd_data = {
                'key': command_class.key,
                'description': command_class.help_entry or command_class.description,
                'category': command_class.help_category
            }
            if verbose:
                cmd_data.update({
                    'aliases': command_class.aliases,
                    'locks': command_class.locks
                })
            results_data.append(cmd_data)
        
        search_data = {
            'search_term': search_term,
            'result_count': len(results),
            'results': results_data
        }
        
        json_str = json.dumps(search_data, indent=2, ensure_ascii=False)
        self.msg(json_str)
    
    def _display_search_results_csv(self, search_term: str, results: List[Any], verbose: bool) -> None:
        """CSV格式显示搜索结果"""
        # 暂时使用文本格式
        self._display_search_results_text(search_term, results, verbose)
