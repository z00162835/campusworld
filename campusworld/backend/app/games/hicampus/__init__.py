from __future__ import annotations

from pathlib import Path

from .game import Game as HiCampusGame
from .package.loader import load_package_snapshot as _load_snapshot


def get_game_instance():
    return HiCampusGame()


def load_package_snapshot(data_root: str):
    return _load_snapshot(Path(data_root))


__all__ = ["HiCampusGame", "get_game_instance", "load_package_snapshot"]

