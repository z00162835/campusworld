"""
HTTP 应用
独立的 FastAPI 应用定义，包含所有 API 路由和 WebSocket 处理
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.api import api_router
from app.api.v1.endpoints.auth import limiter as auth_limiter
from app.api.ws_handler import ws_handler
from app.core.log import get_logger, LoggerNames
from app.core.config_manager import get_config

logger = get_logger(LoggerNames.API)


@asynccontextmanager
async def _http_app_lifespan(app: FastAPI):
    """轻量 lifespan：触发命令系统后台预热，不阻塞 HTTP 启动。"""
    from app.commands.init_commands import trigger_command_init_warmup

    trigger_command_init_warmup()
    yield


def create_http_app() -> FastAPI:
    """创建 FastAPI 应用（工厂函数）"""

    app = FastAPI(
        title="CampusWorld API",
        description="CampusWorld 后端 API - 支持 HTTP REST 和 WebSocket",
        version="1.0.0",
        lifespan=_http_app_lifespan,
    )

    # Add slowapi rate limiting state and handlers
    app.state.limiter = auth_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS - 生产环境应配置具体域名
    # 注意: allow_origins=["*"] 与 allow_credentials=True 不能同时使用
    # 使用 settings.yaml 中的 cors.allowed_origins 配置
    _config = get_config()
    _cors_origins = _config.get("cors.allowed_origins", ["http://localhost:3000"])

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With", "Accept", "Origin"],
        expose_headers=["X-Request-ID"],
        max_age=86400,
    )

    # API 路由
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/")
    async def root():
        return {
            "name": "CampusWorld API",
            "version": "1.0.0",
            "status": "running"
        }

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket 端点 - 为 CLI 客户端提供实时连接"""
        conn = await ws_handler.handle_connect(websocket)
        try:
            while True:
                message = await websocket.receive_text()
                await ws_handler.handle_message(websocket, message)
        except WebSocketDisconnect:
            await ws_handler.handle_disconnect(websocket)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await ws_handler.handle_disconnect(websocket)

    return app


# 全局 HTTP 应用实例（延迟创建）
_http_app: FastAPI = None


def get_http_app() -> FastAPI:
    """获取或创建 HTTP 应用实例"""
    global _http_app
    if _http_app is None:
        _http_app = create_http_app()
    return _http_app
