"""
配置验证器
用于验证配置文件的完整性和有效性
"""

import os
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import yaml
from dataclasses import dataclass


@dataclass
class ValidationError:
    """配置验证错误"""
    path: str
    message: str
    severity: str  # error, warning, info
    value: Any = None
    expected: Any = None


class ConfigValidator:
    """配置验证器"""
    
    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
        self.info: List[ValidationError] = []
    
    def validate_config(self, config: Dict[str, Any], config_path: str = "") -> bool:
        """验证配置"""
        self.errors.clear()
        self.warnings.clear()
        self.info.clear()
        
        # 基础验证
        self._validate_required_fields(config, config_path)
        self._validate_data_types(config, config_path)
        self._validate_value_ranges(config, config_path)
        self._validate_environment_variables(config, config_path)
        self._validate_file_paths(config, config_path)
        self._validate_network_config(config, config_path)
        self._validate_security_config(config, config_path)
        
        return len(self.errors) == 0
    
    def _validate_required_fields(self, config: Dict[str, Any], path: str):
        """验证必需字段"""
        # 只对完整配置文件验证必需字段
        if "app" in config and "server" in config:
            required_fields = {
                "app.name": str,
                "app.version": str,
                "app.environment": str,
                "server.host": str,
                "server.port": int,
            }
            
            for field_path, expected_type in required_fields.items():
                value = self._get_nested_value(config, field_path)
                if value is None:
                    self.errors.append(ValidationError(
                        path=f"{path}.{field_path}",
                        message=f"Required field '{field_path}' is missing",
                        severity="error"
                    ))
                elif not isinstance(value, expected_type):
                    self.errors.append(ValidationError(
                        path=f"{path}.{field_path}",
                        message=f"Field '{field_path}' must be {expected_type.__name__}",
                        severity="error",
                        value=value,
                        expected=expected_type.__name__
                    ))
    
    def _validate_data_types(self, config: Dict[str, Any], path: str):
        """验证数据类型"""
        type_validations = {
            "server.port": (int, lambda x: 1 <= x <= 65535),
            "server.workers": (int, lambda x: x > 0),
            "database.pool.size": (int, lambda x: x > 0),
            "logging.level": (str, lambda x: x in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
        }
        
        for field_path, (expected_type, validator) in type_validations.items():
            value = self._get_nested_value(config, field_path)
            if value is not None:
                if not isinstance(value, expected_type):
                    self.errors.append(ValidationError(
                        path=f"{path}.{field_path}",
                        message=f"Field '{field_path}' must be {expected_type.__name__}",
                        severity="error",
                        value=value,
                        expected=expected_type.__name__
                    ))
                elif not validator(value):
                    self.errors.append(ValidationError(
                        path=f"{path}.{field_path}",
                        message=f"Field '{field_path}' has invalid value: {value}",
                        severity="error",
                        value=value
                    ))
    
    def _validate_value_ranges(self, config: Dict[str, Any], path: str):
        """验证数值范围"""
        range_validations = {
            "server.port": (1, 65535),
            "server.workers": (1, 32),
            "database.pool.size": (1, 1000),
            "database.pool.max_overflow": (0, 1000),
            "redis.pool.max_connections": (1, 1000),
            "logging.max_file_size": (1024, 1024*1024*1024),  # 1KB to 1GB
        }
        
        for field_path, (min_val, max_val) in range_validations.items():
            value = self._get_nested_value(config, field_path)
            if value is not None and isinstance(value, (int, float)):
                if value < min_val or value > max_val:
                    self.errors.append(ValidationError(
                        path=f"{path}.{field_path}",
                        message=f"Field '{field_path}' must be between {min_val} and {max_val}",
                        severity="error",
                        value=value,
                        expected=f"{min_val} to {max_val}"
                    ))
    
    def _validate_environment_variables(self, config: Dict[str, Any], path: str):
        """验证环境变量引用"""
        env_pattern = r'\$\{([^}]+)\}'
        
        def check_env_refs(obj, obj_path):
            if isinstance(obj, str):
                matches = re.findall(env_pattern, obj)
                for env_var in matches:
                    if not os.getenv(env_var):
                        self.warnings.append(ValidationError(
                            path=f"{path}.{obj_path}",
                            message=f"Environment variable '{env_var}' is not set",
                            severity="warning",
                            value=obj
                        ))
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    check_env_refs(value, f"{obj_path}.{key}" if obj_path else key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_env_refs(item, f"{obj_path}[{i}]" if obj_path else f"[{i}]")
        
        check_env_refs(config, "")
    
    def _validate_file_paths(self, config: Dict[str, Any], path: str):
        """验证文件路径"""
        file_path_fields = [
            "logging.file.path",
            "ssh.logging.file.path",
            "security.encryption.key_management.master_key_path",
        ]
        
        for field_path in file_path_fields:
            value = self._get_nested_value(config, field_path)
            if value and isinstance(value, str):
                # 检查路径格式
                if not self._is_valid_file_path(value):
                    self.warnings.append(ValidationError(
                        path=f"{path}.{field_path}",
                        message=f"File path '{value}' may not be valid",
                        severity="warning",
                        value=value
                    ))
    
    def _validate_network_config(self, config: Dict[str, Any], path: str):
        """验证网络配置"""
        # 验证主机地址
        host = self._get_nested_value(config, "server.host")
        if host and host not in ["0.0.0.0", "127.0.0.1", "localhost"]:
            if not self._is_valid_ip(host):
                self.warnings.append(ValidationError(
                    path=f"{path}.server.host",
                    message=f"Host '{host}' may not be a valid IP address",
                    severity="warning",
                    value=host
                ))
        
        # 验证端口冲突
        port = self._get_nested_value(config, "server.port")
        ssh_port = self._get_nested_value(config, "ssh.server.port")
        if port and ssh_port and port == ssh_port:
            self.errors.append(ValidationError(
                path=f"{path}.server.port",
                message=f"Port {port} conflicts with SSH port {ssh_port}",
                severity="error",
                value=port
            ))
    
    def _validate_security_config(self, config: Dict[str, Any], path: str):
        """验证安全配置"""
        # 验证JWT密钥
        jwt_secret = self._get_nested_value(config, "security.authentication.jwt.secret_key")
        if jwt_secret and jwt_secret == "your-secret-key-here-change-in-production":
            self.errors.append(ValidationError(
                path=f"{path}.security.authentication.jwt.secret_key",
                message="JWT secret key must be changed from default value",
                severity="error",
                value=jwt_secret
            ))
        
        # 验证密码策略
        min_length = self._get_nested_value(config, "security.authentication.password.min_length")
        if min_length and min_length < 8:
            self.warnings.append(ValidationError(
                path=f"{path}.security.authentication.password.min_length",
                message="Password minimum length should be at least 8 characters",
                severity="warning",
                value=min_length
            ))
    
    def _get_nested_value(self, config: Dict[str, Any], path: str) -> Any:
        """获取嵌套配置值"""
        keys = path.split('.')
        value = config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value
    
    def _is_valid_file_path(self, path: str) -> bool:
        """检查文件路径是否有效"""
        try:
            Path(path)
            return True
        except Exception:
            return False
    
    def _is_valid_ip(self, ip: str) -> bool:
        """检查IP地址是否有效"""
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(ip_pattern, ip):
            return False
        
        parts = ip.split('.')
        return all(0 <= int(part) <= 255 for part in parts)
    
    def get_validation_report(self) -> str:
        """获取验证报告"""
        report = []
        report.append("Configuration Validation Report")
        report.append("=" * 50)
        
        if self.errors:
            report.append(f"\n❌ Errors ({len(self.errors)}):")
            for error in self.errors:
                report.append(f"  - {error.path}: {error.message}")
                if error.value is not None:
                    report.append(f"    Value: {error.value}")
                if error.expected is not None:
                    report.append(f"    Expected: {error.expected}")
        
        if self.warnings:
            report.append(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                report.append(f"  - {warning.path}: {warning.message}")
        
        if self.info:
            report.append(f"\nℹ️  Info ({len(self.info)}):")
            for info in self.info:
                report.append(f"  - {info.path}: {info.message}")
        
        if not self.errors and not self.warnings:
            report.append("\n✅ Configuration is valid!")
        
        return "\n".join(report)
    
    def has_errors(self) -> bool:
        """是否有错误"""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """是否有警告"""
        return len(self.warnings) > 0


def validate_config_file(config_path: str) -> Tuple[bool, str]:
    """验证配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        validator = ConfigValidator()
        is_valid = validator.validate_config(config, config_path)
        report = validator.get_validation_report()
        
        return is_valid, report
        
    except Exception as e:
        return False, f"Failed to validate config file: {e}"


if __name__ == "__main__":
    # 测试验证器
    test_config = {
        "app": {
            "name": "TestApp",
            "version": "1.0.0",
            "environment": "development"
        },
        "server": {
            "host": "0.0.0.0",
            "port": 8000,
            "workers": 1
        }
    }
    
    validator = ConfigValidator()
    is_valid = validator.validate_config(test_config)
    print(validator.get_validation_report())
