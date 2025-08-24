"""
配置管理器
负责加载和管理YAML配置文件，支持环境变量覆盖和配置继承
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union

# 检查并导入yaml模块
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# 检查并导入pydantic模块
try:
    from pydantic import BaseModel, Field, validator
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

# 检查pydantic-settings模块
try:
    from pydantic_settings import BaseSettings
    PYDANTIC_SETTINGS_AVAILABLE = True
except ImportError:
    PYDANTIC_SETTINGS_AVAILABLE = False


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = "config", env: str = None):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录
            env: 环境名称 (dev, test, prod)
        """
        # 检查依赖是否可用
        if not YAML_AVAILABLE:
            raise ImportError("PyYAML 模块未安装")
        if not PYDANTIC_AVAILABLE:
            raise ImportError("Pydantic 模块未安装")
            
        self.config_dir = Path(config_dir)
        self.env = env or os.getenv("ENVIRONMENT", "development")
        self._config_cache = {}
        self._config = {}
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        try:
            # 加载基础配置
            base_config = self._load_yaml_file("settings.yaml")
            if not base_config:
                print(f"⚠️  基础配置文件不存在: {self.config_dir}/settings.yaml")
                base_config = {}
            
            # 加载环境特定配置
            # 支持多种命名约定：settings.dev.yaml, settings.development.yaml
            env_config = None
            env_file_names = [
                f"settings.{self.env}.yaml",
                f"settings.{self.env[:3]}.yaml"  # 支持 dev, pro, tes 等缩写
            ]
            
            for env_file_name in env_file_names:
                env_config = self._load_yaml_file(env_file_name)
                if env_config:
                    break
            
            if not env_config:
                print(f"⚠️  环境配置文件不存在: {self.config_dir}/settings.{self.env}.yaml 或 {self.config_dir}/settings.{self.env[:3]}.yaml")
                env_config = {}
            
            # 合并配置
            self._config = self._deep_merge(base_config, env_config)
            
            # 应用环境变量覆盖
            self._apply_env_overrides()
            
            print(f"✅ 配置加载成功，环境: {self.env}")
            
        except Exception as e:
            print(f"❌ 配置加载失败: {e}")
            # 创建默认配置
            self._config = self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, Any]:
        """创建默认配置"""
        return {
            "app": {
                "name": "CampusWorld",
                "version": "0.1.0",
                "description": "A modern campus world application",
                "environment": self.env,
                "debug": True
            },
            "database": {
                "engine": "postgresql",
                "host": "localhost",
                "port": 5432,
                "name": "campusworld",
                "user": "campusworld_user",
                "password": "campusworld_password"
            },
            "redis": {
                "host": "localhost",
                "port": 6379,
                "password": "",
                "db": 0
            },
            "security": {
                "secret_key": "your-secret-key-here-change-in-production",
                "algorithm": "HS256",
                "access_token_expire_minutes": 1440,
                "refresh_token_expire_days": 7
            },
            "server": {
                "host": "0.0.0.0",
                "port": 8000,
                "workers": 1,
                "reload": True
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            },
            "cors": {
                "allowed_origins": ["*"],
                "allowed_methods": ["*"],
                "allowed_headers": ["*"],
                "allow_credentials": True
            }
        }
    
    def _load_yaml_file(self, filename: str) -> Optional[Dict[str, Any]]:
        """加载YAML文件"""
        file_path = self.config_dir / filename
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
                if content is None:
                    print(f"⚠️  YAML文件为空: {filename}")
                    return {}
                return content
        except yaml.YAMLError as e:
            print(f"❌ YAML语法错误 {filename}: {e}")
            return None
        except Exception as e:
            print(f"❌ 读取配置文件失败 {filename}: {e}")
            return None
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """深度合并字典"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _apply_env_overrides(self):
        """应用环境变量覆盖"""
        try:
            for key_path, value in self._get_env_configs():
                self._set_nested_value(self._config, key_path, value)
        except Exception as e:
            print(f"⚠️  环境变量覆盖失败: {e}")
    
    def _get_env_configs(self) -> list:
        """获取环境变量配置"""
        env_configs = []
        
        for key, value in os.environ.items():
            if key.startswith("CAMPUSWORLD_"):
                # 转换 CAMPUSWORLD_DATABASE_HOST -> database.host
                config_path = key.replace("CAMPUSWORLD_", "").lower().replace("_", ".")
                env_configs.append((config_path.split("."), value))
        
        return env_configs
    
    def _set_nested_value(self, config: Dict[str, Any], path: list, value: Any):
        """设置嵌套配置值"""
        current = config
        
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # 尝试转换值类型
        current[path[-1]] = self._convert_value(value)
    
    def _convert_value(self, value: str) -> Union[str, int, float, bool]:
        """转换环境变量值类型"""
        # 布尔值
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # 整数
        try:
            return int(value)
        except ValueError:
            pass
        
        # 浮点数
        try:
            return float(value)
        except ValueError:
            pass
        
        # 字符串
        return value
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key_path: 配置键路径，如 'database.host'
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key_path.split('.')
        current = self._config
        
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default
    
    def get_database_url(self) -> str:
        """获取数据库连接URL"""
        db_config = self.get('database')
        if not db_config:
            raise ValueError("Database configuration not found")
        
        engine = db_config.get('engine', 'postgresql')
        host = db_config.get('host', 'localhost')
        port = db_config.get('port', 5432)
        name = db_config.get('name', 'campusworld')
        user = db_config.get('user', '')
        password = db_config.get('password', '')
        
        if user and password:
            return f"{engine}://{user}:{password}@{host}:{port}/{name}"
        else:
            return f"{engine}://{host}:{port}/{name}"
    
    def get_redis_url(self) -> str:
        """获取Redis连接URL"""
        redis_config = self.get('redis')
        if not redis_config:
            raise ValueError("Redis configuration not found")
        
        host = redis_config.get('host', 'localhost')
        port = redis_config.get('port', 6379)
        db = redis_config.get('db', 0)
        password = redis_config.get('password', '')
        
        if password:
            return f"redis://:{password}@{host}:{port}/{db}"
        else:
            return f"redis://{host}:{port}/{db}"
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self._config.copy()
    
    def reload(self):
        """重新加载配置"""
        self._config_cache.clear()
        self._load_config()
    
    def validate(self) -> bool:
        """验证配置"""
        try:
            # 检查必要的配置键
            required_keys = ['app', 'database', 'security']
            missing_keys = []
            
            for key in required_keys:
                if not self.get(key):
                    missing_keys.append(key)
            
            if missing_keys:
                print(f"⚠️  缺少必要配置: {', '.join(missing_keys)}")
                return False
            
            # 检查数据库配置
            db_config = self.get('database')
            if db_config:
                required_db_keys = ['host', 'port', 'name']
                for key in required_db_keys:
                    if not db_config.get(key):
                        print(f"⚠️  数据库配置缺少: {key}")
                        return False
            
            # 检查安全配置
            security_config = self.get('security')
            if security_config:
                if not security_config.get('secret_key') or security_config.get('secret_key') == 'your-secret-key-here-change-in-production':
                    if self.env == 'production':
                        print("❌ 生产环境必须设置安全密钥")
                        return False
                    else:
                        print("⚠️  开发环境使用默认安全密钥")
            
            print("✅ 配置验证通过")
            return True
            
        except Exception as e:
            print(f"❌ 配置验证失败: {e}")
            return False
    
    def print_config_summary(self):
        """打印配置摘要"""
        print("\n📋 配置摘要:")
        print(f"  环境: {self.env}")
        print(f"  应用名称: {self.get('app.name', 'N/A')}")
        print(f"  应用版本: {self.get('app.version', 'N/A')}")
        print(f"  数据库主机: {self.get('database.host', 'N/A')}")
        print(f"  数据库端口: {self.get('database.port', 'N/A')}")
        print(f"  Redis主机: {self.get('redis.host', 'N/A')}")
        print(f"  Redis端口: {self.get('redis.port', 'N/A')}")
        print(f"  服务器端口: {self.get('server.port', 'N/A')}")
        print(f"  日志级别: {self.get('logging.level', 'N/A')}")


# 全局配置管理器实例（延迟初始化）
_config_manager_instance = None


def get_config() -> ConfigManager:
    """获取配置管理器实例"""
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager()
    return _config_manager_instance


def get_setting(key_path: str, default: Any = None) -> Any:
    """获取配置值的便捷函数"""
    return get_config().get(key_path, default)


# 如果直接运行此文件，进行测试
if __name__ == "__main__":
    try:
        print("🧪 测试配置管理器...")
        
        # 创建配置管理器实例
        cm = ConfigManager()
        
        # 打印配置摘要
        cm.print_config_summary()
        
        # 验证配置
        if cm.validate():
            print("✅ 配置管理器测试成功")
        else:
            print("⚠️  配置管理器测试完成，但存在警告")
            
    except Exception as e:
        print(f"❌ 配置管理器测试失败: {e}")
        sys.exit(1)
