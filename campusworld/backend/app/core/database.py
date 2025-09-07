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
        engine = _create_engine()
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

# 在文件末尾添加兼容性包装器
def _get_session_local():
    """获取SessionLocal（向后兼容）"""
    try:
        return _create_session_factory()
    except Exception as e:
        logger.error(f"获取SessionLocal失败: {e}")
        # 返回一个默认的sessionmaker，避免模块导入失败
        from sqlalchemy.orm import sessionmaker
        return sessionmaker()

def _get_engine_global():
    """获取engine（向后兼容）"""
    try:
        return _create_engine()
    except Exception as e:
        logger.error(f"获取engine失败: {e}")
        # 返回None，让调用者处理
        return None

# 为了向后兼容，提供全局变量
# SessionLocal 应该是一个类，不是函数
SessionLocal = _get_session_local()

# engine 应该是一个实例，不是函数
engine = _get_engine_global()

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
    'engine'         # 向后兼容
]
