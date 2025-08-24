"""
配置管理器
管理应用配置的加载、合并、验证和访问
"""

import os
import yaml
import json
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from functools import lru_cache
import logging
from copy import deepcopy

from .validators.config_validator import ConfigValidator, validate_config_file


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_cache: Dict[str, Any] = {}
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.logger = logging.getLogger(__name__)
        
        # 配置加载顺序
        self.load_order = [
            "domains/app_minimal.yaml",
            "domains/ssh_minimal.yaml",
            f"environments/{self.environment}_minimal.yaml"
        ]
        
        # 加载配置
        self._load_configuration()
    
    def _load_configuration(self):
        """加载配置"""
        try:
            # 加载基础配置域
            base_config = {}
            for config_file in self.load_order[:-1]:  # 除了环境配置
                file_path = self.config_dir / config_file
                if file_path.exists():
                    config = self._load_yaml_file(file_path)
                    if config:
                        base_config = self._merge_config(base_config, config)
                        self.logger.info(f"Loaded config: {config_file}")
            
            # 加载环境配置
            env_config_file = self.load_order[-1]
            env_file_path = self.config_dir / env_config_file
            if env_file_path.exists():
                env_config = self._load_yaml_file(env_file_path)
                if env_config:
                    base_config = self._merge_config(base_config, env_config)
                    self.logger.info(f"Loaded environment config: {env_config_file}")
            
            # 处理环境变量
            base_config = self._process_environment_variables(base_config)
            
            # 验证配置
            validator = ConfigValidator()
            if validator.validate_config(base_config):
                self.config_cache = base_config
                self.logger.info("Configuration loaded and validated successfully")
            else:
                self.logger.warning("Configuration validation failed")
                print(validator.get_validation_report())
                # 即使验证失败也使用配置，但记录警告
                self.config_cache = base_config
                
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            # 使用默认配置
            self.config_cache = self._get_default_config()
    
    def _load_yaml_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """加载YAML文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"Failed to load {file_path}: {e}")
            return None
    
    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """合并配置（深度合并）"""
        result = deepcopy(base)
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _process_environment_variables(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """处理环境变量引用"""
        def process_value(value):
            if isinstance(value, str):
                # 处理 ${VAR_NAME} 格式的环境变量
                if value.startswith("${") and value.endswith("}"):
                    env_var = value[2:-1]
                    return os.getenv(env_var, value)
                return value
            elif isinstance(value, dict):
                return {k: process_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [process_value(item) for item in value]
            else:
                return value
        
        return process_value(config)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "app": {
                "name": "CampusWorld",
                "version": "0.1.0",
                "environment": "development",
                "debug": True
            },
            "server": {
                "host": "0.0.0.0",
                "port": 8000,
                "workers": 1
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self.config_cache
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_nested(self, *keys: str, default: Any = None) -> Any:
        """获取嵌套配置值"""
        value = self.config_cache
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """设置配置值"""
        keys = key.split('.')
        config = self.config_cache
        
        # 导航到父级
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # 设置值
        config[keys[-1]] = value
    
    def has(self, key: str) -> bool:
        """检查配置键是否存在"""
        return self.get(key) is not None
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return deepcopy(self.config_cache)
    
    def reload(self) -> bool:
        """重新加载配置"""
        try:
            self._load_configuration()
            return True
        except Exception as e:
            self.logger.error(f"Failed to reload configuration: {e}")
            return False
    
    def validate(self) -> bool:
        """验证当前配置"""
        validator = ConfigValidator()
        return validator.validate_config(self.config_cache)
    
    def get_validation_report(self) -> str:
        """获取验证报告"""
        validator = ConfigValidator()
        validator.validate_config(self.config_cache)
        return validator.get_validation_report()
    
    def export(self, format: str = "yaml", file_path: Optional[str] = None) -> str:
        """导出配置"""
        if format.lower() == "yaml":
            content = yaml.dump(self.config_cache, default_flow_style=False, allow_unicode=True)
        elif format.lower() == "json":
            content = json.dumps(self.config_cache, indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return content
    
    def get_database_url(self) -> str:
        """获取数据库连接URL"""
        postgresql = self.get("postgresql", {})
        if postgresql:
            host = postgresql.get("host", "localhost")
            port = postgresql.get("port", 5432)
            name = postgresql.get("name", "campusworld")
            user = postgresql.get("user", "postgres")
            password = postgresql.get("password", "")
            
            if password:
                return f"postgresql://{user}:{password}@{host}:{port}/{name}"
            else:
                return f"postgresql://{user}@{host}:{port}/{name}"
        
        return "postgresql://postgres@localhost:5432/campusworld"
    
    def get_redis_url(self) -> str:
        """获取Redis连接URL"""
        redis = self.get("redis", {})
        if redis:
            host = redis.get("host", "localhost")
            port = redis.get("port", 6379)
            password = redis.get("password", "")
            db = redis.get("db", 0)
            
            if password:
                return f"redis://:{password}@{host}:{port}/{db}"
            else:
                return f"redis://{host}:{port}/{db}"
        
        return "redis://localhost:6379/0"
    
    def get_ssh_config(self) -> Dict[str, Any]:
        """获取SSH配置"""
        return self.get("ssh", {})
    
    def get_security_config(self) -> Dict[str, Any]:
        """获取安全配置"""
        return self.get("security", {})
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """获取监控配置"""
        return self.get("monitoring", {})
    
    def get_app_config(self) -> Dict[str, Any]:
        """获取应用配置"""
        return self.get("app", {})
    
    def get_server_config(self) -> Dict[str, Any]:
        """获取服务器配置"""
        return self.get("server", {})
    
    def get_api_config(self) -> Dict[str, Any]:
        """获取API配置"""
        return self.get("api", {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.get("logging", {})
    
    def get_cache_config(self) -> Dict[str, Any]:
        """获取缓存配置"""
        return self.get("cache", {})
    
    def get_graph_database_config(self) -> Dict[str, Any]:
        """获取图数据库配置"""
        return self.get("graph_database", {})
    
    def get_environment(self) -> str:
        """获取当前环境"""
        return self.environment
    
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.environment == "development"
    
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.environment == "production"
    
    def is_testing(self) -> bool:
        """是否为测试环境"""
        return self.environment == "testing"
    
    def get_feature_flag(self, feature: str) -> bool:
        """获取特性开关状态"""
        return self.get(f"app.features.{feature}", False)
    
    def get_config_summary(self) -> str:
        """获取配置摘要"""
        summary = []
        summary.append("Configuration Summary")
        summary.append("=" * 50)
        
        # 应用信息
        app = self.get_app_config()
        summary.append(f"Application: {app.get('name', 'Unknown')} v{app.get('version', 'Unknown')}")
        summary.append(f"Environment: {app.get('environment', 'Unknown')}")
        summary.append(f"Debug: {app.get('debug', False)}")
        
        # 服务器信息
        server = self.get_server_config()
        summary.append(f"Server: {server.get('host', 'Unknown')}:{server.get('port', 'Unknown')}")
        summary.append(f"Workers: {server.get('workers', 1)}")
        
        # 数据库信息
        db_url = self.get_database_url()
        summary.append(f"Database: {db_url.split('@')[-1] if '@' in db_url else db_url}")
        
        # Redis信息
        redis_url = self.get_redis_url()
        summary.append(f"Redis: {redis_url.split('@')[-1] if '@' in redis_url else redis_url}")
        
        # SSH信息
        ssh = self.get_ssh_config()
        if ssh:
            ssh_server = ssh.get("server", {})
            summary.append(f"SSH: {ssh_server.get('host', 'Unknown')}:{ssh_server.get('port', 'Unknown')}")
        
        return "\n".join(summary)


# 全局配置管理器实例
config_manager = ConfigManager()


# 便捷函数
def get_config() -> ConfigManager:
    """获取配置管理器"""
    return config_manager


def get_setting(key: str, default: Any = None) -> Any:
    """获取配置值"""
    return config_manager.get(key, default)


def get_nested_setting(*keys: str, default: Any = None) -> Any:
    """获取嵌套配置值"""
    return config_manager.get_nested(*keys, default)


def reload_config() -> bool:
    """重新加载配置"""
    return config_manager.reload()


def validate_config() -> bool:
    """验证配置"""
    return config_manager.validate()


def get_config_summary() -> str:
    """获取配置摘要"""
    return config_manager.get_config_summary()


# 向后兼容的配置访问
@lru_cache()
def get_database_url() -> str:
    """获取数据库URL（缓存版本）"""
    return config_manager.get_database_url()


@lru_cache()
def get_redis_url() -> str:
    """获取Redis URL（缓存版本）"""
    return config_manager.get_redis_url()


if __name__ == "__main__":
    # 测试配置管理器
    print("Testing ConfigManager...")
    print(config_manager.get_config_summary())
    print("\nValidation Report:")
    print(config_manager.get_validation_report())
