"""
World declarative data package validation entry for GameLoader.

Resolves `app.games.<world_id>.package.validator` when present; otherwise
applies a minimal spatial file check for worlds that ship a data/ tree but no package validator module.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Dict, Optional


class WorldDataPackageError(Exception):
    """Structured world data package validation failure surfaced to GameLoader."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code
        self.message = message


_MINIMAL_SPATIAL_FILES = [
    "world.yaml",
    "buildings.yaml",
    "floors.yaml",
    "rooms.yaml",
    "relationships.yaml",
]


def _minimal_spatial_validate(data_root: Path) -> None:
    if not data_root.is_dir():
        raise WorldDataPackageError("WORLD_DATA_UNAVAILABLE", f"data directory not found: {data_root}")
    if not (data_root / "world.yaml").exists():
        return
    missing = [f for f in _MINIMAL_SPATIAL_FILES if not (data_root / f).exists()]
    if missing:
        raise WorldDataPackageError(
            "WORLD_DATA_UNAVAILABLE",
            f"required world data files missing: {missing}",
        )


def validate_world_data_package(game_name: str, data_root: Path) -> Optional[Dict[str, Any]]:
    """
    Run the world's package.validator when exported; else a minimal spatial YAML check.

    Returns the validator payload dict when full validation runs, else None.
    """
    try:
        contracts = importlib.import_module(f"app.games.{game_name}.package.contracts")
        validator = importlib.import_module(f"app.games.{game_name}.package.validator")
    except ImportError:
        _minimal_spatial_validate(data_root)
        return None

    validate_fn = getattr(validator, "validate_data_package", None)
    if not callable(validate_fn):
        _minimal_spatial_validate(data_root)
        return None

    try:
        return validate_fn(data_root)
    except contracts.DataPackageError as e:
        raise WorldDataPackageError(e.error_code, e.message) from e
