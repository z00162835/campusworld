#!/usr/bin/env python3
"""
配置管理工具
用于管理、验证和操作配置文件
"""

import os
import sys
import argparse
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.config_manager import ConfigManager
from config.validators.config_validator import validate_config_file


class ConfigTool:
    """配置管理工具"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
    
    def validate_all(self) -> bool:
        """验证所有配置文件"""
        print("🔍 Validating all configuration files...")
        
        config_dir = Path("config")
        all_valid = True
        
        # 验证域配置文件
        domains_dir = config_dir / "domains"
        if domains_dir.exists():
            print(f"\n📁 Validating domain configurations in {domains_dir}:")
            for config_file in domains_dir.glob("*.yaml"):
                is_valid, report = validate_config_file(str(config_file))
                if is_valid:
                    print(f"  ✅ {config_file.name}")
                else:
                    print(f"  ❌ {config_file.name}")
                    print(f"     {report}")
                    all_valid = False
        
        # 验证环境配置文件
        environments_dir = config_dir / "environments"
        if environments_dir.exists():
            print(f"\n📁 Validating environment configurations in {environments_dir}:")
            for config_file in environments_dir.glob("*.yaml"):
                is_valid, report = validate_config_file(str(config_file))
                if is_valid:
                    print(f"  ✅ {config_file.name}")
                else:
                    print(f"  ❌ {config_file.name}")
                    print(f"     {report}")
                    all_valid = False
        
        # 验证合并后的配置
        print(f"\n🔍 Validating merged configuration:")
        if self.config_manager.validate():
            print("  ✅ Merged configuration is valid")
        else:
            print("  ❌ Merged configuration has issues")
            print(self.config_manager.get_validation_report())
            all_valid = False
        
        return all_valid
    
    def show_config(self, key: Optional[str] = None, format: str = "yaml"):
        """显示配置信息"""
        if key:
            value = self.config_manager.get(key)
            if value is not None:
                if format == "json":
                    print(json.dumps(value, indent=2, ensure_ascii=False))
                else:
                    print(yaml.dump(value, default_flow_style=False, allow_unicode=True))
            else:
                print(f"Configuration key '{key}' not found")
        else:
            # 显示配置摘要
            print(self.config_manager.get_config_summary())
            
            # 显示详细配置
            if format == "json":
                print("\n" + json.dumps(self.config_manager.get_all(), indent=2, ensure_ascii=False))
            else:
                print("\n" + yaml.dump(self.config_manager.get_all(), default_flow_style=False, allow_unicode=True))
    
    def export_config(self, format: str = "yaml", file_path: Optional[str] = None):
        """导出配置"""
        content = self.config_manager.export(format, file_path)
        
        if file_path:
            print(f"✅ Configuration exported to {file_path}")
        else:
            print(content)
    
    def reload_config(self) -> bool:
        """重新加载配置"""
        print("🔄 Reloading configuration...")
        success = self.config_manager.reload()
        
        if success:
            print("✅ Configuration reloaded successfully")
            print(self.config_manager.get_config_summary())
        else:
            print("❌ Failed to reload configuration")
        
        return success
    
    def check_environment_variables(self):
        """检查环境变量"""
        print("🔍 Checking environment variables...")
        
        config = self.config_manager.get_all()
        env_vars = set()
        
        def find_env_refs(obj, path=""):
            if isinstance(obj, str):
                if obj.startswith("${") and obj.endswith("}"):
                    env_var = obj[2:-1]
                    env_vars.add((env_var, path))
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    find_env_refs(value, f"{path}.{key}" if path else key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    find_env_refs(item, f"{path}[{i}]" if path else f"[{i}]")
        
        find_env_refs(config)
        
        if not env_vars:
            print("  ℹ️  No environment variables found in configuration")
            return
        
        print(f"  📋 Found {len(env_vars)} environment variable references:")
        
        all_set = True
        for env_var, path in sorted(env_vars):
            value = os.getenv(env_var)
            if value:
                print(f"    ✅ {env_var} = {value[:20]}{'...' if len(value) > 20 else ''}")
            else:
                print(f"    ❌ {env_var} (referenced in {path}) - NOT SET")
                all_set = False
        
        if all_set:
            print("  ✅ All environment variables are set")
        else:
            print("  ⚠️  Some environment variables are not set")
    
    def generate_template(self, template_type: str, output_path: Optional[str] = None):
        """生成配置模板"""
        templates = {
            "app": self._get_app_template(),
            "database": self._get_database_template(),
            "security": self._get_security_template(),
            "ssh": self._get_ssh_template(),
            "monitoring": self._get_monitoring_template(),
            "environment": self._get_environment_template()
        }
        
        if template_type not in templates:
            print(f"❌ Unknown template type: {template_type}")
            print(f"Available templates: {', '.join(templates.keys())}")
            return
        
        template = templates[template_type]
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(template, f, default_flow_style=False, allow_unicode=True)
            print(f"✅ Template generated: {output_path}")
        else:
            print(yaml.dump(template, default_flow_style=False, allow_unicode=True))
    
    def _get_app_template(self) -> Dict[str, Any]:
        """获取应用配置模板"""
        return {
            "app": {
                "name": "YourAppName",
                "version": "1.0.0",
                "description": "Your application description",
                "environment": "development",
                "debug": False,
                "features": {
                    "feature1": True,
                    "feature2": False
                }
            },
            "server": {
                "host": "0.0.0.0",
                "port": 8000,
                "workers": 1
            }
        }
    
    def _get_database_template(self) -> Dict[str, Any]:
        """获取数据库配置模板"""
        return {
            "postgresql": {
                "host": "localhost",
                "port": 5432,
                "name": "your_database",
                "user": "your_user",
                "password": "your_password"
            },
            "redis": {
                "host": "localhost",
                "port": 6379,
                "password": ""
            }
        }
    
    def _get_security_template(self) -> Dict[str, Any]:
        """获取安全配置模板"""
        return {
            "security": {
                "authentication": {
                    "jwt": {
                        "secret_key": "your-secret-key-here",
                        "algorithm": "HS256"
                    }
                }
            }
        }
    
    def _get_ssh_template(self) -> Dict[str, Any]:
        """获取SSH配置模板"""
        return {
            "ssh": {
                "server": {
                    "host": "0.0.0.0",
                    "port": 2222
                }
            }
        }
    
    def _get_monitoring_template(self) -> Dict[str, Any]:
        """获取监控配置模板"""
        return {
            "monitoring": {
                "logging": {
                    "level": "INFO"
                },
                "metrics": {
                    "enabled": True
                }
            }
        }
    
    def _get_environment_template(self) -> Dict[str, Any]:
        """获取环境配置模板"""
        return {
            "environment": "development",
            "app": {
                "debug": True
            },
            "database": {
                "host": "localhost"
            }
        }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Configuration Management Tool")
    parser.add_argument("command", choices=[
        "validate", "show", "export", "reload", "env-check", "template"
    ], help="Command to execute")
    
    parser.add_argument("--key", "-k", help="Configuration key to show")
    parser.add_argument("--format", "-f", choices=["yaml", "json"], default="yaml",
                       help="Output format")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--template-type", "-t", help="Template type for generation")
    
    args = parser.parse_args()
    
    tool = ConfigTool()
    
    try:
        if args.command == "validate":
            success = tool.validate_all()
            sys.exit(0 if success else 1)
        
        elif args.command == "show":
            tool.show_config(args.key, args.format)
        
        elif args.command == "export":
            tool.export_config(args.format, args.output)
        
        elif args.command == "reload":
            success = tool.reload_config()
            sys.exit(0 if success else 1)
        
        elif args.command == "env-check":
            tool.check_environment_variables()
        
        elif args.command == "template":
            if not args.template_type:
                print("❌ Template type is required for template generation")
                print("Available types: app, database, security, ssh, monitoring, environment")
                sys.exit(1)
            tool.generate_template(args.template_type, args.output)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
