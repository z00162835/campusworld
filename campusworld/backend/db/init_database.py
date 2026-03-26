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
            # 关键：确保 ORM 模型被导入，从而注册到 Base.metadata
            import app.models  # noqa: F401

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

            # 轻量 schema 兼容迁移（让旧库补齐新增字段）
            schema_ok = True
            try:
                from db.schema_migrations import ensure_graph_schema

                ensure_graph_schema(engine)
                print("✅ schema 兼容迁移完成")
            except Exception as e:
                schema_ok = False
                print(f"⚠️  schema 兼容迁移跳过/失败: {e}")

            # 可选：开发环境种子数据
            try:
                from app.core.config_manager import get_setting

                seed_enabled = bool(get_setting("development.seed_data", False))
                # env 覆盖（更直观）：CAMPUSWORLD_DEVELOPMENT_SEED_DATA=true/false
                env_override = os.getenv("CAMPUSWORLD_DEVELOPMENT_SEED_DATA")
                if env_override is not None:
                    seed_enabled = env_override.lower() == "true"

                if seed_enabled:
                    if not schema_ok:
                        print("⚠️  种子数据跳过：schema 兼容迁移未完成（通常是缺少 postgis/vector 扩展）")
                        return True
                    print("🌱 开始初始化种子数据（development.seed_data=true）...")
                    from db.seed_data import seed_minimal

                    if seed_minimal():
                        print("✅ 种子数据初始化完成")
                    else:
                        print("❌ 种子数据初始化失败")
                        return False
            except Exception as e:
                print(f"⚠️  种子数据阶段跳过/失败: {e}")

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
