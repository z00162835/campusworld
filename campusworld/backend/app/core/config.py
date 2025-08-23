"""
Configuration management for CampusWorld application
"""

import os
from typing import List, Optional
from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    """Application settings"""
    
    # Project metadata
    PROJECT_NAME: str = "CampusWorld"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "A modern campus world application"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = "your-secret-key-here"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost/campusworld"
    
    # CORS
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        allowed = ["development", "testing", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v
    
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
