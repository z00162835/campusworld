#!/usr/bin/env python3
"""
配置验证脚本
用于验证YAML配置文件的正确性和完整性
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config_manager import ConfigManager
from app.core.settings import create_settings_from_config


def _try_load_dotenv() -> bool:
    """
    尝试加载 backend/.env 到当前进程环境变量。
    - 仅用于开发/脚本工具，生产建议用真实环境变量或密钥管理系统注入。
    """
    dotenv_path = project_root / ".env"
    if not dotenv_path.exists():
        return False

    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        print(f"⚠️  检测到 {dotenv_path}，但未安装 python-dotenv，已跳过加载")
        return False

    load_dotenv(dotenv_path=dotenv_path, override=False)
    return True


def validate_config():
    """验证配置文件"""
    print("🔍 开始验证CampusWorld配置文件...")
    
    # 检查配置文件目录
    config_dir = project_root / "config"
    if not config_dir.exists():
        print("❌ 配置文件目录不存在:", config_dir)
        return False
    
    # 检查基础配置文件
    base_config = config_dir / "settings.yaml"
    if not base_config.exists():
        print("❌ 基础配置文件不存在:", base_config)
        return False
    
    # 检查环境配置文件
    envs = ["dev", "test", "prod"]
    for env in envs:
        env_config = config_dir / f"settings.{env}.yaml"
        if not env_config.exists():
            print(f"⚠️  环境配置文件不存在: {env_config}")
        else:
            print(f"✅ 环境配置文件存在: {env_config}")
    
    # 测试配置加载
    try:
        print("\n📋 测试配置加载...")
        config_manager = ConfigManager()
        
        # 验证配置
        if not config_manager.validate():
            print("❌ 配置验证失败")
            return False
        
        # 测试Pydantic模型创建
        print("🔧 测试Pydantic模型创建...")
        settings = create_settings_from_config(config_manager)
        print("✅ Pydantic模型创建成功")
        
        # 显示关键配置
        print("\n📊 关键配置信息:")
        print(f"  应用名称: {config_manager.get('app.name')}")
        print(f"  应用版本: {config_manager.get('app.version')}")
        print(f"  运行环境: {config_manager.get('app.environment')}")
        print(f"  数据库主机: {config_manager.get('database.host')}")
        print(f"  数据库端口: {config_manager.get('database.port')}")
        print(f"  Redis主机: {config_manager.get('redis.host')}")
        print(f"  Redis端口: {config_manager.get('redis.port')}")
        print(f"  API前缀: {config_manager.get('api.v1_prefix')}")
        
        # 测试数据库URL生成
        try:
            db_url = config_manager.get_database_url()
            print(f"  数据库URL: {db_url}")
        except Exception as e:
            print(f"  ❌ 数据库URL生成失败: {e}")
            return False
        
        # 测试Redis URL生成
        try:
            redis_url = config_manager.get_redis_url()
            print(f"  Redis URL: {redis_url}")
        except Exception as e:
            print(f"  ❌ Redis URL生成失败: {e}")
            return False
        
        print("\n✅ 所有配置验证通过！")
        return True
        
    except Exception as e:
        print(f"❌ 配置验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_environment_variables():
    """检查环境变量配置"""
    print("\n🔧 检查环境变量配置...")
    
    env_vars = [
        "ENVIRONMENT",
        "CAMPUSWORLD_SECURITY_SECRET_KEY",
        "CAMPUSWORLD_DATABASE_PASSWORD",
        "CAMPUSWORLD_REDIS_PASSWORD"
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # 隐藏敏感信息
            if "PASSWORD" in var or "SECRET" in var:
                display_value = "*" * min(len(value), 8)
            else:
                display_value = value
            print(f"  ✅ {var}: {display_value}")
        else:
            print(f"  ⚠️  {var}: 未设置")
    
    return True


def main():
    """主函数"""
    print("🚀 CampusWorld 配置验证工具")
    print("=" * 50)

    # 尝试加载 .env（混合配置模式：YAML 为主，env 为覆盖）
    if _try_load_dotenv():
        print("✅ 已加载 backend/.env（用于环境变量覆盖）")
    
    # 验证配置文件
    config_valid = validate_config()
    
    # 检查环境变量
    env_valid = check_environment_variables()
    
    # 总结
    print("\n" + "=" * 50)
    if config_valid and env_valid:
        print("🎉 配置验证完成，所有检查通过！")
        sys.exit(0)
    else:
        print("❌ 配置验证失败，请检查上述错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()
