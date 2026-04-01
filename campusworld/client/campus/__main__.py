"""
CampusWorld CLI 客户端入口
python -m campus
"""

import sys
import argparse
import asyncio
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from campus.config import Config
from campus.connection import WSConnection
from campus.terminal import Terminal, format_output
from campus.protocol import WSMessage


class CampusClient:
    """CampusWorld CLI 客户端"""

    def __init__(self, config: Config):
        self.config = config
        self.connection: WSConnection = None
        self.terminal: Terminal = None

    async def connect(self, username: str, password: str) -> bool:
        """连接到服务器"""
        server_config = self.config.get_server_config()
        host = server_config.get("host", "localhost")
        port = server_config.get("port", 8000)
        use_ssl = server_config.get("use_ssl", False)

        # 简化认证：使用用户名作为 user_id
        user_id = username

        self.connection = WSConnection(host, port, use_ssl)
        connected = await self.connection.connect(
            user_id=user_id,
            username=username,
            permissions=["player"]
        )

        if connected:
            self.terminal = Terminal(
                prompt_format=self.config.get("terminal.prompt_format",
                                          "[{user}@{time}] campusworld> ")
            )
            self.terminal.username = username
            self.terminal.set_connection(self.connection)

            # 获取命令补全
            completions = await self.connection.request_completions("")
            self.terminal.set_completions(completions)

            return True
        return False

    async def run(self):
        """运行客户端"""
        print("CampusWorld CLI Client")
        print("=" * 40)

        # 交互式登录
        username = input("Username: ").strip()
        password = input("Password: ").strip()

        print("\nConnecting...")
        if not await self.connect(username, password):
            print("Connection failed!")
            return

        print("Connected!\n")

        # 运行终端
        await self.terminal.run_async(self.handle_command)

    async def handle_command(self, text: str):
        """处理命令"""
        if not self.connection:
            return

        # 发送命令
        if await self.connection.send_command(text):
            # 等待结果
            response = await self.connection.receive()
            if response:
                if WSMessage.is_result(response):
                    if response.get("success"):
                        print(format_output(response.get("message", ""), True))
                    else:
                        print(format_output(response.get("message", ""), False))
                elif WSMessage.is_error(response):
                    print(format_output(response.get("message", "Unknown error"), False))


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="CampusWorld CLI Client")
    parser.add_argument("--host", help="Server host", default=None)
    parser.add_argument("--port", type=int, help="Server port", default=None)
    parser.add_argument("--config", help="Config file path", default=None)
    parser.add_argument("--user", help="Username", default=None)
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    args = parser.parse_args()

    # 加载配置
    config = Config(args.config)

    # 命令行参数覆盖配置
    if args.host:
        server_config = config.get_server_config()
        server_config["host"] = args.host
        config.config["server"] = server_config
    if args.port:
        server_config = config.get_server_config()
        server_config["port"] = args.port
        config.config["server"] = server_config

    # 创建客户端
    client = CampusClient(config)

    # 运行
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
