"""
CampusWorld FastAPI Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import get_api_config, get_server_config, get_cors_config
from app.core.database import engine
from app.core.middleware import LoggingMiddleware
from app.api.v1.api import api_router
from app.core.events import create_start_app_handler, create_stop_app_handler

def create_application() -> FastAPI:
    """Create and configure FastAPI application"""
    
    # 获取配置
    api_config = get_api_config()
    server_config = get_server_config()
    cors_config = get_cors_config()
    
    app = FastAPI(
        title=api_config['title'],
        version=api_config['version'],
        description=api_config['description'],
        openapi_url=f"{api_config['v1_prefix']}/openapi.json",
        docs_url=f"{api_config['v1_prefix']}/docs",
        redoc_url=f"{api_config['v1_prefix']}/redoc",
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_config['allowed_origins'],
        allow_credentials=cors_config['allow_credentials'],
        allow_methods=cors_config['allowed_methods'],
        allow_headers=cors_config['allowed_headers'],
    )
    
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=cors_config['allowed_origins'])
    app.add_middleware(LoggingMiddleware)
    
    # Add event handlers
    app.add_event_handler("startup", create_start_app_handler(app))
    app.add_event_handler("shutdown", create_stop_app_handler(app))
    
    # Include API router
    app.include_router(api_router, prefix=api_config['v1_prefix'])
    
    return app

app = create_application()

if __name__ == "__main__":
    import uvicorn
    server_config = get_server_config()
    uvicorn.run(
        app, 
        host=server_config['host'], 
        port=server_config['port']
    )
