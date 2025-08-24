#!/usr/bin/env python3
"""
数据库初始化脚本
用于setup.sh初始化数据库
"""

import sys
import os
from pathlib import Path

def main():
    """主函数"""
    try:
        print("🔍 开始初始化数据库...")
        
        # 获取当前脚本所在目录
        current_dir = Path(__file__).parent.absolute()
        print(f"当前目录: {current_dir}")
        
        # 添加当前目录到Python路径
        if str(current_dir) not in sys.path:
            sys.path.insert(0, str(current_dir))
        
        print(f"Python路径: {sys.path[:3]}...")
        
        # 测试导入SQLAlchemy
        try:
            import sqlalchemy
            print(f"✅ SQLAlchemy导入成功: {sqlalchemy.__version__}")
        except ImportError as e:
            print(f"❌ SQLAlchemy导入失败: {e}")
            print("请确保已安装SQLAlchemy: pip install sqlalchemy")
            return False
        
        # 测试导入psycopg2
        try:
            import psycopg2
            print(f"✅ psycopg2导入成功")
        except ImportError as e:
            print(f"❌ psycopg2导入失败: {e}")
            print("请确保已安装psycopg2: pip install psycopg2-binary")
            return False
        
        # 导入数据库模块
        try:
            from app.core.database import init_db, engine
            print("✅ 数据库模块导入成功")
        except ImportError as e:
            print(f"❌ 数据库模块导入失败: {e}")
            return False
        
        # 检查数据库连接
        try:
            print("检查数据库连接...")
            with engine.connect() as conn:
                print("✅ 数据库连接成功")
        except Exception as e:
            print(f"❌ 数据库连接失败: {e}")
            print("请确保PostgreSQL服务正在运行")
            print("如果使用Docker，请运行: docker compose up -d")
            return False
        
        # 初始化数据库
        try:
            print("初始化数据库表...")
            init_db()
            print("✅ 数据库初始化完成")
            return True
        except Exception as e:
            print(f"❌ 数据库初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
