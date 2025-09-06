#!/usr/bin/env python3
"""
测试 database.py 的兼容性
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """测试导入兼容性"""
    print("测试导入兼容性...")
    
    try:
        # 测试基本导入
        from app.core.database import SessionLocal, engine, Base, get_db, get_db_session
        print("✅ 基本导入成功")
        
        # 测试 SessionLocal 类型
        if callable(SessionLocal):
            print("✅ SessionLocal 是可调用的")
        else:
            print("❌ SessionLocal 不是可调用的")
            return False
        
        # 测试 engine 类型
        if engine is not None:
            print("✅ engine 不为空")
        else:
            print("⚠️  engine 为空（可能是配置问题）")
        
        # 测试 Base 类型
        if hasattr(Base, 'metadata'):
            print("✅ Base 有 metadata 属性")
        else:
            print("❌ Base 缺少 metadata 属性")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False

def test_session_creation():
    """测试会话创建"""
    print("\n测试会话创建...")
    
    try:
        from app.core.database import SessionLocal
        
        # 测试创建会话
        session = SessionLocal()
        print("✅ 会话创建成功")
        
        # 测试会话方法
        if hasattr(session, 'query'):
            print("✅ 会话有 query 方法")
        else:
            print("❌ 会话缺少 query 方法")
            return False
        
        # 关闭会话
        session.close()
        print("✅ 会话关闭成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 会话创建失败: {e}")
        return False

def test_engine_usage():
    """测试引擎使用"""
    print("\n测试引擎使用...")
    
    try:
        from app.core.database import engine
        from sqlalchemy import text  # 添加 text 导入
        
        if engine is None:
            print("⚠️  engine 为空，跳过测试")
            return True
        
        # 测试引擎连接
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))  # 使用 text() 函数
            print("✅ 引擎连接成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 引擎使用失败: {e}")
        return False

def test_fastapi_integration():
    """测试 FastAPI 集成"""
    print("\n测试 FastAPI 集成...")
    
    try:
        from app.core.database import get_db
        from sqlalchemy.orm import Session
        
        # 测试 get_db 生成器
        db_gen = get_db()
        db = next(db_gen)
        
        if isinstance(db, Session):
            print("✅ get_db 返回正确的 Session 类型")
        else:
            print(f"❌ get_db 返回错误的类型: {type(db)}")
            return False
        
        # 关闭生成器
        try:
            next(db_gen)
        except StopIteration:
            pass
        
        return True
        
    except Exception as e:
        print(f"❌ FastAPI 集成测试失败: {e}")
        return False

def test_sql_execution():
    """测试 SQL 执行"""
    print("\n测试 SQL 执行...")
    
    try:
        from app.core.database import engine
        from sqlalchemy import text
        
        if engine is None:
            print("⚠️  engine 为空，跳过测试")
            return True
        
        # 测试 SQL 执行
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test_value"))
            row = result.fetchone()
            if row and row[0] == 1:
                print("✅ SQL 执行成功")
            else:
                print("❌ SQL 执行结果不正确")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ SQL 执行失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("Database.py 兼容性测试")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_session_creation,
        test_engine_usage,
        test_fastapi_integration,
        test_sql_execution  # 添加新的测试
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 60)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("✅ 所有测试通过，兼容性正常")
        return True
    else:
        print("❌ 部分测试失败，需要修复")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
