from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .game import Game as HiCampusGame
from .package.loader import load_package_snapshot as _load_snapshot


def get_game_instance():
    return HiCampusGame()


def load_package_snapshot(data_root: str):
    return _load_snapshot(Path(data_root))


def get_graph_profile(_manifest: Optional[Dict[str, Any]] = None):
    """Return WorldGraphProfile for graph seed (`_manifest` reserved for future tuning)."""
    from .package.graph_profile import HICAMPUS_GRAPH_PROFILE

    return HICAMPUS_GRAPH_PROFILE


__all__ = ["HiCampusGame", "get_game_instance", "get_graph_profile", "load_package_snapshot"]

