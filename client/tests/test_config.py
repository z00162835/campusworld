import json
from pathlib import Path

from campus.config import Config


def test_default_includes_auth_default_user(tmp_path):
    p = tmp_path / "minimal.json"
    p.write_text("{}", encoding="utf-8")
    c = Config(config_path=str(p))
    assert c.get("auth.default_user") == "guest"


def test_merge_and_cli_user_override(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(
        json.dumps({"auth": {"default_user": "u1"}, "server": {"port": 9000}}),
        encoding="utf-8",
    )
    c = Config(config_path=str(p))
    assert c.get("auth.default_user") == "u1"
    assert c.get_server_config()["port"] == 9000


def test_cli_style_user_override(tmp_path):
    p = tmp_path / "base.json"
    p.write_text("{}", encoding="utf-8")
    c = Config(config_path=str(p))
    auth = c.config.setdefault("auth", {})
    auth["default_user"] = "from_cli"
    assert c.get("auth.default_user") == "from_cli"
