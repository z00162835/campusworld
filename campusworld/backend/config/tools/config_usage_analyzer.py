#!/usr/bin/env python3
"""
配置使用情况分析工具
分析项目中配置项的使用情况，识别未使用的配置和硬编码问题
"""

import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
import yaml
import ast

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.config_manager import ConfigManager


class ConfigUsageAnalyzer:
    """配置使用情况分析器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config_manager = ConfigManager()
        self.used_configs: Set[str] = set()
        self.hardcoded_values: List[Tuple[str, str, str]] = []  # (file, line, value)
        self.unused_configs: Set[str] = set()
        
    def analyze_project(self) -> Dict[str, Any]:
        """分析整个项目的配置使用情况"""
        print("🔍 分析项目配置使用情况...")
        
        # 获取所有配置项
        all_configs = self._get_all_config_keys()
        
        # 分析Python文件中的配置使用
        self._analyze_python_files()
        
        # 分析其他配置文件
        self._analyze_config_files()
        
        # 识别未使用的配置
        self.unused_configs = all_configs - self.used_configs
        
        return {
            'used_configs': list(self.used_configs),
            'unused_configs': list(self.unused_configs),
            'hardcoded_values': self.hardcoded_values,
            'total_configs': len(all_configs),
            'used_count': len(self.used_configs),
            'unused_count': len(self.unused_configs)
        }
    
    def _get_all_config_keys(self) -> Set[str]:
        """获取所有配置键"""
        config = self.config_manager.get_all()
        keys = set()
        
        def extract_keys(obj, prefix=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_key = f"{prefix}.{key}" if prefix else key
                    keys.add(current_key)
                    if isinstance(value, (dict, list)):
                        extract_keys(value, current_key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    current_key = f"{prefix}[{i}]" if prefix else f"[{i}]"
                    if isinstance(item, (dict, list)):
                        extract_keys(item, current_key)
        
        extract_keys(config)
        return keys
    
    def _analyze_python_files(self):
        """分析Python文件中的配置使用"""
        python_files = list(self.project_root.rglob("*.py"))
        
        for py_file in python_files:
            if "venv" in str(py_file) or ".venv" in str(py_file):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 分析get_setting调用
                self._analyze_get_setting_calls(content, py_file)
                
                # 分析硬编码值
                self._analyze_hardcoded_values(content, py_file)
                
            except Exception as e:
                print(f"⚠️  无法分析文件 {py_file}: {e}")
    
    def _analyze_get_setting_calls(self, content: str, file_path: Path):
        """分析get_setting调用"""
        # 匹配 get_setting('key', default) 或 get_setting("key", default)
        pattern = r'get_setting\s*\(\s*[\'"]([^\'"]+)[\'"]'
        matches = re.findall(pattern, content)
        
        for match in matches:
            self.used_configs.add(match)
    
    def _analyze_hardcoded_values(self, content: str, file_path: Path):
        """分析硬编码值"""
        # 常见的硬编码值模式
        hardcoded_patterns = [
            (r'localhost', 'localhost'),
            (r':8000', 'port 8000'),
            (r':5433', 'port 5433'),
            (r':6380', 'port 6380'),
            (r':2222', 'port 2222'),
            (r'0\.0\.0\.0', '0.0.0.0'),
            (r'127\.0\.0\.1', '127.0.0.1'),
        ]
        
        lines = content.split('\n')
        for line_num, line in enumerate(lines, 1):
            for pattern, description in hardcoded_patterns:
                if re.search(pattern, line):
                    self.hardcoded_values.append((
                        str(file_path),
                        str(line_num),
                        description
                    ))
    
    def _analyze_config_files(self):
        """分析配置文件"""
        config_dir = self.project_root / "config"
        
        # 分析环境变量引用
        for config_file in config_dir.rglob("*.yaml"):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 查找环境变量引用
                env_pattern = r'\$\{([^}]+)\}'
                env_matches = re.findall(env_pattern, content)
                
                for env_var in env_matches:
                    self.used_configs.add(f"env:{env_var}")
                    
            except Exception as e:
                print(f"⚠️  无法分析配置文件 {config_file}: {e}")
    
    def generate_report(self) -> str:
        """生成分析报告"""
        report = []
        report.append("配置使用情况分析报告")
        report.append("=" * 50)
        
        # 统计信息
        report.append(f"\n📊 统计信息:")
        report.append(f"  总配置项数量: {self.config_manager.get_all().__len__()}")
        report.append(f"  已使用配置项: {len(self.used_configs)}")
        report.append(f"  未使用配置项: {len(self.unused_configs)}")
        report.append(f"  硬编码问题: {len(self.hardcoded_values)}")
        
        # 未使用的配置项
        if self.unused_configs:
            report.append(f"\n❌ 未使用的配置项 ({len(self.unused_configs)}):")
            for config in sorted(self.unused_configs):
                report.append(f"  - {config}")
        
        # 硬编码问题
        if self.hardcoded_values:
            report.append(f"\n⚠️  硬编码问题 ({len(self.hardcoded_values)}):")
            for file_path, line_num, description in self.hardcoded_values:
                report.append(f"  - {file_path}:{line_num} - {description}")
        
        # 建议
        report.append(f"\n💡 优化建议:")
        if self.unused_configs:
            report.append("  1. 删除未使用的配置项，减少配置文件复杂度")
        if self.hardcoded_values:
            report.append("  2. 将硬编码值替换为配置项引用")
        report.append("  3. 定期运行此工具，保持配置的清洁性")
        
        return "\n".join(report)
    
    def suggest_cleanup(self) -> List[str]:
        """提供清理建议"""
        suggestions = []
        
        # 未使用配置的清理建议
        if self.unused_configs:
            suggestions.append("未使用的配置项清理建议:")
            for config in sorted(self.unused_configs):
                suggestions.append(f"  - 删除: {config}")
        
        # 硬编码问题的修复建议
        if self.hardcoded_values:
            suggestions.append("\n硬编码问题修复建议:")
            for file_path, line_num, description in self.hardcoded_values:
                suggestions.append(f"  - {file_path}:{line_num} - 替换 {description} 为配置项")
        
        return suggestions


def main():
    """主函数"""
    project_root = Path(__file__).parent.parent.parent
    
    analyzer = ConfigUsageAnalyzer(project_root)
    results = analyzer.analyze_project()
    
    # 生成报告
    report = analyzer.generate_report()
    print(report)
    
    # 保存报告到文件
    report_file = project_root / "config_usage_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n📄 详细报告已保存到: {report_file}")
    
    # 显示清理建议
    if results['unused_configs'] or results['hardcoded_values']:
        print("\n🧹 清理建议:")
        suggestions = analyzer.suggest_cleanup()
        for suggestion in suggestions:
            print(suggestion)


if __name__ == "__main__":
    main()
