"""
配置管理
加载和管理 campus 客户端配置
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any


class Config:
    """Campus 客户端配置"""

    DEFAULT_CONFIG = {
        "server": {
            "host": "localhost",
            "port": 8000,
            "use_ssl": False
        },
        "auth": {
            "token_file": "~/.config/campus/token",
            "default_user": "guest",
        },
        "terminal": {
            "theme": "default",
            "font_size": 14,
            "font_family": "monospace",
            "prompt_format": "[{user}@{time}] campusworld> "
        },
        "completion": {
            "enabled": True,
            "show_on_slash": True,
            "fuzzy_match": False
        },
        "history": {
            "enabled": True,
            "size": 1000,
            "file": "~/.local/share/campus/history"
        },
        "logging": {
            "level": "info",
            "file": "~/.local/share/campus/logs/campus.log"
        }
    }

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self._load()

    def _load(self):
        """加载配置"""
        # 尝试加载配置文件
        if self.config_path and Path(self.config_path).exists():
            self._load_from_file(self.config_path)
        else:
            # 尝试默认位置
            local_config = Path("./campus.json")
            if local_config.exists():
                self._load_from_file(str(local_config))
            else:
                user_config = Path(os.path.expanduser("~/.config/campus/config.json"))
                if user_config.exists():
                    self._load_from_file(str(user_config))
                else:
                    # 使用默认配置
                    self.config = self.DEFAULT_CONFIG.copy()

    def _load_from_file(self, path: str):
        """从文件加载配置"""
        try:
            with open(path, 'r') as f:
                loaded = json.load(f) or {}
                # 深度合并默认配置
                self.config = self._merge_config(self.DEFAULT_CONFIG.copy(), loaded)
        except json.JSONDecodeError as e:
            print(f"Failed to parse config from {path}: {e}")
            self.config = self.DEFAULT_CONFIG.copy()
        except Exception as e:
            print(f"Failed to load config from {path}: {e}")
            self.config = self.DEFAULT_CONFIG.copy()

    def _merge_config(self, base: Dict, override: Dict) -> Dict:
        """深度合并配置"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def get_server_config(self) -> Dict[str, Any]:
        """获取服务器配置"""
        return self.config.get("server", {})

    def get_auth_config(self) -> Dict[str, Any]:
        """获取认证配置"""
        return self.config.get("auth", {})

    def get_terminal_config(self) -> Dict[str, Any]:
        """获取终端配置"""
        return self.config.get("terminal", {})

    def get_completion_config(self) -> Dict[str, Any]:
        """获取补全配置"""
        return self.config.get("completion", {})

    def get_history_config(self) -> Dict[str, Any]:
        """获取历史配置"""
        return self.config.get("history", {})


def create_default_config(path: Optional[str] = None) -> Config:
    """创建默认配置文件"""
    if path is None:
        path = os.path.expanduser("~/.config/campus/config.json")

    config_dir = Path(path).parent
    config_dir.mkdir(parents=True, exist_ok=True)

    with open(path, 'w') as f:
        json.dump(Config.DEFAULT_CONFIG, f, indent=2)

    return Config(path)
