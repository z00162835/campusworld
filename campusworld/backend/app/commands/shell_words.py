"""POSIX-style command-line tokenization (quoted strings), similar to typical MUD/Evennia shells."""

from __future__ import annotations

import shlex
from typing import List


def split_command_line(line: str) -> List[str]:
    """
    Split a command line into argv tokens; double-quoted segments stay one token.

    Examples:
        look "HiCampus Gate · 照明回路" -> ["look", "HiCampus Gate · 照明回路"]
        say hello world -> ["say", "hello", "world"]
    """
    s = (line or "").strip()
    if not s:
        return []
    try:
        parts = shlex.split(s, posix=True)
    except ValueError:
        # Unbalanced quotes — degrade to whitespace split (legacy behavior).
        return s.split()
    return list(parts)
