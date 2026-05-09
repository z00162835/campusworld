from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.commands.base import CommandContext
from app.commands.i18n.command_resource import clear_command_resource_cache
from app.commands.lexicon_command import LEXICON_COMMAND
from app.game_engine.agent_runtime.tool_router import paths as tr_paths


@pytest.fixture(autouse=True)
def _clear_i18n_cache() -> None:
    clear_command_resource_cache()


def _patch_lexicon_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(tr_paths, "lexicon_data_root", lambda: tmp_path)
    monkeypatch.setattr(tr_paths, "lexicon_active_pointer_path", lambda: tmp_path / "active.txt")
    monkeypatch.setattr(tr_paths, "lexicon_version_dir", lambda vid: tmp_path / vid)


@pytest.mark.unit
def test_lexicon_list_empty_zh_default(monkeypatch, tmp_path: Path) -> None:
    _patch_lexicon_paths(monkeypatch, tmp_path)
    ctx = CommandContext(
        user_id="1",
        username="admin",
        session_id="s",
        permissions=["admin.world.manage"],
        roles=[],
        db_session=None,
        metadata={"locale": "zh-CN"},
    )
    res = LEXICON_COMMAND.execute(ctx, ["-l"])
    assert res.success
    assert "暂无" in res.message


@pytest.mark.unit
def test_lexicon_list_empty_en(monkeypatch, tmp_path: Path) -> None:
    _patch_lexicon_paths(monkeypatch, tmp_path)
    ctx = CommandContext(
        user_id="1",
        username="admin",
        session_id="s",
        permissions=["admin.world.manage"],
        roles=[],
        db_session=None,
        metadata={"locale": "en-US"},
    )
    res = LEXICON_COMMAND.execute(ctx, ["-l"])
    assert res.success
    assert "no lexicon" in res.message.lower()


@pytest.mark.unit
def test_lexicon_build_requires_session(monkeypatch, tmp_path: Path) -> None:
    _patch_lexicon_paths(monkeypatch, tmp_path)
    ctx = CommandContext(
        user_id="1",
        username="admin",
        session_id="s",
        permissions=["admin.world.manage"],
        roles=[],
        db_session=None,
        metadata={"locale": "zh-CN"},
    )
    res = LEXICON_COMMAND.execute(ctx, ["-b"])
    assert not res.success
    assert "数据库" in res.message


@pytest.mark.unit
def test_lexicon_delete_blocks_active(monkeypatch, tmp_path: Path) -> None:
    _patch_lexicon_paths(monkeypatch, tmp_path)
    vid = "abc123"
    (tmp_path / vid).mkdir(parents=True)
    (tmp_path / vid / "entries.jsonl").write_text("{}", encoding="utf-8")
    (tmp_path / vid / "meta.json").write_text(json.dumps({"id": vid}), encoding="utf-8")
    (tmp_path / "active.txt").write_text(vid + "\n", encoding="utf-8")
    ctx = CommandContext(
        user_id="1",
        username="admin",
        session_id="s",
        permissions=["admin.world.manage"],
        roles=[],
        db_session=MagicMock(),
        metadata={"locale": "zh-CN"},
    )
    res = LEXICON_COMMAND.execute(ctx, ["-d", vid])
    assert not res.success
    assert "激活" in res.message


@pytest.mark.unit
def test_lexicon_permission_denied(monkeypatch, tmp_path: Path) -> None:
    _patch_lexicon_paths(monkeypatch, tmp_path)
    ctx = CommandContext(
        user_id="1",
        username="user",
        session_id="s",
        permissions=[],
        roles=[],
        db_session=None,
        metadata={"locale": "zh-CN"},
    )
    res = LEXICON_COMMAND.execute(ctx, ["-l"])
    assert not res.success
    assert "词表" in res.message or "lexicon" in res.message.lower()


@pytest.mark.unit
def test_lexicon_localized_usage_en() -> None:
    txt = LEXICON_COMMAND.get_localized_usage("en-US")
    assert "lexicon -b" in txt
    assert "graph" in txt.lower()


@pytest.mark.unit
def test_lexicon_localized_usage_zh() -> None:
    txt = LEXICON_COMMAND.get_localized_usage("zh-CN")
    assert "lexicon -b" in txt
    assert "图数据库" in txt
