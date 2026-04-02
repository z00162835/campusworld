"""Shared direction token normalization for movement and cross-world bridges."""

from __future__ import annotations

from typing import Dict

_DIRECTION_ALIASES: Dict[str, str] = {
    "n": "north",
    "north": "north",
    "s": "south",
    "south": "south",
    "e": "east",
    "east": "east",
    "w": "west",
    "west": "west",
    "ne": "northeast",
    "northeast": "northeast",
    "nw": "northwest",
    "northwest": "northwest",
    "se": "southeast",
    "southeast": "southeast",
    "sw": "southwest",
    "southwest": "southwest",
    "u": "up",
    "up": "up",
    "d": "down",
    "down": "down",
    "in": "enter",
    "enter": "enter",
    "o": "out",
    "out": "out",
}


def normalize_direction(raw: str) -> str:
    token = str(raw or "").strip().lower()
    return _DIRECTION_ALIASES.get(token, token)
