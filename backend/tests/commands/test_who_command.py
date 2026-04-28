from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

from app.commands.base import CommandContext
from app.commands.system_commands import WhoCommand, WhoamiCommand


@dataclass
class _FakeSession:
    user_id: str
    username: str
    connected_at: datetime
    last_activity: datetime


class _FakeSessionManager:
    def __init__(self, sessions):
        self._sessions = list(sessions)

    def get_active_sessions(self):
        return list(self._sessions)


class _FakeGameHandler:
    def __init__(self, location_by_user_id):
        self._map = dict(location_by_user_id)

    def get_user_location(self, user_id: str):
        return self._map.get(user_id, {"name": "-"})


class _FailingGameHandler:
    def get_user_location(self, user_id: str):
        raise RuntimeError(f"db failure for {user_id}")


def _ctx(metadata=None):
    md = {"locale": "en-US"}
    if metadata:
        md.update(metadata)
    return CommandContext(
        user_id="1",
        username="admin",
        session_id="s1",
        permissions=[],
        roles=[],
        metadata=md,
    )


@pytest.mark.unit
def test_who_is_independent_command_name():
    assert WhoCommand().name == "who"
    assert "who" not in WhoamiCommand().aliases


@pytest.mark.unit
def test_who_requires_session_manager_in_context():
    res = WhoCommand().execute(_ctx(metadata={}), [])
    assert not res.success
    assert "unavailable" in (res.message or "").lower()
    assert res.error == "session_manager not available in context"


@pytest.mark.unit
def test_who_returns_empty_state_when_no_sessions():
    manager = _FakeSessionManager([])
    res = WhoCommand().execute(_ctx(metadata={"session_manager": manager}), [])
    assert res.success
    assert "No users online." in res.message


@pytest.mark.unit
def test_who_renders_online_sessions_with_locations():
    now = datetime.now()
    sessions = [
        _FakeSession(
            user_id="100",
            username="alice",
            connected_at=now - timedelta(hours=2, minutes=10),
            last_activity=now - timedelta(minutes=3),
        ),
        _FakeSession(
            user_id="101",
            username="bob",
            connected_at=now - timedelta(minutes=20),
            last_activity=now - timedelta(seconds=20),
        ),
    ]
    manager = _FakeSessionManager(sessions)
    handler = _FakeGameHandler(
        {
            "100": {"name": "Singularity Hub"},
            "101": {"name": "HiCampus/Plaza"},
        }
    )

    res = WhoCommand().execute(
        _ctx(metadata={"session_manager": manager, "game_handler": handler}),
        [],
    )
    assert res.success
    assert "CampusWorld Online Users" in res.message
    assert "alice" in res.message
    assert "bob" in res.message
    assert "Singularity Hub" in res.message
    assert "HiCampus/Plaza" in res.message
    assert "2 users online (2 active sessions)." in res.message


@pytest.mark.unit
def test_who_marks_duplicate_username_per_session():
    now = datetime.now()
    sessions = [
        _FakeSession("100", "alice", now - timedelta(hours=1), now - timedelta(minutes=5)),
        _FakeSession("101", "alice", now - timedelta(minutes=30), now - timedelta(minutes=1)),
    ]
    manager = _FakeSessionManager(sessions)
    handler = _FakeGameHandler({"100": {"name": "A"}, "101": {"name": "B"}})

    res = WhoCommand().execute(
        _ctx(metadata={"session_manager": manager, "game_handler": handler}),
        [],
    )
    assert res.success
    assert res.message.count("alice (x2)") == 2


@pytest.mark.unit
def test_who_location_lookup_failure_degrades_with_warning():
    now = datetime.now()
    sessions = [
        _FakeSession("100", "alice", now - timedelta(hours=1), now - timedelta(seconds=10)),
    ]
    manager = _FakeSessionManager(sessions)
    res = WhoCommand().execute(
        _ctx(metadata={"session_manager": manager, "game_handler": _FailingGameHandler()}),
        [],
    )
    assert res.success
    assert "Location information unavailable." in res.message
    assert "alice" in res.message


@pytest.mark.unit
def test_who_uses_zh_cn_locale_text_when_requested():
    now = datetime.now()
    sessions = [
        _FakeSession("100", "alice", now - timedelta(minutes=5), now - timedelta(seconds=20)),
    ]
    manager = _FakeSessionManager(sessions)
    handler = _FakeGameHandler({"100": {"name": "奇点屋"}})
    res = WhoCommand().execute(
        _ctx(
            metadata={
                "session_manager": manager,
                "game_handler": handler,
                "locale": "zh-CN",
            }
        ),
        [],
    )
    assert res.success
    assert "CampusWorld 在线用户" in res.message
    assert "用户" in res.message and "位置" in res.message
    assert "位用户在线" in res.message
