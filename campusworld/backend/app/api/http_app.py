"""
HTTP 应用
独立的 FastAPI 应用定义，包含所有 API 路由和 WebSocket 处理
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.api.ws_handler import ws_handler
from app.core.log import get_logger, LoggerNames

logger = get_logger(LoggerNames.API)


def create_http_app() -> FastAPI:
    """创建 FastAPI 应用（工厂函数）"""

    app = FastAPI(
        title="CampusWorld API",
        description="CampusWorld 后端 API - 支持 HTTP REST 和 WebSocket",
        version="1.0.0",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
