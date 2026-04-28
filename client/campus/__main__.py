"""
CampusWorld CLI 客户端入口
python -m campus
"""

from __future__ import annotations

import sys
import argparse
import asyncio
import getpass
import os
from pathlib import Path

import httpx

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from campus.config import Config
from campus.connection import WSConnection
from campus.terminal import Terminal


def _token_file_path(config: Config) -> Path:
    raw = config.get("auth.token_file", "~/.config/campus/token")
    return Path(os.path.expanduser(str(raw)))


def _try_load_saved_token(config: Config) -> str | None:
    path = _token_file_path(config)
    if not path.is_file():
        return None
    try:
        data = path.read_text(encoding="utf-8").strip()
        return data or None
    except OSError:
        return None


def _save_token_file(config: Config, token: str) -> None:
    path = _token_file_path(config)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(token, encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
    except OSError:
        pass


def _prompt_password() -> str:
    env_pw = os.environ.get("CAMPUS_PASSWORD", "").strip()
    if not sys.stdin.isatty():
        if env_pw:
            print(
                "Warning: Using CAMPUS_PASSWORD from environment "
                "(non-interactive); prefer an interactive terminal."
            )
            return env_pw
        return ""
    return getpass.getpass("Password: ").strip()


class CampusClient:
    """CampusWorld CLI 客户端"""

    def __init__(self, config: Config):
        self.config = config
        self.connection: WSConnection | None = None
        self.terminal: Terminal | None = None
        self._username = ""
        self._token = ""
        self._max_retries = 3
        self._retry_count = 0

    async def login(self, username: str, password: str) -> tuple[bool, str]:
        """
        通过 HTTP API 登录获取 JWT token。

        Returns:
            (success, token_or_error_message)
        """
        server_config = self.config.get_server_config()
        host = server_config.get("host", "localhost")
        port = server_config.get("port", 8000)
        use_ssl = server_config.get("use_ssl", False)
        scheme = "https" if use_ssl else "http"
        base_url = f"{scheme}://{host}:{port}"

        login_url = f"{base_url}/api/v1/auth/login"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    login_url,
                    data={"username": username, "password": password},
                )
        except httpx.RequestError as e:
            return False, f"Connection error: {e}"

        if response.status_code == 200:
            try:
                result = response.json()
            except ValueError:
                return False, "Invalid JSON in login response"
            token = result.get("access_token", "")
            if token:
                return True, token
            return False, "No access token in response"
        if response.status_code == 401:
            return False, "Invalid username or password"
        try:
            detail = response.text
        except Exception:
            detail = ""
        return False, f"Login failed ({response.status_code}): {detail}"

    async def connect_with_token(self, token: str) -> bool:
        """使用 JWT token 连接到服务器"""
        server_config = self.config.get_server_config()
        host = server_config.get("host", "localhost")
        port = server_config.get("port", 8000)
        use_ssl = server_config.get("use_ssl", False)

        self._token = token
        self.connection = WSConnection(host, port, use_ssl)

        connected = await self.connection.connect(token=token)

        if connected:
            self.terminal = Terminal(
                prompt_format=self.config.get(
                    "terminal.prompt_format",
                    "[{user}@{time}] campusworld> ",
                )
            )
            self.terminal.username = self._username
            self.terminal.set_connection(self.connection)

            # 获取命令补全（带重试，最多 3 次，每次等待更长时间）
            completions = []
            for attempt in range(3):
                completions = await self.connection.request_completions("")
                if completions:
                    break
                if attempt < 2:
                    await asyncio.sleep(0.5)  # 等待后重试

            if not completions:
                print("Warning: failed to fetch command completions from server")
            self.terminal.set_completions(completions)

            self._retry_count = 0
            return True
        return False

    async def reconnect(self) -> bool:
        """尝试重新连接（使用相同 token）"""
        if self._retry_count >= self._max_retries:
            return False

        self._retry_count += 1
        print(f"Attempting to reconnect ({self._retry_count}/{self._max_retries})...")

        if not self.connection:
            return False
        connected = await self.connection.reconnect(token=self._token)

        if connected:
            # 重新获取命令补全
            completions = await self.connection.request_completions("")
            if self.terminal:
                self.terminal.set_completions(completions)
            self._retry_count = 0
            return True
        return False

    async def run(self):
        """运行客户端"""
        print("CampusWorld CLI Client")
        print("=" * 40)

        default_user = self.config.get("auth.default_user", "guest")
        saved = _try_load_saved_token(self.config)
        username = ""
        password = ""
        token_from_login: str | None = None

        if saved:
            print("Found saved token; trying connection...")
            self._username = default_user
            if await self.connect_with_token(saved):
                _save_token_file(self.config, saved)
                print("Connected!\n")
                print("=" * 40)
                if self.terminal:
                    await self.terminal.run_async()
                return
            print("Saved token rejected; please sign in again.")

        username = input(f"Username (account name, same as SSH) [{default_user}]: ").strip()
        if not username:
            username = default_user

        password = _prompt_password()
        if not password:
            print("Error: Password is required (or set CAMPUS_PASSWORD for non-interactive only)")
            return

        self._username = username

        print("\nLogging in...")
        success, token_or_error = await self.login(username, password)
        if not success:
            print(f"Login failed: {token_or_error}")
            return

        token_from_login = token_or_error
        print("Connecting to server...")
        if not await self.connect_with_token(token_from_login):
            print("Connection failed!")
            if await self.reconnect():
                print("Reconnected successfully!")
            else:
                return
        else:
            _save_token_file(self.config, token_from_login)

        print("Connected!\n")
        print("=" * 40)

        if self.terminal:
            await self.terminal.run_async()


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="CampusWorld CLI Client")
    parser.add_argument("--host", help="Server host", default=None)
    parser.add_argument("--port", type=int, help="Server port", default=None)
    parser.add_argument("--config", help="Config file path", default=None)
    parser.add_argument("--user", help="Username", default=None)
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    args = parser.parse_args()

    config = Config(args.config)

    if args.host:
        server_config = config.get_server_config()
        server_config["host"] = args.host
        config.config["server"] = server_config
    if args.port:
        server_config = config.get_server_config()
        server_config["port"] = args.port
        config.config["server"] = server_config
    if args.user:
        auth = config.config.setdefault("auth", {})
        if not isinstance(auth, dict):
            auth = {}
            config.config["auth"] = auth
        auth["default_user"] = args.user

    client = CampusClient(config)

    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
