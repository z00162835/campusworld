from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.commands.base import CommandContext
from app.commands.lexicon_command import LEXICON_COMMAND
from app.game_engine.agent_runtime.tool_router import paths as tr_paths


@pytest.mark.unit
def test_lexicon_list_empty(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(tr_paths, "lexicon_data_root", lambda: tmp_path)
    monkeypatch.setattr(tr_paths, "lexicon_active_pointer_path", lambda: tmp_path / "active.txt")
    ctx = CommandContext(
        user_id="1",
        username="admin",
        session_id="s",
        permissions=["admin.world.manage"],
        roles=[],
        db_session=None,
    )
    res = LEXICON_COMMAND.execute(ctx, ["-l"])
    assert res.success


@pytest.mark.unit
def test_lexicon_build_requires_session(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(tr_paths, "lexicon_data_root", lambda: tmp_path)
    monkeypatch.setattr(tr_paths, "lexicon_active_pointer_path", lambda: tmp_path / "active.txt")
    ctx = CommandContext(
        user_id="1",
        username="admin",
        session_id="s",
        permissions=["admin.world.manage"],
        roles=[],
        db_session=None,
    )
    res = LEXICON_COMMAND.execute(ctx, ["-b"])
    assert not res.success


@pytest.mark.unit
def test_lexicon_delete_blocks_active(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(tr_paths, "lexicon_data_root", lambda: tmp_path)
    monkeypatch.setattr(tr_paths, "lexicon_active_pointer_path", lambda: tmp_path / "active.txt")
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
    )
    res = LEXICON_COMMAND.execute(ctx, ["-d", vid])
    assert not res.success
