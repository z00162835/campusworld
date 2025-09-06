"""
配置管理器
负责加载和管理YAML配置文件，支持环境变量覆盖和配置继承
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union
from copy import deepcopy
import json
from app.core.log import get_logger
from app.core.paths import get_config_dir

# 检查并导入yaml模块
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

class ConfigLoader:
    """配置加载器"""
    
    def __init__(self, config_dir: Path, env: str):
        self.config_dir = config_dir
        self.env = env
    
    def load_base_config(self) -> Dict[str, Any]:
        """加载基础配置"""
        return self._load_yaml_file("settings.yaml") or {}
    
    def load_env_config(self) -> Dict[str, Any]:
        """加载环境配置"""
        env_file_names = [
            f"settings.{self.env}.yaml",
            f"settings.{self.env[:3]}.yaml"
        ]
        
        for env_file_name in env_file_names:
            env_config = self._load_yaml_file(env_file_name)
            if env_config:
                return env_config
        
        return {}
    
    def _load_yaml_file(self, filename: str) -> Optional[Dict[str, Any]]:
        """加载YAML文件"""
        file_path = self.config_dir / filename
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
                return content if content is not None else {}
        except yaml.YAMLError as e:
            print(f"❌ YAML语法错误 {filename}: {e}")
            return None
        except Exception as e:
            print(f"❌ 读取配置文件失败 {filename}: {e}")
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

class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录
            env: 环境名称 (dev, test, prod)
        """
        # 检查依赖是否可用
        if not YAML_AVAILABLE:
            raise ImportError("PyYAML 模块未安装")
            # 自动检测配置文件目

        self.config_dir = get_config_dir()

        self.env = os.getenv("ENVIRONMENT", "development")
        self.logger = get_logger("campusworld.config_manager")
        self._config_cache = {}
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        try:
            loader = ConfigLoader(self.config_dir, self.env)
            
            # 加载基础配置
            base_config = loader.load_base_config()
            if not base_config:
                raise RuntimeError(f"基础配置文件不存在: {self.config_dir}/settings.yaml")
            
            # 加载环境配置
            env_config = loader.load_env_config()
            
            # 合并配置
            self._config_cache = loader._merge_config(base_config, env_config)
            
            # 应用环境变量覆盖
            self._apply_env_overrides()
            
            self.logger.info(f"配置加载成功，环境: {self.env}")
            
        except Exception as e:
            self.logger.error(f"配置加载失败: {e}")
            raise RuntimeError(f"配置加载失败: {e}")

    def _apply_env_overrides(self):
        """应用环境变量覆盖"""
        try:
            for key_path, value in self._get_env_configs():
                self._set_nested_value(self._config_cache, key_path, value)
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

    
    def validate(self) -> bool:
        """验证配置"""
        try:
            # 首先检查配置是否已加载
            if not self._config_cache:
                print("❌ 配置未加载")
                return False
            
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


    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        try:
            keys = key.split('.')
            value = self._config_cache
            
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            
            return value
        except Exception as e:
            self.logger.error(f"获取配置失败: {e}")
            return default
    
    def get_nested(self, *keys: str, default: Any = None) -> Any:
        """获取嵌套配置值"""
        try:
            value = self._config_cache
            
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default
            
            return value
        except Exception as e:
            print(f"获取嵌套配置失败: {e}")
            return default
    
    def set(self, key: str, value: Any):
        """设置配置值"""
        keys = key.split('.')
        config = self._config_cache
        
        # 导航到父级
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # 设置值
        config[keys[-1]] = value
    
    def has(self, key: str) -> bool:
        """检查配置键是否存在"""
        try:
            keys = key.split('.')
            value = self._config_cache
            
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return False
            
            return True
        except Exception:
            return False
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return deepcopy(self._config_cache)
    
    def reload(self) -> bool:
        """重新加载配置"""
        try:
            self._config_cache = {}  # 清空现有配置
            self._load_config()  # 重新加载
            return True
        except Exception as e:
            self.logger.error(f"配置重载失败: {e}")
            return False
    
    def export(self, format: str = "yaml", file_path: Optional[str] = None) -> str:
        """导出配置"""
        if format.lower() == "yaml":
            content = yaml.dump(self._config_cache, default_flow_style=False, allow_unicode=True)
        elif format.lower() == "json":
            content = json.dumps(self._config_cache, indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return content
    
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
    
    def get_ssh_config(self) -> Dict[str, Any]:
        """获取SSH配置"""
        return self._config_cache.get("ssh", {})
    
    def get_security_config(self) -> Dict[str, Any]:
        """获取安全配置"""
        return self._config_cache.get("security", {})
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """获取监控配置"""
        return self._config_cache.get("monitoring", {})
    
    def get_app_config(self) -> Dict[str, Any]:
        """获取应用配置"""
        return self._config_cache.get("app", {})
    
    def get_server_config(self) -> Dict[str, Any]:
        """获取服务器配置"""
        return self._config_cache.get("server", {})
    
    def get_api_config(self) -> Dict[str, Any]:
        """获取API配置"""
        return self._config_cache.get("api", {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self._config_cache.get("logging", {})
    
    def get_cache_config(self) -> Dict[str, Any]:
        """获取缓存配置"""
        return self._config_cache.get("cache", {})
    
    def get_environment(self) -> str:
        """获取当前环境"""
        return self.env
    
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.env == "development"
    
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.env == "production"
    
    def is_testing(self) -> bool:
        """是否为测试环境"""
        return self.env == "testing"
    
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
        summary.append(f"SSH: {ssh.get('host', 'Unknown')}:{ssh.get('port', 'Unknown')}")
        
        return "\n".join(summary)

    def is_loaded(self) -> bool:
        """检查配置是否已加载"""
        return bool(self._config_cache)
    
    def get_config_status(self) -> Dict[str, Any]:
        """获取配置状态"""
        return {
            'loaded': self.is_loaded(),
            'environment': self.env,
            'config_dir': str(self.config_dir),
            'config_keys': list(self._config_cache.keys()) if self._config_cache else []
        }


# 全局配置管理器实例（延迟初始化）
_config_manager_instance = None

# 便捷函数

def get_config() -> ConfigManager:
    """获取配置管理器实例"""
    global _config_manager_instance
    if _config_manager_instance is None:
        try:
            _config_manager_instance = ConfigManager()
        except Exception as e:
            raise RuntimeError(f"无法创建配置管理器: {e}")
    return _config_manager_instance


def get_setting(key: str, default: Any = None) -> Any:
    """获取配置值的便捷函数"""
    return get_config().get(key, default)


def get_nested_setting(*keys: str, default: Any = None) -> Any:
    """获取嵌套配置值"""
    return get_config().get_nested(*keys, default)


def reload_config() -> bool:
    """重新加载配置"""
    return get_config().reload()

def get_config_summary() -> str:
    """获取配置摘要"""
    return get_config().get_config_summary()


# 如果直接运行此文件，进行测试
if __name__ == "__main__":
    try:
        print("🧪 测试配置管理器...")
        
        # 创建配置管理器实例
        cm = ConfigManager()
        
        # 打印配置摘要
        print(cm.get_config_summary())
        
        # 验证配置
        if cm.validate():
            print("✅ 配置管理器测试成功")
        else:
            print("⚠️  配置管理器测试完成，但存在警告")
            
    except Exception as e:
        print(f"❌ 配置管理器测试失败: {e}")
        sys.exit(1)
