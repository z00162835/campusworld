"""
Database connection and session management
"""

from typing import Generator, Optional, Dict, Any
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, StaticPool
from sqlalchemy.exc import SQLAlchemyError

from app.core.config_manager import get_config
from app.core.log import get_logger, LoggerNames

# 获取日志器
logger = get_logger(LoggerNames.DATABASE)

# 全局变量
_config_manager: Optional[Any] = None
_engine: Optional[Any] = None
_SessionLocal: Optional[Any] = None

def _get_config_manager():
    """获取配置管理器"""
    global _config_manager
    if _config_manager is None:
        try:
            _config_manager = get_config()
        except Exception as e:
            logger.error(f"配置管理器初始化失败: {e}")
            raise RuntimeError(f"无法初始化配置管理器: {e}")
    return _config_manager

def _get_database_config() -> Dict[str, Any]:
    """获取数据库配置"""
    try:
        config_manager = _get_config_manager()
        db_config = config_manager.get('database', {})
        
        # 验证必要的配置
        required_keys = ['host', 'port', 'name']
        missing_keys = [key for key in required_keys if not db_config.get(key)]
        
        if missing_keys:
            raise ValueError(f"缺少必要的数据库配置: {missing_keys}")
        
        return db_config
    except Exception as e:
        logger.error(f"获取数据库配置失败: {e}")
        raise

def _create_engine():
    """创建数据库引擎"""
    global _engine
    if _engine is None:
        try:
            config_manager = _get_config_manager()
            db_config = _get_database_config()
            
            # 获取数据库URL
            database_url = config_manager.get_database_url()
            
            # 根据数据库类型设置连接参数
            connect_args = {}
            if "sqlite" in database_url:
                connect_args = {"check_same_thread": False}
            elif "postgresql" in database_url:
                connect_args = {
                    "connect_timeout": 10,
                    "application_name": "campusworld"
                }
            
            # 根据数据库类型选择连接池
            poolclass = StaticPool if "sqlite" in database_url else QueuePool
            
            _engine = create_engine(
                database_url,
                poolclass=poolclass,
                pool_pre_ping=db_config.get('pool_pre_ping', True),
                pool_recycle=db_config.get('pool_recycle', 300),
                pool_size=db_config.get('pool_size', 20),
                max_overflow=db_config.get('max_overflow', 30),
                echo=db_config.get('echo', False),
                connect_args=connect_args,
            )
            
        except Exception as e:
            logger.error(f"创建数据库引擎失败: {e}")
            raise
    
    return _engine

def get_engine():
    """获取数据库引擎"""
    return _create_engine()

def _create_session_factory():
    """创建会话工厂"""
    global _SessionLocal
    if _SessionLocal is None:
        try:
            engine = _create_engine()
            _SessionLocal = sessionmaker(
                autocommit=False, 
                autoflush=False, 
                bind=engine
            )
        except Exception as e:
            logger.error(f"创建会话工厂失败: {e}")
            raise
    return _SessionLocal

def get_db() -> Generator[Session, None, None]:
    """获取数据库会话"""
    SessionLocal = _create_session_factory()
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        logger.error(f"数据库操作失败: {e}")
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"数据库会话异常: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def get_db_session() -> Session:
    """获取数据库会话（非生成器版本）"""
    SessionLocal = _create_session_factory()
    return SessionLocal()

def init_db() -> bool:
    """初始化数据库表"""
    try:
        # 关键：确保所有 ORM 模型已被导入并注册到 Base.metadata
        # 否则 Base.metadata 为空，create_all() 会“成功执行但不创建任何表”
        import app.models  # noqa: F401

        engine = _create_engine()

        if not Base.metadata.tables:
            raise RuntimeError(
                "未加载到任何 ORM 表定义（Base.metadata.tables 为空）。"
                "请检查模型是否正确导入并继承 app.core.database.Base。"
            )

        Base.metadata.create_all(bind=engine)
        logger.info("数据库表初始化成功")
        return True
    except Exception as e:
        logger.error(f"数据库表初始化失败: {e}")
        return False

def check_db_connection() -> bool:
    """检查数据库连接"""
    try:
        engine = _create_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("数据库连接检查成功")
        return True
    except Exception as e:
        logger.error(f"数据库连接检查失败: {e}")
        return False

def get_database_info() -> Dict[str, Any]:
    """获取数据库信息"""
    try:
        config_manager = _get_config_manager()
        db_config = _get_database_config()
        
        return {
            "engine": db_config.get('engine', 'unknown'),
            "host": db_config.get('host', 'unknown'),
            "port": db_config.get('port', 'unknown'),
            "name": db_config.get('name', 'unknown'),
            "pool_size": db_config.get('pool_size', 20),
            "max_overflow": db_config.get('max_overflow', 30),
            "echo": db_config.get('echo', False),
            "connected": check_db_connection()
        }
    except Exception as e:
        logger.error(f"获取数据库信息失败: {e}")
        return {"error": str(e)}

# 创建基础模型类
Base = declarative_base()

# ==================================================
# 向后兼容层 - 懒加载，避免模块导入时的初始化问题
# ==================================================

class _LazySessionLocal:
    """懒加载的SessionLocal类"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._factory = None
        return cls._instance

    def __call__(self):
        if self._factory is None:
            self._factory = _create_session_factory()
        return self._factory()

# 为了向后兼容，提供全局变量
# 使用懒加载类，避免模块导入时就初始化
SessionLocal = _LazySessionLocal()


class _LazyEngine:
    """懒加载的engine实例"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._engine = None
        return cls._instance

    @property
    def engine(self):
        if self._engine is None:
            self._engine = _create_engine()
        return self._engine

    def __getattr__(self, name):
        # 代理到实际的engine对象
        return getattr(self.engine, name)


# 使用懒加载类
_engine_wrapper = _LazyEngine()


def __getattr__(name):
    """支持向后兼容访问 engine 属性"""
    if name == 'engine':
        return _engine_wrapper.engine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ==================================================
# 统一 Session 管理工具（解决Session管理混乱问题）
# ==================================================

from contextlib import contextmanager
from functools import wraps
from typing import Callable, TypeVar, Any, Optional
from sqlalchemy.orm import Session

T = TypeVar('T')


@contextmanager
def db_session_context() -> Session:
    """
    统一的Session上下文管理器（推荐使用）

    用法:
        with db_session_context() as session:
            # 使用 session 查询
            ...
        # session 自动关闭和释放

    替代以下模式:
        - session = SessionLocal(); ...; session.close() ❌
        - with SessionLocal() as session: ... ✅ (保留但推荐统一)
        - get_db_session() (仅FastAPI依赖注入场景)
    """
    SessionFactory = _create_session_factory()
    session = SessionFactory()
    try:
        yield session
    except SQLAlchemyError as e:
        logger.error(f"数据库操作失败，回滚事务: {e}")
        session.rollback()
        raise
    except Exception as e:
        logger.error(f"数据库会话异常，回滚事务: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Session:
    """
    获取一个新的Session实例（需手动管理生命周期）

    用法:
        session = get_session()
        try:
            # 使用 session
            ...
        finally:
            session.close()

    注意: 推荐使用 db_session_context() 上下文管理器
    """
    SessionFactory = _create_session_factory()
    return SessionFactory()


def run_in_session(func: Callable[..., T]) -> Callable[..., T]:
    """
    装饰器: 在统一的Session上下文中执行函数

    用法:
        @run_in_session
        def my_query(user_id: int):
            return session.query(User).filter(User.id == user_id).first()
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        with db_session_context() as session:
            return func(session, *args, **kwargs)
    return wrapper


def run_in_session_with_result(func: Callable[..., T]) -> Callable[..., T]:
    """
    装饰器: 在统一的Session上下文中执行函数，传递session作为第一个参数

    用法:
        @run_in_session_with_result
        def get_user(session, user_id: int):
            return session.query(User).filter(User.id == user_id).first()
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        with db_session_context() as session:
            return func(session, *args, **kwargs)
    return wrapper


# ==================================================
# 便捷查询方法
# ==================================================

def execute_query(query_func: Callable[[Session], Any], default_return=None) -> Any:
    """
    执行查询的便捷方法，自动管理Session

    用法:
        users = execute_query(lambda s: s.query(User).all(), default_return=[])
    """
    try:
        with db_session_context() as session:
            return query_func(session)
    except Exception as e:
        logger.error(f"查询执行失败: {e}")
        return default_return


def execute_write(write_func: Callable[[Session], Any], default_return=None) -> Any:
    """
    执行写操作的便捷方法，自动管理Session和事务

    用法:
        new_user = execute_write(lambda s: create_user(s, data))
    """
    try:
        with db_session_context() as session:
            result = write_func(session)
            session.commit()
            return result
    except SQLAlchemyError as e:
        logger.error(f"写操作失败: {e}")
        return default_return
    except Exception as e:
        logger.error(f"写操作异常: {e}")
        return default_return


# 更新 __all__
__all__ = [
    'get_db',
    'get_db_session',
    'get_engine',
    'init_db',
    'check_db_connection',
    'get_database_info',
    'Base',
    'SessionLocal',  # 向后兼容
    'engine',         # 向后兼容
    # 统一Session管理工具
    'db_session_context',
    'get_session',
    'run_in_session',
    'run_in_session_with_result',
    'execute_query',
    'execute_write',
]
