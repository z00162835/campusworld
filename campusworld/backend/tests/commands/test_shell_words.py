"""Tests for POSIX-style command line splitting."""

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.commands.shell_words import split_command_line


def test_split_preserves_quoted_segment_with_spaces():
    parts = split_command_line('look "HiCampus Gate · 照明回路"')
    assert parts == ["look", "HiCampus Gate · 照明回路"]


def test_split_single_quotes_posix():
    parts = split_command_line("say 'hello there'")
    assert parts == ["say", "hello there"]


def test_split_unbalanced_quote_falls_back():
    parts = split_command_line('look "broken')
    assert "look" in parts


def test_split_empty():
    assert split_command_line("") == []
    assert split_command_line("   ") == []
