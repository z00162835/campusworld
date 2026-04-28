"""Tests for Evennia-style look appearance assembly."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.commands.game.look_appearance import (
    return_appearance_room,
    return_appearance_object,
    content_line_for_entry,
    room_list_label_for_entry,
)
from app.commands.base import CommandContext


def test_return_appearance_room_minimal():
    room = {
        "name": "Lab",
        "description": "A test room.",
        "exits": ["东"],
        "items": [],
        "content_entries": [],
    }
    out = return_appearance_room(room, None)
    assert "Lab" in out
    assert "A test room." in out
    assert "出口：东" in out


def test_return_appearance_room_world_entrance_in_world_exits_section():
    room = {
        "name": "Singularity",
        "description": "Root.",
        "exits": ["in"],
        "content_entries": [
            {
                "name": "hicampus",
                "type_code": "world_entrance",
                "attributes": {"entry_hint": "enter hicampus", "portal_world_id": "hicampus"},
                "description": "HiCampus 世界入口",
            },
        ],
    }
    out = return_appearance_room(room, None)
    assert "出口（世界）" in out
    assert "hicampus" in out
    assert "出口：in" in out or "in" in out


def test_return_appearance_room_buckets_portal_and_thing():
    room = {
        "name": "Hall",
        "description": "Hall desc",
        "exits": [],
        "content_entries": [
            {
                "name": "hicampus",
                "type_code": "world",
                "attributes": {"welcome_message": "Hi"},
                "description": "",
            },
            {
                "name": "desk",
                "type_code": "lounge_furniture",
                "attributes": {},
                "description": "",
            },
        ],
    }
    out = return_appearance_room(room, None)
    assert "入口/传送：" in out
    assert "hicampus" in out
    assert "物品：" in out
    assert "desk" in out


def test_content_line_access_terminal_registered_has_starred_name():
    line = content_line_for_entry(
        {
            "name": "Gate Access Terminal",
            "type_code": "access_terminal",
            "attributes": {"display_name": "Gate Access Terminal"},
            "description": "",
        }
    )
    assert line.startswith("- *")
    assert "*Gate Access Terminal*" in line


def test_content_line_lighting_fixture_room_list_name():
    line = content_line_for_entry(
        {
            "name": "HiCampus Gate · 照明回路",
            "type_code": "lighting_fixture",
            "attributes": {"power_on": True, "room_list_name": "照明回路"},
            "description": "",
        }
    )
    assert "*照明回路*" in line
    assert "开" in line


def test_room_list_label_legacy_nested_attributes_key():
    """Pre-flatten graph JSONB often stored package ``attributes:`` under key ``attributes``."""
    label = room_list_label_for_entry(
        {
            "name": "HiCampus Gate · 照明回路",
            "type_code": "lighting_fixture",
            "attributes": {
                "entity_kind": "item",
                "attributes": {"room_list_name": "照明回路", "power_on": True},
            },
            "description": "",
        }
    )
    assert label == "照明回路"


def test_content_line_lighting_fixture():
    line = content_line_for_entry(
        {
            "name": "讲台灯",
            "type_code": "lighting_fixture",
            "attributes": {"power_on": True},
            "description": "",
        }
    )
    assert "*讲台灯*" in line
    assert "开" in line


def test_content_line_lighting_scoped_display_name_yields_short_list_label():
    """Generated items use ``{room} · 短名``; list label should be the short segment (any room)."""
    line = content_line_for_entry(
        {
            "name": "HiCampus Bridge · 照明回路",
            "type_code": "lighting_fixture",
            "attributes": {
                "item_kind": "device",
                "device_role": "lighting",
                "status": "on",
                "lighting": {"brightness_pct": 80, "color_temp_k": 4000, "scene": "work"},
            },
            "description": "",
        }
    )
    assert "*照明回路*" in line


def test_return_appearance_object_lighting_synthetic_desc():
    ctx = CommandContext(
        user_id="1",
        username="t",
        session_id="s",
        permissions=[],
        game_state={},
    )
    obj = {
        "name": "HiCampus Bridge · 照明回路",
        "type_code": "lighting_fixture",
        "node_id": 1,
        "description": "",
        "attributes": {
            "item_kind": "device",
            "device_role": "lighting",
            "status": "on",
            "lighting": {"brightness_pct": 80, "color_temp_k": 4000, "scene": "work"},
        },
    }
    out = return_appearance_object(ctx, obj)
    assert "HiCampus Bridge · 照明回路" in out
    assert "室内照明回路" in out
    assert "亮度" in out or "色温" in out


def test_return_appearance_object_world():
    ctx = CommandContext(
        user_id="1",
        username="t",
        session_id="s",
        permissions=[],
        game_state={},
    )
    obj = {
        "name": "hicampus",
        "type_code": "world",
        "description": "WORLD NODE DESC",
        "attributes": {"world_id": "hicampus"},
    }
    out = return_appearance_object(ctx, obj)
    assert "WORLD NODE DESC" in out
    assert "enter hicampus" in out
    assert "引用:" in out
    assert "hicampus" in out
