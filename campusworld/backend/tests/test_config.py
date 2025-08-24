"""
配置系统测试
"""

import pytest
from unittest.mock import patch, MagicMock
from app.core.config import (
    get_app_config, get_api_config, get_server_config, 
    get_database_config, get_redis_config, get_security_config,
    get_cors_config, get_logging_config, is_development, 
    is_production, is_testing
)


class TestConfigFunctions:
    """测试配置函数"""
    
    def test_get_app_config(self):
        """测试获取应用配置"""
        config = get_app_config()
        
        assert 'name' in config
        assert 'version' in config
        assert 'description' in config
        assert 'environment' in config
        assert 'debug' in config
        
        assert config['name'] == 'CampusWorld'
        assert config['version'] == '0.1.0'
        assert isinstance(config['debug'], bool)
    
    def test_get_api_config(self):
        """测试获取API配置"""
        config = get_api_config()
        
        assert 'v1_prefix' in config
        assert 'title' in config
        assert 'description' in config
        assert 'docs_url' in config
        assert 'redoc_url' in config
        assert 'openapi_url' in config
        
        assert config['v1_prefix'] == '/api/v1'
        assert 'API' in config['title']
    
    def test_get_server_config(self):
        """测试获取服务器配置"""
        config = get_server_config()
        
        assert 'host' in config
        assert 'port' in config
        assert 'workers' in config
        assert 'reload' in config
        assert 'access_log' in config
        
        assert config['host'] == '0.0.0.0'
        assert config['port'] == 8000
        assert isinstance(config['workers'], int)
        assert isinstance(config['reload'], bool)
    
    def test_get_database_config(self):
        """测试获取数据库配置"""
        config = get_database_config()
        
        # 数据库配置应该是一个字典
        assert isinstance(config, dict)
    
    def test_get_redis_config(self):
        """测试获取Redis配置"""
        config = get_redis_config()
        
        # Redis配置应该是一个字典
        assert isinstance(config, dict)
    
    def test_get_security_config(self):
        """测试获取安全配置"""
        config = get_security_config()
        
        assert 'secret_key' in config
        assert 'algorithm' in config
        assert 'access_token_expire_minutes' in config
        assert 'refresh_token_expire_days' in config
        assert 'password_min_length' in config
        assert 'bcrypt_rounds' in config
        
        assert config['algorithm'] == 'HS256'
        assert isinstance(config['access_token_expire_minutes'], int)
        assert isinstance(config['password_min_length'], int)
        assert isinstance(config['bcrypt_rounds'], int)
    
    def test_get_cors_config(self):
        """测试获取CORS配置"""
        config = get_cors_config()
        
        assert 'allowed_origins' in config
        assert 'allowed_methods' in config
        assert 'allowed_headers' in config
        assert 'allow_credentials' in config
        assert 'max_age' in config
        
        assert isinstance(config['allowed_origins'], list)
        assert isinstance(config['allowed_methods'], list)
        assert isinstance(config['allowed_headers'], list)
        assert isinstance(config['allow_credentials'], bool)
        assert isinstance(config['max_age'], int)
    
    def test_get_logging_config(self):
        """测试获取日志配置"""
        config = get_logging_config()
        
        assert 'level' in config
        assert 'format' in config
        assert 'date_format' in config
        assert 'file_path' in config
        assert 'max_file_size' in config
        assert 'backup_count' in config
        assert 'console_output' in config
        assert 'file_output' in config
        
        assert config['level'] == 'INFO'
        assert isinstance(config['backup_count'], int)
        assert isinstance(config['console_output'], bool)
        assert isinstance(config['file_output'], bool)


class TestEnvironmentFunctions:
    """测试环境检查函数"""
    
    @patch('app.core.config.ENVIRONMENT', 'development')
    def test_is_development(self):
        """测试开发环境检查"""
        assert is_development() is True
        assert is_production() is False
        assert is_testing() is False
    
    @patch('app.core.config.ENVIRONMENT', 'production')
    def test_is_production(self):
        """测试生产环境检查"""
        assert is_development() is False
        assert is_production() is True
        assert is_testing() is False
    
    @patch('app.core.config.ENVIRONMENT', 'testing')
    def test_is_testing(self):
        """测试测试环境检查"""
        assert is_development() is False
        assert is_production() is False
        assert is_testing() is True


class TestConfigIntegration:
    """测试配置集成"""
    
    def test_config_consistency(self):
        """测试配置一致性"""
        app_config = get_app_config()
        api_config = get_api_config()
        server_config = get_server_config()
        
        # 应用名称应该一致
        assert app_config['name'] == 'CampusWorld'
        
        # API前缀应该以/开头
        assert api_config['v1_prefix'].startswith('/')
        
        # 服务器端口应该是有效端口
        assert 1 <= server_config['port'] <= 65535
    
    def test_config_types(self):
        """测试配置类型"""
        # 测试所有配置函数返回正确的类型
        assert isinstance(get_app_config(), dict)
        assert isinstance(get_api_config(), dict)
        assert isinstance(get_server_config(), dict)
        assert isinstance(get_database_config(), dict)
        assert isinstance(get_redis_config(), dict)
        assert isinstance(get_security_config(), dict)
        assert isinstance(get_cors_config(), dict)
        assert isinstance(get_logging_config(), dict)
    
    def test_required_config_keys(self):
        """测试必需配置键"""
        # 测试关键配置键是否存在
        app_config = get_app_config()
        assert 'name' in app_config
        assert 'version' in app_config
        
        security_config = get_security_config()
        assert 'secret_key' in security_config
        assert 'algorithm' in security_config
        
        api_config = get_api_config()
        assert 'v1_prefix' in api_config
        assert 'title' in api_config


if __name__ == "__main__":
    pytest.main([__file__])
