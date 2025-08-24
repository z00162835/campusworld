#!/usr/bin/env python3
"""
配置验证脚本
用于setup.sh验证配置文件
"""

import sys
import os
from pathlib import Path

def main():
    """主函数"""
    try:
        print("🔍 开始验证配置文件...")
        
        # 获取当前脚本所在目录
        current_dir = Path(__file__).parent.absolute()
        print(f"当前目录: {current_dir}")
        
        # 添加当前目录到Python路径
        if str(current_dir) not in sys.path:
            sys.path.insert(0, str(current_dir))
        
        print(f"Python路径: {sys.path[:3]}...")
        
        # 测试导入pydantic
        try:
            import pydantic
            print(f"✅ Pydantic导入成功: {pydantic.__version__}")
        except ImportError as e:
            print(f"❌ Pydantic导入失败: {e}")
            return False
        
        # 导入配置管理器
        try:
            from app.core.config_manager import ConfigManager
            print("✅ 配置管理器导入成功")
        except ImportError as e:
            print(f"❌ 配置管理器导入失败: {e}")
            return False
        
        # 创建配置管理器实例
        config_manager = ConfigManager('config')
        
        # 验证配置
        if config_manager.validate():
            print("✅ 配置验证通过")
            
            # 显示关键配置
            print(f"应用名称: {config_manager.get('app.name')}")
            print(f"运行环境: {config_manager.get('app.environment')}")
            print(f"数据库主机: {config_manager.get('database.host')}")
            print(f"Redis主机: {config_manager.get('redis.host')}")
            
            return True
        else:
            print("❌ 配置验证失败")
            return False
            
    except Exception as e:
        print(f"❌ 配置验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
