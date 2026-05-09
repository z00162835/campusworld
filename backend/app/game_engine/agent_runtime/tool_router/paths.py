from __future__ import annotations

from pathlib import Path


def backend_root() -> Path:
    """Directory containing ``app/`` (the backend project root)."""
    return Path(__file__).resolve().parents[4]


def lexicon_data_root() -> Path:
    return backend_root() / "data" / "lexicon"


def lexicon_active_pointer_path() -> Path:
    return lexicon_data_root() / "active.txt"


def lexicon_version_dir(version_id: str) -> Path:
    return lexicon_data_root() / version_id
