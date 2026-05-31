"""Unit tests for world_environment resolve/format helpers."""

from __future__ import annotations

import pytest

from app.game_engine.world_environment import format_environment_summary


@pytest.mark.unit
def test_format_environment_summary_chinese():
    line = format_environment_summary(
        {"weather_code": "clear", "temperature_c": 26, "humidity_pct": 68}
    )
    assert line == "室外：晴，26°C，湿度 68%"


@pytest.mark.unit
def test_format_environment_summary_unknown_weather():
    line = format_environment_summary({"weather_code": "hail"})
    assert line.startswith("室外：hail")
