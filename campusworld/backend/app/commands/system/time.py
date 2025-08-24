"""
Time命令 - 时间命令

用于显示系统时间和游戏时间，包括当前时间、游戏运行时间、时区信息等
参考Evennia框架的time命令设计

作者：AI Assistant
创建时间：2025-08-24
"""

import time
import datetime
from typing import Dict, Any, Optional
from ..base import Command


class CmdTime(Command):
    """
    Time命令 - 时间命令
    
    用法:
        time                    - 显示当前时间
        time -g                - 显示游戏时间
        time -s                - 显示系统时间
        time -z                - 显示时区信息
        time -u                - 显示UTC时间
        time -a                - 显示所有时间信息
        time -f <格式>         - 指定时间格式
    """
    
    key = "time"
    aliases = ["t", "clock", "date"]
    locks = ""
    help_category = "system"
    help_entry = """
时间命令用于显示系统时间和游戏时间，包括当前时间、游戏运行时间、时区信息等。

用法:
  time                    - 显示当前时间
  time -g                - 显示游戏时间
  time -s                - 显示系统时间
  time -z                - 显示时区信息
  time -u                - 显示UTC时间
  time -a                - 显示所有时间信息
  time -f <格式>         - 指定时间格式

示例:
  time                   - 显示当前时间
  time -g                - 显示游戏时间
  time -s                - 显示系统时间
  time -z                - 显示时区信息
  time -u                - 显示UTC时间
  time -a                - 显示所有时间信息
  time -f "%Y-%m-%d"     - 指定时间格式

开关参数:
  -g, --game             - 显示游戏时间
  -s, --system           - 显示系统时间
  -z, --zone             - 显示时区信息
  -u, --utc              - 显示UTC时间
  -a, --all              - 显示所有时间信息
  -f, --format <格式>    - 指定时间格式
  -v, --verbose          - 详细模式
  -t, --timestamp        - 显示时间戳
    """
    
    def __init__(self, **kwargs):
        """初始化时间命令"""
        super().__init__(**kwargs)
        # 游戏启动时间（模拟）
        self.game_start_time = time.time()
        # 游戏时间流速（1秒真实时间 = 1分钟游戏时间）
        self.game_time_multiplier = 60
    
    def func(self) -> None:
        """执行time命令"""
        args = self.parsed_args
        
        # 检查开关参数
        show_game = '-g' in args.get('switches', []) or '--game' in args.get('switches', [])
        show_system = '-s' in args.get('switches', []) or '--system' in args.get('switches', [])
        show_zone = '-z' in args.get('switches', []) or '--zone' in args.get('switches', [])
        show_utc = '-u' in args.get('switches', []) or '--utc' in args.get('switches', [])
        show_all = '-a' in args.get('switches', []) or '--all' in args.get('switches', [])
        verbose = '-v' in args.get('switches', []) or '--verbose' in args.get('switches', [])
        show_timestamp = '-t' in args.get('switches', []) or '--timestamp' in args.get('switches', [])
        
        # 获取时间格式
        time_format = self._get_time_format(args)
        
        # 如果没有指定特定类型，显示当前时间
        if not any([show_game, show_system, show_zone, show_utc, show_all]):
            show_system = True
        
        # 收集时间信息
        time_data = self._collect_time_info(show_game, show_system, show_zone, show_utc, show_all, verbose)
        
        # 显示时间信息
        self._display_time_info(time_data, time_format, show_timestamp)
    
    def _get_time_format(self, args: Dict[str, Any]) -> str:
        """获取时间格式"""
        format_arg = args.get('lhs') or args.get('args', '')
        
        # 检查是否包含格式参数
        if '-f' in args.get('switches', []) or '--format' in args.get('switches', []):
            # 提取格式字符串
            for i, switch in enumerate(args.get('switches', [])):
                if switch in ['-f', '--format'] and i + 1 < len(args.get('switches', [])):
                    return args['switches'][i + 1]
        
        # 默认格式
        return "%Y-%m-%d %H:%M:%S"
    
    def _collect_time_info(self, show_game: bool, show_system: bool, show_zone: bool, 
                          show_utc: bool, show_all: bool, verbose: bool) -> Dict[str, Any]:
        """
        收集时间信息
        
        Args:
            show_game: 是否显示游戏时间
            show_system: 是否显示系统时间
            show_zone: 是否显示时区信息
            show_utc: 是否显示UTC时间
            show_all: 是否显示所有时间信息
            verbose: 是否详细模式
            
        Returns:
            时间信息字典
        """
        time_info = {
            'timestamp': time.time(),
            'system': {},
            'game': {},
            'zone': {},
            'utc': {},
            'relative': {}
        }
        
        # 系统时间信息
        if show_system or show_all:
            time_info['system'] = self._get_system_time_info(verbose)
        
        # 游戏时间信息
        if show_game or show_all:
            time_info['game'] = self._get_game_time_info(verbose)
        
        # 时区信息
        if show_zone or show_all:
            time_info['zone'] = self._get_zone_info(verbose)
        
        # UTC时间信息
        if show_utc or show_all:
            time_info['utc'] = self._get_utc_time_info(verbose)
        
        # 相对时间信息
        if show_all:
            time_info['relative'] = self._get_relative_time_info(verbose)
        
        return time_info
    
    def _get_system_time_info(self, verbose: bool = False) -> Dict[str, Any]:
        """获取系统时间信息"""
        try:
            now = datetime.datetime.now()
            info = {
                'current_time': now.strftime("%Y-%m-%d %H:%M:%S"),
                'date': now.strftime("%Y-%m-%d"),
                'time': now.strftime("%H:%M:%S"),
                'year': now.year,
                'month': now.month,
                'day': now.day,
                'hour': now.hour,
                'minute': now.minute,
                'second': now.second,
                'weekday': now.strftime("%A"),
                'weekday_cn': self._get_weekday_cn(now.weekday()),
                'is_weekend': now.weekday() >= 5,
                'day_of_year': now.timetuple().tm_yday
            }
            
            if verbose:
                info.update({
                    'microsecond': now.microsecond,
                    'timezone': self._get_local_timezone(),
                    'dst': self._is_dst(),
                    'unix_timestamp': int(time.time())
                })
            
            return info
        except Exception as e:
            return {'error': f"获取系统时间失败: {e}"}
    
    def _get_game_time_info(self, verbose: bool = False) -> Dict[str, Any]:
        """获取游戏时间信息"""
        try:
            current_time = time.time()
            game_elapsed = current_time - self.game_start_time
            game_time = game_elapsed * self.game_time_multiplier
            
            # 转换为游戏时间
            game_minutes = int(game_time)
            game_hours = game_minutes // 60
            game_days = game_hours // 24
            
            game_minutes %= 60
            game_hours %= 24
            
            info = {
                'game_start_time': datetime.datetime.fromtimestamp(self.game_start_time).strftime("%Y-%m-%d %H:%M:%S"),
                'game_current_time': datetime.datetime.fromtimestamp(current_time).strftime("%Y-%m-%d %H:%M:%S"),
                'game_elapsed_real': self._format_duration(game_elapsed),
                'game_elapsed_game': self._format_duration(game_time),
                'game_time_multiplier': self.game_time_multiplier,
                'game_day': game_days,
                'game_hour': game_hours,
                'game_minute': game_minutes,
                'game_time_formatted': f"第{game_days + 1}天 {game_hours:02d}:{game_minutes:02d}"
            }
            
            if verbose:
                info.update({
                    'game_start_timestamp': self.game_start_time,
                    'game_current_timestamp': current_time,
                    'game_elapsed_seconds': game_elapsed,
                    'game_elapsed_game_seconds': game_time
                })
            
            return info
        except Exception as e:
            return {'error': f"获取游戏时间失败: {e}"}
    
    def _get_zone_info(self, verbose: bool = False) -> Dict[str, Any]:
        """获取时区信息"""
        try:
            import os
            import platform
            
            info = {
                'local_timezone': self._get_local_timezone(),
                'system': platform.system(),
                'timezone_env': os.environ.get('TZ', 'Not set')
            }
            
            if verbose:
                info.update({
                    'platform': platform.platform(),
                    'timezone_files': self._get_timezone_files()
                })
            
            return info
        except Exception as e:
            return {'error': f"获取时区信息失败: {e}"}
    
    def _get_utc_time_info(self, verbose: bool = False) -> Dict[str, Any]:
        """获取UTC时间信息"""
        try:
            utc_now = datetime.datetime.utcnow()
            info = {
                'utc_time': utc_now.strftime("%Y-%m-%d %H:%M:%S"),
                'utc_date': utc_now.strftime("%Y-%m-%d"),
                'utc_time_only': utc_now.strftime("%H:%M:%S"),
                'utc_year': utc_now.year,
                'utc_month': utc_now.month,
                'utc_day': utc_now.day,
                'utc_hour': utc_now.hour,
                'utc_minute': utc_now.minute,
                'utc_second': utc_now.second
            }
            
            if verbose:
                info.update({
                    'utc_timestamp': int(time.time()),
                    'utc_weekday': utc_now.strftime("%A"),
                    'utc_day_of_year': utc_now.timetuple().tm_yday
                })
            
            return info
        except Exception as e:
            return {'error': f"获取UTC时间失败: {e}"}
    
    def _get_relative_time_info(self, verbose: bool = False) -> Dict[str, Any]:
        """获取相对时间信息"""
        try:
            now = datetime.datetime.now()
            info = {
                'time_of_day': self._get_time_of_day(now.hour),
                'season': self._get_season(now.month),
                'quarter': (now.month - 1) // 3 + 1,
                'is_business_hour': 9 <= now.hour < 18,
                'is_night': now.hour < 6 or now.hour >= 22,
                'is_morning': 6 <= now.hour < 12,
                'is_afternoon': 12 <= now.hour < 18,
                'is_evening': 18 <= now.hour < 22
            }
            
            if verbose:
                info.update({
                    'next_holiday': self._get_next_holiday(now),
                    'days_until_weekend': 5 - now.weekday() if now.weekday() < 5 else 0,
                    'days_until_month_end': (now.replace(day=1) + datetime.timedelta(days=32)).replace(day=1) - now
                })
            
            return info
        except Exception as e:
            return {'error': f"获取相对时间失败: {e}"}
    
    def _get_weekday_cn(self, weekday: int) -> str:
        """获取中文星期名称"""
        weekdays_cn = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
        return weekdays_cn[weekday]
    
    def _get_local_timezone(self) -> str:
        """获取本地时区"""
        try:
            import time
            return time.tzname[time.daylight]
        except:
            return "Unknown"
    
    def _is_dst(self) -> bool:
        """是否夏令时"""
        try:
            import time
            return time.daylight and time.localtime().tm_isdst > 0
        except:
            return False
    
    def _get_timezone_files(self) -> str:
        """获取时区文件信息"""
        try:
            import os
            if os.path.exists('/etc/timezone'):
                with open('/etc/timezone', 'r') as f:
                    return f.read().strip()
            elif os.path.exists('/etc/localtime'):
                return "Local timezone file exists"
            else:
                return "No timezone files found"
        except:
            return "Unable to check timezone files"
    
    def _format_duration(self, seconds: float) -> str:
        """格式化持续时间"""
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}分{secs}秒"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}小时{minutes}分"
        else:
            days = int(seconds // 86400)
            hours = int((seconds % 86400) // 3600)
            return f"{days}天{hours}小时"
    
    def _get_time_of_day(self, hour: int) -> str:
        """获取一天中的时间段"""
        if 5 <= hour < 12:
            return "上午"
        elif 12 <= hour < 13:
            return "中午"
        elif 13 <= hour < 18:
            return "下午"
        elif 18 <= hour < 22:
            return "晚上"
        else:
            return "深夜"
    
    def _get_season(self, month: int) -> str:
        """获取季节"""
        if month in [3, 4, 5]:
            return "春季"
        elif month in [6, 7, 8]:
            return "夏季"
        elif month in [9, 10, 11]:
            return "秋季"
        else:
            return "冬季"
    
    def _get_next_holiday(self, now: datetime.datetime) -> str:
        """获取下一个节日（简化版）"""
        # 这里可以实现更复杂的节日计算逻辑
        return "下一个节日: 元旦 (1月1日)"
    
    def _display_time_info(self, time_info: Dict[str, Any], time_format: str, show_timestamp: bool) -> None:
        """
        显示时间信息
        
        Args:
            time_info: 时间信息字典
            time_format: 时间格式
            show_timestamp: 是否显示时间戳
        """
        self.msg("=" * 60)
        self.msg("⏰ CampusWorld 时间信息")
        self.msg("=" * 60)
        
        if show_timestamp:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time_info['timestamp']))
            self.msg(f"🕐 查询时间: {timestamp}")
            self.msg("")
        
        # 系统时间信息
        if time_info['system']:
            self.msg("🖥️ 系统时间")
            self.msg("-" * 30)
            system = time_info['system']
            if 'error' in system:
                self.msg(f"  ❌ {system['error']}")
            else:
                self.msg(f"  当前时间: {system.get('current_time', 'Unknown')}")
                self.msg(f"  日期: {system.get('date', 'Unknown')}")
                self.msg(f"  时间: {system.get('time', 'Unknown')}")
                self.msg(f"  星期: {system.get('weekday_cn', 'Unknown')}")
                self.msg(f"  是否周末: {'是' if system.get('is_weekend', False) else '否'}")
                self.msg(f"  一年中第几天: {system.get('day_of_year', 'Unknown')}")
            self.msg("")
        
        # 游戏时间信息
        if time_info['game']:
            self.msg("🎮 游戏时间")
            self.msg("-" * 30)
            game = time_info['game']
            if 'error' in game:
                self.msg(f"  ❌ {game['error']}")
            else:
                self.msg(f"  游戏开始时间: {game.get('game_start_time', 'Unknown')}")
                self.msg(f"  游戏当前时间: {game.get('game_current_time', 'Unknown')}")
                self.msg(f"  真实时间流逝: {game.get('game_elapsed_real', 'Unknown')}")
                self.msg(f"  游戏时间流逝: {game.get('game_elapsed_game', 'Unknown')}")
                self.msg(f"  时间流速: 1秒真实时间 = {game.get('game_time_multiplier', 'Unknown')}秒游戏时间")
                self.msg(f"  游戏时间: {game.get('game_time_formatted', 'Unknown')}")
            self.msg("")
        
        # 时区信息
        if time_info['zone']:
            self.msg("🌍 时区信息")
            self.msg("-" * 30)
            zone = time_info['zone']
            if 'error' in zone:
                self.msg(f"  ❌ {zone['error']}")
            else:
                self.msg(f"  本地时区: {zone.get('local_timezone', 'Unknown')}")
                self.msg(f"  系统: {zone.get('system', 'Unknown')}")
                self.msg(f"  时区环境变量: {zone.get('timezone_env', 'Unknown')}")
            self.msg("")
        
        # UTC时间信息
        if time_info['utc']:
            self.msg("🌐 UTC时间")
            self.msg("-" * 30)
            utc = time_info['utc']
            if 'error' in utc:
                self.msg(f"  ❌ {utc['error']}")
            else:
                self.msg(f"  UTC时间: {utc.get('utc_time', 'Unknown')}")
                self.msg(f"  UTC日期: {utc.get('utc_date', 'Unknown')}")
                self.msg(f"  UTC时间: {utc.get('utc_time_only', 'Unknown')}")
            self.msg("")
        
        # 相对时间信息
        if time_info['relative']:
            self.msg("📅 相对时间信息")
            self.msg("-" * 30)
            relative = time_info['relative']
            if 'error' in relative:
                self.msg(f"  ❌ {relative['error']}")
            else:
                self.msg(f"  时间段: {relative.get('time_of_day', 'Unknown')}")
                self.msg(f"  季节: {relative.get('season', 'Unknown')}")
                self.msg(f"  季度: 第{relative.get('quarter', 'Unknown')}季度")
                self.msg(f"  是否工作时间: {'是' if relative.get('is_business_hour', False) else '否'}")
                self.msg(f"  是否夜晚: {'是' if relative.get('is_night', False) else '否'}")
            self.msg("")
        
        self.msg("=" * 60)
