import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_add_player_uses_initial_location():
    from app.games.campus_life.game import Game

    game = Game()
    game._sync_player_world_location = lambda *_args, **_kwargs: None

    ok = game.add_player("100", {"username": "u1"}, initial_location="library")
    assert ok
    assert game.players["100"]["location"] == "library"


def test_add_player_fallback_to_campus_for_invalid_spawn():
    from app.games.campus_life.game import Game

    game = Game()
    game._sync_player_world_location = lambda *_args, **_kwargs: None

    ok = game.add_player("101", {"username": "u2"}, initial_location="unknown_place")
    assert ok
    assert game.players["101"]["location"] == "campus"
