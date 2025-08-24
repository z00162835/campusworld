"""
Configuration management for CampusWorld application
使用YAML配置文件和配置管理器
"""

from app.core.config_manager import get_config, get_setting
from app.core.settings import create_settings_from_config, Settings

# 获取配置管理器
config_manager = get_config()

# 创建新的设置实例
try:
    settings = create_settings_from_config(config_manager)
except Exception as e:
    print(f"Warning: Failed to load YAML config: {e}")
    # 如果YAML配置加载失败，创建一个默认的Settings实例
    # 提供必要的默认值以避免验证错误
    default_settings = {
        "security": {
            "secret_key": "dev-secret-key-change-in-production",
            "algorithm": "HS256",
            "access_token_expire_minutes": 11520,
            "refresh_token_expire_days": 30,
            "password_min_length": 8,
            "bcrypt_rounds": 12
        }
    }
    settings = Settings(**default_settings)

# 为了向后兼容，保留一些常用属性
PROJECT_NAME = get_setting('app.name', 'CampusWorld')
VERSION = get_setting('app.version', '0.1.0')
DESCRIPTION = get_setting('app.description', 'A modern campus world application')
API_V1_STR = get_setting('api.v1_prefix', '/api/v1')
SECRET_KEY = get_setting('security.secret_key', 'your-secret-key-here')
ACCESS_TOKEN_EXPIRE_MINUTES = get_setting('security.access_token_expire_minutes', 11520)
DATABASE_URL = config_manager.get_database_url() if config_manager.get('database') else "postgresql://user:password@localhost/campusworld"
REDIS_URL = config_manager.get_redis_url() if config_manager.get('redis') else "redis://localhost:6379"
ALLOWED_HOSTS = get_setting('cors.allowed_origins', ['*'])
LOG_LEVEL = get_setting('logging.level', 'INFO')
LOG_FORMAT = get_setting('logging.format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ENVIRONMENT = get_setting('app.environment', 'development')
DEBUG = get_setting('app.debug', False)

# 环境检查属性
def is_development() -> bool:
    return ENVIRONMENT == "development"

def is_production() -> bool:
    return ENVIRONMENT == "production"

def is_testing() -> bool:
    return ENVIRONMENT == "testing"

# 便捷的配置访问函数
def get_app_config():
    """获取应用配置"""
    return {
        'name': PROJECT_NAME,
        'version': VERSION,
        'description': DESCRIPTION,
        'environment': ENVIRONMENT,
        'debug': DEBUG
    }

def get_api_config():
    """获取API配置"""
    return {
        'v1_prefix': API_V1_STR,
        'title': get_setting('api.title', 'CampusWorld API'),
        'description': get_setting('api.description', 'CampusWorld REST API Documentation'),
        'docs_url': get_setting('api.docs_url', '/docs'),
        'redoc_url': get_setting('api.redoc_url', '/redoc'),
        'openapi_url': get_setting('api.openapi_url', '/openapi.json')
    }

def get_server_config():
    """获取服务器配置"""
    return {
        'host': get_setting('server.host', '0.0.0.0'),
        'port': get_setting('server.port', 8000),
        'workers': get_setting('server.workers', 1),
        'reload': get_setting('server.reload', True),
        'access_log': get_setting('server.access_log', True)
    }

def get_database_config():
    """获取数据库配置"""
    return get_setting('database', {})

def get_redis_config():
    """获取Redis配置"""
    return get_setting('redis', {})

def get_security_config():
    """获取安全配置"""
    return {
        'secret_key': SECRET_KEY,
        'algorithm': get_setting('security.algorithm', 'HS256'),
        'access_token_expire_minutes': ACCESS_TOKEN_EXPIRE_MINUTES,
        'refresh_token_expire_days': get_setting('security.refresh_token_expire_days', 30),
        'password_min_length': get_setting('security.password_min_length', 8),
        'bcrypt_rounds': get_setting('security.bcrypt_rounds', 12)
    }

def get_cors_config():
    """获取CORS配置"""
    return {
        'allowed_origins': ALLOWED_HOSTS,
        'allowed_methods': get_setting('cors.allowed_methods', ["*"]),
        'allowed_headers': get_setting('cors.allowed_headers', ["*"]),
        'allow_credentials': get_setting('cors.allow_credentials', True),
        'max_age': get_setting('cors.max_age', 86400)
    }

def get_logging_config():
    """获取日志配置"""
    return {
        'level': LOG_LEVEL,
        'format': LOG_FORMAT,
        'date_format': get_setting('logging.date_format', '%Y-%m-%d %H:%M:%S'),
        'file_path': get_setting('logging.file_path', 'logs/campusworld.log'),
        'max_file_size': get_setting('logging.max_file_size', '10MB'),
        'backup_count': get_setting('logging.backup_count', 5),
        'console_output': get_setting('logging.console_output', True),
        'file_output': get_setting('logging.file_output', False)
    }
