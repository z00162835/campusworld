"""
HTTP 服务器管理
管理 HTTP/WebSocket 服务器的生命周期
"""

import threading
from typing import Optional

import uvicorn

from app.api.http_app import get_http_app
from app.core.log import get_logger, LoggerNames

logger = get_logger(LoggerNames.API)


class HTTPServer:
    """HTTP 服务器管理器"""

    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.host = host
        self.port = port
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._server = None

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> bool:
        """启动 HTTP 服务器（在线程中运行）"""
        if self._running:
            logger.warning("HTTP server already running")
            return True

        try:
            logger.info(f"Starting HTTP server: {self.host}:{self.port}")

            # 在线程中运行 uvicorn
            def run_server():
                uvicorn.run(
                    get_http_app(),
                    host=self.host,
                    port=self.port,
                    log_level="info"
                )

            self._thread = threading.Thread(target=run_server, daemon=True)
            self._thread.start()
            self._running = True

            logger.info(f"HTTP server started: {self.host}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to start HTTP server: {e}")
            return False

    def stop(self):
        """停止 HTTP 服务器"""
        if not self._running:
            return

        logger.info("Stopping HTTP server...")
        # 注意：uvicorn 不支持优雅停止线程中的服务器
        # daemon=True 线程会在主进程退出时自动终止
        self._running = False
        self._thread = None
        logger.info("HTTP server stopped")

    def get_config(self) -> dict:
        """获取服务器配置"""
        return {
            "host": self.host,
            "port": self.port,
            "running": self._running
        }
