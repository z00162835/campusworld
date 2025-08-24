"""
Stats命令 - 统计命令

用于显示系统统计信息，包括系统状态、性能指标、用户统计等
参考Evennia框架的stats命令设计

作者：AI Assistant
创建时间：2025-08-24
"""

import time
import psutil
from typing import Dict, Any, List
from ..base import Command


class CmdStats(Command):
    """
    Stats命令 - 统计命令
    
    用法:
        stats                    - 显示系统基本统计
        stats -s                - 显示系统状态
        stats -p                - 显示性能指标
        stats -u                - 显示用户统计
        stats -a                - 显示所有统计信息
        stats -f <格式>         - 指定输出格式
    """
    
    key = "stats"
    aliases = ["stat", "system", "sys"]
    locks = ""
    help_category = "system"
    help_entry = """
统计命令用于显示系统统计信息，包括系统状态、性能指标、用户统计等。

用法:
  stats                    - 显示系统基本统计
  stats -s                - 显示系统状态
  stats -p                - 显示性能指标
  stats -u                - 显示用户统计
  stats -a                - 显示所有统计信息
  stats -f <格式>         - 指定输出格式

示例:
  stats                   - 显示基本统计
  stats -s                - 显示系统状态
  stats -p                - 显示性能指标
  stats -u                - 显示用户统计
  stats -a                - 显示所有信息
  stats -f json           - JSON格式输出

开关参数:
  -s, --system            - 显示系统状态
  -p, --performance       - 显示性能指标
  -u, --users             - 显示用户统计
  -a, --all               - 显示所有信息
  -f, --format <格式>     - 指定输出格式 (text, json, csv)
  -v, --verbose           - 详细模式
  -t, --timestamp         - 显示时间戳
    """
    
    def func(self) -> None:
        """执行stats命令"""
        args = self.parsed_args
        
        # 检查开关参数
        show_system = '-s' in args.get('switches', []) or '--system' in args.get('switches', [])
        show_performance = '-p' in args.get('switches', []) or '--performance' in args.get('switches', [])
        show_users = '-u' in args.get('switches', []) or '--users' in args.get('switches', [])
        show_all = '-a' in args.get('switches', []) or '--all' in args.get('switches', [])
        verbose = '-v' in args.get('switches', []) or '--verbose' in args.get('switches', [])
        show_timestamp = '-t' in args.get('switches', []) or '--timestamp' in args.get('switches', [])
        
        # 获取输出格式
        output_format = self._get_output_format(args)
        
        # 如果没有指定特定类型，显示基本统计
        if not any([show_system, show_performance, show_users, show_all]):
            show_all = True
        
        # 收集统计信息
        stats_data = self._collect_stats(show_system, show_performance, show_users, show_all, verbose)
        
        # 显示统计信息
        self._display_stats(stats_data, output_format, show_timestamp)
    
    def _get_output_format(self, args: Dict[str, Any]) -> str:
        """获取输出格式"""
        format_arg = args.get('lhs') or args.get('args', '')
        
        if 'json' in format_arg.lower():
            return 'json'
        elif 'csv' in format_arg.lower():
            return 'csv'
        else:
            return 'text'
    
    def _collect_stats(self, show_system: bool, show_performance: bool, 
                      show_users: bool, show_all: bool, verbose: bool) -> Dict[str, Any]:
        """
        收集统计信息
        
        Args:
            show_system: 是否显示系统状态
            show_performance: 是否显示性能指标
            show_users: 是否显示用户统计
            show_all: 是否显示所有信息
            verbose: 是否详细模式
            
        Returns:
            统计信息字典
        """
        stats = {
            'timestamp': time.time(),
            'basic': {},
            'system': {},
            'performance': {},
            'users': {},
            'database': {},
            'application': {}
        }
        
        # 基本统计信息
        if show_all or True:  # 基本统计总是显示
            stats['basic'] = self._get_basic_stats()
        
        # 系统状态
        if show_system or show_all:
            stats['system'] = self._get_system_stats(verbose)
        
        # 性能指标
        if show_performance or show_all:
            stats['performance'] = self._get_performance_stats(verbose)
        
        # 用户统计
        if show_users or show_all:
            stats['users'] = self._get_user_stats(verbose)
        
        # 数据库统计
        if show_all:
            stats['database'] = self._get_database_stats(verbose)
        
        # 应用统计
        if show_all:
            stats['application'] = self._get_application_stats(verbose)
        
        return stats
    
    def _get_basic_stats(self) -> Dict[str, Any]:
        """获取基本统计信息"""
        return {
            'uptime': self._get_uptime(),
            'version': self._get_version(),
            'environment': self._get_environment(),
            'start_time': self._get_start_time()
        }
    
    def _get_system_stats(self, verbose: bool = False) -> Dict[str, Any]:
        """获取系统状态信息"""
        try:
            stats = {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory': self._get_memory_info(),
                'disk': self._get_disk_info(),
                'network': self._get_network_info()
            }
            
            if verbose:
                stats.update({
                    'cpu_count': psutil.cpu_count(),
                    'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {},
                    'boot_time': psutil.boot_time(),
                    'users': len(psutil.users())
                })
            
            return stats
        except Exception as e:
            return {'error': f"获取系统状态失败: {e}"}
    
    def _get_performance_stats(self, verbose: bool = False) -> Dict[str, Any]:
        """获取性能指标"""
        try:
            stats = {
                'load_average': self._get_load_average(),
                'process_count': len(psutil.pids()),
                'thread_count': self._get_thread_count()
            }
            
            if verbose:
                stats.update({
                    'io_counters': psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else {},
                    'swap': psutil.swap_memory()._asdict() if hasattr(psutil, 'swap_memory') else {}
                })
            
            return stats
        except Exception as e:
            return {'error': f"获取性能指标失败: {e}"}
    
    def _get_user_stats(self, verbose: bool = False) -> Dict[str, Any]:
        """获取用户统计信息"""
        try:
            # 这里需要根据实际的用户模型来实现
            # 暂时返回模拟数据
            stats = {
                'total_users': 0,
                'online_users': 0,
                'active_users': 0,
                'new_users_today': 0
            }
            
            if verbose:
                stats.update({
                    'user_distribution': {},
                    'user_activity': {},
                    'user_growth': {}
                })
            
            return stats
        except Exception as e:
            return {'error': f"获取用户统计失败: {e}"}
    
    def _get_database_stats(self, verbose: bool = False) -> Dict[str, Any]:
        """获取数据库统计信息"""
        try:
            # 这里需要根据实际的数据库连接来实现
            # 暂时返回模拟数据
            stats = {
                'connection_count': 0,
                'query_count': 0,
                'slow_queries': 0,
                'database_size': 0
            }
            
            if verbose:
                stats.update({
                    'table_count': 0,
                    'index_count': 0,
                    'cache_hit_rate': 0.0
                })
            
            return stats
        except Exception as e:
            return {'error': f"获取数据库统计失败: {e}"}
    
    def _get_application_stats(self, verbose: bool = False) -> Dict[str, Any]:
        """获取应用统计信息"""
        try:
            stats = {
                'command_count': 0,
                'session_count': 0,
                'error_count': 0,
                'request_count': 0
            }
            
            if verbose:
                stats.update({
                    'command_history': [],
                    'error_log': [],
                    'performance_metrics': {}
                })
            
            return stats
        except Exception as e:
            return {'error': f"获取应用统计失败: {e}"}
    
    def _get_uptime(self) -> str:
        """获取系统运行时间"""
        try:
            uptime_seconds = time.time() - psutil.boot_time()
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            
            if days > 0:
                return f"{days}天 {hours}小时 {minutes}分钟"
            elif hours > 0:
                return f"{hours}小时 {minutes}分钟"
            else:
                return f"{minutes}分钟"
        except:
            return "未知"
    
    def _get_version(self) -> str:
        """获取系统版本"""
        try:
            import platform
            return f"{platform.system()} {platform.release()}"
        except:
            return "未知"
    
    def _get_environment(self) -> str:
        """获取运行环境"""
        try:
            import os
            return os.getenv('ENVIRONMENT', 'development')
        except:
            return "development"
    
    def _get_start_time(self) -> str:
        """获取应用启动时间"""
        try:
            # 这里需要根据实际的启动时间来实现
            # 暂时返回当前时间
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        except:
            return "未知"
    
    def _get_memory_info(self) -> Dict[str, Any]:
        """获取内存信息"""
        try:
            memory = psutil.virtual_memory()
            return {
                'total': self._format_bytes(memory.total),
                'available': self._format_bytes(memory.available),
                'used': self._format_bytes(memory.used),
                'percent': memory.percent
            }
        except:
            return {'error': '获取内存信息失败'}
    
    def _get_disk_info(self) -> Dict[str, Any]:
        """获取磁盘信息"""
        try:
            disk = psutil.disk_usage('/')
            return {
                'total': self._format_bytes(disk.total),
                'used': self._format_bytes(disk.used),
                'free': self._format_bytes(disk.free),
                'percent': (disk.used / disk.total) * 100
            }
        except:
            return {'error': '获取磁盘信息失败'}
    
    def _get_network_info(self) -> Dict[str, Any]:
        """获取网络信息"""
        try:
            network = psutil.net_io_counters()
            return {
                'bytes_sent': self._format_bytes(network.bytes_sent),
                'bytes_recv': self._format_bytes(network.bytes_recv),
                'packets_sent': network.packets_sent,
                'packets_recv': network.packets_recv
            }
        except:
            return {'error': '获取网络信息失败'}
    
    def _get_load_average(self) -> List[float]:
        """获取负载平均值"""
        try:
            return psutil.getloadavg()
        except:
            return [0.0, 0.0, 0.0]
    
    def _get_thread_count(self) -> int:
        """获取线程数量"""
        try:
            return psutil.Process().num_threads()
        except:
            return 0
    
    def _format_bytes(self, bytes_value: int) -> str:
        """格式化字节数"""
        if bytes_value == 0:
            return "0B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while bytes_value >= 1024 and i < len(size_names) - 1:
            bytes_value /= 1024.0
            i += 1
        
        return f"{bytes_value:.1f}{size_names[i]}"
    
    def _display_stats(self, stats: Dict[str, Any], output_format: str, show_timestamp: bool) -> None:
        """
        显示统计信息
        
        Args:
            stats: 统计信息字典
            output_format: 输出格式
            show_timestamp: 是否显示时间戳
        """
        if output_format == 'json':
            self._display_json(stats, show_timestamp)
        elif output_format == 'csv':
            self._display_csv(stats, show_timestamp)
        else:
            self._display_text(stats, show_timestamp)
    
    def _display_text(self, stats: Dict[str, Any], show_timestamp: bool) -> None:
        """文本格式显示"""
        self.msg("=" * 60)
        self.msg("📊 CampusWorld 系统统计信息")
        self.msg("=" * 60)
        
        if show_timestamp:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stats['timestamp']))
            self.msg(f"⏰ 统计时间: {timestamp}")
            self.msg("")
        
        # 基本统计
        if stats['basic']:
            self.msg("🔧 基本统计")
            self.msg("-" * 30)
            for key, value in stats['basic'].items():
                self.msg(f"  {key}: {value}")
            self.msg("")
        
        # 系统状态
        if stats['system']:
            self.msg("💻 系统状态")
            self.msg("-" * 30)
            self._display_section_text(stats['system'])
            self.msg("")
        
        # 性能指标
        if stats['performance']:
            self.msg("⚡ 性能指标")
            self.msg("-" * 30)
            self._display_section_text(stats['performance'])
            self.msg("")
        
        # 用户统计
        if stats['users']:
            self.msg("👥 用户统计")
            self.msg("-" * 30)
            self._display_section_text(stats['users'])
            self.msg("")
        
        # 数据库统计
        if stats['database']:
            self.msg("🗄️ 数据库统计")
            self.msg("-" * 30)
            self._display_section_text(stats['database'])
            self.msg("")
        
        # 应用统计
        if stats['application']:
            self.msg("🚀 应用统计")
            self.msg("-" * 30)
            self._display_section_text(stats['application'])
            self.msg("")
        
        self.msg("=" * 60)
    
    def _display_section_text(self, section_data: Dict[str, Any]) -> None:
        """显示章节文本"""
        for key, value in section_data.items():
            if isinstance(value, dict):
                if 'error' in value:
                    self.msg(f"  {key}: ❌ {value['error']}")
                else:
                    self.msg(f"  {key}:")
                    for sub_key, sub_value in value.items():
                        self.msg(f"    {sub_key}: {sub_value}")
            else:
                self.msg(f"  {key}: {value}")
    
    def _display_json(self, stats: Dict[str, Any], show_timestamp: bool) -> None:
        """JSON格式显示"""
        import json
        
        # 处理时间戳
        if not show_timestamp and 'timestamp' in stats:
            stats_copy = stats.copy()
            del stats_copy['timestamp']
        else:
            stats_copy = stats
        
        json_str = json.dumps(stats_copy, indent=2, ensure_ascii=False)
        self.msg(json_str)
    
    def _display_csv(self, stats: Dict[str, Any], show_timestamp: bool) -> None:
        """CSV格式显示"""
        # 这里实现CSV格式输出
        # 暂时使用文本格式
        self._display_text(stats, show_timestamp)
