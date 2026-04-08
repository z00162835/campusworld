"""
HTTP 应用
独立的 FastAPI 应用定义，包含所有 API 路由和 WebSocket 处理
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.api.ws_handler import ws_handler
from app.core.log import get_logger, LoggerNames
from app.core.config_manager import get_config

logger = get_logger(LoggerNames.API)


@asynccontextmanager
async def _http_app_lifespan(app: FastAPI):
    """注册命令系统：原先仅在 SSH 控制台首次连接时 initialize_commands，CLI/纯 WS 会拿到空 registry。"""
    from app.commands.init_commands import initialize_commands

    ok = initialize_commands()
    if not ok:
        logger.error(
            "initialize_commands returned false (e.g. DB/policy bootstrap); "
            "commands may be partially registered — check logs"
        )
    else:
        logger.info("Command registry initialized for HTTP/WebSocket/CLI")
    yield


def create_http_app() -> FastAPI:
    """创建 FastAPI 应用（工厂函数）"""

    app = FastAPI(
        title="CampusWorld API",
        description="CampusWorld 后端 API - 支持 HTTP REST 和 WebSocket",
        version="1.0.0",
        lifespan=_http_app_lifespan,
    )

    # CORS - 生产环境应配置具体域名
    # 注意: allow_origins=["*"] 与 allow_credentials=True 不能同时使用
    # 这是一个安全配置，frontend 需要通过环境变量配置具体来源
    _config = get_config()
    _cors_origins = ["http://localhost:3000", "http://localhost:8080"]  # 默认开发 origins
    _env_origins = _config.get("cors_allowed_origins", "")
    if _env_origins:
        _cors_origins = [o.strip() for o in _env_origins.split(",") if o.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
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
