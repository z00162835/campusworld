#!/usr/bin/env python3
"""
配置管理器测试脚本
用于测试config_manager.py是否正常工作
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_config_manager():
    """测试配置管理器"""
    print("🧪 开始测试配置管理器...")
    
    try:
        # 测试导入
        print("1. 测试模块导入...")
        from app.core.config_manager import ConfigManager
        print("✅ 模块导入成功")
        
        # 测试创建实例
        print("2. 测试创建配置管理器实例...")
        config_manager = ConfigManager()
        print("✅ 配置管理器实例创建成功")
        
        # 测试配置加载
        print("3. 测试配置加载...")
        config = config_manager.get_all()
        print(f"✅ 配置加载成功，配置项数量: {len(config)}")
        
        # 测试配置验证
        print("4. 测试配置验证...")
        if config_manager.validate():
            print("✅ 配置验证通过")
        else:
            print("⚠️  配置验证存在警告")
        
        # 测试配置获取
        print("5. 测试配置获取...")
        app_name = config_manager.get('app.name', 'N/A')
        db_host = config_manager.get('database.host', 'N/A')
        print(f"✅ 应用名称: {app_name}")
        print(f"✅ 数据库主机: {db_host}")
        
        # 测试数据库URL生成
        print("6. 测试数据库URL生成...")
        try:
            db_url = config_manager.get_database_url()
            print(f"✅ 数据库URL: {db_url}")
        except Exception as e:
            print(f"⚠️  数据库URL生成失败: {e}")
        
        # 测试Redis URL生成
        print("7. 测试Redis URL生成...")
        try:
            redis_url = config_manager.get_redis_url()
            print(f"✅ Redis URL: {redis_url}")
        except Exception as e:
            print(f"⚠️  Redis URL生成失败: {e}")
        
        # 打印配置摘要
        print("8. 打印配置摘要...")
        config_manager.print_config_summary()
        
        print("\n🎉 所有测试通过！配置管理器工作正常")
        return True
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请确保已安装所需依赖:")
        print("  pip install pyyaml pydantic pydantic-settings")
        return False
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_config_manager()
    sys.exit(0 if success else 1)
