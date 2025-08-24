"""
Version命令 - 版本命令

用于显示系统版本信息，包括版本号、构建时间、依赖信息等
参考Evennia框架的version命令设计

作者：AI Assistant
创建时间：2025-08-24
"""

import time
import platform
import sys
from typing import Dict, Any, List
from ..base import Command


class CmdVersion(Command):
    """
    Version命令 - 版本命令
    
    用法:
        version                 - 显示系统版本信息
        version -d             - 显示详细版本信息
        version -p             - 显示Python环境信息
        version -s             - 显示系统环境信息
        version -a             - 显示所有版本信息
        version -f <格式>      - 指定输出格式
    """
    
    key = "version"
    aliases = ["ver", "v", "about"]
    locks = ""
    help_category = "system"
    help_entry = """
版本命令用于显示系统版本信息，包括版本号、构建时间、依赖信息等。

用法:
  version                 - 显示系统版本信息
  version -d             - 显示详细版本信息
  version -p             - 显示Python环境信息
  version -s             - 显示系统环境信息
  version -a             - 显示所有版本信息
  version -f <格式>      - 指定输出格式

示例:
  version                - 显示基本版本信息
  version -d             - 显示详细版本信息
  version -p             - 显示Python环境
  version -s             - 显示系统环境
  version -a             - 显示所有信息
  version -f json        - JSON格式输出

开关参数:
  -d, --detailed         - 显示详细版本信息
  -p, --python           - 显示Python环境信息
  -s, --system           - 显示系统环境信息
  -a, --all              - 显示所有版本信息
  -f, --format <格式>    - 指定输出格式 (text, json, csv)
  -v, --verbose          - 详细模式
  -t, --timestamp        - 显示时间戳
    """
    
    def func(self) -> None:
        """执行version命令"""
        args = self.parsed_args
        
        # 检查开关参数
        show_detailed = '-d' in args.get('switches', []) or '--detailed' in args.get('switches', [])
        show_python = '-p' in args.get('switches', []) or '--python' in args.get('switches', [])
        show_system = '-s' in args.get('switches', []) or '--system' in args.get('switches', [])
        show_all = '-a' in args.get('switches', []) or '--all' in args.get('switches', [])
        verbose = '-v' in args.get('switches', []) or '--verbose' in args.get('switches', [])
        show_timestamp = '-t' in args.get('switches', []) or '--timestamp' in args.get('switches', [])
        
        # 获取输出格式
        output_format = self._get_output_format(args)
        
        # 如果没有指定特定类型，显示基本版本信息
        if not any([show_detailed, show_python, show_system, show_all]):
            show_detailed = True
        
        # 收集版本信息
        version_data = self._collect_version_info(show_detailed, show_python, show_system, show_all, verbose)
        
        # 显示版本信息
        self._display_version_info(version_data, output_format, show_timestamp)
    
    def _get_output_format(self, args: Dict[str, Any]) -> str:
        """获取输出格式"""
        format_arg = args.get('lhs') or args.get('args', '')
        
        if 'json' in format_arg.lower():
            return 'json'
        elif 'csv' in format_arg.lower():
            return 'csv'
        else:
            return 'text'
    
    def _collect_version_info(self, show_detailed: bool, show_python: bool, 
                            show_system: bool, show_all: bool, verbose: bool) -> Dict[str, Any]:
        """
        收集版本信息
        
        Args:
            show_detailed: 是否显示详细版本信息
            show_python: 是否显示Python环境信息
            show_system: 是否显示系统环境信息
            show_all: 是否显示所有版本信息
            verbose: 是否详细模式
            
        Returns:
            版本信息字典
        """
        version_info = {
            'timestamp': time.time(),
            'basic': {},
            'detailed': {},
            'python': {},
            'system': {},
            'dependencies': {},
            'build': {}
        }
        
        # 基本版本信息
        if show_all or True:  # 基本版本信息总是显示
            version_info['basic'] = self._get_basic_version_info()
        
        # 详细版本信息
        if show_detailed or show_all:
            version_info['detailed'] = self._get_detailed_version_info(verbose)
        
        # Python环境信息
        if show_python or show_all:
            version_info['python'] = self._get_python_info(verbose)
        
        # 系统环境信息
        if show_system or show_all:
            version_info['system'] = self._get_system_info(verbose)
        
        # 依赖信息
        if show_all:
            version_info['dependencies'] = self._get_dependencies_info(verbose)
        
        # 构建信息
        if show_all:
            version_info['build'] = self._get_build_info(verbose)
        
        return version_info
    
    def _get_basic_version_info(self) -> Dict[str, Any]:
        """获取基本版本信息"""
        return {
            'name': 'CampusWorld',
            'version': '1.0.0',
            'codename': 'Alpha',
            'release_date': '2025-08-24',
            'description': 'CampusWorld - 校园世界虚拟现实系统'
        }
    
    def _get_detailed_version_info(self, verbose: bool = False) -> Dict[str, Any]:
        """获取详细版本信息"""
        info = {
            'major_version': 1,
            'minor_version': 0,
            'patch_version': 0,
            'build_number': 1,
            'commit_hash': 'dev',
            'branch': 'main',
            'release_type': 'development',
            'license': 'MIT',
            'author': 'AI Assistant',
            'homepage': 'https://github.com/campusworld/campusworld'
        }
        
        if verbose:
            info.update({
                'changelog_url': 'https://github.com/campusworld/campusworld/blob/main/CHANGELOG.md',
                'documentation_url': 'https://docs.campusworld.dev',
                'support_url': 'https://github.com/campusworld/campusworld/issues'
            })
        
        return info
    
    def _get_python_info(self, verbose: bool = False) -> Dict[str, Any]:
        """获取Python环境信息"""
        try:
            info = {
                'version': sys.version,
                'version_info': {
                    'major': sys.version_info.major,
                    'minor': sys.version_info.minor,
                    'micro': sys.version_info.micro,
                    'releaselevel': sys.version_info.releaselevel,
                    'serial': sys.version_info.serial
                },
                'executable': sys.executable,
                'platform': sys.platform,
                'implementation': platform.python_implementation()
            }
            
            if verbose:
                info.update({
                    'compiler': platform.python_compiler(),
                    'build': platform.python_build(),
                    'revision': platform.python_revision()
                })
            
            return info
        except Exception as e:
            return {'error': f"获取Python信息失败: {e}"}
    
    def _get_system_info(self, verbose: bool = False) -> Dict[str, Any]:
        """获取系统环境信息"""
        try:
            info = {
                'platform': platform.platform(),
                'system': platform.system(),
                'release': platform.release(),
                'version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor(),
                'architecture': platform.architecture()
            }
            
            if verbose:
                info.update({
                    'uname': platform.uname()._asdict(),
                    'dist': self._get_distribution_info(),
                    'libc': self._get_libc_info()
                })
            
            return info
        except Exception as e:
            return {'error': f"获取系统信息失败: {e}"}
    
    def _get_dependencies_info(self, verbose: bool = False) -> Dict[str, Any]:
        """获取依赖信息"""
        try:
            # 这里需要根据实际的依赖管理来实现
            # 暂时返回模拟数据
            dependencies = {
                'fastapi': '0.104.1',
                'sqlalchemy': '2.0.23',
                'psycopg2-binary': '2.9.9',
                'pydantic': '2.5.0',
                'uvicorn': '0.24.0',
                'redis': '5.0.1',
                'passlib': '1.7.4',
                'python-jose': '3.3.0',
                'python-multipart': '0.0.6'
            }
            
            if verbose:
                # 尝试获取实际安装的版本
                for package in dependencies.keys():
                    try:
                        import importlib.metadata
                        version = importlib.metadata.version(package)
                        dependencies[package] = version
                    except:
                        pass
            
            return dependencies
        except Exception as e:
            return {'error': f"获取依赖信息失败: {e}"}
    
    def _get_build_info(self, verbose: bool = False) -> Dict[str, Any]:
        """获取构建信息"""
        try:
            info = {
                'build_time': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                'build_environment': self._get_environment_info(),
                'build_tools': self._get_build_tools_info()
            }
            
            if verbose:
                info.update({
                    'build_script': 'build.py',
                    'build_config': 'build_config.yaml',
                    'build_output': 'dist/'
                })
            
            return info
        except Exception as e:
            return {'error': f"获取构建信息失败: {e}"}
    
    def _get_distribution_info(self) -> Dict[str, Any]:
        """获取发行版信息"""
        try:
            if hasattr(platform, 'linux_distribution'):
                return platform.linux_distribution()
            elif hasattr(platform, 'dist'):
                return platform.dist()
            else:
                return {'error': '无法获取发行版信息'}
        except:
            return {'error': '获取发行版信息失败'}
    
    def _get_libc_info(self) -> Dict[str, Any]:
        """获取libc信息"""
        try:
            if hasattr(platform, 'libc_ver'):
                return platform.libc_ver()
            else:
                return {'error': '无法获取libc信息'}
        except:
            return {'error': '获取libc信息失败'}
    
    def _get_environment_info(self) -> str:
        """获取环境信息"""
        try:
            import os
            return os.getenv('ENVIRONMENT', 'development')
        except:
            return 'development'
    
    def _get_build_tools_info(self) -> Dict[str, str]:
        """获取构建工具信息"""
        try:
            return {
                'python': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                'pip': self._get_pip_version(),
                'setuptools': self._get_setuptools_version()
            }
        except:
            return {'error': '获取构建工具信息失败'}
    
    def _get_pip_version(self) -> str:
        """获取pip版本"""
        try:
            import subprocess
            result = subprocess.run([sys.executable, '-m', 'pip', '--version'], 
                                 capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().split()[-1]
            else:
                return 'unknown'
        except:
            return 'unknown'
    
    def _get_setuptools_version(self) -> str:
        """获取setuptools版本"""
        try:
            import setuptools
            return setuptools.__version__
        except:
            return 'unknown'
    
    def _display_version_info(self, version_info: Dict[str, Any], output_format: str, 
                            show_timestamp: bool) -> None:
        """
        显示版本信息
        
        Args:
            version_info: 版本信息字典
            output_format: 输出格式
            show_timestamp: 是否显示时间戳
        """
        if output_format == 'json':
            self._display_version_json(version_info, show_timestamp)
        elif output_format == 'csv':
            self._display_version_csv(version_info, show_timestamp)
        else:
            self._display_version_text(version_info, show_timestamp)
    
    def _display_version_text(self, version_info: Dict[str, Any], show_timestamp: bool) -> None:
        """文本格式显示版本信息"""
        self.msg("=" * 60)
        self.msg("🚀 CampusWorld 系统版本信息")
        self.msg("=" * 60)
        
        if show_timestamp:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(version_info['timestamp']))
            self.msg(f"⏰ 查询时间: {timestamp}")
            self.msg("")
        
        # 基本版本信息
        if version_info['basic']:
            self.msg("📋 基本版本信息")
            self.msg("-" * 30)
            basic = version_info['basic']
            self.msg(f"  名称: {basic.get('name', 'Unknown')}")
            self.msg(f"  版本: {basic.get('version', 'Unknown')}")
            self.msg(f"  代号: {basic.get('codename', 'Unknown')}")
            self.msg(f"  发布日期: {basic.get('release_date', 'Unknown')}")
            self.msg(f"  描述: {basic.get('description', 'Unknown')}")
            self.msg("")
        
        # 详细版本信息
        if version_info['detailed']:
            self.msg("🔍 详细版本信息")
            self.msg("-" * 30)
            detailed = version_info['detailed']
            self.msg(f"  主版本: {detailed.get('major_version', 'Unknown')}")
            self.msg(f"  次版本: {detailed.get('minor_version', 'Unknown')}")
            self.msg(f"  修订版本: {detailed.get('patch_version', 'Unknown')}")
            self.msg(f"  构建号: {detailed.get('build_number', 'Unknown')}")
            self.msg(f"  提交哈希: {detailed.get('commit_hash', 'Unknown')}")
            self.msg(f"  分支: {detailed.get('branch', 'Unknown')}")
            self.msg(f"  发布类型: {detailed.get('release_type', 'Unknown')}")
            self.msg(f"  许可证: {detailed.get('license', 'Unknown')}")
            self.msg(f"  作者: {detailed.get('author', 'Unknown')}")
            self.msg("")
        
        # Python环境信息
        if version_info['python']:
            self.msg("🐍 Python环境信息")
            self.msg("-" * 30)
            python = version_info['python']
            if 'error' in python:
                self.msg(f"  ❌ {python['error']}")
            else:
                self.msg(f"  版本: {python.get('version', 'Unknown')}")
                self.msg(f"  可执行文件: {python.get('executable', 'Unknown')}")
                self.msg(f"  平台: {python.get('platform', 'Unknown')}")
                self.msg(f"  实现: {python.get('implementation', 'Unknown')}")
            self.msg("")
        
        # 系统环境信息
        if version_info['system']:
            self.msg("💻 系统环境信息")
            self.msg("-" * 30)
            system = version_info['system']
            if 'error' in system:
                self.msg(f"  ❌ {system['error']}")
            else:
                self.msg(f"  平台: {system.get('platform', 'Unknown')}")
                self.msg(f"  系统: {system.get('system', 'Unknown')}")
                self.msg(f"  发行版: {system.get('release', 'Unknown')}")
                self.msg(f"  机器: {system.get('machine', 'Unknown')}")
                self.msg(f"  处理器: {system.get('processor', 'Unknown')}")
            self.msg("")
        
        # 依赖信息
        if version_info['dependencies']:
            self.msg("📦 依赖信息")
            self.msg("-" * 30)
            dependencies = version_info['dependencies']
            if 'error' in dependencies:
                self.msg(f"  ❌ {dependencies['error']}")
            else:
                for package, version in dependencies.items():
                    self.msg(f"  {package:<20} {version}")
            self.msg("")
        
        # 构建信息
        if version_info['build']:
            self.msg("🔨 构建信息")
            self.msg("-" * 30)
            build = version_info['build']
            if 'error' in build:
                self.msg(f"  ❌ {build['error']}")
            else:
                self.msg(f"  构建时间: {build.get('build_time', 'Unknown')}")
                self.msg(f"  构建环境: {build.get('build_environment', 'Unknown')}")
            self.msg("")
        
        self.msg("=" * 60)
    
    def _display_version_json(self, version_info: Dict[str, Any], show_timestamp: bool) -> None:
        """JSON格式显示版本信息"""
        import json
        
        # 处理时间戳
        if not show_timestamp and 'timestamp' in version_info:
            version_copy = version_info.copy()
            del version_copy['timestamp']
        else:
            version_copy = version_info
        
        json_str = json.dumps(version_copy, indent=2, ensure_ascii=False)
        self.msg(json_str)
    
    def _display_version_csv(self, version_info: Dict[str, Any], show_timestamp: bool) -> None:
        """CSV格式显示版本信息"""
        # 这里实现CSV格式输出
        # 暂时使用文本格式
        self._display_version_text(version_info, show_timestamp)
