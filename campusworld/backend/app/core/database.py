"""
Database connection and session management
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_database_config, config_manager

# 获取数据库配置
db_config = get_database_config()

# Create database engine
engine = create_engine(
    config_manager.get_database_url(),
    pool_pre_ping=db_config.get('pool_pre_ping', True),
    pool_recycle=db_config.get('pool_recycle', 300),
    pool_size=db_config.get('pool_size', 20),
    max_overflow=db_config.get('max_overflow', 30),
    echo=db_config.get('echo', False),
    connect_args={"check_same_thread": False} if "sqlite" in config_manager.get_database_url() else {},
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
