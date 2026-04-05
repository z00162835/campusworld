"""Startup loading: installed worlds (DB) vs legacy discover-based auto_load_games."""

from unittest.mock import MagicMock, patch

import pytest

from app.game_engine.base import GameEngine
from app.game_engine.loader import GameLoader
from app.game_engine.manager import CampusWorldGameEngine


@pytest.mark.game
@pytest.mark.unit
def test_loader_auto_load_games_empty_allowlist_loads_nothing():
    engine = MagicMock()
    loader = GameLoader(engine)
    loader.discover_games = MagicMock(return_value=["hicampus", "other"])
    loader.load_game = MagicMock(return_value={"ok": True})
    out = loader.auto_load_games(only_world_ids=[])
    assert out == []
    loader.load_game.assert_not_called()


@pytest.mark.game
@pytest.mark.unit
def test_loader_auto_load_games_filter_intersection():
    engine = MagicMock()
    loader = GameLoader(engine)
    loader.discover_games = MagicMock(return_value=["hicampus", "other"])
    loader.load_game = MagicMock(return_value={"ok": True})
    out = loader.auto_load_games(only_world_ids=["hicampus"])
    assert out == ["hicampus"]
    loader.load_game.assert_called_once_with("hicampus")


@pytest.mark.game
@pytest.mark.unit
def test_loader_load_installed_worlds_at_start_intersection():
    engine = MagicMock()
    loader = GameLoader(engine)
    loader.repository.list_world_ids_with_status = MagicMock(
        return_value=["hicampus", "missing_pkg"]
    )
    loader.discover_games = MagicMock(return_value=["hicampus", "other"])
    loader.load_game = MagicMock(return_value={"ok": True})
    out = loader.load_installed_worlds_at_start()
    assert out == ["hicampus"]
    loader.load_game.assert_called_once_with("hicampus")


@pytest.mark.game
@pytest.mark.unit
def test_campus_engine_start_skips_installed_load_when_config_false():
    eng = CampusWorldGameEngine()
    eng.loader.load_installed_worlds_at_start = MagicMock()
    eng.loader.auto_load_games = MagicMock()

    def _gs(key, default=None):
        if key == "game_engine.load_installed_worlds_on_start":
            return False
        if key == "game_engine.auto_load_discovered_on_start":
            return None
        if key == "game_engine.auto_load_on_start":
            return False
        return default

    with patch.object(GameEngine, "start", return_value=True):
        with patch("app.game_engine.manager.get_setting", side_effect=_gs):
            assert eng.start() is True
    eng.loader.load_installed_worlds_at_start.assert_not_called()
    eng.loader.auto_load_games.assert_not_called()


@pytest.mark.game
@pytest.mark.unit
def test_campus_engine_start_calls_load_installed_by_default():
    eng = CampusWorldGameEngine()
    eng.loader.load_installed_worlds_at_start = MagicMock(return_value=["hicampus"])
    eng.loader.auto_load_games = MagicMock()

    def _gs(key, default=None):
        if key == "game_engine.load_installed_worlds_on_start":
            return True
        if key == "game_engine.auto_load_discovered_on_start":
            return None
        if key == "game_engine.auto_load_on_start":
            return False
        return default

    with patch.object(GameEngine, "start", return_value=True):
        with patch("app.game_engine.manager.get_setting", side_effect=_gs):
            assert eng.start() is True
    eng.loader.load_installed_worlds_at_start.assert_called_once()
    eng.loader.auto_load_games.assert_not_called()


@pytest.mark.game
@pytest.mark.unit
def test_campus_engine_start_legacy_auto_load_on_start_still_triggers_discover_load():
    eng = CampusWorldGameEngine()
    eng.loader.load_installed_worlds_at_start = MagicMock(return_value=[])
    eng.loader.auto_load_games = MagicMock(return_value=[])

    def _gs(key, default=None):
        if key == "game_engine.load_installed_worlds_on_start":
            return False
        if key == "game_engine.auto_load_discovered_on_start":
            return None
        if key == "game_engine.auto_load_on_start":
            return True
        if key == "game_engine.auto_load_worlds":
            return ["hicampus"]
        return default

    with patch.object(GameEngine, "start", return_value=True):
        with patch("app.game_engine.manager.get_setting", side_effect=_gs):
            assert eng.start() is True
    eng.loader.load_installed_worlds_at_start.assert_not_called()
    eng.loader.auto_load_games.assert_called_once_with(only_world_ids=["hicampus"])
