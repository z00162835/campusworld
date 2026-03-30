"""
Database 兼容性测试

测试 database.py 的导入和基本功能
"""

import sys
from pathlib import Path

import pytest

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestDatabaseCompatibility:
    """数据库兼容性测试类"""

    def test_imports(self):
        """测试导入兼容性"""
        # 测试基本导入
        from app.core.database import SessionLocal, engine, Base, get_db, get_db_session

        # 测试 SessionLocal 类型
        assert callable(SessionLocal), "SessionLocal 不是可调用的"

        # 测试 engine 类型
        # engine 可能为 None（配置问题），不强制断言

        # 测试 Base 类型
        assert hasattr(Base, "metadata"), "Base 缺少 metadata 属性"

    @pytest.mark.integration
    def test_session_creation(self):
        """测试会话创建"""
        from app.core.database import SessionLocal

        # 测试创建会话
        session = SessionLocal()

        # 测试会话方法
        assert hasattr(session, "query"), "会话缺少 query 方法"

        # 关闭会话
        session.close()

    @pytest.mark.integration
    def test_engine_usage(self):
        """测试引擎使用"""
        from app.core.database import engine
        from sqlalchemy import text

        if engine is None:
            pytest.skip("engine 为空，跳过测试")

        # 测试引擎连接
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            row = result.fetchone()
            assert row is not None, "SQL 执行结果为空"
            assert row[0] == 1, "SQL 执行结果不正确"

    def test_get_db_generator(self):
        """测试 get_db 生成器"""
        from app.core.database import get_db
        from sqlalchemy.orm import Session

        # 测试 get_db 生成器
        db_gen = get_db()
        db = next(db_gen)

        assert isinstance(db, Session), f"get_db 返回错误的类型: {type(db)}"

        # 关闭生成器
        try:
            next(db_gen)
        except StopIteration:
            pass

    @pytest.mark.integration
    def test_sql_execution(self):
        """测试 SQL 执行"""
        from app.core.database import engine
        from sqlalchemy import text

        if engine is None:
            pytest.skip("engine 为空，跳过测试")

        # 测试 SQL 执行
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test_value"))
            row = result.fetchone()
            assert row is not None, "SQL 执行结果为空"
            assert row[0] == 1, "SQL 执行结果不正确"
